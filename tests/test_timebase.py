from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.timebase import YearGrid


def test_non_leap_year_has_35040_quarters() -> None:
    assert YearGrid.for_year(2025).quarters == 35_040


def test_leap_year_has_35136_quarters() -> None:
    assert YearGrid.for_year(2024).quarters == 35_136


def test_grid_starts_at_local_midnight() -> None:
    grid = YearGrid.for_year(2025)
    assert grid.local_hour[0] == 0
    assert grid.weekday[0] == 2  # 1 January 2025 is a Wednesday


def test_summer_time_start_skips_an_hour_of_local_clock() -> None:
    grid = YearGrid.for_year(2025)
    # 30 March 2025, the clock jumps from 02:00 to 03:00 local time.
    march_30 = (31 + 28 + 29) * 96
    hours_that_day = sorted(set(grid.local_hour[march_30 : march_30 + 96].tolist()))
    assert 2 not in hours_that_day
    assert len(hours_that_day) == 23


def test_winter_time_end_repeats_an_hour_of_local_clock() -> None:
    grid = YearGrid.for_year(2025)
    # 26 October 2025, the clock falls back from 03:00 to 02:00 local time.
    october_26 = (31 + 28 + 31 + 30 + 31 + 30 + 31 + 31 + 30 + 25) * 96
    day = grid.local_hour[october_26 : october_26 + 96].tolist()
    assert day.count(2) == 8  # the hour is lived through twice


def test_hourly_to_quarters_preserves_a_constant_series() -> None:
    grid = YearGrid.for_year(2025)
    quarters = grid.hourly_to_quarters(np.full(grid.hours, 7.0))
    assert quarters.shape == (grid.quarters,)
    assert np.allclose(quarters, 7.0)


def test_hourly_to_quarters_is_monotone_for_a_monotone_input() -> None:
    grid = YearGrid.for_year(2025)
    quarters = grid.hourly_to_quarters(np.arange(grid.hours, dtype=float))
    assert np.all(np.diff(quarters) >= -1e-12)


def test_hourly_to_quarters_peaks_around_the_hour_midpoint() -> None:
    grid = YearGrid.for_year(2025)
    hourly = np.zeros(grid.hours)
    hourly[11] = 4.0
    quarters = grid.hourly_to_quarters(hourly)
    # The midpoint of hour 11 sits at quarter position 45.5, between 45 and 46.
    assert quarters[45] == pytest.approx(3.5)
    assert quarters[46] == pytest.approx(3.5)
    assert int(quarters.argmax()) in (45, 46)


def test_hourly_to_quarters_rejects_a_wrong_length_series() -> None:
    grid = YearGrid.for_year(2025)
    with pytest.raises(ValueError, match="8760"):
        grid.hourly_to_quarters(np.zeros(100))


def test_align_hourly_year_drops_29_february_for_a_non_leap_grid() -> None:
    grid = YearGrid.for_year(2025)
    leap_hourly = np.arange(8784, dtype=float)
    aligned = grid.align_hourly_year(leap_hourly, weather_year=2024)
    assert aligned.shape == (8760,)
    # The first hour of 1 March survives; 29 February is gone.
    assert aligned[(31 + 28) * 24] == pytest.approx(leap_hourly[(31 + 29) * 24])


def test_align_hourly_year_duplicates_28_february_for_a_leap_grid() -> None:
    grid = YearGrid.for_year(2024)
    normal_hourly = np.arange(8760, dtype=float)
    aligned = grid.align_hourly_year(normal_hourly, weather_year=2025)
    assert aligned.shape == (8784,)
    feb_28 = (31 + 27) * 24
    feb_29 = (31 + 28) * 24
    assert np.allclose(aligned[feb_29 : feb_29 + 24], aligned[feb_28 : feb_28 + 24])


def test_align_hourly_year_leaves_a_matching_year_alone() -> None:
    grid = YearGrid.for_year(2025)
    hourly = np.arange(8760, dtype=float)
    assert np.allclose(grid.align_hourly_year(hourly, weather_year=2025), hourly)


def test_align_hourly_year_rejects_a_wrong_length_series() -> None:
    grid = YearGrid.for_year(2025)
    with pytest.raises(ValueError, match="8760 hourly values"):
        grid.align_hourly_year(np.zeros(100), weather_year=2025)


def test_align_hourly_year_rejects_a_series_that_is_not_the_year_it_claims() -> None:
    """The check the weather year exists for.

    Until 2026-08-24 that argument was in the signature and nowhere in the
    body: leapness came off the length alone.

    The dates were not wrong, and I wrote that they were before measuring it.
    A series of 8760 values on a leap grid puts a copy of 28 February on the
    29th and every later day lands on its own date. What went unreported is
    the disagreement: a provider that returns 8760 values for a leap year is a
    day of weather short, and the model runs a February day twice instead of
    saying so.

    Both directions, because a provider can be wrong either way: a leap year
    that arrived short, and a common year that arrived long.
    """
    grid = YearGrid.for_year(2025)
    with pytest.raises(ValueError, match="2024 has 8784"):
        grid.align_hourly_year(np.zeros(8_760), weather_year=2024)
    with pytest.raises(ValueError, match="2023 has 8760"):
        grid.align_hourly_year(np.zeros(8_784), weather_year=2023)
