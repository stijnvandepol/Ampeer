"""The PVGIS cache.

One entry is two hourly series for one roof in one weather year. Those
combinations repeat enormously: a four digit postcode area holds thousands of
houses and most roofs sit on a handful of orientations.

It lives in Postgres rather than Redis for two reasons. It has to survive a
restart, or the first visitor after every deploy pays for an external call. And
it keeps Redis out of the request path entirely, which is one fewer thing that
can be down at the moment somebody is on the site.
"""

from __future__ import annotations

import io
import zlib

import numpy as np

from advice.models import ProductionCache
from ampeer_sim.production.pvgis import FallbackProvider, PvgisProvider, ResilientProductionProvider
from ampeer_sim.providers import ProductionProvider
from ampeer_sim.types import ProductionSource


# Measured on 2026-08-21: one 8760 value series encodes to 30312 bytes, so a
# cache row holding a production and a temperature series costs roughly 60 kB.
# The series measured was a smooth ramp; a real PVGIS year is mostly zeros at
# night and compresses better, so this is an upper bound rather than a typical
# figure.
def encode_series(values: np.ndarray) -> bytes:
    """Compress an hourly series for storage.

    float32, not float64. PVGIS reports irradiance to roughly three significant
    digits and float32 carries seven, so the second half of a float64 is
    precision the source never had. Halving the row is the whole benefit and
    nothing measurable is lost.
    """
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(values, dtype=np.float32), allow_pickle=False)
    return zlib.compress(buffer.getvalue(), level=6)


def decode_series(blob: bytes) -> np.ndarray:
    """Restore a series as float64, which is what the engine works in."""
    buffer = io.BytesIO(zlib.decompress(bytes(blob)))
    restored: np.ndarray = np.load(buffer, allow_pickle=False)
    return restored.astype(np.float64)


class CachedProductionProvider:
    """A production provider that asks the one behind it at most once per roof."""

    def __init__(self, inner: ProductionProvider, weather_year: int) -> None:
        self._inner = inner
        self._weather_year = weather_year

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        # Whole degrees, so 35.0 and 35 are one roof rather than two. The
        # serializer already rounds; this makes the cache correct even when it
        # is called from somewhere that did not.
        azimuth = round(azimuth_deg)
        tilt = round(tilt_deg)
        cached = ProductionCache.objects.filter(
            postcode4=postcode4,
            azimuth_deg=azimuth,
            tilt_deg=tilt,
            weather_year=self._weather_year,
        ).first()
        if cached is not None:
            return (
                # bytes(...) because a BinaryField hands back a memoryview
                # on some backends and bytes on others.
                decode_series(bytes(cached.production_w_per_kwp)),
                decode_series(bytes(cached.temperature_c)),
                # The stored name, not a constant. A cache that assumed PVGIS
                # would claim it for a series the offline table produced, which
                # is a confidence claim the data does not support.
                ProductionSource[cached.source],
            )

        production, temperature, source = self._inner.hourly_series(
            postcode4, float(azimuth), float(tilt)
        )
        # get_or_create rather than create: two requests for the same new roof
        # can arrive together, and losing that race must cost a wasted call,
        # never a 500.
        ProductionCache.objects.get_or_create(
            postcode4=postcode4,
            azimuth_deg=azimuth,
            tilt_deg=tilt,
            weather_year=self._weather_year,
            defaults={
                "production_w_per_kwp": encode_series(production),
                "temperature_c": encode_series(temperature),
                "source": source.name,
            },
        )
        return production, temperature, source


def production_provider(weather_year: int) -> ProductionProvider:
    """The provider the service uses: cache in front, PVGIS behind, offline
    table behind that. A visitor never waits for an external service and an
    advice never fails because one is slow."""
    return CachedProductionProvider(
        ResilientProductionProvider(PvgisProvider(weather_year), FallbackProvider(weather_year)),
        weather_year=weather_year,
    )
