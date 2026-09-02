from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.assets import (
    ev_grid_topup,
    ev_profile,
    ev_solar_profile,
    heat_pump_profile,
)
from ampeer_sim.timebase import QUARTERS_PER_DAY, QUARTERS_PER_HOUR, YearGrid
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


#: Charge powers to hold the invariant below against, from a wall box down to a
#: household socket. The API asks for none of them: it asks whether there is a
#: car and when it charges, and takes 3.7 kW from the dataclass default. The
#: lower ones are here because the reason the invariant holds gets thinner as
#: the power falls, and a check that only ever sees the comfortable case is not
#: holding anything.
CHARGE_POWERS_KW = (3.7, 2.3, 1.4, 0.7)


@pytest.mark.parametrize("charge_power_kw", CHARGE_POWERS_KW)
def test_a_solar_charged_car_never_draws_more_than_its_charger(charge_power_kw: float) -> None:
    """The two halves of solar charging are capped apart and summed together.

    ``compose_consumption`` adds ``ev_solar_profile`` and ``ev_grid_topup``,
    and each caps itself at the charge power. Nothing caps the sum. That is the
    same shape as the battery bug fixed on 2026-08-23, where a rating was
    enforced per call while the loop called twice, and it is worth pinning here
    because this path runs for every household that says it charges on its own
    surplus.

    It holds today, and not by the arithmetic. ``_allocate_daily`` places the
    shortfall in the night window and spills outward when a day needs more than
    the window holds, so an overrun needs a quarter where the sun charged and
    the spill landed. Those cannot be the same quarter often, because the
    shortfall is largest exactly on the days the sun gave least: the two series
    are anti-correlated by construction rather than kept apart by a rule.

    Which is why this is a test rather than a comment. A change to the window,
    to the order ``_charging_priority`` fills it in, or to the kilometres the
    API assumes would break the coincidence quietly, and the result would be a
    car drawing more than its charger can deliver, which flatters solar
    charging in the direction this project is most careful about.
    """
    ev = EV(
        behaviour=EVChargingBehaviour.SOLAR,
        annual_km=12_000,
        charge_power_kw=charge_power_kw,
    )
    # A surplus that is present on some days and absent on others, so the
    # shortfall varies the way a real year makes it vary. Flat sunshine would
    # never produce a spill and would leave this passing on the easy case.
    quarters = np.arange(GRID.quarters)
    daylight = (quarters % QUARTERS_PER_DAY >= 40) & (quarters % QUARTERS_PER_DAY < 64)
    dull_day = (quarters // QUARTERS_PER_DAY) % 3 == 0
    surplus = np.where(daylight & ~dull_day, 1.0, 0.0)

    from_sun = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    from_grid = ev_grid_topup(ev, GRID, from_sun)
    cap = charge_power_kw / QUARTERS_PER_HOUR

    together = from_sun + from_grid
    worst = int(np.argmax(together))
    assert together[worst] <= cap + 1e-12, (
        f"quarter {worst} draws {together[worst]:.4f} kWh from a charger that can deliver "
        f"{cap:.4f}: {from_sun[worst]:.4f} from the sun and {from_grid[worst]:.4f} from the grid"
    )


def test_the_surplus_this_invariant_is_measured_against_is_not_flat() -> None:
    """The floor under the check above, which is a maximum over a series.

    A surplus that never runs out means the grid top-up is never asked for
    anything, and then the sum it is asserting about has one term in it. The
    case has to contain both a day the sun covered and a day it did not.
    """
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=12_000, charge_power_kw=3.7)
    quarters = np.arange(GRID.quarters)
    daylight = (quarters % QUARTERS_PER_DAY >= 40) & (quarters % QUARTERS_PER_DAY < 64)
    dull_day = (quarters // QUARTERS_PER_DAY) % 3 == 0
    surplus = np.where(daylight & ~dull_day, 1.0, 0.0)

    from_sun = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    from_grid = ev_grid_topup(ev, GRID, from_sun)
    assert from_sun.sum() > 0.0, "the sun charged nothing, so only one term is being summed"
    assert from_grid.sum() > 0.0, "the grid topped up nothing, so only one term is being summed"
