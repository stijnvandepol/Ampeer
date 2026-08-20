"""Turn model uncertainty into a measured band.

A hard-coded plus or minus percentage is forbidden. The honest band is the
whole point of this product, so it has to come out of varying the inputs we
know we do not know.

The variations are combined rather than applied one at a time. Moving a single
assumption while holding the rest at their central value never reaches the
corners, and a band that cannot reach its own corners is decoration. A full
factorial over three levels of four assumptions is 81 runs, which at roughly
six milliseconds each is affordable inside the two second budget.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from ampeer_sim.types import Band

#: The multiplier that leaves an assumption at its central value.
CENTRAL_FACTOR = 1.0


@dataclass(frozen=True)
class Variation:
    """One uncertain input and how far it plausibly moves, as a multiplier."""

    name: str
    low: float
    high: float

    @property
    def levels(self) -> tuple[float, float, float]:
        return (self.low, CENTRAL_FACTOR, self.high)


VARIATIONS: tuple[Variation, ...] = (
    # The annual figure people type in is rarely exact.
    Variation(name="annual_consumption_kwh", low=0.90, high=1.10),
    # The shiftable block is assumed, not measured: 0.5 to 2.0 kWh around 1.0.
    Variation(name="shiftable_block_kwh", low=0.50, high=2.00),
    # System losses depend on shading, cabling and inverter, none of which we see.
    Variation(name="system_loss_fraction", low=0.80, high=1.20),
    # Nobody knows what suppliers will pay for feed-in in 2027.
    Variation(name="feed_in_price", low=0.60, high=1.40),
    # Feed-in charges run from 4.46 to 11.50 cent per kWh across suppliers, a
    # 2.6 times spread and the widest of any input here. Leaving it out made the
    # band silent about the single most uncertain term in the answer.
    Variation(name="feed_in_cost_per_kwh", low=0.59, high=1.53),
)


def variation_grid() -> list[dict[str, float]]:
    """Every combination of low, central and high across all variations."""
    names = [variation.name for variation in VARIATIONS]
    return [
        dict(zip(names, factors, strict=True))
        for factors in itertools.product(*(variation.levels for variation in VARIATIONS))
    ]


def is_central(factors: dict[str, float]) -> bool:
    return all(factor == CENTRAL_FACTOR for factor in factors.values())


def band_from_differences(differences: list[Decimal]) -> Band:
    """Return the p10, p50 and p90 of a set of scenario differences."""
    if not differences:
        raise ValueError("a band needs at least one run")
    values = np.array([float(value) for value in differences])
    p10, p50, p90 = np.percentile(values, [10, 50, 90])
    return Band(
        p10_eur=Decimal(repr(round(float(p10), 2))),
        p50_eur=Decimal(repr(round(float(p50), 2))),
        p90_eur=Decimal(repr(round(float(p90), 2))),
        runs=len(differences),
    )
