"""Read and scale NEDU standard consumption profiles.

Verified against the real 2025 file on 2026-08-20: six header rows plus a
column caption row, semicolon separated, decimal point, 35040 data rows for a
non-leap year.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import ProfileCategory

HEADER_ROWS = 7
FIRST_DATA_COLUMN = 3
NAME_ROW = 0
YEAR_ROW = 1

#: Only E1A and E2A carry a single register. The rest hold two, each summing to 1.
SINGLE_REGISTER = frozenset({ProfileCategory.E1A})

#: Measured spread on the real files is about 6e-7, so 1e-9 would be far too strict.
SUM_TOLERANCE = 1e-6

#: The base consumption shape always comes from connections without feed-in.
BASE_SERIES_SUFFIX = "AZI_A"


class ProfileValidationError(ValueError):
    """The profile file or series did not match what the format guarantees."""


def expected_sum(category: ProfileCategory) -> float:
    """The nominal annual sum of the fractions for one category."""
    return 1.0 if category in SINGLE_REGISTER else 2.0


def validate_fractions(fractions: np.ndarray, category: ProfileCategory, grid: YearGrid) -> None:
    """Check length and total. Raises ``ProfileValidationError`` on a mismatch."""
    if fractions.shape != (grid.quarters,):
        raise ProfileValidationError(
            f"expected {grid.quarters} values for {grid.year}, got {fractions.shape[0]}"
        )
    nominal = expected_sum(category)
    total = float(fractions.sum())
    # A leap year adds one day of fractions on top of the nominal sum.
    upper = nominal * (366 / 365) if grid.is_leap else nominal
    if not nominal - SUM_TOLERANCE <= total <= upper + SUM_TOLERANCE:
        raise ProfileValidationError(
            f"{category.value} fraction sum {total!r} outside "
            f"[{nominal - SUM_TOLERANCE}, {upper + SUM_TOLERANCE}]"
        )


def scale_to_annual(
    fractions: np.ndarray, annual_kwh: float, category: ProfileCategory
) -> np.ndarray:
    """Scale a fraction series so it totals exactly ``annual_kwh``.

    Dividing by the observed sum rather than the nominal one makes this correct
    for single and dual register profiles and for leap years alike.
    """
    total = float(fractions.sum())
    if total <= 0.0:
        raise ProfileValidationError(f"{category.value} fractions sum to {total!r}")
    return fractions * (annual_kwh / total)


class NeduFileProvider:
    """A ``ProfileProvider`` backed by an ingested NEDU CSV."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        with self._path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, delimiter=";"))
        column = self._locate_column(rows, year, category)
        values = [float(row[column]) for row in rows[HEADER_ROWS:] if row[column].strip()]
        return np.array(values, dtype=float)

    def _locate_column(self, rows: list[list[str]], year: int, category: ProfileCategory) -> int:
        wanted = f"{category.value}_{BASE_SERIES_SUFFIX}"
        for index, name in enumerate(rows[NAME_ROW]):
            if index < FIRST_DATA_COLUMN or not name.endswith(wanted):
                continue
            if rows[YEAR_ROW][index].strip() != str(year):
                continue
            return index
        raise ProfileValidationError(f"{self._path.name} holds no {wanted} series for {year}")
