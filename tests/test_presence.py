from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.presence import EVENING_WINDOW, MIDDAY_WINDOW, apply_presence
from ampeer_sim.timebase import QUARTERS_PER_DAY, YearGrid

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


def _shaped_series() -> np.ndarray:
    """A year whose every day rises from midnight to midnight.

    Flat is the wrong fixture for the two claims below and it is the fixture
    every other test in this file uses. On a flat window, taking energy out
    proportionally and taking it out evenly produce the same numbers, so a
    change from one to the other passes all eight of them. A real NEDU profile
    has a shape, and the shape is what the proportional rule exists to keep.
    """
    rising = 1.0 + (np.arange(GRID.quarters) % QUARTERS_PER_DAY) / QUARTERS_PER_DAY
    return rising * (3_500.0 / rising.sum())


def test_the_source_window_keeps_its_shape_and_the_target_gains_evenly() -> None:
    """The sentence in the module comment, held to a series that can show it.

    "Take a share out of the source window proportionally, put it into the
    target window evenly." Two different rules for the two ends, and the reason
    is that the source is a real profile whose shape is a measurement, while
    the target is a household deciding to run a machine at another hour, which
    the model has no information to shape.

    Measured on 2026-08-24: the source window comes out scaled by one constant,
    so every ratio inside it survives, and each of the sixteen target quarters
    gains exactly a sixteenth of the block.
    """
    before = _shaped_series()
    after = apply_presence(before, GRID, block_kwh=1.0, daytime_occupancy=False)

    source = _window_mask(MIDDAY_WINDOW)
    target = _window_mask(EVENING_WINDOW)
    first_day_source_before = before[source].reshape(GRID.days, -1)[0]
    first_day_source_after = after[source].reshape(GRID.days, -1)[0]
    ratios = first_day_source_after / first_day_source_before
    assert np.allclose(ratios, ratios[0]), (
        "the source window did not come out scaled by one number, so the profile's own "
        f"shape inside it was changed: ratios ran from {ratios.min()} to {ratios.max()}"
    )

    first_day_target_before = before[target].reshape(GRID.days, -1)[0]
    first_day_target_after = after[target].reshape(GRID.days, -1)[0]
    additions = first_day_target_after - first_day_target_before
    assert np.allclose(additions, additions[0]), (
        "the block did not arrive evenly across the target window, which would be the "
        "model inventing an hour the household prefers"
    )
    assert np.isclose(additions.sum(), 1.0), (
        f"the target window gained {additions.sum()} of a 1.0 kWh block"
    )


def test_the_shaped_series_has_a_shape_inside_both_windows() -> None:
    """The floor under the test above.

    Handed a flat series it would pass on both assertions while checking
    neither, which is exactly how the rest of this file passes today.
    """
    series = _shaped_series()
    for name, window in (("midday", MIDDAY_WINDOW), ("evening", EVENING_WINDOW)):
        first_day = series[_window_mask(window)].reshape(GRID.days, -1)[0]
        assert not np.allclose(first_day, first_day[0]), (
            f"the {name} window is flat in this fixture, so the shape it is supposed to "
            "preserve is not there to preserve"
        )
