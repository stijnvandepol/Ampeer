"""Turn one link's stored quarters into a window the simulation can read.

This is the seam between a table and a pure package. Everything above it is
Django and rows; everything below it is ``ampeer_sim.fit``, which must not know
either exists.

Only ``QuarterReading`` is read. ``HourAggregate`` survives forever and
``QuarterReading`` does not, so the hourly table is the larger history and the
tempting one. It is left out on purpose. It carries a quarter of the
resolution, it covers only what is already more than ninety days old, and
feeding it in would put the oldest and coarsest part of a household's year in
charge of a figure whose whole defence is that the weeks it rests on can be
withheld one at a time and the answer not move. Using it is a decision with its
own evidence, not a detail of this one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
from django.utils import timezone

from accounts.models import RETENTION, MeterLink, QuarterReading
from ampeer_sim.fit import MeasuredWindow
from ampeer_sim.timebase import MINUTES_PER_QUARTER, YearGrid

#: The grid's first quarter in UTC. ``YearGrid`` runs in continuous winter
#: time, which is UTC+1 all year with no gap in March and no repeated hour in
#: October, so the grid's 1 January 00:00 is the previous 31 December 23:00
#: UTC. Writing the offset once here is what keeps the conversion from being
#: rediscovered, differently, at the next call site.
WINTER_TIME_OFFSET = timedelta(hours=1)


def grid_epoch(grid: YearGrid) -> datetime:
    """The UTC instant that quarter zero of this grid begins."""
    return datetime(grid.year, 1, 1, tzinfo=UTC) - WINTER_TIME_OFFSET


def quarter_index(measured_at: datetime, grid: YearGrid) -> int:
    """Which quarter of the grid a measurement falls in.

    Positional and exact. A measurement is stored on a quarter boundary, the
    serializer refuses anything else, so this never rounds a reading into a
    neighbour it did not belong to.
    """
    elapsed = measured_at.astimezone(UTC) - grid_epoch(grid)
    return int(elapsed // timedelta(minutes=MINUTES_PER_QUARTER))


def grid_position(measured_at: datetime, grid: YearGrid) -> int | None:
    """Where a real measurement sits on the fixed profile year, or nothing.

    THIS FUNCTION EXISTS BECAUSE THE OBVIOUS ONE CANNOT WORK. ``quarter_index``
    above measures from the grid's own first quarter, which is the right answer
    to "which quarter of 2025 is this" and the wrong one to ask of a reading
    that arrived this week. ``settings.AMPEER_PROFILE_YEAR`` is 2025 and stays
    2025, because the NEDU profile and the golden answers are that year;
    ``RETENTION`` in the purge command is ninety days, so no quarter from 2025
    can still be in the table. Measured on 2026-09-13: a reading taken that day
    lands at index 59608 in a grid of 35040, and the oldest reading retention
    allows lands at 50968. Both outside. Every reading a household could
    possibly have pushed was dropped, ``build_window`` returned ``None``, and
    the calibration proposed nothing, in silence, forever.

    So a measurement is placed by WHAT TIME OF YEAR IT IS rather than by how
    long after the grid's epoch it happened: the same date and the same clock
    time in the grid's year, then moved to the nearest day with the same
    weekday, because the NEDU profile a household is compared against differs
    between a Wednesday and a Sunday and a two day error there is a real one.

    That shift is the same whole number of days for every reading in a year, so
    the window is translated rather than distorted: the gaps inside it, the
    order of it and the distance between any two readings all survive intact.
    What it does assume is that this household's July resembles the model's
    July, which is the seasonal assumption the whole route already rests on and
    which decision 63 answers with the band rather than with a disclaimer: pull
    a week out, refit, and if the answer moves the band is wide and nothing is
    proposed.

    Returns ``None`` for the two dates that have nowhere to go: 29 February
    onto a common year, and a reading whose weekday shift would carry it out of
    the grid's year altogether. At most three days a year, and dropping them
    costs a window nothing it can notice.
    """
    # A naive wall clock in continuous winter time, which is what the grid
    # counts in. Adding the offset to a UTC instant rather than converting to
    # Europe/Amsterdam on purpose: that zone has a gap in March and a repeated
    # hour in October, and the grid has neither.
    winter = measured_at.astimezone(UTC) + WINTER_TIME_OFFSET
    try:
        same_date = winter.replace(year=grid.year)
    except ValueError:
        return None  # 29 February, and the grid's year is not a leap year
    shift = (winter.weekday() - same_date.weekday()) % 7
    if shift > 3:
        shift -= 7  # nearest matching weekday, not the next one
    target = same_date + timedelta(days=shift)
    if target.year != grid.year:
        return None  # the shift carried it over a new year
    position = quarter_index(target - WINTER_TIME_OFFSET, grid)
    return position if 0 <= position < grid.quarters else None


def build_window(link: MeterLink, grid: YearGrid) -> MeasuredWindow | None:
    """Read one link's quarters into a window, or nothing if it has none.

    The caller resolves ``link`` from ``request.user``; this function filters on
    the link it is handed and never on a primary key alone, so a link that is
    not the requester's cannot be read through it.

    Sorted by the position on the grid and not by the instant it was measured.
    Those agree for every window that stays inside one calendar year, and they
    do not for one that spans a new year: December and January are seasonally
    next to each other and sit at opposite ends of the grid. ``MeasuredWindow``
    requires a strictly increasing index and raises otherwise, so without the
    sort a household whose ninety days happened to straddle New Year would meet
    a 500 instead of an advice. A duplicate position cannot arise while
    retention is ninety days, and is dropped rather than raised on, because
    finding out through a stack trace is not a way to learn it.
    """
    # Bounded by the table's own retention and not only by the purge having
    # run. Nothing in the ingest serializer says how old a reading may be, so a
    # device is free to push a timestamp from 2022; until the nightly fold
    # removes it, that row is live. Before 2026-09-13 the year check dropped
    # such a reading as a side effect of being wrong about everything else, and
    # the mapping above deliberately places a reading from any year. This is
    # that protection put back as what it actually is: the window is the ninety
    # days the table is allowed to hold, and a row older than that has no claim
    # on a figure about now.
    #
    # Bounded at the top as well, for the same reason read the other way. The
    # serializer does not refuse a timestamp in the future either, so a meter
    # whose clock is wrong by a year pushes readings that are placed on the grid
    # perfectly happily and move the household's fitted figure. Before the
    # placement changed this could not happen, since a future date fell outside
    # the profile year and was dropped; it can now, so it is refused here.
    now = timezone.now()
    rows = QuarterReading.objects.filter(
        link=link, measured_at__gte=now - RETENTION, measured_at__lte=now
    ).order_by("measured_at")
    placed: dict[int, tuple[float, float]] = {}
    for measured_at, consumption_kwh, feed_in_kwh in rows.values_list(
        "measured_at", "consumption_kwh", "feed_in_kwh"
    ):
        position = grid_position(measured_at, grid)
        if position is None or position in placed:
            continue
        placed[position] = (consumption_kwh, feed_in_kwh)

    if not placed:
        return None
    order = sorted(placed)
    return MeasuredWindow(
        quarter_index=np.array(order, dtype=np.int64),
        offtake_kwh=np.array([placed[position][0] for position in order], dtype=float),
        feed_in_kwh=np.array([placed[position][1] for position in order], dtype=float),
    )
