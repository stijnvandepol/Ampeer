"""The cache and the two provider choices.

The cache is the reason a visitor never waits for PVGIS. What it must never do
is answer with a series computed for a different roof, which is why the key is
integers and the test below asks for the same roof twice by two routes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from django.test import override_settings

from advice.models import ProductionCache
from advice.production import (
    POSTCODE_AREA_LENGTH,
    CachedProductionProvider,
    decode_series,
    encode_series,
    production_provider,
)
from advice.profiles import profile_provider
from ampeer_sim.production.pvgis import FallbackProvider, postcode4_to_latlon
from ampeer_sim.profiles.nedu import NeduFileProvider
from ampeer_sim.types import ProductionSource

pytestmark = pytest.mark.django_db

WEATHER_YEAR = 2023


class CountingProvider:
    """A production provider that records how often it was actually asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float]] = []

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        self.calls.append((postcode4, azimuth_deg, tilt_deg))
        production = np.linspace(0.0, 900.0, 8760, dtype=np.float64)
        temperature = np.linspace(-5.0, 30.0, 8760, dtype=np.float64)
        return production, temperature, ProductionSource.PVGIS


def test_a_series_survives_the_round_trip_within_float32_precision() -> None:
    """Stored as float32 on purpose. PVGIS reports irradiance to about three
    significant digits; float32 carries seven. Keeping float64 would double the
    row for precision the source does not have."""
    original = np.linspace(0.0, 900.0, 8760, dtype=np.float64)
    restored = decode_series(encode_series(original))
    assert restored.shape == original.shape
    assert np.allclose(restored, original, rtol=1e-6, atol=1e-3)


def test_the_first_request_asks_the_inner_provider() -> None:
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    production, temperature, source = provider.hourly_series("5401", 0.0, 35.0)
    assert len(inner.calls) == 1
    assert source is ProductionSource.PVGIS
    assert production.shape == (8760,)
    assert temperature.shape == (8760,)


def test_a_second_identical_request_does_not_ask_again() -> None:
    """The definition of done says this in so many words, and a cache that is
    never observed missing is a cache nobody has seen work."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    first = provider.hourly_series("5401", 0.0, 35.0)
    second = provider.hourly_series("5401", 0.0, 35.0)
    assert len(inner.calls) == 1, f"the inner provider was asked {len(inner.calls)} times"
    assert np.allclose(first[0], second[0])
    assert first[2] is second[2]


def test_a_different_roof_is_a_different_entry() -> None:
    """Three genuinely different keys: one orientation apart and one postcode
    century apart. 5401 and 5402 would not do it any more, and that is the
    point of the test below."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    provider.hourly_series("5401", 90.0, 35.0)
    provider.hourly_series("6501", 0.0, 35.0)
    assert len(inner.calls) == 3
    assert ProductionCache.objects.count() == 3


def test_two_postcodes_in_one_century_share_a_single_entry() -> None:
    """5401 and 5402 resolve to one centroid, so PVGIS answers them with the
    same series. Keyed on four digits the cache stored that series twice, once
    per neighbourhood and forever, and paid for a second external call to learn
    what it already had."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    provider.hourly_series("5402", 0.0, 35.0)
    provider.hourly_series("5499", 0.0, 35.0)
    assert len(inner.calls) == 1, f"the inner provider was asked {len(inner.calls)} times"
    assert ProductionCache.objects.count() == 1
    assert ProductionCache.objects.get().postcode_area == "54"


def test_the_cache_key_is_exactly_as_coarse_as_the_data_behind_it() -> None:
    """The reason the key is two digits, checked rather than assumed.

    `postcode4_to_latlon` slices `postcode4[:2]` today. If a later version ever
    resolves finer, a cache still keyed on two digits would hand a household a
    series computed for a different place, silently and with no error anywhere,
    which is the failure mode this project exists to not have. This test goes
    red at that moment instead.
    """
    area = "54"
    postcodes = [f"{area}01", f"{area}02", f"{area}99"]
    assert len({postcode4_to_latlon(postcode) for postcode in postcodes}) == 1
    series = [FallbackProvider(WEATHER_YEAR).hourly_series(p, 0.0, 35.0) for p in postcodes]
    for other in series[1:]:
        assert np.array_equal(series[0][0], other[0])
        assert np.array_equal(series[0][1], other[1])
    assert len({p[:POSTCODE_AREA_LENGTH] for p in postcodes}) == 1


def test_two_spellings_of_the_same_roof_hit_the_same_entry() -> None:
    """35.0 and 35 are the same roof. A float somewhere in the key would make
    them two, and the second one would pay for a network call that already
    happened."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    provider.hourly_series("5401", 0, 35)
    assert len(inner.calls) == 1
    assert ProductionCache.objects.count() == 1


