"""Move the shiftable block between the midday and the evening window.

This is a shift and never a scale. Somebody who works from home does not use
more electricity, they use it at another moment, and the daily total is the
invariant that keeps the model honest.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_DAY, YearGrid

MIDDAY_WINDOW = (11, 15)
EVENING_WINDOW = (17, 21)


def _mask(grid: YearGrid, window: tuple[int, int]) -> np.ndarray:
    start, end = window
    return (grid.local_hour >= start) & (grid.local_hour < end)


def apply_presence(
    series: np.ndarray, grid: YearGrid, block_kwh: float, daytime_occupancy: bool
) -> np.ndarray:
    """Return a copy of ``series`` with the shiftable block relocated."""
    if block_kwh <= 0.0:
        return series.copy()

    source_window, target_window = (
        (EVENING_WINDOW, MIDDAY_WINDOW) if daytime_occupancy else (MIDDAY_WINDOW, EVENING_WINDOW)
    )
    source = _mask(grid, source_window).reshape(grid.days, QUARTERS_PER_DAY)
    target = _mask(grid, target_window).reshape(grid.days, QUARTERS_PER_DAY)

    shifted = series.copy().reshape(grid.days, QUARTERS_PER_DAY)
    for day in range(grid.days):
        source_slots = shifted[day][source[day]]
        available = float(source_slots.sum())
        moved = min(block_kwh, available)
        target_slot_count = int(target[day].sum())
        if moved <= 0.0 or target_slot_count == 0:
            continue
        shifted[day, source[day]] = source_slots * (1.0 - moved / available)
        shifted[day, target[day]] += moved / target_slot_count
    return shifted.reshape(grid.quarters)
