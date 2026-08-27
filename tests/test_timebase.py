from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

import ampeer_advice.facts
from ampeer_sim.timebase import MINUTES_PER_QUARTER, YearGrid


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
    """Where an hourly value lands, which is a convention and not a given.

    The anchor is half past, because an hourly value is read here as the mean of
    its hour. That is right for every series built as hour means, which is what
    the offline production shape is, and it is not right for PVGIS, which stamps
    its rows ten minutes past the hour. The engine consequently places a PVGIS
    series twenty minutes late, and the measurement of what that costs is above
    ``UTC_TO_WINTER_TIME_HOURS`` in ``ampeer_sim.production.pvgis``.

    So the anchor is asserted in minutes as well as in quarter positions, and
    the second half of this is what tests/test_pvgis_provider.py measures the
    twenty minutes against. Moving it is a change to where every hourly series
    in the model sits, and it should cost a red test here first.
    """
    grid = YearGrid.for_year(2025)
    hourly = np.zeros(grid.hours)
    hourly[11] = 4.0
    quarters = grid.hourly_to_quarters(hourly)
    # The midpoint of hour 11 sits at quarter position 45.5, between 45 and 46.
    assert quarters[45] == pytest.approx(3.5)
    assert quarters[46] == pytest.approx(3.5)
    assert int(quarters.argmax()) in (45, 46)

    positions = np.arange(quarters.size, dtype=float)
    centre = float((positions * quarters).sum() / quarters.sum())
    anchor_minutes = (centre + 0.5) * MINUTES_PER_QUARTER - 11 * 60.0
    assert anchor_minutes == pytest.approx(30.0, abs=1e-9), (
        f"an hourly value is now anchored {anchor_minutes:.2f} minutes past its hour rather "
        "than half past, so every hourly series in the model has moved in time and the "
        "twenty minute residual recorded for PVGIS is a different number"
    )


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


def test_the_advice_layer_borrows_the_midday_window_it_judges() -> None:
    """One constant, and this asserts that rather than comparing two.

    ampeer_advice.facts said in prose that its MIDDAY_WINDOW was the one
    presence.py uses, so a load the presence model moves into midday lands in
    the surplus facts measures. Two constants in two packages, and nothing
    compared them, so on 2026-08-23 this file paired them.

    The pairing is gone because the duplication is. facts.py imports the
    constant now, which is what its own docstring asks for: one definition of
    what a window means, since a second module with its own idea of it gives no
    error and two advices that disagree.

    Read off the source rather than through the module, because importing a name
    a module re-exports is what mypy's strict mode refuses, and rightly: the
    question here is where facts.py gets the value, not what the value is.
    """
    tree = ast.parse(
        (Path(ampeer_advice.facts.__file__ or "").read_text(encoding="utf-8")),
        filename="facts.py",
    )
    borrowed = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "MIDDAY_WINDOW" for alias in node.names)
    ]
    assert borrowed == ["ampeer_sim.profiles.presence"], (
        f"facts.py takes MIDDAY_WINDOW from {borrowed}, and the module that fills that "
        "window is ampeer_sim.profiles.presence"
    )

    assigned = [
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "MIDDAY_WINDOW"
    ]
    assert not assigned, "facts.py defines its own MIDDAY_WINDOW again"
