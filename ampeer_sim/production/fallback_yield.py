"""Offline yield table, used when PVGIS is unreachable.

Provenance: derived on 2026-08-21 from PVGIS SARAH3 for Uden (51.66, 5.61), a
plane at 35 degrees facing south, averaged over the nine weather years 2015
through 2023, one kWp with the system loss set to zero. Annual total is 1221 kWh
per kWp before losses.

Nine years rather than one, and the difference matters. The first version of
this table averaged 2020 alone, which put the annual peak in May and made
November brighter than October. Both are real properties of that year and
neither is a property of the Netherlands. The calibration against the measured
national feed-in profile found the May peak: the country peaks in June, and a
fallback that disagrees about which month is sunniest is not a fallback, it is a
different climate.

The temperatures come from the same call, so the fallback no longer mixes PVGIS
irradiance with a temperature series from another station.

Remaining weakness, acceptable for something whose only job is to keep the
advice available when PVGIS is not: the daily shape is a half sine of fixed
length rather than real solar geometry, so winter days are too long and summer
days too short.
"""

from __future__ import annotations

#: Monthly mean production in W per installed kWp, before system losses.
MONTHLY_MEAN_PRODUCTION_W_PER_KWP = (
    52.1,
    98.0,
    141.7,
    195.1,
    209.4,
    209.7,
    197.0,
    188.6,
    163.7,
    102.0,
    70.9,
    42.5,
)

#: Monthly mean outdoor temperature in degrees Celsius, from the same PVGIS call
#: as the production above, so irradiance and temperature describe one place and
#: one set of years rather than two.
MONTHLY_MEAN_TEMPERATURE = (
    4.0,
    4.6,
    6.6,
    9.5,
    13.9,
    18.3,
    19.1,
    19.3,
    16.0,
    12.3,
    7.6,
    5.7,
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
