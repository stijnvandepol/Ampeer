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
from ampeer_advice.battery import CAPACITIES, battery_advice
from ampeer_advice.confidence import confidence_for
from ampeer_advice.facts import build_context
from ampeer_advice.rules import RULES, evaluate
from ampeer_advice.tariffs import scenario_2027_tariffs
from ampeer_advice.types import Advice, BatteryAdvice, FiredRule, Route
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

#: Above this payback the recommendation flips from "worth considering" to
#: "not worth it". Twelve years, because home batteries are sold with a ten
#: year warranty: a payback beyond it means the household is betting on the
#: battery outliving the guarantee that it will. The Dutch text names the same
#: number out loud, so the reader can check the reasoning rather than trust it.
MAX_ACCEPTABLE_PAYBACK_YEARS = Decimal("12")


def _storage_verdict(battery: BatteryAdvice) -> str:
    """Decide the storage outcome from the whole payback band, not its midpoint.

    A battery costs between 450 and 900 euro per kWh installed, a spread of a
    factor two, and the package publishes that band itself. Flipping a buy or
    do-not-buy recommendation on the midpoint alone would put a household like
    Rob, whose central payback is 11.83 years against a limit of 12, on the
    recommend side while the pessimistic end of the same band says 15.77. That
    is a single number without a band deciding the most consequential sentence
    in the product.

    So there are three outcomes rather than two:

    - worth it even at the worst price in the band
    - not worth it even at the middle of it
    - and in between, where the honest answer is that it depends on the quote,
      which is the one variable the reader can actually go and find out
    """
    if battery.payback_years_p90 <= MAX_ACCEPTABLE_PAYBACK_YEARS:
        return "CONSIDER_BATTERY"
    if battery.payback_years_p50 > MAX_ACCEPTABLE_PAYBACK_YEARS:
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


def _capacity_curve(
    consumption: np.ndarray,
    production: np.ndarray,
    scenario: TariffSet,
) -> tuple[tuple[float, Decimal], ...]:
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
    """
    without = annual_cost(simulate(consumption, production), scenario)
    curve = []
    for capacity in CAPACITIES:
        spec = BatterySpec(
            capacity_kwh=capacity,
            max_charge_kw=capacity * BATTERY_C_RATE,
            max_discharge_kw=capacity * BATTERY_C_RATE,
        )
        flows = simulate(consumption, production, battery_spec=spec)
        curve.append((capacity, without - annual_cost(flows, scenario)))
    return tuple(curve)


#: The free routes, in the order the household should do them. Each one is
#: measured by simulating the household with that change applied on top of the
#: previous one, so the figures are additive by construction rather than three
#: independent estimates of the same kilowatt hours.
FREE_ROUTE_ORDER = ("SHIFT_FLEXIBLE_LOAD", "CHARGE_EV_ON_SURPLUS", "CONSIDER_DYNAMIC_CONTRACT")


def _measure_free_routes(
    household: Household,
    grid: YearGrid,
    fractions: np.ndarray,
    temperature: np.ndarray,
    production: np.ndarray,
    scenario: TariffSet,
    dynamic_scenario: TariffSet,
    fired_ids: frozenset[str],
    battery_spec: BatterySpec | None,
    weather_year: int,
) -> tuple[dict[str, Decimal], float]:
    """Apply each free route on top of the last and measure what it is worth.

    This replaces three analytic estimators that priced the same surplus
    independently. Two of them drew from the same midday kilowatt hours and the
    third valued the entire annual export, so the numbers could not be read
    together, and the first valued a shifted kWh at 0.27 euro where this
    measurement puts it near 0.16.

    Returns the measured saving per rule and the export that is left once every
    free route has been applied. That residual is what the storage rules judge,
    which is what the spec and the Dutch copy have always claimed happens.
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

    def run(for_household: Household) -> tuple[EnergyFlows, Decimal]:
        flows = simulate(compose(for_household), production, battery_spec=battery_spec)
        return flows, annual_cost(flows, scenario)

    savings: dict[str, Decimal] = {}
    current = household
    flows, running_cost = run(current)

    if "SHIFT_FLEXIBLE_LOAD" in fired_ids:
        # The advice is to run the washing machine at midday, which is exactly
        # what daytime occupancy models: the same block, moved.
        current = dataclasses.replace(current, daytime_occupancy=True)
        flows, after = run(current)
        savings["SHIFT_FLEXIBLE_LOAD"] = running_cost - after
        running_cost = after

    if "CHARGE_EV_ON_SURPLUS" in fired_ids and current.ev is not None:
        current = dataclasses.replace(
            current,
            ev=dataclasses.replace(current.ev, behaviour=EVChargingBehaviour.SOLAR),
        )
        flows, after = run(current)
        savings["CHARGE_EV_ON_SURPLUS"] = running_cost - after
        running_cost = after

    if "CONSIDER_DYNAMIC_CONTRACT" in fired_ids:
        # Switching contract moves no energy at all, it only changes what the
        # same kilowatt hours are worth. So the flows are reused rather than
        # simulated again, which is both the honest expression of what a
        # contract switch is and two fewer passes through the timestep loop.
        savings["CONSIDER_DYNAMIC_CONTRACT"] = running_cost - annual_cost(flows, dynamic_scenario)

    # The last flows already describe the household with every free route
    # applied, so the residual needs no further simulation.
    return savings, float(flows.total_export.sum())


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
    weather_year: int = DEFAULT_WEATHER_YEAR,
) -> Advice:
    """Turn a simulated year into an explainable advice.

    ``result`` comes from ``ampeer_sim.simulate.run_advice`` and supplies the
    headline band and the engine version. The central year is simulated again
    here rather than carried across, because ``Result`` holds money and not
    flows, and the rules judge energy.

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
    savings, residual_export = _measure_free_routes(
        household=household,
        grid=grid,
        fractions=fractions,
        temperature=temperature,
        production=production,
        scenario=scenario,
        dynamic_scenario=dynamic_scenario or scenario_2027_tariffs(dynamic=True),
        fired_ids=free_ids,
        battery_spec=battery_spec,
        weather_year=weather_year,
    )
    context = dataclasses.replace(context, export_after_free_routes_kwh=residual_export)
    fired = tuple(
        dataclasses.replace(item, estimated_saving_eur=savings.get(item.rule_id))
        for item in evaluate(context)
    )

    battery: BatteryAdvice | None = None
    if any(item.rule_id == "CONSIDER_BATTERY" for item in fired):
        battery = battery_advice(_capacity_curve(consumption, production, scenario))
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
