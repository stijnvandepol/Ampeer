from __future__ import annotations

import dataclasses
import enum
import importlib
import json
import pkgutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import ampeer_sim
from ampeer_sim import ENGINE_VERSION
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EV, EnergyFlows, EVChargingBehaviour, HeatPump, Household, PVSystem

GOLDEN: dict[str, dict[str, Any]] = json.loads(
    (Path(__file__).parent / "golden" / "households.json").read_text(encoding="utf-8")
)
GRID = YearGrid.for_year(2025)
WEATHER_YEAR = 2025
FLAT_FRACTIONS = np.full(GRID.quarters, 1.0 / GRID.quarters)


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


def _run(case: dict[str, Any]) -> tuple[EnergyFlows, np.ndarray]:
    household = _household(case)
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0, tilt_deg=35)
    hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    consumption = compose_consumption(
        household,
        GRID,
        FLAT_FRACTIONS,
        temperature,
        weather_year=WEATHER_YEAR,
        production_kwh=production,
    )
    return simulate(consumption, production), consumption


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_household_self_consumption(name: str) -> None:
    case = GOLDEN[name]
    flows, _ = _run(case)
    assert flows.self_consumption_rate == pytest.approx(
        case["expected_self_consumption_rate"], abs=case["tolerance"]
    )


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_household_consumption_total(name: str) -> None:
    case = GOLDEN[name]
    _, consumption = _run(case)
    assert consumption.sum() == pytest.approx(case["expected_consumption_kwh"], rel=1e-3)


def test_the_hand_checkable_case_can_be_derived_by_hand() -> None:
    """Verify the pencil case rather than trusting the recorded number.

    With no shiftable block and no assets, consumption is exactly flat at
    3650 / 35040 kWh per quarter. Self consumption is then the integral of
    min(flat, production) over the year divided by the annual yield, which the
    assertion below recomputes directly instead of restating.
    """
    case = GOLDEN["hand_checkable"]
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0, tilt_deg=35)
    hourly, _, _ = FallbackProvider(WEATHER_YEAR).hourly_series("5401", 0.0, 35.0)
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    flat = np.full(GRID.quarters, case["annual_consumption_kwh"] / GRID.quarters)

    by_hand = float(np.minimum(flat, production).sum() / production.sum())
    flows, _ = _run(case)
    assert flows.self_consumption_rate == pytest.approx(by_hand, abs=1e-9)


def test_charging_the_car_on_your_own_surplus_beats_charging_it_at_night() -> None:
    """The single most valuable piece of advice the product gives.

    Same household, same annual driving need, same energy. Only the moment of
    charging differs. If this gap ever collapses, either the model or the advice
    is wrong.
    """
    at_night, night_consumption = _run(GOLDEN["marloes_ev_at_night"])
    on_solar, solar_consumption = _run(GOLDEN["marloes_ev_on_solar"])

    assert solar_consumption.sum() == pytest.approx(night_consumption.sum(), rel=1e-6)
    assert on_solar.self_consumption_rate > at_night.self_consumption_rate + 0.30
    assert on_solar.to_grid.sum() < at_night.to_grid.sum()
    assert on_solar.from_grid.sum() < at_night.from_grid.sum()


def test_a_bigger_array_on_the_same_house_wastes_a_larger_share() -> None:
    small, _ = _run(GOLDEN["rob_fixed_contract"])
    large, _ = _run(GOLDEN["large_array_small_use"])
    assert large.self_consumption_rate < small.self_consumption_rate


