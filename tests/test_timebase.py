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


# ---------------------------------------------------------------------------
# One window mask, and the branch two of the three copies used to be missing
# ---------------------------------------------------------------------------


def test_a_window_that_runs_past_midnight_selects_both_ends_of_the_day() -> None:
    """The branch that was in two of the three copies and not in the third.

    Until 2026-08-23 there were three implementations of this: private ones in
    ``ampeer_sim.profiles.assets`` and ``ampeer_advice.facts`` with the branch,
    and one in ``ampeer_sim.profiles.presence`` without it, all three pointing
    at each other in comments. A window whose start is later than its end runs
    past midnight and wants the union, and the version without the branch
    selects nothing at all for one.

    Selecting nothing is not an error anywhere it was used, which is what makes
    it worth a test rather than a comment. In presence.py the shiftable block
    would have stayed where it was on every day of the year, and every guard in
    that function would have reported a day with nowhere to put its energy.
    """
    grid = YearGrid.for_year(2025)
    night = grid.window_mask((23, 7))
    hours = set(grid.local_hour[night].tolist())
    assert hours == {23, 0, 1, 2, 3, 4, 5, 6}, f"the night window selected hours {sorted(hours)}"
    assert int(night.sum()) == 8 * 4 * grid.days, (
        f"eight hours a day over {grid.days} days is {8 * 4 * grid.days} quarters, not "
        f"{int(night.sum())}"
    )


def test_a_forward_window_selects_exactly_its_own_hours() -> None:
    """The floor, since the check above is about one of two branches.

    A mask that took the union for every window would pass the test above and
    select twenty of the twenty four hours here.
    """
    grid = YearGrid.for_year(2025)
    midday = grid.window_mask((11, 15))
    hours = set(grid.local_hour[midday].tolist())
    assert hours == {11, 12, 13, 14}, f"the midday window selected hours {sorted(hours)}"


def test_the_two_packages_measure_the_same_midday() -> None:
    """A claim ampeer_advice.facts makes in prose about another package.

    Its comment says its MIDDAY_WINDOW is the one presence.py uses, so a load
    the presence model moves into midday lands in the surplus facts measures.
    Two constants in two packages, and nothing compared them: the rule that
    fires on midday surplus would have judged a window the shift never filled.
    """
    from ampeer_advice.facts import MIDDAY_WINDOW as JUDGED
    from ampeer_sim.profiles.presence import MIDDAY_WINDOW as SHIFTED_INTO

    assert JUDGED == SHIFTED_INTO, (
        f"the presence model moves load into {SHIFTED_INTO} and the rules judge surplus in "
        f"{JUDGED}, so a household is measured on a window nothing filled"
    )
