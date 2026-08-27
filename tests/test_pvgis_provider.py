from __future__ import annotations

import calendar
import math
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import requests

from ampeer_sim.production.fallback_yield import (
    MONTHLY_MEAN_PRODUCTION_W_PER_KWP,
    ORIENTATION_FACTORS,
    TABLE_LONGITUDE,
)
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import (
    FALLBACK_DAYLIGHT_HOURS,
    FALLBACK_SOLAR_NOON_HOUR,
    UTC_TO_WINTER_TIME_HOURS,
    FallbackProvider,
    PvgisProvider,
    ResilientProductionProvider,
    postcode4_to_latlon,
)
from ampeer_sim.timebase import (
    HOURS_PER_DAY,
    MINUTES_PER_QUARTER,
    QUARTERS_PER_DAY,
    YearGrid,
)
from ampeer_sim.types import ProductionSource, PVSystem


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


# ---------------------------------------------------------------------------
# Where the fallback puts a day's energy
# ---------------------------------------------------------------------------


def test_the_day_is_centred_on_solar_noon_and_not_on_the_clock() -> None:
    """The shape sat 38 minutes early until 2026-08-26, and it showed.

    The grid runs in continuous winter time, which is UTC plus an hour, and the
    table was measured at 5.61 degrees east, so solar noon there is 12:38 and
    not 12:00. The shape was a half sine from 06:00 to 18:00, so it put the
    whole day early by that much and stopped exporting while the country had
    not.

    Derived from the longitude rather than repeated, because the constant and
    the location have to move together or the fallback places one location's
    energy at another location's hours.
    """
    assert FALLBACK_SOLAR_NOON_HOUR == pytest.approx(13.0 - TABLE_LONGITUDE / 15.0), (
        f"solar noon is {FALLBACK_SOLAR_NOON_HOUR:.3f} and no longer follows the longitude "
        f"of {TABLE_LONGITUDE} the yield table was measured at"
    )
    assert FALLBACK_SOLAR_NOON_HOUR == pytest.approx(12.626, abs=5e-4), (
        f"{FALLBACK_SOLAR_NOON_HOUR:.3f} is not 12:38, so the table is describing another place"
    )

    shape = FallbackProvider._day_shape(100.0)
    # The centre of mass of a symmetric shape is its centre, plus the half hour
    # by which an index names the hour that starts there.
    centre = sum(hour * value for hour, value in enumerate(shape)) / sum(shape) + 0.5
    assert centre == pytest.approx(FALLBACK_SOLAR_NOON_HOUR, abs=0.01), (
        f"the fallback's day is centred on {centre:.2f} in winter time and solar noon at the "
        f"table's location is {FALLBACK_SOLAR_NOON_HOUR:.2f}"
    )


#: What PVGIS says about the hour of the day, for the plane this table was
#: measured for: the share of nine years of output that falls in each hour.
#:
#: Read on 2026-08-26 from the same call as ORIENTATION_FACTORS, Uden at 35
#: degrees facing south, 2015 through 2023, and written here in winter time
#: rather than in the UTC PVGIS stamps it with. Twenty four shares of a series
#: are a fact about it and not a copy of it, the same reading that puts the NEDU
#: shares in tests/fixtures rather than the profile itself.
#:
#: This is the reference the offline shape should answer to, because standing in
#: for this call is the whole of its job. The national feed-in profile in
#: tests/test_calibration.py is measured where this is modelled, but it averages
#: every roof in the country and this is one plane.
PVGIS_HOUR_OF_DAY_WINTER_TIME = (
    0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0003, 0.0032, 0.0161,
    0.0443, 0.0820, 0.1119, 0.1280, 0.1354, 0.1316, 0.1201, 0.0980,
    0.0710, 0.0402, 0.0144, 0.0033, 0.0003, 0.0000, 0.0000, 0.0000,
)  # fmt: skip

