from __future__ import annotations

import re
from pathlib import Path
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


# ---------------------------------------------------------------------------
# A compass direction is a direction, however it is spelled
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOF_PICKER = REPO_ROOT / "frontend" / "src" / "components" / "form" / "RoofPicker.tsx"

#: One entry of COMPASS_AZIMUTH_DEG, the single place the form turns a direction
#: a visitor recognises into a number the API accepts.
_COMPASS_ENTRY = re.compile(r"^\s*([A-Z]+):\s*(-?\d+),\s*$", re.MULTILINE)


def _compass_azimuths() -> dict[str, int]:
    """The eight azimuths the form can send, read from the file that sends them.

    Derived rather than copied. A test that repeated the eight numbers would
    keep passing after somebody respelled north as -180 in the component, which
    is the exact change the comment there warns against and the exact input the
    bug below mishandled.
    """
    source = ROOF_PICKER.read_text(encoding="utf-8")
    block = source.split("COMPASS_AZIMUTH_DEG = {")[1].split("}")[0]
    return {name: int(value) for name, value in _COMPASS_ENTRY.findall(block)}


def test_the_two_spellings_of_north_produce_one_year() -> None:
    """180 and -180 name the same roof and returned different years.

    Both sit inside the range the API declares legal, MIN_AZIMUTH_DEG is -180
    and MAX_AZIMUTH_DEG is 180, so this was reachable by anything posting to a
    public endpoint. The azimuth term of the nearest-entry search was a plain
    subtraction, which put the table's north entry 355 degrees from a roof at
    -175 and let the east entry win instead.

    Measured on 2026-08-23 over every integer azimuth and tilt the API accepts:
    the band from -180 to -136, north through north-north-east, took 0.85 where
    north is 0.62. A yield overstated by 37 percent, and an overstated yield
    overstates both the export a household loses in 2027 and what a battery is
    worth to them.
    """
    provider = FallbackProvider(2023)
    written_positive, _, _ = provider.hourly_series("5401", 180.0, 35.0)
    written_negative, _, _ = provider.hourly_series("5401", -180.0, 35.0)
    assert np.array_equal(written_positive, written_negative), (
        f"north spelled 180 yields {written_positive.sum():.0f} W and spelled -180 yields "
        f"{written_negative.sum():.0f}, and they are the same roof"
    )


def test_east_and_west_of_south_are_mirror_images() -> None:
    """The general form of the same claim, over the whole input space.

    The table is symmetric by construction: (90, 35) and (-90, 35) are both
    0.85, because a plane turned so many degrees off south loses the same
    whichever way it is turned. Nothing made the lookup honour that, and the
    test above only pins the one azimuth where the old arithmetic was worst.
    """
    wrong = [
        (azimuth, tilt)
        for azimuth in range(181)
        for tilt in range(91)
        if FallbackProvider._orientation_factor(azimuth, tilt)
        != FallbackProvider._orientation_factor(-azimuth, tilt)
    ]
    assert not wrong, f"{len(wrong)} orientations differ from their mirror, first {wrong[:3]}"


def test_no_direction_the_form_can_send_was_moved_by_the_fix() -> None:
    """What the correction is allowed to cost, which is nothing.

    RoofPicker.tsx writes north as 180 rather than -180 and its comment says
    why, so no visitor of the shipped form ever reached the broken band. These
    are the factors those eight directions returned before 2026-08-23, and a
    change here means the fix moved a number that a household actually sees.
    """
    expected = {
        "NORTH": 0.62,
        "NORTHEAST": 0.85,
        "EAST": 0.85,
        "SOUTHEAST": 1.00,
        "SOUTH": 1.00,
        "SOUTHWEST": 1.00,
        "WEST": 0.85,
        "NORTHWEST": 0.85,
    }
    compass = _compass_azimuths()
    assert set(compass) == set(expected), (
        f"the form now sends {sorted(compass)}, and this test knows {sorted(expected)}"
    )
    moved = {
        name: (FallbackProvider._orientation_factor(azimuth, 35), expected[name])
        for name, azimuth in compass.items()
        if FallbackProvider._orientation_factor(azimuth, 35) != expected[name]
    }
    assert not moved, f"the fallback yield of a household changed: {moved}"


def test_a_tie_between_two_table_entries_takes_the_higher_factor() -> None:
    """Recorded, not endorsed. Northeast and northwest sit on one.

    Both are 45 degrees from east or west and 45 from north, and the search
    breaks the tie on the order of ORIENTATION_FACTORS, which in this table
    hands them the higher of the two: 0.85 rather than 0.62. Neither is right.
    A plane at 35 degrees facing northeast is not as good as one facing east.

    Left alone deliberately. Moving it changes what a real household is told by
    27 percent on a judgement call rather than on a measurement, and the honest
    repair is a table entry for those two directions derived from the same PVGIS
    call the rest of the table came from. Recorded in docs/decisions.md under
    what was not decided here.
    """
    for azimuth in (-135, 135):
        assert FallbackProvider._orientation_factor(azimuth, 35) == 0.85, (
            f"the tie at azimuth {azimuth} now resolves differently, which changes what a "
            "household with that roof is told"
        )