def _engine_constants() -> tuple[tuple[str, str], ...]:
    """Every default value the engine carries, found rather than listed.

    A list written here would cover the constants somebody thought of, which is
    the shape of guard this repository keeps replacing with a derived one.

    Defaults and not every literal in the package. A default is the value the
    engine uses for a caller who does not override it, so it is part of what
    ampeer_sim promises, and all of the model figures in docs/methodologie.md
    live as one: the COP at seven degrees, its slope, the kilometres a year, the
    system loss. Constants inside a function body are not covered, and saying so
    is better than implying they are.
    """
    found: dict[str, type] = {}
    for module in pkgutil.walk_packages(ampeer_sim.__path__, "ampeer_sim."):
        imported = importlib.import_module(module.name)
        for name in dir(imported):
            candidate = getattr(imported, name)
            if (
                isinstance(candidate, type)
                and dataclasses.is_dataclass(candidate)
                and candidate.__module__.startswith("ampeer_sim")
            ):
                found[f"{candidate.__module__}.{candidate.__name__}"] = candidate

    def shown(value: object) -> str:
        # An enum member reprs as "<ProfileCategory.E1A: 'E1A'>", which carries
        # its own value and would move if the value moved without the member
        # moving. The member name is the thing being pinned.
        if isinstance(value, enum.Enum):
            return f"{type(value).__name__}.{value.name}"
        return repr(value)

    return tuple(
        sorted(
            (f"{qualified}.{field.name}", shown(field.default))
            for qualified, cls in found.items()
            for field in dataclasses.fields(cls)
            if field.default is not dataclasses.MISSING
        )
    )


def _golden_answers() -> tuple[tuple[str, float], ...]:
    """The numbers the six golden households are asserted to produce.

    Only the expected values. A tolerance is slack around an answer rather than
    an answer, so widening one is not an engine change and must not be able to
    look like one. That tolerances should not quietly widen is a separate rule
    with its own guard in tests/test_advise.py.
    """
    return tuple(
        sorted(
            (f"{name}.{key}", float(value))
            for name, case in GOLDEN.items()
            for key, value in case.items()
            if key.startswith("expected_")
        )
    )


def _difference(
    actual: tuple[tuple[str, object], ...], pinned: tuple[tuple[str, object], ...]
) -> str:
    """What moved, so a failure names the value rather than the mismatch."""
    found, recorded = dict(actual), dict(pinned)
    return "\n".join(
        f"  {name}: pinned {recorded.get(name)!r}, found {found.get(name)!r}"
        for name in sorted(set(found) | set(recorded))
        if found.get(name) != recorded.get(name)
    )