#: Ceilings on the summed absolute difference from the table above, over its 24
#: hours, with both sides normalised. One rule and not two round numbers: each
#: is the distance measured on 2026-08-27 rounded up to the next hundredth. They
#: may be tightened when a model gets closer and never widened to make a change
#: pass, which is the rule the calibration file already states for its own two.
#:
#: Until 2026-08-27 there were two ceilings on this quantity, a factor of two
#: apart, and neither could be defended against the other: 0.05 in
#: tests/test_calibration.py on the PVGIS path, measuring 0.0171, and 0.10 here
#: on the offline shape, measuring 0.0759. Only the first was ever fitted to
#: anything, and the second sat a third above its own measurement.
#:
#: One number could not replace both, and finding that out is what settled it.
#: At 0.10 the calibration check stops refusing a drift of a quarter of an hour,
#: which measures 0.0680 and is the whole reason that ceiling exists. At 0.05
#: the offline shape is red at 0.0759, and it should not be: it is a half sine
#: standing in for a sky model when PVGIS is unreachable and it has never
#: claimed to reproduce that call. So they were never one ceiling on one
#: quantity; they were one distance measured on two subjects, and the fix is to
#: name the subject in each and derive both from the same rule.
#:
#: The PVGIS-path number is now 0.02 rather than 0.05, which is that rule
#: applied. It costs nothing in stability: that path is measured on a canned
#: response, so the figure can only move when the code does.
#:
#: What the tightening on this side buys, shown rather than argued: a fallback
#: day shortened from twelve hours to eleven measures 0.0898, which 0.08 refuses
#: and the 0.10 that stood here waved through.
MAX_HOUR_OF_DAY_GAP = 0.02
MAX_FALLBACK_DAY_SHAPE_GAP = 0.08


def _hour_of_day(shape: list[float]) -> list[float]:
    return [value / sum(shape) for value in shape]


def _distance(shape: list[float]) -> float:
    return sum(
        abs(share - measured)
        for share, measured in zip(_hour_of_day(shape), PVGIS_HOUR_OF_DAY_WINTER_TIME, strict=True)
    )


def test_the_shape_moved_towards_pvgis_and_not_only_towards_the_country() -> None:
    """The check that decides whether the repair of 2026-08-26 was one.

    Two references disagree about this shape and only one of them is describing
    the same thing. The national feed-in profile is wider than any single house,
    because it averages every orientation, so it rewards a longer day; PVGIS
    models this exact plane at this exact place. A repair judged only on the
    first would have widened the day to 13.28 hours, which is the mean day
    length weighted by the energy each day carries and scores better against the
    country in both families.

    Measured as the summed absolute difference over the 24 hours:

        12.00 h centred on 12:00, before   0.2291
        13.28 h centred on solar noon      0.1576
        12.00 h centred on solar noon      0.0759, what is here now
        11.57 h centred on solar noon      0.0677, the best fitting length

    So the widening would have moved the shape away from what it stands in for
    while every test in the suite went greener. This asserts the direction, not
    the figure, because the figure moves with the table it is normalised from.

    The ceiling was 0.10 until 2026-08-27, which was a round number above the
    measurement rather than a figure fitted to it. It is now the same rule the
    PVGIS path's ceiling follows, and the argument for having two numbers under
    one rule is above MAX_FALLBACK_DAY_SHAPE_GAP.
    """
    shipped = _distance(FallbackProvider._day_shape(100.0))
    assert shipped <= MAX_FALLBACK_DAY_SHAPE_GAP, (
        f"the fallback's day is {shipped:.4f} away from PVGIS's own, over "
        f"{MAX_FALLBACK_DAY_SHAPE_GAP}, and it was 0.0759 when this was measured"
    )

    peak = max(range(HOURS_PER_DAY), key=lambda hour: PVGIS_HOUR_OF_DAY_WINTER_TIME[hour])
    assert peak == 12, f"PVGIS's fullest hour is now {peak}:00 winter time"
    assert FALLBACK_SOLAR_NOON_HOUR > peak, (
        "solar noon no longer falls inside the hour PVGIS puts most of its energy in"
    )

    old = [0.0] * HOURS_PER_DAY
    for offset in range(12):
        old[6 + offset] = math.sin((offset + 0.5) / 12 * math.pi)
    assert _distance(old) > 2.0 * shipped, (
        f"the shape this replaced is {_distance(old):.4f} from PVGIS and the one here is "
        f"{shipped:.4f}, so the change is no longer worth the numbers moved for it"
    )


