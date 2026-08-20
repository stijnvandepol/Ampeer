from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.assets import (
    ev_grid_topup,
    ev_profile,
    ev_solar_profile,
    heat_pump_profile,
)
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EV, EVChargingBehaviour, HeatPump

GRID = YearGrid.for_year(2025)


def test_night_charging_hits_the_annual_energy_need() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT, annual_km=12_000, kwh_per_100km=18.0)
    series = ev_profile(ev, GRID)
    assert series.sum() == pytest.approx(ev.annual_kwh)


def test_night_charging_only_happens_at_night() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT)
    series = ev_profile(ev, GRID)
    daytime = series[(GRID.local_hour >= 7) & (GRID.local_hour < 23)]
    assert daytime.sum() == pytest.approx(0.0)


def test_arrival_charging_only_happens_in_the_evening() -> None:
    ev = EV(behaviour=EVChargingBehaviour.ARRIVAL)
    series = ev_profile(ev, GRID)
    outside = series[(GRID.local_hour < 17) | (GRID.local_hour >= 21)]
    assert outside.sum() == pytest.approx(0.0)


def test_charging_never_exceeds_the_charge_power_limit() -> None:
    ev = EV(behaviour=EVChargingBehaviour.ARRIVAL, annual_km=60_000, charge_power_kw=3.7)
    series = ev_profile(ev, GRID)
    assert series.max() <= 3.7 / 4 + 1e-9


def test_a_need_larger_than_the_window_spills_outside_it() -> None:
    ev = EV(behaviour=EVChargingBehaviour.ARRIVAL, annual_km=60_000, charge_power_kw=3.7)
    series = ev_profile(ev, GRID)
    outside = series[(GRID.local_hour < 17) | (GRID.local_hour >= 21)]
    assert outside.sum() > 0.0
    assert series.sum() == pytest.approx(ev.annual_kwh)


def test_a_need_no_charger_could_ever_meet_is_rejected() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT, annual_km=1_000_000, charge_power_kw=3.7)
    with pytest.raises(ValueError, match="charge_power_kw"):
        ev_profile(ev, GRID)


def test_solar_charging_requires_a_surplus() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR)
    series = ev_solar_profile(ev, GRID, surplus_kwh=np.zeros(GRID.quarters))
    assert series.sum() == pytest.approx(0.0)


def test_solar_charging_takes_from_the_surplus_up_to_the_daily_need() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=3_650, kwh_per_100km=20.0)
    surplus = np.zeros(GRID.quarters)
    surplus[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 1.0
    series = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    assert series.sum() == pytest.approx(ev.annual_kwh, rel=1e-6)
    assert series[GRID.local_hour < 11].sum() == pytest.approx(0.0)


def test_solar_charging_is_capped_by_the_available_surplus() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=100_000)
    surplus = np.zeros(GRID.quarters)
    surplus[GRID.local_hour == 12] = 0.1
    series = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    assert np.all(series <= surplus + 1e-9)


def test_a_solar_ev_tops_up_from_the_grid_when_the_sun_falls_short() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=15_000)
    from_sun = ev_solar_profile(ev, GRID, surplus_kwh=np.zeros(GRID.quarters))
    topup = ev_grid_topup(ev, GRID, from_sun)
    assert topup.sum() == pytest.approx(ev.annual_kwh)


def test_a_solar_ev_needs_no_top_up_when_the_sun_covers_it() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=3_650, kwh_per_100km=20.0)
    surplus = np.zeros(GRID.quarters)
    surplus[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 1.0
    from_sun = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    assert ev_grid_topup(ev, GRID, from_sun).sum() == pytest.approx(0.0, abs=1e-9)


def test_the_top_up_only_applies_to_solar_charging() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT)
    assert ev_grid_topup(ev, GRID, np.zeros(GRID.quarters)).sum() == pytest.approx(0.0)


def test_a_non_solar_ev_charges_nothing_from_surplus() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT)
    surplus = np.full(GRID.quarters, 1.0)
    assert ev_solar_profile(ev, GRID, surplus_kwh=surplus).sum() == pytest.approx(0.0)


def test_heat_pump_consumes_nothing_in_a_warm_year() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0, base_temperature_c=15.0)
    warm = np.full(GRID.hours, 25.0)
    series = heat_pump_profile(pump, warm, GRID, weather_year=2025)
    assert series.sum() == pytest.approx(0.0)


def test_heat_pump_delivers_the_requested_heat_demand() -> None:
    pump = HeatPump(
        heat_demand_kwh=6_000.0, base_temperature_c=15.0, cop_at_7c=3.0, cop_slope_per_c=0.0
    )
    cold = np.full(GRID.hours, 5.0)
    series = heat_pump_profile(pump, cold, GRID, weather_year=2025)
    # With a flat COP of 3, electricity is a third of the heat demand.
    assert series.sum() == pytest.approx(2_000.0, rel=1e-6)


def test_heat_pump_uses_more_electricity_per_unit_of_heat_when_it_is_colder() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0, base_temperature_c=15.0)
    mild = np.full(GRID.hours, 10.0)
    cold = np.full(GRID.hours, -5.0)
    mild_total = heat_pump_profile(pump, mild, GRID, weather_year=2025).sum()
    cold_total = heat_pump_profile(pump, cold, GRID, weather_year=2025).sum()
    assert cold_total > mild_total


def test_heat_pump_efficiency_never_drops_below_a_resistive_heater() -> None:
    pump = HeatPump(
        heat_demand_kwh=6_000.0, base_temperature_c=15.0, cop_at_7c=1.2, cop_slope_per_c=0.5
    )
    arctic = np.full(GRID.hours, -30.0)
    series = heat_pump_profile(pump, arctic, GRID, weather_year=2025)
    assert series.sum() == pytest.approx(6_000.0, rel=1e-6)
