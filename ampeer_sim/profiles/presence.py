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


def apply_presence(
    series: np.ndarray, grid: YearGrid, block_kwh: float, daytime_occupancy: bool
) -> np.ndarray:
    """Return a copy of ``series`` with the shiftable block relocated."""
    if block_kwh <= 0.0:
        return series.copy()

    source_window, target_window = (
        (EVENING_WINDOW, MIDDAY_WINDOW) if daytime_occupancy else (MIDDAY_WINDOW, EVENING_WINDOW)
    )
    source = grid.window_mask(source_window).reshape(grid.days, QUARTERS_PER_DAY)
    target = grid.window_mask(target_window).reshape(grid.days, QUARTERS_PER_DAY)

    shifted = series.copy().reshape(grid.days, QUARTERS_PER_DAY)

    # Vectorised rather than a loop over days. This runs once per composition,
    # and a composition happens 243 times for the sensitivity band plus once per
    # measured free route, so the day loop showed up as half a second on a CI
    # runner. The arithmetic is unchanged: take a share out of the source window
    # proportionally, put it into the target window evenly.
    available = np.where(source, shifted, 0.0).sum(axis=1)
    target_slots = target.sum(axis=1)
    moved = np.minimum(block_kwh, available)

    # A day with nothing in the source window, or nowhere to put it, is left
    # alone. Guarding the divisors keeps that from becoming a nan.
    movable = (moved > 0.0) & (target_slots > 0)
    safe_available = np.where(available > 0.0, available, 1.0)
    safe_slots = np.where(target_slots > 0, target_slots, 1)

    scale = np.where(movable, 1.0 - moved / safe_available, 1.0)[:, None]
    addition = np.where(movable, moved / safe_slots, 0.0)[:, None]

    shifted = np.where(source, shifted * scale, shifted)
    shifted = np.where(target, shifted + addition, shifted)
    return shifted.reshape(grid.quarters)
