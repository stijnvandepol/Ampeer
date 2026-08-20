from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EV, EVChargingBehaviour, HeatPump, Household, ProfileCategory

GRID = YearGrid.for_year(2025)
FRACTIONS = np.full(GRID.quarters, 1.0 / GRID.quarters)
MILD = np.full(GRID.hours, 20.0)


def _household(**overrides: Any) -> Household:
    defaults: dict[str, Any] = {
        "postcode4": "5401",
        "annual_consumption_kwh": 3_500.0,
        "profile_category": ProfileCategory.E1A,
    }
    defaults.update(overrides)
    return Household(**defaults)


def test_a_bare_household_totals_its_annual_consumption() -> None:
    series = compose_consumption(_household(), GRID, FRACTIONS, MILD, weather_year=2025)
    assert series.sum() == pytest.approx(3_500.0)


def test_an_ev_adds_its_own_annual_energy() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT, annual_km=12_000, kwh_per_100km=18.0)
    series = compose_consumption(_household(ev=ev), GRID, FRACTIONS, MILD, weather_year=2025)
    assert series.sum() == pytest.approx(3_500.0 + ev.annual_kwh)


def test_a_heat_pump_adds_consumption_in_a_cold_year() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0)
    cold = np.full(GRID.hours, 0.0)
    series = compose_consumption(
        _household(heat_pump=pump), GRID, FRACTIONS, cold, weather_year=2025
    )
    assert series.sum() > 3_500.0


def test_presence_changes_the_shape_but_not_the_total() -> None:
    home = compose_consumption(
        _household(daytime_occupancy=True), GRID, FRACTIONS, MILD, weather_year=2025
    )
    away = compose_consumption(
        _household(daytime_occupancy=False), GRID, FRACTIONS, MILD, weather_year=2025
    )
    assert home.sum() == pytest.approx(away.sum())
    assert not np.allclose(home, away)


def test_daytime_occupancy_raises_midday_consumption() -> None:
    midday = (GRID.local_hour >= 11) & (GRID.local_hour < 15)
    home = compose_consumption(
        _household(daytime_occupancy=True), GRID, FRACTIONS, MILD, weather_year=2025
    )
    away = compose_consumption(
        _household(daytime_occupancy=False), GRID, FRACTIONS, MILD, weather_year=2025
    )
    assert home[midday].sum() > away[midday].sum()


def test_solar_charging_needs_a_production_series() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR)
    with pytest.raises(ValueError, match="production"):
        compose_consumption(_household(ev=ev), GRID, FRACTIONS, MILD, weather_year=2025)


def test_solar_charging_uses_the_surplus_that_is_left() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=3_650, kwh_per_100km=20.0)
    production = np.zeros(GRID.quarters)
    production[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 2.0
    series = compose_consumption(
        _household(ev=ev), GRID, FRACTIONS, MILD, weather_year=2025, production_kwh=production
    )
    assert series.sum() == pytest.approx(3_500.0 + ev.annual_kwh, rel=1e-6)


def test_a_mismatched_fraction_length_is_rejected() -> None:
    with pytest.raises(ValueError, match="35040"):
        compose_consumption(_household(), GRID, np.zeros(10), MILD, weather_year=2025)
