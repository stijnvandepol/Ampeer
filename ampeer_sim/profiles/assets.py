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


def _window_mask(grid: YearGrid, window: tuple[int, int]) -> np.ndarray:
    start, end = window
    if start < end:
        return (grid.local_hour >= start) & (grid.local_hour < end)
    return (grid.local_hour >= start) | (grid.local_hour < end)


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


def ev_profile(ev: EV, grid: YearGrid) -> np.ndarray:
    """Return quarter-hour EV consumption in kWh for NIGHT and ARRIVAL behaviour.

    SOLAR is handled by ``ev_solar_profile`` because it needs the production
    series, and that dependency belongs in the signature.
    """
    if ev.behaviour is EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    cap = ev.charge_power_kw / QUARTERS_PER_HOUR
    daily_need = ev.annual_kwh / grid.days
    if daily_need > cap * QUARTERS_PER_DAY:
        raise ValueError(
            f"charging {daily_need:.1f} kWh a day needs more than charge_power_kw="
            f"{ev.charge_power_kw}"
        )

    window = NIGHT_WINDOW if ev.behaviour is EVChargingBehaviour.NIGHT else ARRIVAL_WINDOW
    in_window = _window_mask(grid, window).reshape(grid.days, QUARTERS_PER_DAY)

    series = np.zeros((grid.days, QUARTERS_PER_DAY))
    for day in range(grid.days):
        remaining = daily_need
        for position in _charging_priority(in_window[day]):
            if remaining <= 0.0:
                break
            take = min(cap, remaining)
            series[day, position] = take
            remaining -= take
    return series.reshape(grid.quarters)


def ev_solar_profile(ev: EV, grid: YearGrid, surplus_kwh: np.ndarray) -> np.ndarray:
    """Charge from the production surplus, day by day, up to the daily need."""
    if ev.behaviour is not EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    cap = ev.charge_power_kw / QUARTERS_PER_HOUR
    daily_need = ev.annual_kwh / grid.days
    available = np.minimum(surplus_kwh, cap).reshape(grid.days, QUARTERS_PER_DAY)

    cumulative_before = np.cumsum(available, axis=1) - available
    headroom = np.clip(daily_need - cumulative_before, 0.0, None)
    return np.minimum(available, headroom).reshape(grid.quarters)


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
