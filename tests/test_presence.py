from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.presence import EVENING_WINDOW, MIDDAY_WINDOW, apply_presence
from ampeer_sim.timebase import YearGrid

GRID = YearGrid.for_year(2025)


def _flat_series() -> np.ndarray:
    return np.full(GRID.quarters, 3_500.0 / GRID.quarters)


def _window_mask(window: tuple[int, int]) -> np.ndarray:
    start, end = window
    return (GRID.local_hour >= start) & (GRID.local_hour < end)


def test_daily_totals_are_unchanged() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=True)
    daily_before = before.reshape(GRID.days, 96).sum(axis=1)
    daily_after = after.reshape(GRID.days, 96).sum(axis=1)
    assert np.allclose(daily_before, daily_after)


def test_daytime_occupancy_moves_energy_into_the_midday_window() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=True)
    midday = _window_mask(MIDDAY_WINDOW)
    assert after[midday].sum() > before[midday].sum()


def test_absence_moves_energy_into_the_evening_window() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=False)
    evening = _window_mask(EVENING_WINDOW)
    assert after[evening].sum() > before[evening].sum()


def test_the_moved_amount_matches_the_block() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.0, daytime_occupancy=True)
    midday = _window_mask(MIDDAY_WINDOW)
    moved = after[midday].sum() - before[midday].sum()
    assert moved == pytest.approx(1.0 * GRID.days, rel=1e-6)


def test_a_block_larger_than_the_window_is_clamped_not_negative() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=999.0, daytime_occupancy=True)
    assert after.min() >= 0.0
    daily_before = before.reshape(GRID.days, 96).sum(axis=1)
    daily_after = after.reshape(GRID.days, 96).sum(axis=1)
    assert np.allclose(daily_before, daily_after)


def test_a_zero_block_changes_nothing() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=0.0, daytime_occupancy=True)
    assert np.allclose(before, after)


def test_the_input_series_is_not_mutated() -> None:
    before = _flat_series()
    original = before.copy()
    apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=True)
    assert np.allclose(before, original)


def test_the_annual_total_survives_the_shift() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=False)
    assert after.sum() == pytest.approx(before.sum())
