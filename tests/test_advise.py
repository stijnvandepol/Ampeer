"""The seams between the advice lanes, and the golden households.

The individual lanes each test their own module. What is left, and what this
file is for, is the composition: that the rule table, the tariff band, the
capacity curve and the Dutch texts still describe the same household when they
are put together, and that the two battery rules can never both come out.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import re
import time
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import ampeer_advice as ADVICE_PACKAGE
from ampeer_advice import ADVICE_VERSION
from ampeer_advice.advise import (
    MAX_ACCEPTABLE_PAYBACK_YEARS,
    _storage_verdict,
    advise,
    recommended_route,
)
from ampeer_advice.battery import CAPACITIES, battery_advice
from ampeer_advice.nl import RULE_TEXTS
from ampeer_advice.rules import RULES
from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs
from ampeer_advice.types import Advice, AdviceContext, Confidence, Route
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
    assert float(battery.payback_years_p50) == pytest.approx(
        expected["battery_payback_p50_years"], abs=expected["payback_tolerance_years"]
    )


@pytest.mark.parametrize("name", sorted(HOUSEHOLDS))
def test_a_battery_recommendation_never_arrives_as_a_single_number(name: str) -> None:
    """Every advice rule: no figure without a band around it."""
    battery = _golden_advice(name).battery
    if battery is None:
        return
    assert battery.payback_years_p10 < battery.payback_years_p50 < battery.payback_years_p90


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
    assert advice.battery.payback_years_p50 > MAX_ACCEPTABLE_PAYBACK_YEARS


def test_a_payback_inside_the_cost_band_is_reported_as_depending_on_the_price() -> None:
    """The one household left with a maybe, and why the verdict has three states.

    This case exports 89 percent of what it makes, so storage is closer to worth
    it here than anywhere else in the golden set. Its central payback clears
    twelve years and its pessimistic end does not, and nothing about the
    household decides which it turns out to be: the price of the quote does.
    That is the one variable the reader can go and find out, so they are told
    the price at which it flips rather than a yes they cannot check.

    This used to be Rob, at 11.83 years against a limit of twelve. Correcting
    the central net feed-in from a derived -0.010 per kWh to the published
    +0.0025 pushed him to 12.46 and a clear no.
    """
    advice = _golden_advice("large_array_small_use")
    ids = [fired.rule_id for fired in advice.fired]
    assert "BATTERY_DEPENDS_ON_PRICE" in ids
    assert "CONSIDER_BATTERY" not in ids
    assert "BATTERY_DOES_NOT_PAY_BACK" not in ids
    assert advice.battery is not None
    assert advice.battery.payback_years_p50 <= MAX_ACCEPTABLE_PAYBACK_YEARS
    assert advice.battery.payback_years_p90 > MAX_ACCEPTABLE_PAYBACK_YEARS
    # The actionable number: below this installed price it pays back in time.
    assert advice.battery.break_even_cost_per_kwh == Decimal("835.73")


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
    generous = [(capacity, Decimal(str(capacity * 200))) for capacity in CAPACITIES]
    battery = battery_advice(generous)
    assert battery.payback_years_p90 <= MAX_ACCEPTABLE_PAYBACK_YEARS
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
        (fired.estimated_saving_eur for fired in advice.fired if fired.estimated_saving_eur),
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
            assert isinstance(fired.estimated_saving_eur, Decimal), fired


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