def test_a_roof_angle_that_was_not_rounded_upstream_still_hits_one_entry() -> None:
    """The serializer rounds, but the cache has to be correct when it is called
    from somewhere that did not. 35.000000001 degrees is not a second roof, and
    a float key would miss its own entry on it."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    provider.hourly_series("5401", 0.0, 35.000000001)
    provider.hourly_series("5401", -0.4, 34.6)
    assert len(inner.calls) == 1
    assert ProductionCache.objects.count() == 1


def test_the_inner_provider_is_asked_for_the_rounded_roof() -> None:
    """Otherwise the stored series describes 34.6 degrees while every later
    reader of that row believes it describes 35."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", -0.4, 34.6)
    assert inner.calls == [("5401", 0.0, 35.0)]


def test_a_cached_entry_remembers_where_the_data_came_from() -> None:
    """The response reports production_source. A cache that forgot it would
    report PVGIS for a series the offline table produced, which is a confidence
    claim the data does not support."""
    inner = CountingProvider()
    provider = CachedProductionProvider(inner, weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    _, _, source = provider.hourly_series("5401", 0.0, 35.0)
    assert source is ProductionSource.PVGIS
    assert ProductionCache.objects.get().source == "PVGIS"


def test_a_fallback_answer_is_cached_as_a_fallback_answer() -> None:
    class FallbackOnly(CountingProvider):
        def hourly_series(
            self, postcode4: str, azimuth_deg: float, tilt_deg: float
        ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
            production, temperature, _ = super().hourly_series(postcode4, azimuth_deg, tilt_deg)
            return production, temperature, ProductionSource.FALLBACK

    provider = CachedProductionProvider(FallbackOnly(), weather_year=WEATHER_YEAR)
    provider.hourly_series("5401", 0.0, 35.0)
    _, _, source = provider.hourly_series("5401", 0.0, 35.0)
    assert source is ProductionSource.FALLBACK
    assert ProductionCache.objects.get().source == "FALLBACK"


def test_a_different_weather_year_is_a_different_entry() -> None:
    inner = CountingProvider()
    CachedProductionProvider(inner, weather_year=2022).hourly_series("5401", 0.0, 35.0)
    CachedProductionProvider(inner, weather_year=2023).hourly_series("5401", 0.0, 35.0)
    assert len(inner.calls) == 2


def test_the_composed_provider_puts_the_cache_in_front() -> None:
    """Building it must not touch the network, so this is safe to assert here
    and it is the only place the wiring itself is exercised."""
    assert isinstance(production_provider(WEATHER_YEAR), CachedProductionProvider)


@override_settings(AMPEER_NEDU_PROFILE_PATH=None)
def test_without_a_profile_file_the_service_refuses_to_answer() -> None:
    """There is no fallback consumption shape and there must not be one. A
    profile nobody measured would be an invented number sitting at the centre
    of every answer, and it would produce a confident wrong result rather than
    an error."""
    with pytest.raises(RuntimeError, match="AMPEER_NEDU_PROFILE_PATH"):
        profile_provider()


@override_settings(AMPEER_NEDU_PROFILE_PATH="/does/not/exist.csv")
def test_a_profile_path_that_points_at_nothing_is_reported_as_such() -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        profile_provider()


def test_a_configured_profile_file_is_accepted(tmp_path: Path) -> None:
    """The two refusals above are only meaningful if the accepting path works."""
    profile_file = tmp_path / "nedu-profiles-2025.csv"
    profile_file.write_text("", encoding="utf-8")
    with override_settings(AMPEER_NEDU_PROFILE_PATH=str(profile_file)):
        provider = profile_provider()
    assert isinstance(provider, NeduFileProvider)
