"""The seams between the advice lanes, and the golden households.

The individual lanes each test their own module. What is left, and what this
file is for, is the composition: that the rule table, the tariff band, the
capacity curve and the Dutch texts still describe the same household when they
are put together, and that the two battery rules can never both come out.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import re
import time
from collections.abc import Sequence
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import ampeer_advice as ADVICE_PACKAGE
from ampeer_advice import ADVICE_VERSION
from ampeer_advice.advise import (
    FREE_ROUTE_ORDER,
    FreeRouteOutcome,
    _annual_costs,
    _measure_free_routes,
    _storage_verdict,
    advise,
    recommended_route,
)
from ampeer_advice.battery import CAPACITIES, MAX_ACCEPTABLE_PAYBACK_YEARS, battery_advice
from ampeer_advice.nl import RULE_TEXTS
from ampeer_advice.rules import RULES
from ampeer_advice.tariffs import (
    baseline_tariffs,
    scenario_2027_levels,
    scenario_2027_tariffs,
)
from ampeer_advice.types import (
    Advice,
    AdviceContext,
    BatteryAdvice,
    Confidence,
    Route,
    ScenarioBand,
)
from ampeer_sim.economics.tariffs import annual_cost
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.simulate import run_advice
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
    EV,
    Band,
    BatterySpec,
    EVChargingBehaviour,
    HeatPump,
    Household,
    ProductionSource,
    ProfileCategory,
    PVSystem,
    Result,
)

GOLDEN_DIR = Path(__file__).parent / "golden"
HOUSEHOLDS: dict[str, dict[str, Any]] = json.loads(
    (GOLDEN_DIR / "households.json").read_text(encoding="utf-8")
)
EXPECTED: dict[str, dict[str, Any]] = json.loads(
    (GOLDEN_DIR / "advice_households.json").read_text(encoding="utf-8")
)

GRID = YearGrid.for_year(2025)
WEATHER_YEAR = 2025

#: The break even price is recorded to the cent and asserted to the cent. It is
#: a deterministic figure and the reader is told to hold a quote against it, so
#: a tolerance wide enough to hide a rounding change would be a tolerance wide
#: enough to hide the defect that put a rounding rule for euro amounts inside a
#: constant named after a payback time.
BREAK_EVEN_TOLERANCE_EUR = 0.01

#: The advice must complete inside this, excluding the capacity curve. The curve
#: costs five more year simulations through the Python timestep loop and is only
#: run when a battery is actually on the table.
BUDGET_SECONDS = 0.5


class FlatProfiles:
    """A profile provider that spreads consumption evenly over the year.

    The same flat series ``tests/test_golden.py`` uses, so the two golden files
    describe the same six households rather than two different ones.
    """

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        return np.full(GRID.quarters, 1.0 / GRID.quarters)


def _stub_result() -> Result:
    """A ``Result`` with a band that ``advise`` only passes through.

    The fired rules do not depend on the headline band, so the golden cases do
    not need the eighty one run sensitivity analysis to produce it. One test
    below does run the real thing, to prove the two compose.
    """
    return Result(
        engine_version="0.1.0",
        band=Band(Decimal("500"), Decimal("600"), Decimal("700"), runs=81),
        self_consumption_rate=0.3,
        production_source=ProductionSource.FALLBACK,
        profile_year=2025,
        weather_year=WEATHER_YEAR,
    )


def _household(case: dict[str, Any]) -> Household:
    ev = None
    if "ev_behaviour" in case:
        ev = EV(
            behaviour=EVChargingBehaviour[case["ev_behaviour"]],
            annual_km=case["ev_annual_km"],
        )
    heat_pump = None
    if "heat_pump_demand_kwh" in case:
        heat_pump = HeatPump(heat_demand_kwh=case["heat_pump_demand_kwh"])
    return Household(
        postcode4=case["postcode4"],
        annual_consumption_kwh=case["annual_consumption_kwh"],
        daytime_occupancy=case["daytime_occupancy"],
        shiftable_block_kwh=case["shiftable_block_kwh"],
        ev=ev,
        heat_pump=heat_pump,
    )


def _advise(
    case: dict[str, Any],
    filled_fields: int = 6,
    has_meter_data: bool = False,
    dynamic_contract: bool = False,
    battery_spec: BatterySpec | None = None,
) -> Advice:
    household = _household(case)
    return advise(
        household=household,
        pv_system=PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0.0, tilt_deg=35.0),
        scenario=scenario_2027_tariffs(),
        grid=GRID,
        profile_provider=FlatProfiles(),
        production_provider=FallbackProvider(WEATHER_YEAR),
        result=_stub_result(),
        filled_fields=filled_fields,
        has_meter_data=has_meter_data,
        dynamic_contract=dynamic_contract,
        battery_spec=battery_spec,
        weather_year=WEATHER_YEAR,
    )


@cache
def _central_shock(name: str) -> Decimal:
    """What the end of net metering costs this household in the central case.

    Computed here rather than taken from ``advice.headline``, because the tests
    feed advise() a stub Result with a fixed band. This is the same difference
    the headline reports: identical flows, priced once under net metering and
    once under the 2027 regime.
    """
    case = HOUSEHOLDS[name]
    household = _household(case)
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0.0, tilt_deg=35.0)
    hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    consumption = compose_consumption(
        household,
        GRID,
        FlatProfiles().fractions(GRID.year, household.profile_category),
        temperature,
        weather_year=WEATHER_YEAR,
        production_kwh=production,
    )
    flows = simulate(consumption, production)
    return annual_cost(flows, scenario_2027_tariffs()) - annual_cost(flows, baseline_tariffs())


@cache
def _golden_advice(name: str) -> Advice:
    """One advice per golden household, computed once for the whole module."""
    return _advise(HOUSEHOLDS[name])


def test_the_two_golden_files_describe_the_same_households() -> None:
    """An expectation for a household that no longer exists tests nothing."""
    assert set(EXPECTED) == set(HOUSEHOLDS)


def test_no_dutch_text_lives_outside_the_text_module() -> None:
    """The language boundary, enforced rather than agreed.

    One sentence written straight into a rule condition is all it takes to make
    a copy change and a behaviour change break the same test, and to make a
    second language a rewrite instead of a second file. The words below are ones
    that cannot plausibly appear in English prose about energy, so a hit is a
    sentence and not a false alarm.
    """
    dutch = re.compile(
        r"\b(uw|jij|jouw|wij|niet|stroom|batterij|thuisbatterij|verbruik|opwek"
        r"|zonnepanelen|zonnestroom|teruglevert|terugleverkosten|vaatwasser"
        r"|het|een|geen|deze|dat|wordt|worden|zijn|hebben|wettelijk|jaar"
        r"|kosten|bedrag|prijs|meeste|grote|volgens|omdat|maar|ook|nog)\b",
        re.IGNORECASE,
    )
    package = Path(ADVICE_PACKAGE.__file__ or "").parent
    offenders = {
        path.name: sorted(set(dutch.findall(path.read_text(encoding="utf-8"))))
        for path in sorted(package.rglob("*.py"))
        if path.name != "nl.py" and dutch.search(path.read_text(encoding="utf-8"))
    }
    assert offenders == {}, f"Dutch outside nl.py: {offenders}"


def test_the_advice_carries_both_versions() -> None:
    """Two packages, two versions.

    A recorded advice has to say which engine produced the numbers and which
    rule table judged them, because the two move independently: a rule threshold
    can change without the simulation changing a single kWh.
    """
    advice = _golden_advice("rob_fixed_contract")
    assert advice.engine_version == "0.1.0"
    assert advice.advice_version == ADVICE_VERSION


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_all_three_routes_are_always_present_and_free_ones_come_first(name: str) -> None:
    """Including the routes in which nothing fired.

    The frontend renders three sections. Dropping an empty one would hide the
    fact that there is nothing free left to do, which is information.
    """
    assert _golden_advice(name).routes == (
        Route.SHIFT_BEHAVIOUR,
        Route.SMART_CONTROL,
        Route.STORAGE,
    )


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_fired_rules_never_leave_the_free_routes_for_last(name: str) -> None:
    routes = [fired.route.value for fired in _golden_advice(name).fired]
    assert routes == sorted(routes)


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_the_two_battery_rules_are_mutually_exclusive(name: str) -> None:
    """The invariant the whole substitution exists to keep.

    ``CONSIDER_BATTERY`` and ``BATTERY_DOES_NOT_PAY_BACK`` contradict each
    other in plain Dutch. Emitting both would not raise anything; it would just
    print two opposite sentences under the same heading.
    """
    ids = {fired.rule_id for fired in _golden_advice(name).fired}
    assert not {"CONSIDER_BATTERY", "BATTERY_DOES_NOT_PAY_BACK"} <= ids


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_every_fired_rule_has_dutch_text(name: str) -> None:
    for fired in _golden_advice(name).fired:
        assert RULE_TEXTS[fired.rule_id].strip()


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_the_golden_household_fires_the_recorded_rules(name: str) -> None:
    """Ids and order, not sentences.

    If this fails, read the produced list and decide whether the model or the
    expectation is wrong before touching the json. A golden file edited to match
    whatever the code produced is not a test.
    """
    assert [fired.rule_id for fired in _golden_advice(name).fired] == EXPECTED[name]["fired"]


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_the_golden_household_gets_the_recorded_route(name: str) -> None:
    route = recommended_route(_golden_advice(name))
    assert (route.name if route is not None else None) == EXPECTED[name]["recommended_route"]


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_the_golden_battery_sizing_is_stable(name: str) -> None:
    """The capacity at the knee and the payback that decides which rule fires."""
    expected = EXPECTED[name]
    battery = _golden_advice(name).battery
    if expected["battery_capacity_kwh"] is None:
        assert battery is None
        return
    assert battery is not None
    assert battery.sized_capacity_kwh == expected["battery_capacity_kwh"]
    tolerance = expected["payback_tolerance_years"]
    assert float(battery.payback_years.mid) == pytest.approx(
        expected["battery_payback_mid_years"], abs=tolerance
    )
    # Both ends too. The band decides whether a household is told "worth it
    # even at the worst combination we price", so leaving its ends unrecorded
    # would let the most consequential sentence in the product move without a
    # diff. They are named low and high because they are the extremes of nine
    # priced combinations and not percentiles of anything.
    assert float(battery.payback_years.low) == pytest.approx(
        expected["battery_payback_low_years"], abs=tolerance
    )
    assert float(battery.payback_years.high) == pytest.approx(
        expected["battery_payback_high_years"], abs=tolerance
    )
    # Recorded and asserted. It sat in the golden file unread until 2026-08-21,
    # which made it a number nothing could contradict: the figure the Dutch text
    # tells the reader to compare a quote against was pinned by no test at all.
    assert float(battery.break_even_cost_per_kwh.mid) == pytest.approx(
        expected["battery_break_even_mid_cost_per_kwh"], abs=BREAK_EVEN_TOLERANCE_EUR
    )
    # The low end decides the unconditional yes: a battery is worth it at every
    # combination we price only when the break even price clears the top of the
    # cost band at the tariff level where storage earns least.
    assert float(battery.break_even_cost_per_kwh.low) == pytest.approx(
        expected["battery_break_even_low_cost_per_kwh"], abs=BREAK_EVEN_TOLERANCE_EUR
    )
    assert float(battery.break_even_cost_per_kwh.high) == pytest.approx(
        expected["battery_break_even_high_cost_per_kwh"], abs=BREAK_EVEN_TOLERANCE_EUR
    )


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_a_battery_recommendation_never_arrives_as_a_single_number(name: str) -> None:
    """Every advice rule: no figure without a band around it."""
    battery = _golden_advice(name).battery
    if battery is None:
        return
    assert battery.payback_years.low < battery.payback_years.mid < battery.payback_years.high
    assert battery.annual_saving_eur.low < battery.annual_saving_eur.high
    assert battery.break_even_cost_per_kwh.low < battery.break_even_cost_per_kwh.high


def test_a_household_whose_battery_takes_over_twelve_years_is_told_so() -> None:
    """The case the neutrality of this product rests on.

    Sander heats with a pump, so his winter demand is enormous and falls in the
    months with no sun to store. The curve flattens at seven kWh and even that
    does not earn itself back inside the warranty at the central price. He is
    told not to buy one, which is the sentence that makes the rest of the advice
    worth believing.

    This used to be Marloes. It moved when find_knee was fixed: it had been
    comparing a whole step's euro total against a per kWh threshold, which sized
    her battery at fifteen kWh instead of ten and pushed the payback past the
    limit for the wrong reason. A negative verdict produced by an arithmetic
    error is not neutrality, it is luck.
    """
    advice = _golden_advice("sander_heat_pump")
    ids = [fired.rule_id for fired in advice.fired]
    assert "BATTERY_DOES_NOT_PAY_BACK" in ids
    assert "CONSIDER_BATTERY" not in ids
    assert "BATTERY_DEPENDS_ON_PRICE" not in ids
    assert advice.battery is not None
    assert advice.battery.payback_years.mid > MAX_ACCEPTABLE_PAYBACK_YEARS


#: What a band built in this file says it moved and held. The real ones get
#: these from ampeer_advice.tariffs; here they only have to be present, because
#: what is under test is that they travel with the figure.
VARIED = ("supply_price", "feed_in_price", "feed_in_cost_per_kwh")
PINNED = ("annual_consumption_kwh",)


def _band_of(low: str, mid: str, high: str) -> ScenarioBand:
    return ScenarioBand.over(
        values=[Decimal(low), Decimal(mid), Decimal(high)],
        mid=Decimal(mid),
        varied=VARIED,
        pinned=PINNED,
    )


def _battery_with_payback(low: str, mid: str, high: str) -> BatteryAdvice:
    """A battery advice that exists only to be judged by ``_storage_verdict``.

    The payback band is named low, mid and high rather than p10, p50 and p90.
    Those are not percentiles: they are the extremes of nine priced
    combinations of the installed price and the tariff level, and the response
    used to publish them under the percentile names the headline uses for a
    genuine 243 run distribution.
    """
    return BatteryAdvice(
        sized_capacity_kwh=7.0,
        sized_at_largest_simulated_capacity=False,
        annual_saving_eur=_band_of("240.00", "300.00", "360.00"),
        payback_years=_band_of(low, mid, high),
        curve=((7.0, _band_of("240.00", "300.00", "360.00")),),
        break_even_cost_per_kwh=_band_of("480.00", "600.00", "720.00"),
    )


def test_the_verdict_has_three_states_and_each_one_is_reachable() -> None:
    """Why the storage verdict is not a yes or a no.

    A battery costs between 450 and 900 euro per kWh installed. Flipping the
    most consequential sentence in the product on the midpoint of a factor two
    spread would be a single number without a band deciding an answer, which is
    the one thing this product promises not to do. So there are three outcomes,
    and the middle one hands the reader the price at which it flips rather than
    a yes they cannot check.

    This is asserted against the function rather than against a household on
    purpose, and the reason is a finding rather than a convenience. Until
    2026-08-21 ``large_array_small_use`` carried this case end to end at 9.69
    years. Once the capacity curve stopped being priced on consumption the free
    routes had already claimed, it moved to 12.05, and no household in the
    golden set reaches the middle state any more. Reaching for a household that
    happens to land there would make this test a hostage to whichever case is
    currently nearest the line; the boundaries themselves are what has to hold.
    """
    assert _storage_verdict(_battery_with_payback("6.0", "9.0", "11.9")) == "CONSIDER_BATTERY"
    assert (
        _storage_verdict(_battery_with_payback("8.0", "11.0", "16.0")) == "BATTERY_DEPENDS_ON_PRICE"
    )
    assert (
        _storage_verdict(_battery_with_payback("10.0", "13.0", "19.0"))
        == "BATTERY_DOES_NOT_PAY_BACK"
    )

    # Exactly on the limit is still a yes: twelve years is the warranty, and a
    # battery that pays back in exactly twelve has paid back inside it.
    on_the_line = _battery_with_payback("8.0", "10.0", str(MAX_ACCEPTABLE_PAYBACK_YEARS))
    assert _storage_verdict(on_the_line) == "CONSIDER_BATTERY"


def test_no_reference_household_is_told_to_buy_a_battery() -> None:
    """The state of the answer after the double count was removed.

    This is not a rule and it must not become one. It is a record of what the
    corrected model says today about six households: for every one of them that
    exports enough to be shown a battery at all, storage does not earn itself
    back inside its warranty. If a change ever makes one of them a yes, this
    test fails and somebody has to look at why, which is the point.
    """
    verdicts = {}
    for name in EXPECTED:
        advice = _golden_advice(name)
        storage = [f.rule_id for f in advice.fired if f.route is Route.STORAGE]
        if storage:
            verdicts[name] = storage[0]
    assert verdicts, "no golden household reaches the storage route at all"
    assert set(verdicts.values()) == {"BATTERY_DOES_NOT_PAY_BACK"}, verdicts


def test_an_unambiguous_buy_needs_the_whole_band_inside_the_limit() -> None:
    """Reachable, and deliberately hard to reach.

    CONSIDER_BATTERY requires the pessimistic end of the cost band to clear
    twelve years, so the break even price must sit above the 900 euro per kWh
    top of that band. No golden household manages it, which is itself the
    finding: at today's installed prices and the 2027 tariffs suppliers have
    published, an unconditional yes is rare. This test builds the curve directly
    rather than pretending a household produces it, so the branch stays covered
    and the threshold stays honest.
    """
    generous = [
        (
            capacity,
            _band_of(str(capacity * 190), str(capacity * 200), str(capacity * 210)),
        )
        for capacity in CAPACITIES
    ]
    battery = battery_advice(generous)
    assert battery.payback_years.high <= MAX_ACCEPTABLE_PAYBACK_YEARS
    assert _storage_verdict(battery) == "CONSIDER_BATTERY"


@pytest.mark.parametrize(
    "name", ["rob_fixed_contract", "large_array_small_use", "marloes_ev_at_night"]
)
def test_the_free_routes_never_save_more_than_the_problem_is_worth(name: str) -> None:
    """The invariant that proves the figures are not double counted.

    Each free route is measured by simulating it on top of the previous one, so
    the savings are additive by construction. Their total therefore cannot
    exceed the headline, which is the whole cost the end of net metering adds:
    under net metering self consumption was worth nothing, so none of these
    interventions would have earned anything before 2027.

    The estimators this replaced could and did break it. Two of them drew on the
    same midday kilowatt hours and the third valued the entire annual export, so
    three separate numbers were charged against one physical surplus.
    """
    advice = _golden_advice(name)
    measured = sum(
        (
            fired.estimated_saving_eur.mid
            for fired in advice.fired
            if fired.estimated_saving_eur is not None
        ),
        start=Decimal("0"),
    )
    assert measured > Decimal("0"), "a household with free routes should have measured savings"
    assert measured <= _central_shock(name)


def test_every_free_route_that_fires_carries_a_measured_figure() -> None:
    """Route 1 and 2 always say what they are worth; route 3 never invents one."""
    advice = _golden_advice("marloes_ev_at_night")
    for fired in advice.fired:
        if fired.route is Route.STORAGE:
            assert fired.estimated_saving_eur is None, fired
        else:
            assert isinstance(fired.estimated_saving_eur, ScenarioBand), fired


def test_a_household_with_nothing_to_gain_gets_no_advice_and_no_curve() -> None:
    """An empty advice is a real outcome, not a failure to produce one.

    This household already uses seventy percent of its own production. There is
    nothing free left to shift and no reason to run a capacity curve, so the
    expensive part is skipped as well.
    """
    advice = _golden_advice("marloes_ev_on_solar")
    assert advice.fired == ()
    assert advice.battery is None
    assert recommended_route(advice) is None


def test_an_existing_battery_is_reviewed_rather_than_sized() -> None:
    """A second battery is not the answer to a badly configured first one."""
    advice = _advise(
        HOUSEHOLDS["rob_fixed_contract"],
        battery_spec=BatterySpec(capacity_kwh=5.0, max_charge_kw=2.5, max_discharge_kw=2.5),
    )
    assert [fired.rule_id for fired in advice.fired] == ["REVIEW_EXISTING_BATTERY"]
    assert advice.battery is None


def test_a_dynamic_contract_removes_the_advice_to_switch_to_one() -> None:
    fixed = _golden_advice("rob_fixed_contract")
    dynamic = _advise(HOUSEHOLDS["rob_fixed_contract"], dynamic_contract=True)
    assert "CONSIDER_DYNAMIC_CONTRACT" in {fired.rule_id for fired in fixed.fired}
    assert "CONSIDER_DYNAMIC_CONTRACT" not in {fired.rule_id for fired in dynamic.fired}


@pytest.mark.parametrize(
    ("filled_fields", "has_meter_data", "expected"),
    [
        (2, False, Confidence.INDICATIVE),
        (7, False, Confidence.GOOD),
        (0, True, Confidence.PRECISE),
    ],
)
def test_the_confidence_label_reaches_the_advice(
    filled_fields: int, has_meter_data: bool, expected: Confidence
) -> None:
    """The label is wired through the composition root, not decided in it."""
    advice = _advise(
        HOUSEHOLDS["marloes_ev_on_solar"],
        filled_fields=filled_fields,
        has_meter_data=has_meter_data,
    )
    assert advice.confidence is expected


def test_the_headline_band_is_passed_through_untouched() -> None:
    advice = _golden_advice("rob_fixed_contract")
    assert advice.headline == _stub_result().band


def test_a_full_advice_fits_the_budget_excluding_the_capacity_curve() -> None:
    """Timed on the path that does not run the curve.

    The curve is five more year simulations through the Python timestep loop and
    is only reached when a battery is genuinely on the table. What has to be
    fast is everything else, because that is what every visitor waits for.
    """
    case = HOUSEHOLDS["rob_fixed_contract"]
    spec = BatterySpec(capacity_kwh=5.0, max_charge_kw=2.5, max_discharge_kw=2.5)
    started = time.perf_counter()
    advice = _advise(case, battery_spec=spec)
    elapsed = time.perf_counter() - started
    assert advice.battery is None, "this path must not have run the curve"
    assert advice.fired, "an empty advice would make this timing meaningless"
    assert elapsed < BUDGET_SECONDS, f"advice took {elapsed:.3f}s"


def test_the_simulation_result_and_the_advice_compose() -> None:
    """One run of the real thing, end to end.

    Every other test here feeds ``advise`` a stub ``Result``, because the rules
    never read the band. This one proves the two halves actually fit: the band
    that ``run_advice`` measures is the band the advice reports.
    """
    case = HOUSEHOLDS["rob_fixed_contract"]
    household = _household(case)
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0.0, tilt_deg=35.0)
    profiles, production = FlatProfiles(), FallbackProvider(WEATHER_YEAR)
    result = run_advice(
        household=household,
        pv_system=system,
        baseline=baseline_tariffs(),
        scenario=scenario_2027_tariffs(),
        grid=GRID,
        profile_provider=profiles,
        production_provider=production,
        weather_year=WEATHER_YEAR,
    )
    advice = advise(
        household=household,
        pv_system=system,
        scenario=scenario_2027_tariffs(),
        grid=GRID,
        profile_provider=profiles,
        production_provider=production,
        result=result,
        filled_fields=6,
        weather_year=WEATHER_YEAR,
    )
    assert advice.headline == result.band
    assert advice.engine_version == result.engine_version
    # The end of net metering costs this household hundreds of euro a year, and
    # the band is measured rather than a percentage of the middle value.
    assert advice.headline.p10_eur < advice.headline.p50_eur < advice.headline.p90_eur
    assert advice.headline.p50_eur > Decimal("0")


def test_no_rule_reads_anything_outside_the_advice_context() -> None:
    """Spec section 9 point 5: the rule table cannot see a commercial relationship.

    AdviceContext holds no supplier, no installer, no affiliate and no price a
    partner sets, so a rule structurally cannot judge on one. That was true by
    construction and enforced by nothing, which means the next field added to
    the context is the moment it could stop being true quietly. This walks every
    condition and asserts the names it touches are fields of the context.
    """
    allowed = {field.name for field in dataclasses.fields(AdviceContext)}
    for rule in RULES:
        touched = set(rule.condition.__code__.co_names)
        closure = inspect.getclosurevars(rule.condition)
        touched |= set(closure.nonlocals) | set(closure.globals)
        assert touched <= allowed, f"{rule.rule_id} reads {sorted(touched - allowed)}"


def test_every_assumption_round_one_makes_pushes_the_answer_up() -> None:
    """The claim chapter 16 of the methodology makes, held against the model.

    Round one asks four questions and fills in the rest: nobody home during the
    day, no electric car, no heat pump, no battery, a fixed contract. Every one
    of those defaults makes the figure at the top of the answer larger than it
    would be if the household said otherwise. That is the direction that makes
    this product's case, not the direction that protects the reader, and the
    published methodology says so in words. This is what keeps those words
    true: if a default is ever changed to one that shrinks the shock, or the
    model moves so that one of these stops holding, the document has to be
    rewritten rather than quietly become wrong.

    Directions only, not the figures. The figures are in the document, measured
    on this same household, and they move with every tariff revision; the sign
    of each difference is the claim.
    """
    case = HOUSEHOLDS["rob_fixed_contract"]
    assumed = _central_shock("rob_fixed_contract")

    def shock(
        household: Household, dynamic: bool = False, battery: BatterySpec | None = None
    ) -> Decimal:
        system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0.0, tilt_deg=35.0)
        hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
            household.postcode4, system.azimuth_deg, system.tilt_deg
        )
        production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
        consumption = compose_consumption(
            household,
            GRID,
            FlatProfiles().fractions(GRID.year, household.profile_category),
            temperature,
            weather_year=WEATHER_YEAR,
            production_kwh=production,
        )
        flows = simulate(consumption, production, battery_spec=battery)
        return annual_cost(flows, scenario_2027_tariffs(dynamic=dynamic)) - annual_cost(
            flows, baseline_tariffs()
        )

    household = _household(case)
    assert household.daytime_occupancy is False, "this case must carry the round one defaults"
    assert household.ev is None and household.heat_pump is None

    at_home = shock(dataclasses.replace(household, daytime_occupancy=True))
    solar_car = shock(dataclasses.replace(household, ev=EV(behaviour=EVChargingBehaviour.SOLAR)))
    heat_pump = shock(dataclasses.replace(household, heat_pump=HeatPump(heat_demand_kwh=8000.0)))
    stored = shock(
        household, battery=BatterySpec(capacity_kwh=5.0, max_charge_kw=2.5, max_discharge_kw=2.5)
    )
    dynamic = shock(household, dynamic=True)
    #: The row each variant has in the table in chapter 16 of the methodology.
    rows = {
        "Overdag iemand thuis": at_home,
        "Auto die overdag op eigen overschot laadt": solar_car,
        "Warmtepomp": heat_pump,
        "Thuisbatterij van 5 kWh": stored,
        "Dynamisch contract": dynamic,
    }
    document = (Path(__file__).resolve().parent.parent / "docs" / "methodologie.md").read_text(
        encoding="utf-8"
    )
    assert f"met deze aannames {round(assumed)} euro per jaar" in document
    for label, measured in rows.items():
        assert measured < assumed, f"{label} no longer lowers the shock: {measured} vs {assumed}"
        # And the figure the document prints for it is the one measured here.
        # This is the check the document did not have when it kept quoting a
        # break even price the model had stopped producing.
        row = f"| {label} | {round(measured)} euro, dus {round(assumed - measured)} lager |"
        assert row in document, f"chapter 16 does not say {row!r}"

    # The one that changes nothing, and it is not a rounding accident. While a
    # household takes more from the grid than it exports, extra night time
    # consumption is netted against itself under the rules that end in 2027, so
    # what their end costs is unchanged by it.
    night_car = shock(dataclasses.replace(household, ev=EV(behaviour=EVChargingBehaviour.NIGHT)))
    assert night_car == assumed


def test_no_constant_is_defined_twice_in_the_package() -> None:
    """One name, one definition, or the two copies decide different things.

    MAX_ACCEPTABLE_PAYBACK_YEARS was written out in both battery.py and
    advise.py. The verdict a household reads was taken on advise.py's copy while
    the break even price printed beside it, the Dutch text and this suite all
    came from battery.py's, so moving one of them to fifteen would have shown a
    household "worth considering" at fourteen years next to a price computed for
    twelve, with every test still green and the published methodology still
    saying twelve. Nothing pointed at the duplication, so this does.

    Uppercase module level names only, which is what a constant looks like here.
    """
    definitions: dict[str, list[str]] = {}
    package = Path(ADVICE_PACKAGE.__file__ or "").parent
    for path in sorted(package.rglob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                if name.isupper():
                    definitions.setdefault(name, []).append(path.name)
    duplicated = {name: files for name, files in definitions.items() if len(files) > 1}
    assert duplicated == {}, f"defined in more than one module: {duplicated}"


def test_every_measured_saving_arrives_as_a_band_that_names_its_own_limits() -> None:
    """No amount leaves this package alone, and none of them claims too much.

    Each free route is measured at all three levels of the tariff band, which
    costs no extra simulation because a tariff changes what a kilowatt hour is
    worth and not where it goes. Three of the five assumptions the headline
    varies are held still here, and the band carries their names so the response
    can say the real spread is wider rather than implying it is this.
    """
    advice = _golden_advice("rob_fixed_contract")
    measured = [
        fired.estimated_saving_eur for fired in advice.fired if fired.route is not Route.STORAGE
    ]
    assert measured, "this household takes free routes, so it must have measured savings"
    for band in measured:
        assert band is not None
        assert band.low < band.mid < band.high, band
        assert set(band.varied) == {"supply_price", "feed_in_price", "feed_in_cost_per_kwh"}
        assert set(band.pinned) == {
            "annual_consumption_kwh",
            "shiftable_block_kwh",
            "system_loss_fraction",
        }
        assert band.combinations == 3


def test_the_battery_band_moves_the_tariffs_and_not_only_the_battery_price() -> None:
    """The band on a payback used to pin the tariffs and move the price alone.

    That made its optimistic end the payback at the cheapest quote in the market
    under tariffs assumed to be exactly right, which is the end that favours
    buying. The saving itself now moves with the tariff band as well, and the
    figures that stay pinned are named in the band rather than left out of it.
    """
    battery = _golden_advice("rob_fixed_contract").battery
    assert battery is not None
    # Rob is advised to move to a dynamic contract, so his battery is priced in
    # the regime he is being told to move to. There is no separate feed-in
    # charge there at any level, so that input is honestly absent rather than
    # listed as something that moved.
    assert set(battery.payback_years.varied) == {
        "supply_price",
        "feed_in_price",
        "battery_cost_per_kwh",
    }
    assert battery.payback_years.combinations == 9
    price_only_low = battery.payback_years.mid * Decimal("450") / Decimal("675")
    assert battery.payback_years.low < price_only_low


def test_the_rule_table_is_pinned_to_the_advice_version() -> None:
    """A stored advice must stay explainable.

    advice_version is a hand written string and the only test touching it
    compared it to itself, which cannot fail. Nothing tied it to the content of
    the rule table, so a threshold could move, a rule could be added or a route
    could change while the version stayed put, and an advice recorded last month
    could no longer be reproduced or defended.
    """
    snapshot = {
        "0.1.0": (
            ("SHIFT_FLEXIBLE_LOAD", "SHIFT_BEHAVIOUR", 10),
            ("CHARGE_EV_ON_SURPLUS", "SMART_CONTROL", 20),
            ("CONSIDER_DYNAMIC_CONTRACT", "SMART_CONTROL", 30),
            ("CONSIDER_BATTERY", "STORAGE", 40),
            ("BATTERY_DOES_NOT_PAY_BACK", "STORAGE", 45),
            ("BATTERY_DEPENDS_ON_PRICE", "STORAGE", 46),
            ("REVIEW_EXISTING_BATTERY", "STORAGE", 50),
        )
    }
    assert ADVICE_VERSION in snapshot, "the rule table moved, so ADVICE_VERSION must move too"
    actual = tuple((rule.rule_id, rule.route.name, rule.priority) for rule in RULES)
    assert actual == snapshot[ADVICE_VERSION]


def test_an_advice_refuses_a_result_from_a_different_run() -> None:
    """Two runs must not be mixed into one answer without anybody noticing."""
    case = HOUSEHOLDS["rob_fixed_contract"]
    with pytest.raises(ValueError, match="weather year"):
        advise(
            household=_household(case),
            pv_system=PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0.0, tilt_deg=35.0),
            scenario=scenario_2027_tariffs(),
            grid=GRID,
            profile_provider=FlatProfiles(),
            production_provider=FallbackProvider(WEATHER_YEAR),
            result=dataclasses.replace(_stub_result(), weather_year=WEATHER_YEAR - 1),
            filled_fields=6,
            weather_year=WEATHER_YEAR,
        )


#: The tolerance every payback comparison is allowed to use, in years.
#:
#: The figure lives per household in advice_households.json, beside the value it
#: guards. That is a convenient shape and a dangerous one: when one case fails,
#: widening its own tolerance is a one character edit in a data file, it turns
#: the assertion for that household into nothing, and the diff looks like the
#: golden file being updated, which is a thing that legitimately happens.
#:
#: tests/golden/README.md already says not to do it, and CLAUDE.md makes it one
#: of the standing rules for this repository. Neither could fail a build. This
#: constant is what makes them able to.
#:
#: It may be lowered and not raised, for the same reason the coverage floor may
#: only go up. Raising it means editing this line, which is a diff in a test
#: rather than in a data file, and it has to be argued for where somebody
#: reviewing will see it.
MAX_PAYBACK_TOLERANCE_YEARS = 0.25


def _households_with_a_payback() -> dict[str, Any]:
    return {
        name: case
        for name, case in EXPECTED.items()
        if case.get("battery_payback_mid_years") is not None
    }


def test_no_household_carries_a_payback_tolerance_of_its_own() -> None:
    """One number for all of them, so no single case can be loosened alone.

    Measured on 2026-08-22: all three households that get a payback carry 0.25,
    which is about two percent of the tightest of the three middles. Nothing is
    loosened here; what changes is that loosening one of them now fails.
    """
    households = _households_with_a_payback()
    assert households, "no golden household has a payback; this test reads nothing"
    tolerances = {name: case["payback_tolerance_years"] for name, case in households.items()}
    assert set(tolerances.values()) == {MAX_PAYBACK_TOLERANCE_YEARS}, (
        "the golden households no longer share one payback tolerance, so at least one "
        f"assertion has been loosened on its own: {tolerances}"
    )


def test_the_payback_tolerance_stays_small_against_the_figure_it_guards() -> None:
    """A tolerance is only a tolerance while it is smaller than the answer.

    Equality with a shared constant does not say the constant is sensible: all
    three could carry a tolerance of ten years and agree perfectly. This is the
    other half, and it is deliberately loose, because the point is not to pick a
    percentage but to refuse a tolerance that has stopped meaning anything.
    """
    for name, case in _households_with_a_payback().items():
        middle = float(case["battery_payback_mid_years"])
        share = float(case["payback_tolerance_years"]) / middle
        assert share < 0.05, (
            f"{name} allows {share:.1%} of its own payback as slack, which is wide "
            "enough to hide a change in the sentence a household acts on"
        )


# ---------------------------------------------------------------------------
# What find_knee's early break rests on
# ---------------------------------------------------------------------------


def _marginal_savings(points: Sequence[tuple[float, Decimal]]) -> list[Decimal]:
    """Euro per extra kWh for each step, the first one measured from no battery."""
    out: list[Decimal] = []
    previous_capacity, previous_saving = 0.0, Decimal("0")
    for capacity, saving in points:
        out.append((saving - previous_saving) / Decimal(str(capacity - previous_capacity)))
        previous_capacity, previous_saving = capacity, saving
    return out


def test_a_step_below_the_knee_threshold_is_never_followed_by_one_above_it() -> None:
    """The assumption that lets find_knee stop at the first failing step.

    Its docstring says the curve only flattens, so nothing beyond the first
    failing step can recover. Measured on 2026-08-23 that is not exactly true:
    on large_array_small_use the marginal saving rises again, by up to 0.0005
    euro per kWh. That cannot move a knee, because the thresholds in play are
    tens of euro per kWh, but a claim that is nearly true is not one to keep
    resting a battery recommendation on without checking.

    What the early break actually needs is weaker and exactly this: the steps
    that clear the threshold form an unbroken run from the start. A curve with a
    second knee would size a household's battery on the first of them and never
    look at the rest, and the direction of that mistake depends on the curve,
    which is worse than a mistake with a known direction.

    Read off the advice rather than recomputed, so it costs no simulation and so
    it judges the curve the product actually builds: advise.py prices capacity
    against the consumption left after the free routes, which is not the curve a
    direct call to _capacity_curve produces.
    """
    checked, mixed = 0, 0
    for name in sorted(HOUSEHOLDS):
        battery = _golden_advice(name).battery
        if battery is None:
            continue
        for level in ("low", "mid", "high"):
            points = [(capacity, getattr(band, level)) for capacity, band in battery.curve]
            marginal = _marginal_savings(points)
            threshold = marginal[0] / 2
            above = [step >= threshold for step in marginal]
            checked += 1
            if any(above) and not all(above):
                mixed += 1
            assert above == sorted(above, reverse=True), (
                f"{name} at {level}: steps clearing the threshold are {above}, so the curve "
                "recovers after falling and find_knee stops too early"
            )
    assert checked >= 9, f"only {checked} curve levels were judged"
    assert mixed > 0, (
        "every curve was entirely above or entirely below its own threshold, so nothing here "
        "exercised the ordering this test is about"
    )


def test_enough_of_the_golden_households_reach_a_capacity_curve() -> None:
    """The floor under the test above, which walks whatever curves exist.

    Three of the six households get no battery advice at all, which is the
    product working as intended. If the other three stopped getting one the test
    above would pass over an empty set and say nothing.
    """
    with_curve = [name for name in HOUSEHOLDS if _golden_advice(name).battery is not None]
    assert len(with_curve) >= 3, f"only {sorted(with_curve)} still reach a capacity curve"


# ---------------------------------------------------------------------------
# The chain the free route figures are measured along
# ---------------------------------------------------------------------------


@cache
def _free_routes(name: str) -> tuple[Decimal, FreeRouteOutcome, np.ndarray]:
    """Run _measure_free_routes the way advise() runs it, plus the starting cost.

    Built here rather than read off the Advice because the Advice carries the
    savings and not the two endpoints they are supposed to span.
    """
    case = HOUSEHOLDS[name]
    household = _household(case)
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0.0, tilt_deg=35.0)
    hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    fractions = FlatProfiles().fractions(GRID.year, household.profile_category)
    levels = dataclasses.replace(scenario_2027_levels(dynamic=False), mid=scenario_2027_tariffs())
    alternative = dataclasses.replace(
        scenario_2027_levels(dynamic=True), mid=scenario_2027_tariffs(dynamic=True)
    )
    free_ids = frozenset(
        fired.rule_id for fired in _golden_advice(name).fired if fired.route is not Route.STORAGE
    )
    consumption = compose_consumption(
        household,
        GRID,
        fractions,
        temperature,
        weather_year=WEATHER_YEAR,
        production_kwh=production,
    )
    started_at = _annual_costs(simulate(consumption, production), levels)[1]
    outcome = _measure_free_routes(
        household=household,
        grid=GRID,
        fractions=fractions,
        temperature=temperature,
        production=production,
        scenario=levels,
        dynamic_scenario=alternative,
        fired_ids=free_ids,
        battery_spec=None,
        weather_year=WEATHER_YEAR,
    )
    return started_at, outcome, production


@pytest.mark.parametrize(
    "name", ["rob_fixed_contract", "large_array_small_use", "marloes_ev_at_night"]
)
def test_the_free_route_savings_span_exactly_the_two_ends_they_claim_to(name: str) -> None:
    """Each step measured from where the last one left off, to the cent.

    The comment above FREE_ROUTE_ORDER says the figures are additive by
    construction, and FreeRouteOutcome's own docstring calls the failure this
    prevents the most expensive defect this package has had: the same kilowatt
    hours sold twice, once as a free saving and again as a reason to buy a
    battery. Additive by construction means the three savings telescope, so
    their total is the distance between the household that did nothing and the
    household that did everything.

    The existing invariant is an upper bound, that the total cannot exceed the
    headline. That is necessary and it is not this. Measured on 2026-08-23:
    dropping one of the running_cost assignments, so a step is measured from the
    original household again instead of from the previous step, leaves the upper
    bound satisfied and the whole suite green except one frontend fixture
    comparison, which says a number moved and not which claim broke.
    """
    started_at, outcome, production = _free_routes(name)
    assert outcome.savings, f"{name} took no free routes, so there is no chain to check"

    total = sum(band.mid for band in outcome.savings.values())
    ended_at = _annual_costs(simulate(outcome.consumption, production), outcome.scenario)[1]
    assert total == started_at - ended_at, (
        f"{name}: the three savings add up to {total} while the household moved from "
        f"{started_at} to {ended_at}, a distance of {started_at - ended_at}"
    )


def test_the_measured_free_routes_are_the_ones_the_module_lists() -> None:
    """FREE_ROUTE_ORDER is read by nothing, so it is a second copy of an order.

    _measure_free_routes applies its three routes in hand written if blocks. The
    tuple above it names the same three in the same order and no code consults
    it, which means a reordering or a fourth route can leave the two disagreeing
    with nothing to say so. The order is not decoration: each step is measured
    on top of the last, so which one runs first decides how the same total is
    split between them.
    """
    import inspect as _inspect

    body = _inspect.getsource(_measure_free_routes)
    guarded = re.findall(r'"([A-Z_]+)" in fired_ids', body)
    assert guarded == list(FREE_ROUTE_ORDER), (
        f"the function applies {guarded}, which is not what FREE_ROUTE_ORDER says"
    )
