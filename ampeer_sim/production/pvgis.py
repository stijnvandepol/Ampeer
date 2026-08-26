"""Production providers.

This is the only module in ``ampeer_sim`` that performs outbound HTTP. The URL
is a constant; user input contributes validated numeric parameters only, never
parts of the URL itself. That is what keeps the project SSRF rule intact.

PVGIS is asked to do the photovoltaic physics, for one kWp and with zero system
loss. Everything we apply on top of that is linear, so a whole sensitivity
analysis costs one call rather than one call per variation.
"""

from __future__ import annotations

import calendar
import math

import numpy as np
import requests

from ampeer_sim.production.fallback_yield import (
    MONTHLY_MEAN_PRODUCTION_W_PER_KWP,
    MONTHLY_MEAN_TEMPERATURE,
    ORIENTATION_FACTORS,
    TABLE_LONGITUDE,
)
from ampeer_sim.providers import ProductionProvider
from ampeer_sim.timebase import HOURS_PER_DAY
from ampeer_sim.types import ProductionSource

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
RADIATION_DATABASE = "PVGIS-SARAH3"

#: We ask for one kWp and no losses so the caller can scale and vary freely.
REFERENCE_PEAK_POWER_KW = 1.0
REFERENCE_LOSS_PERCENT = 0.0

#: Solar noon at the table's location, on the continuous winter time the grid
#: runs in. Winter time is UTC plus one hour and true solar noon is 12:00 minus
#: four minutes per degree of eastward longitude, so Uden's is 12:38.
#:
#: The fallback shape was centred on 12:00 until 2026-08-26, which put its whole
#: day 38 minutes early. That is most of the evening problem recorded in
#: docs/decisions.md: the model exported nothing after 17:00 while the country
#: still exported 0.0295 of its year at 18:00.
#:
#: One thing this does not repair, and it is larger. PVGIS stamps its hours in
#: UTC and ``YearGrid`` runs in continuous winter time, which is UTC plus one,
#: and ``align_hourly_year`` places the series by index without shifting it. So
#: the PVGIS path, which is the one a visitor normally gets, puts every kilowatt
#: hour a full hour early. Measured on 2026-08-26 over the nine years of the
#: yield table: PVGIS's own peak hour is 11:00 UTC, which is 12:00 winter time
#: and where solar noon at 11:38 UTC belongs, and the model reads it as 11:00.
#: That is in ampeer_sim/production/model.py and ampeer_sim/timebase.py rather
#: than here, so it is written up rather than fixed; it also explains why the
#: old fallback shape agreed with the PVGIS path so well. They shared the error.
#:
#: The equation of time is not modelled. It moves solar noon by at most a
#: quarter of an hour either way over the year and averages to nothing, which is
#: below what a table of monthly means can resolve.
FALLBACK_SOLAR_NOON_HOUR = 13.0 - TABLE_LONGITUDE / 15.0


#: Hours of daylight the crude fallback shape spreads its energy over. It is
#: also the plain mean of the 365 day lengths at this latitude, which is where
#: the number came from.
#:
#: Not moved on 2026-08-26, and the measurement that kept it is worth more than
#: the one that would have moved it. A longer window is tempting, because the
#: national feed-in profile is wider than this shape and lengthening it closes
#: the gap on both families at once. Measured on the reference household of
#: tests/test_calibration.py, worst hourly and worst monthly bucket:
#:
#:     12.00 h centred on 12:00   0.0490 at 17:00     0.0230 in July
#:     12.00 h centred on noon    0.0333 at 11:00     0.0233 in July
#:     13.28 h centred on noon    0.0299 at 11:00     0.0218 in July
#:
#: 13.28 is the mean day length weighted by the energy each day carries, which
#: is a defensible derivation and still the wrong answer. The national profile
#: is wide because it averages every roof orientation in the country, which
#: tests/test_calibration.py says in as many words, and this shape describes one
#: south facing plane. Asking the thing it stands in for gives the opposite
#: verdict. Against PVGIS's own hour of the day for that plane, nine years, as
#: the sum of the absolute difference over the 24 hours and the worst single
#: hour:
#:
#:     12.00 h centred on 12:00   0.2291   0.0352
#:     13.28 h centred on noon    0.1576   0.0253
#:     12.00 h centred on noon    0.0759   0.0172
#:     11.57 h centred on noon    0.0677   0.0142   the best fitting length
#:
#: So the centring is worth a factor of three, 0.2291 down to 0.0759, and the
#: lengthening would have handed back more than half of it. A half sine over the
#: real day length, which varies with the
#: season, was measured too: it scores 0.0337 hourly and 0.0389 monthly against
#: the country, and the second is over its ceiling. Widening to fit an aggregate
#: of orientations this model does not have would have made the fallback agree
#: with a curve it is not describing.
#:
#: The best fitting 11.57 is not adopted either. It buys a tenth of the
#: remaining disagreement by making the evening shorter, which is the direction
#: this shape is already wrong in, and 12 has a meaning where 11.57 has a fit.
FALLBACK_DAYLIGHT_HOURS = 12.0

