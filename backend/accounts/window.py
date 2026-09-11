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

from accounts.models import MeterLink, QuarterReading
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


def build_window(link: MeterLink, grid: YearGrid) -> MeasuredWindow | None:
    """Read one link's quarters into a window, or nothing if it has none.

    The caller resolves ``link`` from ``request.user``; this function filters on
    the link it is handed and never on a primary key alone, so a link that is
    not the requester's cannot be read through it.

    Readings outside the grid's year are dropped rather than clamped. A device
    is free to backfill, and a quarter from a different year has no position
    here at all.
    """
    rows = QuarterReading.objects.filter(link=link).order_by("measured_at")
    index: list[int] = []
    offtake: list[float] = []
    feed_in: list[float] = []
    for measured_at, consumption_kwh, feed_in_kwh in rows.values_list(
        "measured_at", "consumption_kwh", "feed_in_kwh"
    ):
        position = quarter_index(measured_at, grid)
        if not 0 <= position < grid.quarters:
            continue
        index.append(position)
        offtake.append(consumption_kwh)
        feed_in.append(feed_in_kwh)

    if not index:
        return None
    return MeasuredWindow(
        quarter_index=np.array(index, dtype=np.int64),
        offtake_kwh=np.array(offtake, dtype=float),
        feed_in_kwh=np.array(feed_in, dtype=float),
    )
