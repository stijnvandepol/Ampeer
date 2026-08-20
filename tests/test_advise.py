"""The seams between the advice lanes, and the golden households.

The individual lanes each test their own module. What is left, and what this
file is for, is the composition: that the rule table, the tariff band, the
capacity curve and the Dutch texts still describe the same household when they
are put together, and that the two battery rules can never both come out.
"""

from __future__ import annotations

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
from ampeer_advice.advise import MAX_ACCEPTABLE_PAYBACK_YEARS, advise, recommended_route
from ampeer_advice.nl import RULE_TEXTS
from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs
from ampeer_advice.types import Advice, Confidence, Route
from ampeer_sim.production.pvgis import FallbackProvider
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
        r"|zonnepanelen|zonnestroom|teruglevert|terugleverkosten|vaatwasser)\b",
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
    assert battery.recommended_capacity_kwh == expected["battery_capacity_kwh"]
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

    Marloes charges her car at night, so her evening demand is large enough that
    the curve keeps rising to the biggest battery on offer. That makes the
    saving look impressive and the invoice more so: fifteen kWh at the central
    price does not earn itself back inside the warranty, and the free advice
    above it does the same job for nothing.
    """
    advice = _golden_advice("marloes_ev_at_night")
    ids = [fired.rule_id for fired in advice.fired]
    assert "BATTERY_DOES_NOT_PAY_BACK" in ids
    assert "CONSIDER_BATTERY" not in ids
    assert advice.battery is not None
    assert advice.battery.payback_years_p50 > MAX_ACCEPTABLE_PAYBACK_YEARS
    assert "CHARGE_EV_ON_SURPLUS" in ids


def test_a_household_whose_battery_pays_back_keeps_the_positive_rule() -> None:
    advice = _golden_advice("rob_fixed_contract")
    ids = [fired.rule_id for fired in advice.fired]
    assert "CONSIDER_BATTERY" in ids
    assert "BATTERY_DOES_NOT_PAY_BACK" not in ids
    assert advice.battery is not None
    assert advice.battery.payback_years_p50 <= MAX_ACCEPTABLE_PAYBACK_YEARS


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