def test_the_daylight_window_is_still_twelve_hours() -> None:
    """Pinned because it was nearly changed, not because it is hard to change.

    12 is the plain mean of the 365 day lengths at this latitude. The case for
    lengthening it, and the measurement that refused, sit above the constant.
    """
    assert FALLBACK_DAYLIGHT_HOURS == 12.0, (
        f"the window is {FALLBACK_DAYLIGHT_HOURS} hours; if that is the energy weighted day "
        "length again, read the comment above the constant first"
    )


def test_a_month_carries_exactly_the_energy_the_table_gives_it() -> None:
    """The floor under both changes above: they may move energy, never make it.

    Centring and lengthening the window redistribute a day; the annual total is
    the table's and must not move. It used to, by 0.29 percent, because the peak
    was a closed form for the integral of a sine and the shape was then sampled
    at twelve points: 1224.09 kWh per kWp against the 1220.60 the table adds up
    to and the 1221 the module's docstring claims.
    """
    for mean_power in (52.1, 209.7):
        shape = FallbackProvider._day_shape(mean_power)
        assert len(shape) == HOURS_PER_DAY, f"a day is {len(shape)} hours long"
        assert sum(shape) / HOURS_PER_DAY == pytest.approx(mean_power, rel=1e-12), (
            f"a day asked for a mean of {mean_power} W per kWp came back with "
            f"{sum(shape) / HOURS_PER_DAY:.4f}"
        )

    production, _, _ = FallbackProvider(2023).hourly_series("5401", 0.0, 35.0)
    by_table = sum(
        calendar.monthrange(2023, month)[1]
        * HOURS_PER_DAY
        * MONTHLY_MEAN_PRODUCTION_W_PER_KWP[month - 1]
        for month in range(1, 13)
    )
    assert production.sum() == pytest.approx(by_table, rel=1e-9), (
        f"the year sums to {production.sum() / 1_000:.2f} kWh per kWp and the table it is "
        f"built from sums to {by_table / 1_000:.2f}"
    )
    assert production.sum() / 1_000.0 == pytest.approx(1_220.6, abs=0.05), (
        f"{production.sum() / 1_000:.2f} kWh per kWp is not the annual total this module's "
        "docstring gives its provenance for"
    )


def test_the_fallback_still_produces_after_the_old_window_had_closed() -> None:
    """What the evening repair is worth, at the hours it was missing.

    The old shape was zero from 18:00 in winter time onward, which is 19:00 on
    a summer evening, while the measured national feed-in profile still puts
    0.0295 of the year at 18:00 local and 0.0120 at 19:00. Whether that reaches
    the meter is a question about consumption and belongs to
    tests/test_calibration.py; whether there is anything there at all is this
    one.
    """
    production, _, _ = FallbackProvider(2023).hourly_series("5401", 0.0, 35.0)
    june = production[(31 + 28 + 31 + 30 + 31) * HOURS_PER_DAY :][:HOURS_PER_DAY]
    assert june[18] > 0.0, "the fallback is dark again at 18:00 winter time"
    assert june[6] > 0.0, "the fallback no longer produces in the early morning either"
    assert june[20] == 0.0 and june[4] == 0.0, (
        "the window now spans more than fifteen hours of the clock, which no fixed window "
        "here can be defended at: the shortest day of the year is eight"
    )


# ---------------------------------------------------------------------------
# The time base a PVGIS series arrives on
# ---------------------------------------------------------------------------


def _shaped_payload(hour_of_day: tuple[float, ...], days: int = 365) -> dict[str, Any]:
    """A year whose every day repeats ``hour_of_day``, in PVGIS's own shape.

    The rows carry the timestamps PVGIS writes, ten past each hour, so that a
    reader can see which hour each value claims to be. Nothing reads them: the
    provider places by index, which is the property these tests are about.
    """
    return {
        "outputs": {
            "hourly": [
                {
                    "time": f"{date(2023, 1, 1) + timedelta(days=day):%Y%m%d}:{hour:02d}10",
                    "P": watts,
                    "G(i)": watts,
                    "T2m": float(hour),
                }
                for day in range(days)
                for hour, watts in enumerate(hour_of_day)
            ]
        }
    }


