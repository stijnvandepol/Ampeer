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
)
from ampeer_sim.providers import ProductionProvider
from ampeer_sim.timebase import HOURS_PER_DAY
from ampeer_sim.types import ProductionSource

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
RADIATION_DATABASE = "PVGIS-SARAH3"

#: We ask for one kWp and no losses so the caller can scale and vary freely.
REFERENCE_PEAK_POWER_KW = 1.0
REFERENCE_LOSS_PERCENT = 0.0

#: Hours of daylight the crude fallback shape spreads its energy over.
FALLBACK_DAYLIGHT_HOURS = 12
FALLBACK_SUNRISE_HOUR = 6

#: Coarse centroid per postcode century, good enough because irradiance barely
#: varies over a few kilometres. Keys are the first two digits of the postcode.
_POSTCODE_CENTROIDS: dict[str, tuple[float, float]] = {
    "10": (52.37, 4.90), "11": (52.31, 4.94), "12": (52.16, 5.02), "13": (52.35, 5.24),
    "14": (52.52, 4.96), "15": (52.46, 4.63), "16": (52.63, 4.75), "17": (52.79, 4.83),
    "18": (52.63, 4.74), "19": (52.46, 4.61), "20": (52.38, 4.63), "21": (52.26, 4.49),
    "22": (52.16, 4.49), "23": (52.16, 4.49), "24": (52.05, 4.63), "25": (52.08, 4.31),
    "26": (52.01, 4.36), "27": (52.02, 4.71), "28": (51.99, 4.47), "29": (51.92, 4.48),
    "30": (51.92, 4.48), "31": (51.92, 4.48), "32": (51.87, 4.60), "33": (51.81, 4.67),
    "34": (52.09, 5.11), "35": (52.09, 5.11), "36": (52.02, 5.17), "37": (52.16, 5.39),
    "38": (52.16, 5.39), "39": (52.05, 5.24), "40": (51.96, 5.32), "41": (51.90, 5.29),
    "42": (51.82, 4.66), "43": (51.49, 3.61), "44": (51.50, 3.90), "45": (51.44, 3.57),
    "46": (51.49, 4.29), "47": (51.59, 4.78), "48": (51.59, 4.78), "49": (51.69, 5.30),
    "50": (51.56, 5.09), "51": (51.56, 5.06), "52": (51.44, 5.48), "53": (51.69, 5.30),
    "54": (51.66, 5.61), "55": (51.44, 5.48), "56": (51.44, 5.48), "57": (51.48, 5.66),
    "58": (51.36, 5.22), "59": (51.44, 5.98), "60": (51.44, 5.98), "61": (51.20, 5.99),
    "62": (50.85, 5.69), "63": (50.85, 5.69), "64": (50.88, 5.98), "65": (51.84, 5.86),
    "66": (51.84, 5.86), "67": (51.98, 5.90), "68": (51.98, 5.90), "69": (51.90, 5.98),
    "70": (51.99, 6.56), "71": (51.99, 6.56), "72": (52.15, 6.19), "73": (52.21, 6.19),
    "74": (52.22, 6.89), "75": (52.22, 6.89), "76": (52.26, 6.79), "77": (52.51, 6.09),
    "78": (52.51, 6.09), "79": (52.71, 6.19), "80": (52.51, 6.09), "81": (52.51, 6.09),
    "82": (52.51, 5.47), "83": (52.71, 6.19), "84": (52.90, 5.90), "85": (52.90, 5.90),
    "86": (53.03, 5.66), "87": (53.03, 5.66), "88": (53.20, 5.79), "89": (53.20, 5.79),
    "90": (53.22, 6.57), "91": (53.22, 6.57), "92": (53.22, 6.57), "93": (53.11, 6.56),
    "94": (53.11, 6.56), "95": (53.33, 6.75), "96": (53.33, 6.75), "97": (53.22, 6.57),
    "98": (53.33, 6.92), "99": (53.33, 6.92),
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
        params = {
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

    The daily shape is a half sine between sunrise and sunset, scaled so the
    monthly mean matches the table. This is deliberately crude; its only job is
    to keep the advice available when PVGIS is not.
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
    def _orientation_factor(azimuth_deg: float, tilt_deg: float) -> float:
        nearest = min(
            ORIENTATION_FACTORS,
            key=lambda key: abs(key[0] - azimuth_deg) + abs(key[1] - tilt_deg),
        )
        return ORIENTATION_FACTORS[nearest]

    @staticmethod
    def _day_shape(mean_power: float) -> list[float]:
        """A half sine over the daylight hours, averaging to ``mean_power``."""
        peak = mean_power * HOURS_PER_DAY / FALLBACK_DAYLIGHT_HOURS * (math.pi / 2)
        values = [0.0] * HOURS_PER_DAY
        for offset in range(FALLBACK_DAYLIGHT_HOURS):
            phase = (offset + 0.5) / FALLBACK_DAYLIGHT_HOURS * math.pi
            values[FALLBACK_SUNRISE_HOUR + offset] = peak * math.sin(phase)
        return values


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
