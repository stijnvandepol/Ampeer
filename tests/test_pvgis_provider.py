from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import requests

from ampeer_sim.production.pvgis import (
    FallbackProvider,
    PvgisProvider,
    ResilientProductionProvider,
    postcode4_to_latlon,
)
from ampeer_sim.types import ProductionSource


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None

    def get(self, url: str, params: dict[str, Any], timeout: float) -> _FakeResponse:
        self.last_url = url
        self.last_params = params
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return _FakeResponse(self.payload)


def _payload(hours: int = 8_760) -> dict[str, Any]:
    return {
        "outputs": {
            "hourly": [
                {"time": "20230101:0010", "P": 120.0, "G(i)": 100.0, "T2m": 5.0}
                for _ in range(hours)
            ]
        }
    }


def _provider(session: _FakeSession) -> PvgisProvider:
    return PvgisProvider(weather_year=2023, session=session)  # type: ignore[arg-type]


def test_provider_returns_production_and_temperature() -> None:
    session = _FakeSession(payload=_payload())
    production, temperature, source = _provider(session).hourly_series("5401", 0.0, 35.0)
    assert production.shape == (8_760,)
    assert temperature.shape == (8_760,)
    assert production[0] == pytest.approx(120.0)
    assert source is ProductionSource.PVGIS


def test_provider_never_puts_user_input_in_the_url() -> None:
    session = _FakeSession(payload=_payload())
    _provider(session).hourly_series("5401", 0.0, 35.0)
    assert session.last_url == "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
    assert session.last_params is not None
    assert isinstance(session.last_params["lat"], float)


def test_provider_asks_pvgis_to_do_the_photovoltaic_physics() -> None:
    session = _FakeSession(payload=_payload())
    _provider(session).hourly_series("5401", 0.0, 35.0)
    assert session.last_params is not None
    assert session.last_params["pvcalculation"] == 1
    # One kWp and no losses, so scaling and sensitivity need no further calls.
    assert session.last_params["peakpower"] == pytest.approx(1.0)
    assert session.last_params["loss"] == pytest.approx(0.0)


def test_fallback_provider_returns_a_full_year_without_network() -> None:
    production, temperature, source = FallbackProvider(2023).hourly_series("5401", 0.0, 35.0)
    assert production.shape == (8_760,)
    assert temperature.shape == (8_760,)
    assert source is ProductionSource.FALLBACK
    assert production.sum() > 0.0


def test_fallback_provider_lands_near_the_real_dutch_annual_yield() -> None:
    production, _, _ = FallbackProvider(2023).hourly_series("5401", 0.0, 35.0)
    annual_kwh_per_kwp = production.sum() / 1_000.0
    assert 1_100.0 < annual_kwh_per_kwp < 1_400.0


def test_fallback_provider_handles_a_leap_year() -> None:
    production, _, _ = FallbackProvider(2024).hourly_series("5401", 0.0, 35.0)
    assert production.shape == (8_784,)


def test_a_north_facing_roof_yields_less_than_a_south_facing_one() -> None:
    south, _, _ = FallbackProvider(2023).hourly_series("5401", 0.0, 35.0)
    north, _, _ = FallbackProvider(2023).hourly_series("5401", 180.0, 35.0)
    assert north.sum() < south.sum()


def test_resilient_provider_falls_back_on_timeout() -> None:
    session = _FakeSession(error=requests.Timeout("too slow"))
    provider = ResilientProductionProvider(
        primary=_provider(session), fallback=FallbackProvider(2023)
    )
    _, _, source = provider.hourly_series("5401", 0.0, 35.0)
    assert source is ProductionSource.FALLBACK


def test_resilient_provider_falls_back_on_rate_limit() -> None:
    session = _FakeSession(error=requests.HTTPError("429 Too Many Requests"))
    provider = ResilientProductionProvider(
        primary=_provider(session), fallback=FallbackProvider(2023)
    )
    _, _, source = provider.hourly_series("5401", 0.0, 35.0)
    assert source is ProductionSource.FALLBACK


def test_resilient_provider_does_not_swallow_a_programming_error() -> None:
    class Broken:
        def hourly_series(
            self, postcode4: str, azimuth_deg: float, tilt_deg: float
        ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
            raise TypeError("wrong argument")

    provider = ResilientProductionProvider(primary=Broken(), fallback=FallbackProvider(2023))
    with pytest.raises(TypeError):
        provider.hourly_series("5401", 0.0, 35.0)


def test_postcode_lookup_returns_a_dutch_coordinate() -> None:
    lat, lon = postcode4_to_latlon("5401")
    assert 50.7 <= lat <= 53.6
    assert 3.3 <= lon <= 7.3


def test_postcode_lookup_rejects_a_non_numeric_postcode() -> None:
    with pytest.raises(ValueError, match="four digits"):
        postcode4_to_latlon("54AB")


def test_every_postcode_century_maps_to_a_dutch_coordinate() -> None:
    for century in range(10, 100):
        lat, lon = postcode4_to_latlon(f"{century}00")
        assert 50.7 <= lat <= 53.6, century
        assert 3.3 <= lon <= 7.3, century