#: Minutes past the hour that PVGIS stamps a row with. Read off a live SARAH3
#: response on 2026-08-27: 8760 rows for 2023 at Uden, the first stamped
#: 20230101:0010 and the last 20231231:2310. The payloads below carry the same
#: stamps and the tests read them rather than assuming them.
PVGIS_STAMP_MINUTES_PAST_HOUR = 10

#: Winter time is UTC plus one hour, all year, because the grid is continuous
#: winter time by construction. Written here as the fact about the country that
#: it is, so that the placement tests below do not check the engine against a
#: constant the engine also supplies.
WINTER_TIME_MINUS_UTC_HOURS = 1.0

PLACEMENT_YEAR = 2023
PLACEMENT_SYSTEM = PVSystem(peak_power_wp=3_500, azimuth_deg=0.0, tilt_deg=35.0)


def _sun_above_horizon(year: int, latitude: float, longitude: float) -> tuple[float, ...]:
    """A year of the sine of the sun's elevation, hourly, sampled where PVGIS samples.

    The independent source these placement tests are built from. Until
    2026-08-27 the payload was ``np.roll(PVGIS_HOUR_OF_DAY_WINTER_TIME, -1)``,
    which is the table the same test then asserted against, put through the
    inverse of the rotation under test. That passes by construction for any
    provider whose rotation matches the test's roll, and it cannot say whether
    either of them is right.

    This owes nothing to the engine or to any table in this file. Cooper's
    declination and the hour angle are textbook solar geometry, the location
    comes from the postcode the call is made for, and the result is symmetric
    about solar noon by construction, which is the property that makes it
    usable as a reference: it is a shape whose own centre is known without
    measuring it.

    The equation of time is left out, exactly as FALLBACK_SOLAR_NOON_HOUR
    leaves it out, and for the same reason: it moves solar noon by at most a
    quarter of an hour either way over the year and averages to nothing. The
    tests below compare against this series' own weighted centre rather than
    against 12:00, so anything it does get wrong is subtracted out.
    """
    days = 366 if calendar.isleap(year) else 365
    phi = math.radians(latitude)
    values: list[float] = []
    for day in range(days):
        declination = math.radians(23.45) * math.sin(2.0 * math.pi * (284 + day + 1) / 365.0)
        for hour in range(HOURS_PER_DAY):
            stamped_utc = hour + PVGIS_STAMP_MINUTES_PAST_HOUR / 60.0
            hour_angle = math.radians(15.0 * (stamped_utc + longitude / 15.0 - 12.0))
            elevation = math.sin(phi) * math.sin(declination) + math.cos(phi) * math.cos(
                declination
            ) * math.cos(hour_angle)
            values.append(max(0.0, elevation) * 1_000.0)
    return tuple(values)


def _stamped_payload(year: int, hourly: tuple[float, ...]) -> dict[str, Any]:
    """``hourly`` written into the rows and stamps a PVGIS response carries."""
    start = date(year, 1, 1)
    return {
        "outputs": {
            "hourly": [
                {
                    "time": (
                        f"{start + timedelta(days=index // HOURS_PER_DAY):%Y%m%d}:"
                        f"{index % HOURS_PER_DAY:02d}{PVGIS_STAMP_MINUTES_PAST_HOUR:02d}"
                    ),
                    "P": watts,
                    "G(i)": watts,
                    "T2m": 10.0,
                }
                for index, watts in enumerate(hourly)
            ]
        }
    }


def _hour_of_day_from_stamps(payload: dict[str, Any]) -> float:
    """Where the payload's own timestamps put its energy, in UTC hours.

    Parsed out of the rows, not taken from whatever built them. That is the
    whole point: the reference for where a series belongs is what the response
    says about itself.
    """
    weighted = 0.0
    total = 0.0
    for row in payload["outputs"]["hourly"]:
        clock = row["time"].split(":")[1]
        stamped = int(clock[:2]) + int(clock[2:]) / 60.0
        weighted += row["P"] * stamped
        total += row["P"]
    return weighted / total


