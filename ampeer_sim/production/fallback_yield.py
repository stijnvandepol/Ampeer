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
days too short. Real per-day geometry was measured on 2026-08-26 and rejected;
the argument is in ``FALLBACK_DAYLIGHT_HOURS`` in
``ampeer_sim/production/pvgis.py``, which is where the shape lives.
"""

from __future__ import annotations

#: Where the table was measured, in degrees east. The daily shape in
#: ``ampeer_sim/production/pvgis.py`` needs it, because solar noon is a property
#: of a place: reading it from anywhere else would put this table's energy at
#: another location's hours. The latitude is not exported because nothing
#: computes with it; it is 51.66 and the docstring above is its home.
TABLE_LONGITUDE = 5.61

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
#:
#: Measured on 2026-08-26 from the same PVGIS SARAH3 call as the two tables
#: above: Uden, one kWp, zero loss, the nine years 2015 through 2023, one
#: request per plane and nothing changed between them but ``aspect`` and
#: ``angle``. South at 35 degrees came back at 1221.13 kWh per kWp per year,
#: which is the 1221 this module's docstring has claimed since 2026-08-21, so
#: the call is the one the rest of the file describes.
#:
#: Annual kWh per kWp, and the ratio each entry below is rounded from:
#:
#:     south      35   1221.13   1.0000        south  15   1143.23   0.9362
#:     southeast  35   1160.59   0.9504        south  60   1164.33   0.9535
#:     southwest  35   1136.64   0.9308
#:     east       35    979.35   0.8020
#:     west       35    948.91   0.7771
#:     northeast  35    748.97   0.6133
#:     northwest  35    730.26   0.5980
#:     north      35    632.09   0.5176
#:
#: Until that date the six entries here were the published Dutch rule of thumb
#: (south 100, east and west 85, north 62, and 95 against 94 for the two tilts)
#: and not this measurement, which nothing in the file said and the entry in
#: docs/decisions.md assumed the other way round. No reading of the call
#: reproduces them: the ratio of in-plane irradiance rather than of PV output
#: gives 0.8109 for east and 0.5553 for north, and 2020 alone gives 0.8141 and
#: 0.5103. The rule of thumb also has the two tilts the wrong way round, since
#: 60 degrees beats 15 here and the table said the reverse.
#:
#: Each mirrored pair carries the mean of the two measurements rather than the
#: two figures. The table is symmetric by construction, which
#: ``tests/test_pvgis_provider.py`` holds it to, and the measured asymmetry is
#: real but small: east beats west by 3.2 percent, northeast beats northwest by
#: 2.6 percent, southeast beats southwest by 2.1 percent. Splitting the pairs
#: would model the country's morning cloud out of one location's nine years,
#: which is more than a table of ten numbers can carry honestly.
#:
#: Southeast and southwest are here for the same reason northeast and northwest
#: are: without a row of their own the nearest-entry search ties them between
#: south and east, and the tie went to south, so a southeast roof was priced as
#: a south one. All eight directions the form can send now hit an entry rather
#: than a tie.
ORIENTATION_FACTORS: dict[tuple[int, int], float] = {
    (0, 35): 1.00,
    (-45, 35): 0.94,
    (45, 35): 0.94,
    (-90, 35): 0.79,
    (90, 35): 0.79,
    (-135, 35): 0.61,
    (135, 35): 0.61,
    (180, 35): 0.52,
    (0, 15): 0.94,
    (0, 60): 0.95,
}