#: Coarse centroid per postcode century, good enough because irradiance barely
#: varies over a few kilometres. Keys are the first two digits of the postcode.
_POSTCODE_CENTROIDS: dict[str, tuple[float, float]] = {
    "10": (52.37, 4.90),
    "11": (52.31, 4.94),
    "12": (52.16, 5.02),
    "13": (52.35, 5.24),
    "14": (52.52, 4.96),
    "15": (52.46, 4.63),
    "16": (52.63, 4.75),
    "17": (52.79, 4.83),
    "18": (52.63, 4.74),
    "19": (52.46, 4.61),
    "20": (52.38, 4.63),
    "21": (52.26, 4.49),
    "22": (52.16, 4.49),
    "23": (52.16, 4.49),
    "24": (52.05, 4.63),
    "25": (52.08, 4.31),
    "26": (52.01, 4.36),
    "27": (52.02, 4.71),
    "28": (51.99, 4.47),
    "29": (51.92, 4.48),
    "30": (51.92, 4.48),
    "31": (51.92, 4.48),
    "32": (51.87, 4.60),
    "33": (51.81, 4.67),
    "34": (52.09, 5.11),
    "35": (52.09, 5.11),
    "36": (52.02, 5.17),
    "37": (52.16, 5.39),
    "38": (52.16, 5.39),
    "39": (52.05, 5.24),
    "40": (51.96, 5.32),
    "41": (51.90, 5.29),
    "42": (51.82, 4.66),
    "43": (51.49, 3.61),
    "44": (51.50, 3.90),
    "45": (51.44, 3.57),
    "46": (51.49, 4.29),
    "47": (51.59, 4.78),
    "48": (51.59, 4.78),
    "49": (51.69, 5.30),
    "50": (51.56, 5.09),
    "51": (51.56, 5.06),
    "52": (51.44, 5.48),
    "53": (51.69, 5.30),
    "54": (51.66, 5.61),
    "55": (51.44, 5.48),
    "56": (51.44, 5.48),
    "57": (51.48, 5.66),
    "58": (51.36, 5.22),
    "59": (51.44, 5.98),
    "60": (51.44, 5.98),
    "61": (51.20, 5.99),
    "62": (50.85, 5.69),
    "63": (50.85, 5.69),
    "64": (50.88, 5.98),
    "65": (51.84, 5.86),
    "66": (51.84, 5.86),
    "67": (51.98, 5.90),
    "68": (51.98, 5.90),
    "69": (51.90, 5.98),
    "70": (51.99, 6.56),
    "71": (51.99, 6.56),
    "72": (52.15, 6.19),
    "73": (52.21, 6.19),
    "74": (52.22, 6.89),
    "75": (52.22, 6.89),
    "76": (52.26, 6.79),
    "77": (52.51, 6.09),
    "78": (52.51, 6.09),
    "79": (52.71, 6.19),
    "80": (52.51, 6.09),
    "81": (52.51, 6.09),
    "82": (52.51, 5.47),
    "83": (52.71, 6.19),
    "84": (52.90, 5.90),
    "85": (52.90, 5.90),
    "86": (53.03, 5.66),
    "87": (53.03, 5.66),
    "88": (53.20, 5.79),
    "89": (53.20, 5.79),
    "90": (53.22, 6.57),
    "91": (53.22, 6.57),
    "92": (53.22, 6.57),
    "93": (53.11, 6.56),
    "94": (53.11, 6.56),
    "95": (53.33, 6.75),
    "96": (53.33, 6.75),
    "97": (53.22, 6.57),
    "98": (53.33, 6.92),
    "99": (53.33, 6.92),
}