def _grid_anchor_minutes(grid: YearGrid) -> float:
    """How far past the start of its hour the grid places an hourly value.

    Measured rather than restated. A lone hourly spike goes through
    ``hourly_to_quarters`` and the centre of what comes out is the anchor, so
    this reads the convention out of the code that applies it instead of
    repeating the 1.5 that appears in its body.
    """
    hourly = np.zeros(grid.hours)
    hourly[11] = 1.0
    quarters = grid.hourly_to_quarters(hourly)
    positions = np.arange(quarters.size, dtype=float)
    centre = float((positions * quarters).sum() / quarters.sum())
    return (centre + 0.5) * MINUTES_PER_QUARTER - 11 * 60.0


def _modelled_hour_of_day(payload: dict[str, Any], grid: YearGrid) -> float:
    """Where the whole path puts the payload's energy, in winter time hours."""
    session = _FakeSession(payload=payload)
    hourly, _, _ = PvgisProvider(
        weather_year=PLACEMENT_YEAR,
        session=session,  # type: ignore[arg-type]
    ).hourly_series("5401", 0.0, 35.0)
    quarters = production_series(hourly, PLACEMENT_SYSTEM, grid, weather_year=PLACEMENT_YEAR)
    minute_of_day = (
        np.arange(grid.quarters) % QUARTERS_PER_DAY
    ) * MINUTES_PER_QUARTER + MINUTES_PER_QUARTER / 2.0
    return float((quarters * (minute_of_day / 60.0)).sum() / quarters.sum())


def test_a_pvgis_series_arrives_on_the_grids_time_base_and_not_on_utc() -> None:
    """The defect this file's fallback section already described, on the live path.

    PVGIS stamps its hourly rows in UTC and the grid runs in continuous winter
    time, which is UTC plus one. Until 2026-08-27 nothing converted between
    them, so hour i of the response was placed at hour i of the grid and every
    kilowatt hour a visitor was shown sat an hour early.

    Built from solar geometry and read against the payload's own stamps, so
    neither side of the comparison comes from the engine. The quantity is the
    hour of the day the modelled year's energy sits at, which is what a
    displacement moves and what nothing else in the path touches.
    """
    grid = YearGrid.for_year(PLACEMENT_YEAR)
    latitude, longitude = postcode4_to_latlon("5401")
    payload = _stamped_payload(
        PLACEMENT_YEAR, _sun_above_horizon(PLACEMENT_YEAR, latitude, longitude)
    )

    stamped = _hour_of_day_from_stamps(payload)
    modelled = _modelled_hour_of_day(payload, grid)
    # To the hour, and the tolerance says so: it admits the twenty minute stamp
    # residual the test below owns and refuses anything nearing half an hour.
    assert modelled - stamped == pytest.approx(WINTER_TIME_MINUS_UTC_HOURS, abs=0.45), (
        f"the payload's stamps put its energy at {stamped:.4f} UTC and the model puts it at "
        f"{modelled:.4f} on a clock that is UTC plus {WINTER_TIME_MINUS_UTC_HOURS:.0f}, which "
        f"is {(modelled - stamped - WINTER_TIME_MINUS_UTC_HOURS) * 60:+.1f} minutes out"
    )

    solar_noon_winter_time = 12.0 + WINTER_TIME_MINUS_UTC_HOURS - longitude / 15.0
    assert stamped + WINTER_TIME_MINUS_UTC_HOURS == pytest.approx(
        solar_noon_winter_time, abs=0.02
    ), "the reference series is not centred on solar noon, so it cannot say where anything belongs"


