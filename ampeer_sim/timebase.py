"""The single definition of the simulation year grid.

Every series entering the core is placed on this grid first. After that,
everything is index against index and no module needs timezone logic.

The grid itself runs in continuous winter time, which is the convention NEDU
uses, so there are exactly ``days * 96`` quarters and no gap or repeat. Local
clock time, which is what human behaviour follows, is derived from it. That is
where the March and October jumps appear.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from functools import cached_property

import numpy as np

QUARTERS_PER_HOUR = 4
QUARTERS_PER_DAY = 96
HOURS_PER_DAY = 24
MINUTES_PER_QUARTER = 15
MINUTES_PER_DAY = 1_440

#: Summer time starts and ends at 02:00 continuous winter time.
DST_SWITCH_QUARTER = 8


def _last_sunday(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    last_date = date(year, month, last_day)
    return date(year, month, last_day - ((last_date.weekday() - 6) % 7))


def _day_of_year(moment: date) -> int:
    return (moment - date(moment.year, 1, 1)).days


@dataclass(frozen=True)
class YearGrid:
    """A quarter-hour grid for one calendar year."""

    year: int
    days: int

    @classmethod
    def for_year(cls, year: int) -> YearGrid:
        return cls(year=year, days=366 if calendar.isleap(year) else 365)

    @property
    def quarters(self) -> int:
        return self.days * QUARTERS_PER_DAY

    @property
    def hours(self) -> int:
        return self.days * HOURS_PER_DAY

    @property
    def is_leap(self) -> bool:
        return self.days == 366

    @cached_property
    def _local_minutes(self) -> np.ndarray:
        """Minutes since the start of 1 January in local clock time."""
        grid_minutes = np.arange(self.quarters, dtype=np.int64) * MINUTES_PER_QUARTER
        summer_start = (
            _day_of_year(_last_sunday(self.year, 3)) * QUARTERS_PER_DAY + DST_SWITCH_QUARTER
        )
        summer_end = (
            _day_of_year(_last_sunday(self.year, 10)) * QUARTERS_PER_DAY + DST_SWITCH_QUARTER
        )
        index = np.arange(self.quarters)
        in_summer = (index >= summer_start) & (index < summer_end)
        return grid_minutes + np.where(in_summer, 60, 0)

    @cached_property
    def local_hour(self) -> np.ndarray:
        """Local clock hour per quarter. Behaviour models use this, not UTC."""
        return ((self._local_minutes // 60) % HOURS_PER_DAY).astype(np.int8)

    def window_mask(self, window: tuple[int, int]) -> np.ndarray:
        """Quarters whose local clock hour falls inside ``window``.

        One implementation, because there were three and they were not the
        same. ``ampeer_sim.profiles.assets`` and ``ampeer_advice.facts`` each
        carried a private copy with the branch below, pointing at each other in
        comments, and ``ampeer_sim.profiles.presence`` carried one without it.

        The branch is what a window like (23, 7) needs: a start later than its
        end runs past midnight and wants the union rather than the
        intersection. Without it such a window selects nothing, and selecting
        nothing is not an error anywhere it was used. In presence.py it would
        have made the shiftable block stay where it was, on every day of the
        year, while every guard in that function reported a day with nowhere to
        put its energy.

        Nothing exercised that on 2026-08-23: the suite is red on the edit that
        would trigger it, because the windows in use all read forwards. This is
        about not resting on that.
        """
        start, end = window
        if start < end:
            inside: np.ndarray = (self.local_hour >= start) & (self.local_hour < end)
            return inside
        wrapped: np.ndarray = (self.local_hour >= start) | (self.local_hour < end)
        return wrapped

    @cached_property
    def weekday(self) -> np.ndarray:
        """Monday is 0, Sunday is 6, in local time."""
        first_weekday = date(self.year, 1, 1).weekday()
        local_day = self._local_minutes // MINUTES_PER_DAY
        return ((first_weekday + local_day) % 7).astype(np.int8)

    @cached_property
    def day_index(self) -> np.ndarray:
        """Zero-based grid day number, one value per quarter.

        This follows the grid rather than the local clock, so every day holds
        exactly 96 quarters and a reshape to (days, 96) is always valid.
        """
        return np.repeat(np.arange(self.days, dtype=np.int16), QUARTERS_PER_DAY)

    def hourly_to_quarters(self, hourly: np.ndarray) -> np.ndarray:
        """Interpolate an hourly series onto the quarter grid.

        The hourly value is treated as the average over its hour, so its
        midpoint sits at quarter position ``hour * 4 + 1.5``. Values outside the
        first and last midpoint are clamped rather than extrapolated.
        """
        if hourly.shape != (self.hours,):
            raise ValueError(f"expected {self.hours} hourly values, got {hourly.shape}")
        hour_midpoints = np.arange(self.hours, dtype=float) * QUARTERS_PER_HOUR + 1.5
        quarter_positions = np.arange(self.quarters, dtype=float)
        interpolated: np.ndarray = np.interp(quarter_positions, hour_midpoints, hourly)
        return interpolated

    def align_hourly_year(self, hourly: np.ndarray, weather_year: int) -> np.ndarray:
        """Align an hourly series from another year onto this grid by calendar date.

        Production is not weekday dependent, so aligning on date rather than on
        weekday is correct and leaves the profile year in charge of the weekday
        structure.

        ``weather_year`` is the caller's claim about where the series came
        from. Until 2026-08-24 it sat in the signature and appeared nowhere in
        the body: leapness was read off the length alone.

        That was not a misalignment, and the first version of this paragraph
        said it was. Measured: a series of 8760 values aligned onto a leap grid
        puts a copy of 28 February on the 29th and every later day lands on its
        own date. The dates were right.

        What passed silently is the disagreement itself. A provider that
        returns 8760 values for a leap year is a day of weather short, and the
        model then runs a February day twice without anybody being told. That
        is a fact about the data rather than about this function, which is
        exactly the kind this package cannot report later, so the claim is
        checked here instead of trusted.
        """
        expected = 8_784 if calendar.isleap(weather_year) else 8_760
        if hourly.shape[0] != expected:
            raise ValueError(
                f"weather year {weather_year} has {expected} hourly values and this "
                f"series carries {hourly.shape[0]}"
            )
        source_is_leap = calendar.isleap(weather_year)
        if source_is_leap == self.is_leap:
            return hourly.astype(float, copy=False)

        feb_29_start = (31 + 28) * HOURS_PER_DAY
        if source_is_leap:
            return np.delete(hourly, np.arange(feb_29_start, feb_29_start + HOURS_PER_DAY))

        feb_28_start = (31 + 27) * HOURS_PER_DAY
        duplicated = hourly[feb_28_start : feb_28_start + HOURS_PER_DAY]
        return np.insert(hourly, feb_29_start, duplicated)
