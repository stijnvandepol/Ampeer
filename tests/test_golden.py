from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

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
