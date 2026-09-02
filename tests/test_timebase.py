from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

import ampeer_advice.facts
from ampeer_sim.timebase import (
    HOURLY_MEAN_ANCHOR_MINUTES,
    MINUTES_PER_QUARTER,
    YearGrid,
)


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


def _placed_minutes_past(grid: YearGrid, hour: int, anchor: float | None = None) -> float:
    """Where a lone hourly spike at ``hour`` ends up, in minutes past that hour.

    Read out of what the function returns rather than out of the arithmetic in
    its body, so this measures the placement instead of restating the formula.
    A quarter names the fifteen minutes beginning at it, hence the half quarter
    that turns an index into the middle of what it covers.
    """
    hourly = np.zeros(grid.hours)
    hourly[hour] = 4.0
    quarters = (
        grid.hourly_to_quarters(hourly)
        if anchor is None
        else grid.hourly_to_quarters(hourly, anchor)
    )
    positions = np.arange(quarters.size, dtype=float)
    centre = float((positions * quarters).sum() / quarters.sum())
    return (centre + 0.5) * MINUTES_PER_QUARTER - hour * 60.0


def test_an_unstamped_hourly_series_is_read_as_the_mean_of_its_hour() -> None:
    """The default anchor, which is the only one true of a series that says nothing.

    An hourly value with no stamp on it is the mean of its hour, so it belongs
    in the middle of that hour. That is what every series in this model was read
    as until 2026-08-27, when the anchor became an argument because one series
    is not: PVGIS stamps its rows ten minutes past the hour, and reading those
    as hour means put them twenty minutes late. The measurement of what that
    cost is above ``UTC_TO_WINTER_TIME_HOURS`` in ``ampeer_sim.production.pvgis``.

    The default is asserted here and not merely used, because a default is what
    a caller who says nothing gets. Moving it moves every unstamped series in
    the model at once, and it should cost a red test here first.
    """
    grid = YearGrid.for_year(2025)
    hourly = np.zeros(grid.hours)
    hourly[11] = 4.0
    quarters = grid.hourly_to_quarters(hourly)
    # The middle of hour 11 sits at quarter position 45.5, between 45 and 46.
    assert quarters[45] == pytest.approx(3.5)
    assert quarters[46] == pytest.approx(3.5)
    assert int(quarters.argmax()) in (45, 46)

    anchor_minutes = _placed_minutes_past(grid, 11)
    assert anchor_minutes == pytest.approx(HOURLY_MEAN_ANCHOR_MINUTES, abs=1e-9), (
        f"an unstamped hourly value is now anchored {anchor_minutes:.2f} minutes past its "
        f"hour rather than {HOURLY_MEAN_ANCHOR_MINUTES:.0f}, so every series in the model "
        "that carries no stamp has moved in time"
    )
    assert HOURLY_MEAN_ANCHOR_MINUTES == pytest.approx(30.0), (
        "the mean of an hour belongs in the middle of it, and half of sixty is thirty"
    )


@pytest.mark.parametrize("anchor", [0.0, 10.0, 22.5, 30.0, 45.0, 59.0])
def test_a_stamped_hourly_series_lands_where_its_stamp_says(anchor: float) -> None:
    """The argument does what it says, over the whole hour it may name.

    Six anchors and not one, because a single case cannot tell a working
    parameter from a constant that happens to agree with it at one value: the
    two ends and the two that the engine actually uses, PVGIS's ten past and the
    hourly mean's half past.

    Measured out of the returned series and compared against the argument, which
    are the two ends of the thing under test and neither of them is the line of
    arithmetic in between.
    """
    grid = YearGrid.for_year(2025)
    placed = _placed_minutes_past(grid, 11, anchor)
    assert placed == pytest.approx(anchor, abs=1e-9), (
        f"a value stamped {anchor:.2f} minutes past its hour was placed {placed:.2f} past"
    )


def test_the_anchor_moves_a_series_and_nothing_else_about_it() -> None:
    """A displacement, not a rescaling: the same energy, twenty minutes earlier.

    Worth its own check because the anchor is applied inside an interpolation
    and an interpolation is where a total quietly stops being conserved. The two
    anchors compared are the ones the engine uses, and twenty minutes is exactly
    the residual the argument was added to remove.

    The input has the shape of a day because the property is only true of a
    series that is smooth across an hour, and that is a fact about linear
    resampling rather than about this code. Measured on 2026-08-29: a daylight
    shaped series and a constant both conserve exactly, to 0.00e+00, while
    ``abs(sin(0.7n))``, which turns over about every nine samples, moves by
    5.3e-05 and only a third of that sits at the two ends. This test used that
    jagged series and demanded 1e-9, which no resampler can give it. Production
    and temperature, the two series the engine actually carries through here,
    are smooth over an hour, so the tolerance below is the right one for them
    and the input has to look like them for it to mean anything.
    """
    grid = YearGrid.for_year(2025)
    hours = np.arange(grid.hours)
    hourly = np.clip(np.sin((hours % 24 - 6) / 12 * np.pi), 0.0, None) * 300.0

    as_mean = grid.hourly_to_quarters(hourly, HOURLY_MEAN_ANCHOR_MINUTES)
    as_stamped = grid.hourly_to_quarters(hourly, 10.0)
    assert as_stamped.sum() == pytest.approx(as_mean.sum(), rel=1e-9), (
        "moving where a value sits inside its hour changed how much of it there is"
    )

    positions = np.arange(grid.quarters, dtype=float)
    moved = (
        float((positions * as_mean).sum() / as_mean.sum())
        - float((positions * as_stamped).sum() / as_stamped.sum())
    ) * MINUTES_PER_QUARTER
    assert moved == pytest.approx(20.0, abs=1e-6), (
        f"the two anchors the engine uses are {moved:.2f} minutes apart and the residual "
        "they were introduced to remove is twenty"
    )


@pytest.mark.parametrize("anchor", [-1.0, 60.0, 90.0])
def test_an_anchor_outside_its_own_hour_is_refused(anchor: float) -> None:
    """Sixty minutes past is the next hour, and saying so is not a placement.

    Left to numpy this would not raise; it would silently interpolate against a
    shifted set of anchors and place the whole series in a neighbouring hour,
    which is the failure this argument exists to make impossible to reach by
    accident.
    """
    grid = YearGrid.for_year(2025)
    with pytest.raises(ValueError, match="inside its own hour"):
        grid.hourly_to_quarters(np.zeros(grid.hours), anchor)


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
