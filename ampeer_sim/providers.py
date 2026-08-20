"""Protocols for every source of external data.

The simulation core performs no I/O. Implementations of these protocols are
the only place where the network or the filesystem is touched.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ampeer_sim.types import ProductionSource, ProfileCategory


@runtime_checkable
class ProfileProvider(Protocol):
    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        """Return the quarter-hour fraction series for one profile category.

        The array holds 35040 values, or 35136 in a leap year.
        """


@runtime_checkable
class ProductionProvider(Protocol):
    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        """Return (irradiance_w_m2, temperature_c, source) at hourly resolution."""


@runtime_checkable
class PriceProvider(Protocol):
    def hourly_day_ahead(self, year: int) -> np.ndarray:
        """Return day-ahead prices in euro per kWh, one value per hour."""