def test_the_pvgis_series_is_twenty_minutes_late_and_no_whole_rotation_helps() -> None:
    """The residual the rotation cannot reach, pinned so it cannot become something else.

    PVGIS stamps ten past the hour and the grid anchors an hourly value half
    past, so a PVGIS series sits twenty minutes late whatever whole rotation is
    applied to it: rotating by n leaves (n - 1) * 60 + 20 minutes, and n = 1 is
    the smallest of those. What it costs, why it is stated here rather than
    resampled away, and where the repair belongs are all above
    UTC_TO_WINTER_TIME_HOURS.

    This is the residual measured end to end, and it fails in both directions.
    It goes red if somebody moves the series onto its stamps without saying so,
    which is the change that should be made and is not this file's to make; and
    it goes red if the displacement grows, which is the change nobody wants.
    Neither number is written down twice: the stamp is parsed out of the
    payload, the anchor is measured through hourly_to_quarters, and the lag is
    the difference.
    """
    grid = YearGrid.for_year(PLACEMENT_YEAR)
    latitude, longitude = postcode4_to_latlon("5401")
    payload = _stamped_payload(
        PLACEMENT_YEAR, _sun_above_horizon(PLACEMENT_YEAR, latitude, longitude)
    )

    anchor = _grid_anchor_minutes(grid)
    assert anchor == pytest.approx(30.0, abs=1e-9), (
        f"the grid anchors an hourly value {anchor:.2f} minutes past its hour, and this file's "
        "account of the residual is written for the half past that hourly_to_quarters documents"
    )

    expected_lag = anchor - PVGIS_STAMP_MINUTES_PAST_HOUR
    stamped = _hour_of_day_from_stamps(payload)
    modelled = _modelled_hour_of_day(payload, grid)
    lag = (modelled - stamped - WINTER_TIME_MINUS_UTC_HOURS) * 60.0
    assert lag == pytest.approx(expected_lag, abs=1.0), (
        f"the modelled year sits {lag:+.1f} minutes after where PVGIS stamped it, and the "
        f"stamp at {PVGIS_STAMP_MINUTES_PAST_HOUR} past against an anchor at {anchor:.0f} past "
        f"accounts for {expected_lag:+.1f}. Either the placement moved, which is the repair "
        "described above UTC_TO_WINTER_TIME_HOURS and wants this test rewritten, or something "
        "else has started moving the series in time"
    )

    best = min(abs((rotation - 1) * 60.0 + expected_lag) for rotation in range(-2, 3))
    assert abs(expected_lag) == pytest.approx(best, abs=1e-9), (
        f"a whole rotation can now leave less than {abs(expected_lag):.0f} minutes, so "
        "UTC_TO_WINTER_TIME_HOURS is no longer the best available placement"
    )


def test_the_conversion_moves_the_temperature_with_the_production() -> None:
    """Both columns come off the same rows, so both carry the same stamp.

    Shifting the production alone would leave the outside temperature an hour
    early, and the temperature series has exactly one consumer: the heat pump
    demand curve. Its hour would then be the hour the defect was.

    The payload writes the hour number into T2m, so what comes back names the
    UTC hour each value was stamped with.
    """
    session = _FakeSession(payload=_shaped_payload(tuple(float(hour) for hour in range(24))))
    production, temperature, _ = _provider(session).hourly_series("5401", 0.0, 35.0)
    assert temperature[12] == pytest.approx(11.0), (
        f"winter time 12:00 carries the reading PVGIS stamped {temperature[12]:.0f}:10 UTC, "
        "and 11:10 UTC is the one that belongs there"
    )
    assert production[12] == pytest.approx(temperature[12]), (
        "the two columns no longer move together, so they describe different hours"
    )


def test_the_conversion_neither_loses_energy_nor_makes_any() -> None:
    """A rotation rather than a shift with a fill, and the floor under saying so.

    Shifting with a fill would drop the last hour of the response and invent a
    first one. This wraps instead: 31 December 23:00 UTC is midnight winter
    time and lands on the grid's 1 January 00:00, which is the following year's
    hour rather than this one's. It costs nothing because the sun is down at
    midwinter midnight either way, and the annual total PVGIS reports therefore
    survives to the last digit.

    The payload's own last hour is non-zero on purpose. A real December
    midnight is 0.0 W per kWp, measured on 2026-08-27 for 2023 at postcode
    5401, and a test built on that could not tell a rotation from a fill.
    """
    shape = tuple(float(hour) for hour in range(24))
    session = _FakeSession(payload=_shaped_payload(shape))
    production, _, _ = _provider(session).hourly_series("5401", 0.0, 35.0)

    assert production.sum() == pytest.approx(sum(shape) * 365, rel=0, abs=0), (
        "the conversion moved energy, and every factor after it is a multiplication"
    )
    assert sorted(production.tolist()) == sorted(np.tile(shape, 365).tolist()), (
        "the returned year is not a permutation of the one PVGIS sent"
    )
    assert production[0] == pytest.approx(shape[-1]), (
        "the grid's first hour does not hold the last hour of the response, so the wrap "
        "is not the one described above UTC_TO_WINTER_TIME_HOURS"
    )