def test_the_model_constants_are_pinned_to_the_engine_version() -> None:
    """A stored advice must stay reproducible.

    CLAUDE.md asks every calculation to log the engine version, and every
    calculation does: simulate() stamps it, advise() carries it through, the API
    returns it, and the audit log records it beside the token digest. All of
    that answers "which engine produced this number" with a hand written string
    that nothing forces to move. Change the COP and every advice from before and
    after the change says 0.1.0, and the older one can no longer be reproduced
    or defended.

    ADVICE_VERSION already has this guard, pinned to the rule table in
    tests/test_advise.py. ENGINE_VERSION is the half that produces the numbers,
    and until now the only test touching it asserted it was a string with two
    dots in it.

    Nothing here needs a companion test proving it can fail on an empty reading.
    The assertion is an equality against a non-empty tuple, so a walk that
    imported nothing compares () against twenty-three rows and fails. A pairing
    that tested membership would need that companion; this one carries its own
    floor.
    """
    snapshot = {
        "0.1.0": (
            ("ampeer_sim.types.BatterySpec.allow_grid_charging", "False"),
            ("ampeer_sim.types.BatterySpec.round_trip_efficiency", "0.9"),
            ("ampeer_sim.types.BatterySpec.usable_dod", "0.9"),
            ("ampeer_sim.types.EV.annual_km", "12000"),
            ("ampeer_sim.types.EV.charge_power_kw", "3.7"),
            ("ampeer_sim.types.EV.kwh_per_100km", "18.0"),
            ("ampeer_sim.types.EnergyFlows.grid_charge", "None"),
            ("ampeer_sim.types.EnergyFlows.grid_discharge", "None"),
            ("ampeer_sim.types.HeatPump.base_temperature_c", "15.0"),
            ("ampeer_sim.types.HeatPump.cop_at_7c", "3.5"),
            ("ampeer_sim.types.HeatPump.cop_slope_per_c", "0.06"),
            ("ampeer_sim.types.Household.daytime_occupancy", "False"),
            ("ampeer_sim.types.Household.ev", "None"),
            ("ampeer_sim.types.Household.heat_pump", "None"),
            ("ampeer_sim.types.Household.profile_category", "ProfileCategory.E1A"),
            ("ampeer_sim.types.Household.shiftable_block_kwh", "1.0"),
            ("ampeer_sim.types.PVSystem.install_year", "None"),
            ("ampeer_sim.types.PVSystem.system_loss_fraction", "0.14"),
            ("ampeer_sim.types.TariffSet.dynamic", "False"),
            ("ampeer_sim.types.TariffSet.feed_in_cost_per_kwh", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.feed_in_fixed_cost_year", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.net_metering", "False"),
            ("ampeer_sim.types.TariffSet.standing_charge_year", "Decimal('0')"),
        )
    }
    assert ENGINE_VERSION in snapshot, (
        f"ENGINE_VERSION is {ENGINE_VERSION!r} and this table has no row for it. "
        "A version that moved without recording what it computes leaves the "
        "advice stamped with it unexplainable."
    )
    actual = _engine_constants()
    assert actual == snapshot[ENGINE_VERSION], (
        "the engine computes with different constants than the version says:\n"
        + _difference(actual, snapshot[ENGINE_VERSION])
        + f"\nEither restore the value or move ENGINE_VERSION past {ENGINE_VERSION} "
        "and add a row above. docs/methodologie.md holds the source for each of "
        "these, so a change here is a change there too."
    )


def test_the_golden_answers_are_pinned_to_the_engine_version() -> None:
    """The other way the engine's numbers move without the version moving.

    A constant can stay put while the arithmetic around it changes, and the
    golden households are where that shows: six answers computed end to end. The
    tests above already fail when one of them drifts, which is what makes
    updating tests/golden/households.json the ordinary response, and that edit
    is a single file with no mention of a version anywhere in it.

    Pinning them here does not make the goldens harder to update. It makes
    updating them say which engine the new answers belong to.
    """
    snapshot = {
        "0.1.0": (
            ("hand_checkable.expected_consumption_kwh", 3650.0),
            ("hand_checkable.expected_self_consumption_rate", 0.9381),
            ("large_array_small_use.expected_consumption_kwh", 2200.0),
            ("large_array_small_use.expected_self_consumption_rate", 0.1134),
            ("marloes_ev_at_night.expected_consumption_kwh", 5700.0),
            ("marloes_ev_at_night.expected_self_consumption_rate", 0.2557),
            ("marloes_ev_on_solar.expected_consumption_kwh", 5700.0),
            ("marloes_ev_on_solar.expected_self_consumption_rate", 0.7572),
            ("rob_fixed_contract.expected_consumption_kwh", 3500.0),
            ("rob_fixed_contract.expected_self_consumption_rate", 0.332),
            ("sander_heat_pump.expected_consumption_kwh", 6802.0),
            ("sander_heat_pump.expected_self_consumption_rate", 0.5032),
        )
    }
    assert ENGINE_VERSION in snapshot, (
        f"ENGINE_VERSION is {ENGINE_VERSION!r} and no golden answers are recorded for it"
    )
    actual = _golden_answers()
    assert actual == snapshot[ENGINE_VERSION], (
        "the golden households no longer hold the answers this engine version promises:\n"
        + _difference(actual, snapshot[ENGINE_VERSION])
        + f"\nIf the engine changed on purpose, move ENGINE_VERSION past {ENGINE_VERSION} "
        "and record the new answers above."
    )
