"""The composition root of the advice layer: one household in, one advice out.

This is the only module that knows about every other one in the package, and
the only one that talks to ``ampeer_sim``. It performs no I/O itself; the
providers do that, exactly as in ``ampeer_sim.simulate``.

Two things happen here that cannot happen anywhere else.

The first is the battery substitution. ``BATTERY_DOES_NOT_PAY_BACK`` needs a
payback figure, and a payback figure needs a second simulation per capacity.
``AdviceContext`` deliberately does not carry it, because a rule judges facts
about the household rather than the outcome of another model run. So the rule
table can only ever emit ``CONSIDER_BATTERY``, and this module replaces it when
the capacity curve says the battery does not earn itself back inside its
warranty. Substituting in place is also what makes the two mutually exclusive:
there is one storage slot and either rule may occupy it, never both.

The second is that the curve is only computed when it is going to be used. It
costs five extra year simulations through the Python timestep loop, and a
household that already owns a battery, or that exports too little to fill one,
never needs the number.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import numpy as np

from ampeer_advice import ADVICE_VERSION
from ampeer_advice.battery import CAPACITIES, MAX_ACCEPTABLE_PAYBACK_YEARS, battery_advice
from ampeer_advice.confidence import confidence_for
from ampeer_advice.facts import build_context
from ampeer_advice.rules import RULES, evaluate
from ampeer_advice.tariffs import ScenarioLevels, scenario_2027_levels, scenario_2027_tariffs
from ampeer_advice.types import Advice, BatteryAdvice, FiredRule, Route, ScenarioBand
from ampeer_sim.economics.tariffs import annual_cost
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.providers import ProductionProvider, ProfileProvider
from ampeer_sim.simulate import DEFAULT_WEATHER_YEAR
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
    BatterySpec,
    EnergyFlows,
    EVChargingBehaviour,
    Household,
    PVSystem,
    Result,
    TariffSet,
)

#: The routes, always in this order, whether or not a rule fired in each of
#: them. The frontend renders three sections and the free ones come first even
#: when they are empty, because "there is nothing free left to do here" is
#: itself an answer and hiding the section would hide it.
ROUTES: tuple[Route, ...] = (Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE)

#: The uncertain inputs that the bands computed in this module hold at their
#: central value. Named rather than left out: a band that does not say what it
#: left out is read as covering everything, and these three are exactly the
#: assumptions the headline band does vary. Every band this module builds is
#: therefore narrower than the truth, never wider, and it travels with the list
#: that says so.
PINNED_INPUTS: tuple[str, ...] = (
    "annual_consumption_kwh",
    "shiftable_block_kwh",
    "system_loss_fraction",
)


def _storage_verdict(battery: BatteryAdvice) -> str:
    """Decide the storage outcome from the whole payback band, not its midpoint.

    A battery costs between 450 and 900 euro per kWh installed, a spread of a
    factor two, and the tariffs it is priced against carry a band of their own.
    Flipping a buy or do-not-buy recommendation on the midpoint alone would put
    a household like Rob, whose central payback is 11.83 years against a limit
    of 12, on the recommend side while the pessimistic end of the same band
    says 15.77. That is a single number without a band deciding the most
    consequential sentence in the product.

    So there are three outcomes rather than two:

    - worth it at every combination this package prices, which means the worst
      installed price together with the tariff level that makes storage least
      attractive. It is not "the worst case" without qualification: annual
      consumption, the shiftable block and the system loss are pinned at their
      central values, so a household at the pessimistic end of those would do
      worse still. ``BatteryAdvice.payback_years.pinned`` names them and the
      response carries them, because the previous version of this docstring
      claimed the whole band and the code only ever moved the battery price
    - not worth it even at the middle of it
    - and in between, where the honest answer is that it depends on the quote,
      which is the one variable the reader can actually go and find out
    """
    if battery.payback_years.high <= MAX_ACCEPTABLE_PAYBACK_YEARS:
        return "CONSIDER_BATTERY"
    if battery.payback_years.mid > MAX_ACCEPTABLE_PAYBACK_YEARS:
        return "BATTERY_DOES_NOT_PAY_BACK"
    return "BATTERY_DEPENDS_ON_PRICE"


#: Charge and discharge power as a fraction of capacity, used to build the
#: specs for the capacity curve. Home batteries ship at roughly half a C: a
#: 5 kWh unit at 2.2 kW, a 13.5 kWh unit at 5 kW. Measured on the golden
#: households this value does not move the curve at all between 0.3 and 1.0,
#: because a quarter-hour surplus that a slow battery cannot swallow at noon is
#: still there at one o'clock. It is written down rather than left implicit so
#: that the day it does start to matter, it is visible.
BATTERY_C_RATE = 0.5

_STORAGE_RULES = {rule.rule_id: rule for rule in RULES if rule.route is Route.STORAGE}


def _annual_costs(flows: EnergyFlows, levels: ScenarioLevels) -> tuple[Decimal, Decimal, Decimal]:
    """The same simulated year, priced at all three levels of the tariff band.

    Three prices over one set of flows rather than three simulations. A tariff
    changes what a kilowatt hour is worth and not where it goes, so the band
    this produces costs array arithmetic and no extra passes through the
    timestep loop. That is why every euro figure in this module can carry a band
    at all: measuring one would otherwise have been too expensive to do, which
    is how a single number gets published.
    """
    low, mid, high = levels.each()
    return (annual_cost(flows, low), annual_cost(flows, mid), annual_cost(flows, high))


def _capacity_curve(
    consumption: np.ndarray,
    production: np.ndarray,
    levels: ScenarioLevels,
) -> tuple[tuple[float, ScenarioBand], ...]:
    """What a battery of each capacity saves per year under the 2027 regime.

    The saving is the reduction in the annual bill, priced against the scenario
    tariffs only. The pre-2027 baseline is deliberately not part of this
    calculation: net metering ends whatever the household buys, so crediting the
    battery with money that the end of net metering takes away anyway would pay
    it for a loss it did not prevent.

    The battery charges from surplus and discharges into demand, with no grid
    charging and no price arbitrage. That is the behaviour the advice actually
    recommends, and it is the honest floor: a battery that does not pay back on
    self-consumption alone is being sold on a trading strategy the household has
    not been shown.

    Each point is a band rather than a figure, because what a battery saves
    depends on what the exported kilowatt hour it keeps at home would otherwise
    have earned, and that is the most uncertain price in the whole model.
    """
    without = _annual_costs(simulate(consumption, production), levels)
    curve = []
    for capacity in CAPACITIES:
        spec = BatterySpec(
            capacity_kwh=capacity,
            max_charge_kw=capacity * BATTERY_C_RATE,
            max_discharge_kw=capacity * BATTERY_C_RATE,
        )
        flows = simulate(consumption, production, battery_spec=spec)
        withs = _annual_costs(flows, levels)
        savings = [before - after for before, after in zip(without, withs, strict=True)]
        curve.append(
            (
                capacity,
                ScenarioBand.over(
                    values=savings,
                    mid=savings[1],
                    varied=levels.inputs,
                    pinned=PINNED_INPUTS,
                ),
            )
        )
    return tuple(curve)


#: The free routes, in the order the household should do them. Each one is
#: measured by simulating the household with that change applied on top of the
#: previous one, so the figures are additive by construction rather than three
#: independent estimates of the same kilowatt hours.
FREE_ROUTE_ORDER = ("SHIFT_FLEXIBLE_LOAD", "CHARGE_EV_ON_SURPLUS", "CONSIDER_DYNAMIC_CONTRACT")


@dataclasses.dataclass(frozen=True)
class FreeRouteOutcome:
    """The household as it stands once every free route has been taken.

    This exists because returning only the residual export was not enough, and
    the gap it left was the most expensive defect this package has had. The
    storage gate judged the household after the free routes while the capacity
    curve behind it was still priced on the household before them, so the same
    kilowatt hours were sold twice in one answer: once as a free saving and
    again as a reason to buy a battery. Carrying the whole outcome rather than
    one number of it is what makes that impossible to repeat.
    """

    #: What each free route was measured to be worth, per rule id. A band and
    #: not an amount: it is measured at all three levels of the tariff band,
    #: because what an avoided export is worth is precisely what nobody knows.
    savings: dict[str, ScenarioBand]
    #: What still leaves the meter after all of them. The storage gate reads it.
    residual_export_kwh: float
    #: The consumption series of the household that took the advice. Anything
    #: priced after the free routes must be priced against this one.
    consumption: np.ndarray
    #: The tariffs the household ends up on, at all three levels. If the advice
    #: says to switch contract, a battery bought afterwards is worth what it is
    #: worth there.
    scenario: ScenarioLevels


def _measure_free_routes(
    household: Household,
    grid: YearGrid,
    fractions: np.ndarray,
    temperature: np.ndarray,
    production: np.ndarray,
    scenario: ScenarioLevels,
    dynamic_scenario: ScenarioLevels,
    fired_ids: frozenset[str],
    battery_spec: BatterySpec | None,
    weather_year: int,
) -> FreeRouteOutcome:
    """Apply each free route on top of the last and measure what it is worth.

    This replaces three analytic estimators that priced the same surplus
    independently. Two of them drew from the same midday kilowatt hours and the
    third valued the entire annual export, so the numbers could not be read
    together, and the first valued a shifted kWh at 0.27 euro where this
    measurement puts it near 0.16.

    Returns the whole state of the household that took the advice, not just a
    figure from it. See ``FreeRouteOutcome`` for why that distinction is the
    point of this function.
    """

    def compose(for_household: Household) -> np.ndarray:
        return compose_consumption(
            for_household,
            grid,
            fractions,
            temperature,
            weather_year=weather_year,
            production_kwh=production,
        )

    def run(
        for_household: Household,
    ) -> tuple[np.ndarray, EnergyFlows, tuple[Decimal, Decimal, Decimal]]:
        consumption = compose(for_household)
        flows = simulate(consumption, production, battery_spec=battery_spec)
        return consumption, flows, _annual_costs(flows, scenario)

    def band(
        before: tuple[Decimal, Decimal, Decimal], after: tuple[Decimal, Decimal, Decimal]
    ) -> ScenarioBand:
        """What this step saved, at each level of the tariff band."""
        measured = [start - end for start, end in zip(before, after, strict=True)]
        return ScenarioBand.over(
            values=measured,
            # Index one is the central level, which is the tariff set every
            # decision in this advice is taken on.
            mid=measured[1],
            varied=scenario.inputs,
            pinned=PINNED_INPUTS,
        )

    savings: dict[str, ScenarioBand] = {}
    current = household
    consumption, flows, running_cost = run(current)

    if "SHIFT_FLEXIBLE_LOAD" in fired_ids:
        # The advice is to run the washing machine at midday, which is exactly
        # what daytime occupancy models: the same block, moved.
        current = dataclasses.replace(current, daytime_occupancy=True)
        consumption, flows, after = run(current)
        savings["SHIFT_FLEXIBLE_LOAD"] = band(running_cost, after)
        running_cost = after

    if "CHARGE_EV_ON_SURPLUS" in fired_ids and current.ev is not None:
        current = dataclasses.replace(
            current,
            ev=dataclasses.replace(current.ev, behaviour=EVChargingBehaviour.SOLAR),
        )
        consumption, flows, after = run(current)
        savings["CHARGE_EV_ON_SURPLUS"] = band(running_cost, after)
        running_cost = after

    ends_on = scenario
    if "CONSIDER_DYNAMIC_CONTRACT" in fired_ids:
        # Switching contract moves no energy at all, it only changes what the
        # same kilowatt hours are worth. So the flows are reused rather than
        # simulated again, which is both the honest expression of what a
        # contract switch is and two fewer passes through the timestep loop.
        #
        # Both sides are read at the same level of their own band, so the band
        # on this saving is the difference between two contracts under one set
        # of assumptions rather than the difference between the best case of
        # one and the worst case of the other.
        savings["CONSIDER_DYNAMIC_CONTRACT"] = band(
            running_cost, _annual_costs(flows, dynamic_scenario)
        )
        # The household is being told to switch, so this is the regime anything
        # bought afterwards lives in. Pricing a battery against the contract the
        # advice just recommended leaving overstates it, because the higher
        # feed-in price of a dynamic contract is exactly what makes storing a
        # kilowatt hour worth less than selling it.
        ends_on = dynamic_scenario

    # The last consumption and flows already describe the household with every
    # free route applied, so the residual needs no further simulation.
    return FreeRouteOutcome(
        savings=savings,
        residual_export_kwh=float(flows.total_export.sum()),
        consumption=consumption,
        scenario=ends_on,
    )


def _substitute(
    fired: tuple[FiredRule, ...], rule_id: str, replacement_id: str
) -> tuple[FiredRule, ...]:
    """Swap one fired rule for another in place, keeping the output order.

    In place matters. ``BATTERY_DOES_NOT_PAY_BACK`` sits at priority 45, between
    the rule it replaces and ``REVIEW_EXISTING_BATTERY``, so putting it in the
    slot the old rule occupied leaves the ordering exactly as ``evaluate``
    produced it. It also leaves one storage slot rather than two, which is what
    keeps the pair mutually exclusive without a second check.
    """
    replacement = _STORAGE_RULES[replacement_id]
    return tuple(
        FiredRule(
            rule_id=replacement.rule_id,
            route=replacement.route,
            estimated_saving_eur=None,
        )
        if item.rule_id == rule_id
        else item
        for item in fired
    )


def advise(
    household: Household,
    pv_system: PVSystem,
    scenario: TariffSet,
    grid: YearGrid,
    profile_provider: ProfileProvider,
    production_provider: ProductionProvider,
    result: Result,
    filled_fields: int,
    has_meter_data: bool = False,
    dynamic_contract: bool = False,
    battery_spec: BatterySpec | None = None,
    dynamic_scenario: TariffSet | None = None,
    scenario_levels: ScenarioLevels | None = None,
    dynamic_scenario_levels: ScenarioLevels | None = None,
    weather_year: int = DEFAULT_WEATHER_YEAR,
) -> Advice:
    """Turn a simulated year into an explainable advice.

    ``result`` comes from ``ampeer_sim.simulate.run_advice`` and supplies the
    headline band and the engine version. The central year is simulated again
    here rather than carried across, because ``Result`` holds money and not
    flows, and the rules judge energy.

    ``scenario`` is the tariff set every decision here is taken on, and
    ``scenario_levels`` is the band around it. Every euro figure this function
    reports is measured at all three of those levels, so no amount leaves here
    as a lone number. When the levels are not supplied they come from the
    national band in ``ampeer_advice.tariffs``, with ``scenario`` itself put in
    the middle so the band is measured around the figure that was decided on.
    A caller pricing a household against its own contract should pass the band
    for that contract rather than let the national one stand in for it.

    ``filled_fields`` is a count the caller supplies and this package cannot
    derive. A frozen dataclass cannot tell an answer of "nobody is home during
    the day" apart from the default that says the same thing, and guessing which
    it was would inflate the confidence label on exactly the households that
    answered the fewest questions.
    """
    # Result comes from a separate call and carries the years it was computed
    # for. Nothing else compares them, so a caller could hand over a band from a
    # different weather year and get an advice that quietly mixes two runs. The
    # fields exist precisely so that cannot happen silently.
    if result.weather_year != weather_year or result.profile_year != grid.year:
        raise ValueError(
            f"result describes profile year {result.profile_year} and weather year "
            f"{result.weather_year}, but this advice is for {grid.year} and {weather_year}"
        )

    fractions = profile_provider.fractions(grid.year, household.profile_category)
    hourly_production, temperature, _ = production_provider.hourly_series(
        household.postcode4, pv_system.azimuth_deg, pv_system.tilt_deg
    )
    production = production_series(hourly_production, pv_system, grid, weather_year=weather_year)
    consumption = compose_consumption(
        household,
        grid,
        fractions,
        temperature,
        weather_year=weather_year,
        production_kwh=production,
    )
    flows = simulate(consumption, production, battery_spec=battery_spec)

    context = build_context(
        flows=flows,
        household=household,
        grid=grid,
        result=result,
        confidence=confidence_for(filled_fields, has_meter_data),
        dynamic_contract=dynamic_contract,
        battery=battery_spec,
    )
    # First pass decides which free routes apply. The storage rules are read on
    # the second pass, once there is a measured residual for them to judge.
    free_ids = frozenset(
        item.rule_id for item in evaluate(context) if item.route is not Route.STORAGE
    )
    # The band around the tariff set that was decided on, with that tariff set
    # in the middle of it. Replacing the middle rather than taking the national
    # one whole is what keeps the band measured around the figure the advice is
    # actually built on, including when a caller prices a household against a
    # contract of its own.
    levels = scenario_levels or dataclasses.replace(
        scenario_2027_levels(dynamic=dynamic_contract), mid=scenario
    )
    alternative = dynamic_scenario_levels or dataclasses.replace(
        scenario_2027_levels(dynamic=not dynamic_contract),
        mid=dynamic_scenario or scenario_2027_tariffs(dynamic=not dynamic_contract),
    )
    outcome = _measure_free_routes(
        household=household,
        grid=grid,
        fractions=fractions,
        temperature=temperature,
        production=production,
        scenario=levels,
        dynamic_scenario=alternative,
        fired_ids=free_ids,
        battery_spec=battery_spec,
        weather_year=weather_year,
    )
    context = dataclasses.replace(context, export_after_free_routes_kwh=outcome.residual_export_kwh)
    fired = tuple(
        dataclasses.replace(item, estimated_saving_eur=outcome.savings.get(item.rule_id))
        for item in evaluate(context)
    )

    battery: BatteryAdvice | None = None
    if any(item.rule_id == "CONSIDER_BATTERY" for item in fired):
        # Priced on the household that took the free advice, in the contract it
        # was told to move to. Using the original consumption here sold the same
        # kilowatt hours twice in one answer, and using the original tariffs
        # priced the battery in a regime the reader was simultaneously being
        # advised to leave. Both made the battery look better, and neither
        # produced an error.
        battery = battery_advice(_capacity_curve(outcome.consumption, production, outcome.scenario))
        fired = _substitute(fired, "CONSIDER_BATTERY", _storage_verdict(battery))

    return Advice(
        engine_version=result.engine_version,
        advice_version=ADVICE_VERSION,
        confidence=context.confidence,
        headline=context.headline,
        fired=fired,
        routes=ROUTES,
        battery=battery,
    )


def recommended_route(advice: Advice) -> Route | None:
    """The route of the first thing we tell this household to do.

    ``evaluate`` orders the free routes before storage, so the first fired rule
    is by construction the cheapest route that has anything to say. ``None``
    means no rule fired at all, which is a real outcome and not an error: a
    household that already uses most of its own production has nothing to gain
    from any of the three.
    """
    return advice.fired[0].route if advice.fired else None
