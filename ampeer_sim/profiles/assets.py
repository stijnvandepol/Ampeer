"""Consumption profiles for assets the NEDU average does not represent.

An EV and a heat pump are added on top of the base shape rather than mixed
into it, because the household that has them is not the household the average
describes.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_DAY, QUARTERS_PER_HOUR, YearGrid
from ampeer_sim.types import EV, EVChargingBehaviour, HeatPump

NIGHT_WINDOW = (23, 7)
ARRIVAL_WINDOW = (17, 21)

#: A heat pump never does worse than a resistive heater.
MIN_COP = 1.0


def _charging_priority(in_window: np.ndarray) -> np.ndarray:
    """Rank the quarters of one day: inside the window first, then nearest to it.

    A car that needs more energy than fits in its window charges for longer
    rather than failing to charge, which is what a real charger does.
    """
    positions = np.arange(QUARTERS_PER_DAY)
    window_positions = positions[in_window]
    if window_positions.size == 0:
        return positions
    distance = np.abs(positions[:, None] - window_positions[None, :]).min(axis=1)
    return np.argsort(distance, kind="stable")


def _allocate_daily(
    daily_need: np.ndarray, grid: YearGrid, window: tuple[int, int], cap: float
) -> np.ndarray:
    """Place each day's charging need into its window, spilling outward if needed."""
    if float(daily_need.max(initial=0.0)) > cap * QUARTERS_PER_DAY:
        raise ValueError(
            f"charging {daily_need.max():.1f} kWh a day needs more than charge_power_kw="
            f"{cap * QUARTERS_PER_HOUR}"
        )
    in_window = grid.window_mask(window).reshape(grid.days, QUARTERS_PER_DAY)
    series = np.zeros((grid.days, QUARTERS_PER_DAY))
    for day in range(grid.days):
        remaining = float(daily_need[day])
        if remaining <= 0.0:
            continue
        for position in _charging_priority(in_window[day]):
            if remaining <= 0.0:
                break
            take = min(cap, remaining)
            series[day, position] = take
            remaining -= take
    return series.reshape(grid.quarters)


def ev_profile(ev: EV, grid: YearGrid) -> np.ndarray:
    """Return quarter-hour EV consumption in kWh for NIGHT and ARRIVAL behaviour.

    SOLAR is handled by ``ev_solar_profile`` because it needs the production
    series, and that dependency belongs in the signature.
    """
    if ev.behaviour is EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    window = NIGHT_WINDOW if ev.behaviour is EVChargingBehaviour.NIGHT else ARRIVAL_WINDOW
    daily_need = np.full(grid.days, ev.annual_kwh / grid.days)
    return _allocate_daily(daily_need, grid, window, ev.charge_power_kw / QUARTERS_PER_HOUR)


def ev_solar_profile(ev: EV, grid: YearGrid, surplus_kwh: np.ndarray) -> np.ndarray:
    """Charge from the production surplus, day by day, up to the daily need."""
    if ev.behaviour is not EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    cap = ev.charge_power_kw / QUARTERS_PER_HOUR
    daily_need = ev.annual_kwh / grid.days
    available = np.minimum(surplus_kwh, cap).reshape(grid.days, QUARTERS_PER_DAY)

    cumulative_before = np.cumsum(available, axis=1) - available
    headroom = np.clip(daily_need - cumulative_before, 0.0, None)
    charged: np.ndarray = np.minimum(available, headroom).reshape(grid.quarters)
    return charged


def ev_grid_topup(ev: EV, grid: YearGrid, solar_charged_kwh: np.ndarray) -> np.ndarray:
    """Charge whatever the sun did not deliver, from the grid, at night.

    Without this the model would let a solar-charging car quietly drive fewer
    kilometres on a dull week. That understates consumption and flatters the
    self consumption rate, both in the direction that makes solar charging look
    better than it is.
    """
    if ev.behaviour is not EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    daily_need = ev.annual_kwh / grid.days
    charged_per_day = solar_charged_kwh.reshape(grid.days, QUARTERS_PER_DAY).sum(axis=1)
    shortfall = np.clip(daily_need - charged_per_day, 0.0, None)
    return _allocate_daily(shortfall, grid, NIGHT_WINDOW, ev.charge_power_kw / QUARTERS_PER_HOUR)


def heat_pump_profile(
    pump: HeatPump, temperature_c: np.ndarray, grid: YearGrid, weather_year: int
) -> np.ndarray:
    """Return quarter-hour heat pump electricity consumption in kWh.

    Heat demand follows degree hours below the base temperature. The COP falls
    with the outdoor temperature, which is why a flat COP understates winter
    consumption in exactly the months without production.
    """
    aligned = grid.align_hourly_year(temperature_c, weather_year=weather_year)
    quarterly_temperature = grid.hourly_to_quarters(aligned)

    degree_steps = np.clip(pump.base_temperature_c - quarterly_temperature, 0.0, None)
    total = float(degree_steps.sum())
    if total == 0.0:
        return np.zeros(grid.quarters)

    heat_kwh = degree_steps / total * pump.heat_demand_kwh
    cop = np.clip(
        pump.cop_at_7c + (quarterly_temperature - 7.0) * pump.cop_slope_per_c,
        MIN_COP,
        None,
    )
    return heat_kwh / cop