#: Annual yield of an east facing and a west facing plane at 35 degrees, kWh per
#: kWp, from the same PVGIS SARAH3 call over 2015 through 2023 that
#: PVGIS_HOUR_OF_DAY_WINTER_TIME and ORIENTATION_FACTORS come from. The two
#: figures are in the comment above ORIENTATION_FACTORS with their provenance;
#: the table itself carries their mean, 0.79, because it is symmetric by
#: construction, so they cannot be read back out of the code.
PVGIS_EAST_KWH_PER_KWP = 979.35
PVGIS_WEST_KWH_PER_KWP = 948.91


def test_the_two_pvgis_tables_agree_about_which_half_of_the_day_is_sunnier() -> None:
    """What decides whether the ten past is real, and it is not a preference.

    An hourly row can be read two ways. If the stamp names where the value
    sits, PVGIS's day is centred twenty minutes before the grid puts it. If the
    value is instead the mean of the whole hour that starts on the hour, it is
    already in the right place and there is no residual at all. The whole
    account above UTC_TO_WINTER_TIME_HOURS rests on the first reading, so it is
    worth a check that does not come from the same sentence.

    The check is that one call cannot say two things. The nine year distribution
    above and the orientation yields below it were read from the same PVGIS
    call, and an east plane out-yielding a west plane by 3.2 percent means the
    morning half of the day carries more energy than the afternoon half at that
    location over those years.

    Measured on 2026-08-27, splitting the table at solar noon:

        the stamp names where the value sits   morning / afternoon  1.065
        the value is the mean of its hour      morning / afternoon  0.889

    The second reading says the afternoon is eleven percent the sunnier half
    while the yield table from the same call says the morning is three percent
    the sunnier. Only the first reading is consistent with it, and it is the
    smaller correction of the two, so this is not a case of picking the answer
    that flatters anything.
    """
    assert PVGIS_EAST_KWH_PER_KWP > PVGIS_WEST_KWH_PER_KWP, (
        "the yield table now says the afternoon is the sunnier half, so the reading of the "
        "hourly stamp that this file rests on has lost its corroboration"
    )

    solar_noon = FALLBACK_SOLAR_NOON_HOUR
    shares = PVGIS_HOUR_OF_DAY_WINTER_TIME

    def morning_ratio(offset_hours: float) -> float:
        """Energy before solar noon over energy after it, for one reading."""
        before = 0.0
        for hour, share in enumerate(shares):
            low = hour + offset_hours - 0.5
            high = low + 1.0
            if high <= solar_noon:
                before += share
            elif low < solar_noon:
                before += share * (solar_noon - low)
        return before / (sum(shares) - before)

    stamped = morning_ratio(PVGIS_STAMP_MINUTES_PAST_HOUR / 60.0)
    as_hour_mean = morning_ratio(0.5)
    assert stamped > 1.0, (
        f"read at the stamp, PVGIS's day puts {stamped:.3f} as much energy before solar noon "
        f"as after, and the same call's east and west yields say more than one"
    )
    assert as_hour_mean < 1.0 < stamped, (
        f"the two readings of the hourly row no longer disagree ({as_hour_mean:.3f} against "
        f"{stamped:.3f}), so this test has stopped telling them apart"
    )


def test_the_offset_is_the_one_winter_time_actually_is() -> None:
    """Winter time is UTC plus one, and only that.

    Not a restatement of the line above the constant: this is what refuses a
    conversion that follows summer time for part of the year. The grid is
    continuous winter time by construction, so the offset has no season, and a
    two hour offset in July would be a whole extra defect wearing this repair's
    name.
    """
    assert UTC_TO_WINTER_TIME_HOURS == 1, (
        f"the conversion moves PVGIS by {UTC_TO_WINTER_TIME_HOURS} hours and continuous "
        "winter time is UTC plus exactly one"
    )


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


