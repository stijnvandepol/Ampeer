"""The seam between stored quarters and the pure fit.

The case that matters most here is the clock. Readings are stored in UTC and
the grid runs in continuous winter time, which has no gap in March and no
repeated hour in October. An off-by-one-hour here would not raise anything: it
would quietly compare a household's evening against the model's afternoon, and
the fitted figure would come back wrong with every test still green.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from helpers.accounts import TEST_PASSWORD

from accounts.models import MeterLink, QuarterReading, User
from accounts.window import build_window, grid_epoch, grid_position, quarter_index
from ampeer_sim.timebase import QUARTERS_PER_DAY, YearGrid

pytestmark = pytest.mark.django_db

GRID = YearGrid.for_year(2025)


def _link(email: str = "meter@voorbeeld.nl") -> MeterLink:
    user = User.objects.create_user(email=email, password=TEST_PASSWORD)
    return MeterLink.objects.create(user=user, token_sha256=f"digest-for-{email}")


def _reading(link: MeterLink, moment: datetime, consumption: float = 0.2) -> None:
    QuarterReading.objects.create(
        link=link, measured_at=moment, consumption_kwh=consumption, feed_in_kwh=0.0
    )


def test_the_grid_begins_an_hour_before_new_year_in_utc() -> None:
    """Continuous winter time is UTC+1, so quarter zero is 31 December 23:00."""
    assert grid_epoch(GRID) == datetime(2024, 12, 31, 23, 0, tzinfo=UTC)


def test_the_first_quarter_of_the_year_is_index_zero() -> None:
    assert quarter_index(datetime(2024, 12, 31, 23, 0, tzinfo=UTC), GRID) == 0
    assert quarter_index(datetime(2024, 12, 31, 23, 15, tzinfo=UTC), GRID) == 1


def test_a_reading_across_the_march_switch_is_not_placed_an_hour_out() -> None:
    """The Sunday the clocks go forward, which the grid does not do.

    30 March 2025 is the last Sunday of March. At 02:30 UTC local clocks have
    already jumped to 04:30, but the grid stays on winter time, so this
    measurement belongs at 03:30 of grid day 88 and nowhere else. A conversion
    that followed the local clock would put it four quarters later.
    """
    moment = datetime(2025, 3, 30, 2, 30, tzinfo=UTC)
    day = (moment.date() - datetime(2025, 1, 1, tzinfo=UTC).date()).days
    expected = day * QUARTERS_PER_DAY + 3 * 4 + 2
    assert quarter_index(moment, GRID) == expected


def test_a_reading_after_the_october_switch_lands_on_one_position_only() -> None:
    """The hour that happens twice locally happens once on the grid."""
    first = datetime(2025, 10, 26, 0, 30, tzinfo=UTC)
    second = first + timedelta(hours=1)
    assert quarter_index(second, GRID) - quarter_index(first, GRID) == 4


def test_a_reading_taken_today_lands_inside_the_grid() -> None:
    """THE TEST THAT WAS MISSING, and the whole feature rested on it.

    `AMPEER_PROFILE_YEAR` is 2025 and stays 2025, because the NEDU profile and
    the golden answers are that year. Quarter readings are deleted after ninety
    days. So no reading a household could possibly have in the table is from
    2025, and the first version of this module placed a measurement by counting
    quarters from the grid's own epoch: measured on 2026-09-13, a reading taken
    that day landed at 59608 in a grid of 35040 and was dropped, along with
    every other one. `build_window` returned None, the calibration proposed
    nothing, and nothing anywhere went red.

    Every test in this file used a 2025 date, so every test agreed with a
    module that could not work. This one uses `timezone.now()` on purpose, and
    it is the reason to keep using it: a date typed into a test is a date the
    author chose, and the bug was in what production would hand over instead.
    """
    from django.utils import timezone

    position = grid_position(timezone.now(), GRID)

    assert position is not None
    assert 0 <= position < GRID.quarters


def test_a_measurement_keeps_its_time_of_day_and_its_day_type() -> None:
    """What the mapping is for, stated as the two things it must not break.

    The model's production peaks at noon and the NEDU profile differs between
    a working day and a Sunday, so a placement that moved a Sunday evening onto
    a Tuesday afternoon would compare a household against the wrong half of the
    model and report the difference as their consumption.
    """
    moment = datetime(2026, 7, 5, 18, 30, tzinfo=UTC)  # a Sunday
    position = grid_position(moment, GRID)

    assert position is not None
    landed = grid_epoch(GRID) + timedelta(minutes=15 * position)
    winter = landed + timedelta(hours=1)
    assert winter.hour == 19 and winter.minute == 30  # 18:30 UTC is 19:30 winter time
    assert winter.weekday() == moment.weekday()  # still a Sunday
    assert abs((winter.date() - date(GRID.year, 7, 5)).days) <= 3


def test_the_whole_window_moves_by_one_offset_rather_than_being_stretched() -> None:
    """The shift is the same for every reading in a year, so the distance
    between two measurements survives the mapping.

    That is what makes it safe to compare a fitted figure against the model at
    these positions: the gaps, the order and the spacing are the household's
    own, and only the calendar underneath them changed.
    """
    first = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    offsets = [timedelta(minutes=15), timedelta(days=1), timedelta(days=17, hours=6)]
    base = grid_position(first, GRID)

    assert base is not None
    for offset in offsets:
        later = grid_position(first + offset, GRID)
        assert later is not None
        assert later - base == int(offset // timedelta(minutes=15))


def test_a_window_carries_the_quarters_it_was_given() -> None:
    from django.utils import timezone

    link = _link()
    start = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    for step in range(4):
        _reading(link, start + timedelta(minutes=15 * step), consumption=0.1 * (step + 1))

    window = build_window(link, GRID)

    assert window is not None
    first = grid_position(start, GRID)
    assert first is not None
    assert list(window.quarter_index) == [first, first + 1, first + 2, first + 3]
    assert list(window.offtake_kwh) == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_a_reading_older_than_the_table_may_hold_it_is_refused() -> None:
    """The protection the year check used to give by accident, put back.

    Nothing in the ingest serializer bounds how old a reading may be, so a
    device can push a timestamp from 2022 and it is live until the nightly fold
    removes it. The mapping above deliberately places a reading from any year,
    which is right for a reading from three months ago and wrong for one from
    three years ago, so the bound is now what it should always have been: the
    ninety days the table is allowed to hold.
    """
    from django.utils import timezone

    link = _link()
    _reading(link, datetime(2022, 6, 1, 12, 0, tzinfo=UTC), consumption=99.0)
    recent = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=2)
    _reading(link, recent)

    window = build_window(link, GRID)

    assert window is not None
    assert window.quarter_index.size == 1
    assert list(window.offtake_kwh) == pytest.approx([0.2])


def test_a_leap_day_has_nowhere_to_go_and_says_so() -> None:
    """29 February onto a common year. Refused rather than moved to the 28th,
    because a silent move is the class of thing this module exists to stop."""
    assert grid_position(datetime(2028, 2, 29, 12, 0, tzinfo=UTC), GRID) is None


def test_a_link_with_nothing_stored_yields_no_window() -> None:
    assert build_window(_link(), GRID) is None


def test_one_links_quarters_are_never_read_through_another() -> None:
    from django.utils import timezone

    mine = _link("ik@voorbeeld.nl")
    theirs = _link("zij@voorbeeld.nl")
    # Inside the retention window, like every other fixture in this file since
    # 2026-09-13. A date from the profile year would make the second assertion
    # below pass for the wrong reason: no window, rather than a window that
    # belongs to somebody else.
    _reading(theirs, timezone.now().replace(minute=0, second=0, microsecond=0))

    assert build_window(mine, GRID) is None
    assert build_window(theirs, GRID) is not None


def test_a_weekday_match_may_be_backwards_rather_than_forwards() -> None:
    """The nearest day with the same weekday, and nearest means either side.

    Taking the next matching day instead would push a reading up to six days
    later in the year, which in March or October is a real move in both the
    modelled production and the heating demand it is compared against. Two
    dates are asserted rather than one, because a shift that is always forward
    passes any single case that happens to need a forward one.
    """
    forward = grid_position(datetime(2027, 7, 5, 12, 0, tzinfo=UTC), GRID)
    backward = grid_position(datetime(2028, 7, 5, 12, 0, tzinfo=UTC), GRID)

    assert forward is not None and backward is not None
    july = date(GRID.year, 7, 5)
    for position, expected in ((forward, 2), (backward, -3)):
        landed = (grid_epoch(GRID) + timedelta(minutes=15 * position) + timedelta(hours=1)).date()
        assert (landed - july).days == expected


def test_a_reading_whose_shift_would_leave_the_year_is_refused() -> None:
    """31 December 2026 wants to be a Thursday in 2025 and the nearest one is
    1 January 2026, which is not on this grid. Refused rather than clamped to
    the last quarter of the year, where it would be a winter evening reported
    against a different winter evening."""
    assert grid_position(datetime(2026, 12, 31, 12, 0, tzinfo=UTC), GRID) is None


def test_a_reading_from_the_future_is_refused() -> None:
    """A meter with a wrong clock is a meter, not an attacker, and the
    serializer bounds only the quarter boundary and not the date.

    Before the placement changed this could not do harm: a future date was
    outside the profile year and dropped. It maps cleanly now, so it would be
    fitted against and would move the household's figure.
    """
    from django.utils import timezone

    link = _link()
    _reading(link, timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(days=30))

    assert build_window(link, GRID) is None


def test_a_window_that_straddles_new_year_skips_what_cannot_be_placed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ninety days across a new year is the one window that meets both edges.

    It holds dates from two calendar years, which take different shifts, so the
    positions are not in the order the readings were measured and two of them
    could land on one quarter. `MeasuredWindow` raises on both, so without the
    sort and the skip a household whose window happened to straddle New Year
    would meet a 500 rather than an advice. Time is frozen because that
    household exists for about three months a year and a test may not.
    """
    from types import SimpleNamespace

    from django.utils import timezone as django_timezone

    frozen = datetime(2027, 1, 15, 12, 0, tzinfo=UTC)
    # The name `accounts.window.timezone`, and not `...timezone.now`. The
    # module attribute is the shared django.utils.timezone, so patching `.now`
    # through it moves the clock for everything in the process, not for the one
    # function under test. First written that way, and the assertion below
    # caught it.
    monkeypatch.setattr("accounts.window.timezone", SimpleNamespace(now=lambda: frozen))

    link = _link()
    _reading(link, datetime(2026, 12, 31, 12, 0, tzinfo=UTC), consumption=9.9)  # unplaceable
    _reading(link, datetime(2026, 12, 30, 12, 0, tzinfo=UTC), consumption=0.3)
    _reading(link, datetime(2027, 1, 2, 12, 0, tzinfo=UTC), consumption=0.5)
    assert django_timezone.now() != frozen  # the real clock is untouched

    window = build_window(link, GRID)

    assert window is not None
    assert 9.9 not in list(window.offtake_kwh)
    assert list(window.quarter_index) == sorted(window.quarter_index)
    assert len(set(window.quarter_index)) == window.quarter_index.size
