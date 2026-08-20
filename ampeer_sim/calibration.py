"""Hold a modelled export profile against the measured national one.

Every other test in this package asks whether the code does what the design
says. This asks whether the design resembles the Netherlands, using the one
piece of measured Dutch data available without a single user: ``E1A_AMI_I``, the
NEDU feed-in profile of connections that actually export.

It is a shape comparison and not an accuracy claim. The measured series averages
every orientation, every array size and every household in the country; a model
run describes one house. What should agree is the season and the time of day the
electricity leaves the meter. Where they disagree, the disagreement is the
finding, not the failure.

Only shares are compared, never volumes. The two totals have no reason to agree.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass

import numpy as np

from ampeer_sim.timebase import HOURS_PER_DAY, QUARTERS_PER_DAY, YearGrid


@dataclass(frozen=True)
class ShareGap:
    """One bucket where the model and the measurement disagree."""

    label: str
    modelled: float
    measured: float

    @property
    def gap(self) -> float:
        """Positive means the model puts more of its export here than reality."""
        return self.modelled - self.measured


@dataclass(frozen=True)
class ProfileComparison:
    """How a modelled export profile lines up with the measured one."""

    monthly: tuple[ShareGap, ...]
    hourly: tuple[ShareGap, ...]

    @property
    def largest_monthly_gap(self) -> ShareGap:
        return max(self.monthly, key=lambda bucket: abs(bucket.gap))

    @property
    def largest_hourly_gap(self) -> ShareGap:
        return max(self.hourly, key=lambda bucket: abs(bucket.gap))

    @property
    def worst_gap(self) -> float:
        """The largest absolute disagreement in any bucket."""
        return max(abs(bucket.gap) for bucket in self.monthly + self.hourly)


def _normalise(series: np.ndarray) -> np.ndarray:
    total = float(series.sum())
    if total <= 0.0:
        raise ValueError("cannot compare the shape of a series that exports nothing")
    return series / total


def monthly_share(series: np.ndarray, grid: YearGrid) -> tuple[float, ...]:
    """The fraction of the annual total that falls in each calendar month."""
    normalised = _normalise(series)
    shares = []
    start = 0
    for month in range(1, 13):
        days = calendar.monthrange(grid.year, month)[1]
        stop = start + days * QUARTERS_PER_DAY
        shares.append(float(normalised[start:stop].sum()))
        start = stop
    return tuple(shares)


def hourly_share(series: np.ndarray, grid: YearGrid) -> tuple[float, ...]:
    """The fraction of the annual total that falls in each hour of the local day."""
    normalised = _normalise(series)
    return tuple(float(normalised[grid.local_hour == hour].sum()) for hour in range(HOURS_PER_DAY))


def compare_export_profile(
    modelled: np.ndarray,
    grid: YearGrid,
    measured_monthly: tuple[float, ...],
    measured_hourly: tuple[float, ...],
) -> ProfileComparison:
    """Compare a modelled export series against measured national shares.

    No correlation coefficient is reported. Over twelve monthly shares two
    seasonal curves correlate at almost any level of disagreement, so the number
    would look like evidence while carrying none. The gap per bucket is what
    says something, and it says it in percentage points a reader can check.
    """
    modelled_monthly = monthly_share(modelled, grid)
    modelled_hourly = hourly_share(modelled, grid)
    return ProfileComparison(
        monthly=tuple(
            ShareGap(label=f"month {index + 1}", modelled=model, measured=real)
            for index, (model, real) in enumerate(
                zip(modelled_monthly, measured_monthly, strict=True)
            )
        ),
        hourly=tuple(
            ShareGap(label=f"{hour:02d}:00", modelled=model, measured=real)
            for hour, (model, real) in enumerate(zip(modelled_hourly, measured_hourly, strict=True))
        ),
    )
