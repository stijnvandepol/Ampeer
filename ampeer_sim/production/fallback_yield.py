"""Offline yield table, used when PVGIS is unreachable.

Provenance: derived on 2026-08-20 from a real PVGIS SARAH3 series for Uden
(51.66, 5.61), a plane at 35 degrees facing south, weather year 2020, with the
system loss divided out again. Annual total is 1248 kWh per kWp before losses.

Two known weaknesses, both acceptable for something whose only job is to keep
the advice available when PVGIS is not:

- It is one year at one location, so it carries that year's weather. October
  2020 was unusually dull and November unusually bright, which is why the two
  months look inverted. That is the data, not a typo.
- The daily shape is a half sine of fixed length rather than a real solar
  geometry, so winter days are too long and summer days too short.

Replace this with a PVGIS typical meteorological year once that is ingested.
"""

from __future__ import annotations

#: Monthly mean production in W per installed kWp, before system losses.
MONTHLY_MEAN_PRODUCTION_W_PER_KWP = (
    45.6,
    67.2,
    164.4,
    245.1,
    243.4,
    203.2,
    186.7,
    192.6,
    170.6,
    72.4,
    77.1,
    40.2,
)

#: Monthly mean outdoor temperature in degrees Celsius, De Bilt long-term average.
MONTHLY_MEAN_TEMPERATURE = (
    3.6,
    3.9,
    6.5,
    9.8,
    13.4,
    16.2,
    18.3,
    17.9,
    14.8,
    11.0,
    7.0,
    4.2,
)

#: Relative yield of a plane compared with south at 35 degrees.
ORIENTATION_FACTORS: dict[tuple[int, int], float] = {
    (0, 35): 1.00,
    (90, 35): 0.85,
    (-90, 35): 0.85,
    (180, 35): 0.62,
    (0, 15): 0.95,
    (0, 60): 0.94,
}