def test_every_direction_the_form_can_send_returns_its_measured_factor() -> None:
    """The eight factors a household can actually be told, pinned.

    These are the ratios measured from PVGIS on 2026-08-26 and written into
    ORIENTATION_FACTORS, rounded the way the table rounds them. A change here is
    a change to what somebody with that roof is told when PVGIS is down, which
    is the only reason this test is worth its lines.

    What the eight returned before that measurement, and what moved:

        NORTH      0.62 -> 0.52    EAST       0.85 -> 0.79
        NORTHEAST  0.85 -> 0.61    SOUTHEAST  1.00 -> 0.94
        NORTHWEST  0.85 -> 0.61    SOUTHWEST  1.00 -> 0.94
        WEST       0.85 -> 0.79    SOUTH      1.00 -> 1.00

    Five of the eight moved and all five moved down, so every household with a
    roof off south now hears a smaller yield. Northeast and northwest were on a
    tie that the table's write order handed the east factor; southeast and
    southwest were on the same tie the other way, taking south's 1.00; and the
    three that had a row of their own had it from a rule of thumb rather than
    from this call. The argument sits above ORIENTATION_FACTORS with the
    kilowatt hours it is rounded from.
    """
    expected = {
        "NORTH": 0.52,
        "NORTHEAST": 0.61,
        "EAST": 0.79,
        "SOUTHEAST": 0.94,
        "SOUTH": 1.00,
        "SOUTHWEST": 0.94,
        "WEST": 0.79,
        "NORTHWEST": 0.61,
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


def test_each_step_around_the_compass_away_from_south_costs_something() -> None:
    """The one thing a yield table may not get wrong, whatever its numbers.

    Until 2026-08-26 it did, twice, and neither showed as a table entry being
    wrong: they showed as two directions having no entry at all. Northeast sat
    45 degrees from both east and north, the nearest-entry search broke that tie
    on the order the table is written in, and it came back with east's 0.85.
    Southeast sat between south and east the same way and came back with south's
    1.00. So the table said a northeast roof is exactly an east roof and a
    southeast roof is exactly a south one, which is the sort of claim a
    monotonicity check waves through: the sequence never rose, it just stopped
    falling where it should not have.

    Hence strictly, and hence on each step rather than on the range. The eight
    are what the form can send; the second half of this asserts the milder
    property over every whole azimuth the public API accepts.
    """
    compass = _compass_azimuths()
    for side in (
        ("SOUTH", "SOUTHEAST", "EAST", "NORTHEAST", "NORTH"),
        ("SOUTH", "SOUTHWEST", "WEST", "NORTHWEST", "NORTH"),
    ):
        factors = [FallbackProvider._orientation_factor(compass[name], 35) for name in side]
        for step in range(1, len(side)):
            assert factors[step] < factors[step - 1], (
                f"{side[step]} at {factors[step]} is not worse than {side[step - 1]} at "
                f"{factors[step - 1]}, and it is 45 degrees further from south"
            )

    every = [FallbackProvider._orientation_factor(azimuth, 35) for azimuth in range(181)]
    rose = [
        (azimuth, every[azimuth - 1], every[azimuth])
        for azimuth in range(1, 181)
        if every[azimuth] > every[azimuth - 1]
    ]
    assert not rose, f"turning further from south raised the yield at {rose}"


def test_no_whole_azimuth_still_lands_on_a_tie() -> None:
    """The defect behind the one above, rather than the symptom.

    A tie is decided by dict order, which is not a fact about roofs, so the
    table should not leave one reachable. With a row for all eight compass
    directions the nearest-entry search only ties at 22.5 degrees and its odd
    multiples, and the API rounds azimuth to whole degrees before it gets here.

    Tilt is a separate matter and still ties: 25 degrees sits ten from both 15
    and 35. That one is recorded rather than fixed, in _orientation_factor.
    """
    for azimuth in range(-180, 181):
        gaps = sorted(
            FallbackProvider._azimuth_gap(key[0], azimuth) + abs(key[1] - 35)
            for key in ORIENTATION_FACTORS
        )
        assert gaps[0] < gaps[1], (
            f"azimuth {azimuth} at 35 degrees is equidistant from two table entries, so which "
            "one it gets is decided by the order the table happens to be written in"
        )
