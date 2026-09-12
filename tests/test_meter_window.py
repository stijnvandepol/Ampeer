"""The seam between stored quarters and the pure fit.

The case that matters most here is the clock. Readings are stored in UTC and
the grid runs in continuous winter time, which has no gap in March and no
repeated hour in October. An off-by-one-hour here would not raise anything: it
would quietly compare a household's evening against the model's afternoon, and
the fitted figure would come back wrong with every test still green.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from helpers.accounts import TEST_PASSWORD

from accounts.models import MeterLink, QuarterReading, User
from accounts.window import build_window, grid_epoch, quarter_index
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


def test_a_window_carries_the_quarters_it_was_given() -> None:
    link = _link()
    start = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    for step in range(4):
        _reading(link, start + timedelta(minutes=15 * step), consumption=0.1 * (step + 1))

    window = build_window(link, GRID)

    assert window is not None
    assert list(window.quarter_index) == [4, 5, 6, 7]
    assert list(window.offtake_kwh) == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_a_reading_from_another_year_is_dropped_and_not_clamped() -> None:
    """A device may backfill. A quarter of 2024 has no position in 2025."""
    link = _link()
    _reading(link, datetime(2024, 6, 1, 12, 0, tzinfo=UTC))
    _reading(link, datetime(2025, 6, 1, 12, 0, tzinfo=UTC))

    window = build_window(link, GRID)

    assert window is not None
    assert window.quarter_index.size == 1


def test_a_link_with_nothing_stored_yields_no_window() -> None:
    assert build_window(_link(), GRID) is None


def test_one_links_quarters_are_never_read_through_another() -> None:
    mine = _link("ik@voorbeeld.nl")
    theirs = _link("zij@voorbeeld.nl")
    _reading(theirs, datetime(2025, 6, 1, 12, 0, tzinfo=UTC))

    assert build_window(mine, GRID) is None
    assert build_window(theirs, GRID) is not None