_DEFAULT_CENTROID = (52.09, 5.11)


def postcode4_to_latlon(postcode4: str) -> tuple[float, float]:
    """Map a four digit postcode onto a coarse centroid."""
    if len(postcode4) != 4 or not postcode4.isdigit():
        raise ValueError("postcode4 must be exactly four digits")
    return _POSTCODE_CENTROIDS.get(postcode4[:2], _DEFAULT_CENTROID)


class PvgisProvider:
    """Fetch an hourly production and temperature series from PVGIS."""

    def __init__(
        self,
        weather_year: int,
        timeout_s: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self._weather_year = weather_year
        self._timeout_s = timeout_s
        self._session = session or requests.Session()

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        latitude, longitude = postcode4_to_latlon(postcode4)
        params: dict[str, str | float] = {
            "lat": float(latitude),
            "lon": float(longitude),
            "raddatabase": RADIATION_DATABASE,
            "startyear": int(self._weather_year),
            "endyear": int(self._weather_year),
            "pvcalculation": 1,
            "peakpower": REFERENCE_PEAK_POWER_KW,
            "loss": REFERENCE_LOSS_PERCENT,
            "angle": float(tilt_deg),
            "aspect": float(azimuth_deg),
            "outputformat": "json",
        }
        response = self._session.get(PVGIS_URL, params=params, timeout=self._timeout_s)
        response.raise_for_status()
        hourly = response.json()["outputs"]["hourly"]
        production = np.array([row["P"] for row in hourly], dtype=float)
        temperature = np.array([row["T2m"] for row in hourly], dtype=float)
        return production, temperature, ProductionSource.PVGIS


class FallbackProvider:
    """Build an hourly series from monthly means, with no network access.

    The daily shape is a half sine centred on solar noon at the table's
    location, scaled so the monthly mean matches the table. This is deliberately
    crude; its only job is to keep the advice available when PVGIS is not.

    The shape is the reference plane's, south at 35 degrees, whatever roof it is
    asked about; the orientation only scales it. That is wrong for a west roof,
    whose real day runs later, and it is the price of a table with one shape in
    it. Deriving the shape from the roof's own plane was measured on 2026-08-26
    and does not work here: a beam cosine on a north facing plane at 35 degrees
    is zero all winter, because the sun never comes round to it, and the month
    would then have no shape to scale. Getting that right needs a diffuse term,
    which is a sky model, which is what PVGIS is for.
    """

    def __init__(self, weather_year: int) -> None:
        self._weather_year = weather_year

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        postcode4_to_latlon(postcode4)  # validate the input the same way PVGIS does
        factor = self._orientation_factor(azimuth_deg, tilt_deg)
        production: list[float] = []
        temperature: list[float] = []
        for month in range(1, 13):
            days = calendar.monthrange(self._weather_year, month)[1]
            day_shape = self._day_shape(MONTHLY_MEAN_PRODUCTION_W_PER_KWP[month - 1] * factor)
            for _ in range(days):
                production.extend(day_shape)
                temperature.extend([MONTHLY_MEAN_TEMPERATURE[month - 1]] * HOURS_PER_DAY)
        return (
            np.array(production, dtype=float),
            np.array(temperature, dtype=float),
            ProductionSource.FALLBACK,
        )

    @staticmethod
    def _azimuth_gap(one: float, other: float) -> float:
        """Degrees between two compass directions, the short way round.

        A plain subtraction calls 180 and -180 opposites when they are the same
        direction, and the API declares both legal: MIN_AZIMUTH_DEG is -180 and
        MAX_AZIMUTH_DEG is 180.
        """
        return abs((one - other + 180.0) % 360.0 - 180.0)

    @staticmethod
    def _orientation_factor(azimuth_deg: float, tilt_deg: float) -> float:
        """The nearest entry in the table, with azimuth measured on the circle.

        Until 2026-08-23 the azimuth term was a plain difference, so the table's
        north entry at 180 sat 355 degrees away from a roof at -175 and could
        never win. Everything from -180 to -136, which is north through
        north-north-east, took the east factor of 0.85 instead of the north one
        of 0.62: a yield overstated by 37 percent, and overstating yield
        overstates both the export a household loses in 2027 and what a battery
        is worth to them.

        Nothing the form emits moved. ``COMPASS_AZIMUTH_DEG`` in RoofPicker.tsx
        writes north as 180 rather than -180 and says why, so all eight
        directions it can send return what they returned before. This was
        reachable by anything else that posts to the API, which is a public
        endpoint and not the form's private back door.

        Ties are still broken by the order of ``ORIENTATION_FACTORS``, and as of
        2026-08-26 no whole azimuth can reach one at 35 degrees: the table has a
        row for all eight compass directions, so a tie needs a roof at exactly
        22.5, 67.5, 112.5 or 157.5 degrees and the API rounds azimuth to whole
        degrees on the way in. Tilt can still tie. A roof at 25 degrees sits ten
        from both 15 and 35 and takes 35, which is the more generous of the two.
        """
        nearest = min(
            ORIENTATION_FACTORS,
            key=lambda key: (
                FallbackProvider._azimuth_gap(key[0], azimuth_deg) + abs(key[1] - tilt_deg)
            ),
        )
        return ORIENTATION_FACTORS[nearest]

    @staticmethod
    def _day_shape(mean_power: float) -> list[float]:
        """A half sine centred on solar noon, averaging to ``mean_power``.

        Each hour holds the half sine's mean over that hour, integrated rather
        than sampled at the midpoint. The window no longer starts on an hour
        boundary, so a midpoint sample would drop the part of the first and last
        hour that falls inside it and pick up nothing in exchange.

        The scaling is a division by what the shape actually sums to, not a
        closed form for what it should sum to. The closed form was there until
        2026-08-26 and it was 0.29 percent high, because it integrated the sine
        and then evaluated it at twelve points: the annual total came out at
        1224.09 kWh per kWp where the table says 1220.60, and the docstring of
        fallback_yield.py says 1221.
        """
        start = FALLBACK_SOLAR_NOON_HOUR - FALLBACK_DAYLIGHT_HOURS / 2.0
        end = start + FALLBACK_DAYLIGHT_HOURS
        if start < 0.0 or end > HOURS_PER_DAY:
            raise ValueError(
                f"a {FALLBACK_DAYLIGHT_HOURS:.2f} hour window centred on "
                f"{FALLBACK_SOLAR_NOON_HOUR:.2f} runs outside the day, so part of the "
                "month's energy would be dropped and the rest silently scaled up"
            )
        scale = FALLBACK_DAYLIGHT_HOURS / math.pi

        def swept(until: float) -> float:
            return -scale * math.cos((until - start) / FALLBACK_DAYLIGHT_HOURS * math.pi)

        values = [
            swept(min(hour + 1.0, end)) - swept(max(float(hour), start))
            if hour + 1.0 > start and hour < end
            else 0.0
            for hour in range(HOURS_PER_DAY)
        ]
        total = sum(values)
        return [value * mean_power * HOURS_PER_DAY / total for value in values]


class ResilientProductionProvider:
    """Try the primary provider, fall back on a network problem.

    Only network failures are caught. A ``TypeError`` is a bug in our own code
    and must not be hidden behind a degraded result. The fallback marks itself
    as ``ProductionSource.FALLBACK`` so the degradation stays visible in the
    output instead of being silent.
    """

    def __init__(self, primary: ProductionProvider, fallback: ProductionProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        try:
            return self._primary.hourly_series(postcode4, azimuth_deg, tilt_deg)
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError):
            return self._fallback.hourly_series(postcode4, azimuth_deg, tilt_deg)
