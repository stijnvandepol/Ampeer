# Golden households

Six households with a recorded expected outcome. When a number here changes, the
diff must show it and the change must be deliberate.

`hand_checkable` is the one case small enough to verify with a pencil: a flat
consumption profile, no shiftable block, no assets and no battery. Its expected
value is recomputed from first principles in `tests/test_golden.py` rather than
trusted, which is the only way to catch a mistake in the golden file itself.

The two `marloes` cases are the same household with the same annual driving
need, charged at two different moments. They exist to keep the model honest
about the single most valuable piece of advice the product gives: an electric
car charged on your own surplus is the cheapest home battery you already own.
If the gap between those two rows ever collapses, either the model or the advice
is wrong.

If a case fails, do not widen its tolerance to make it pass. Read the produced
value, decide whether it is plausible for that household, and only then update
this file. A golden file edited to match whatever the code produced is not a
test.

Values were produced with the offline fallback yield table, not with PVGIS, so
the suite runs without a network connection. They are therefore not predictions
about a real roof in that postcode.

## Revised on 2026-08-21

Every self consumption rate moved up by one to five percentage points, and
sander_heat_pump's annual consumption dropped by 22 kWh. Neither is a change in
the engine. The offline yield table was rebuilt from nine weather years instead
of one, and its temperatures now come from the same PVGIS call as its
irradiance rather than from a different station.

The direction is what you would expect and is worth checking rather than
assuming: nine years have a flatter seasonal curve than 2020 alone, so there is
less extreme midsummer surplus and more shoulder season production, and
shoulder season production is the kind a household uses itself. marloes_ev_on_solar
gains the most, from 0.7057 to 0.7572, because charging a car on surplus is
exactly the behaviour a wider production curve helps.

The old table was found to be wrong by the calibration against the measured
national feed-in profile: it put the annual peak in May, where the country peaks
in June, and made November brighter than October. Both were properties of 2020
rather than of the Netherlands.

## Revised on 2026-08-26, engine 0.2.0

Every self consumption rate moved. Five went up by between 0.001 and 0.009 and
`sander_heat_pump` went down by 0.006. Neither the households nor the engine's
rules changed: the offline production model did, in two ways, and the sizes
below say which of the two each household felt.

The daily shape used to run 06:00 to 18:00 in continuous winter time while
solar noon at the location the yield table was measured at is 12:38, so the
whole modelled day sat 38 minutes early. It is now centred on solar noon.
Separately, the shape's peak was scaled by a closed form that integrated a sine
and then sampled it at twelve points, which ran 0.29 percent above the table it
is built from; each hour is now an exact integral and the scaling divides by
what the shape actually sums to.

The two were measured apart rather than attributed by eye, holding the household
fixed and moving the centre back to 12:00:

| household | 0.1.0 | normalisation only | and centred |
|---|---|---|---|
| hand_checkable | 0.9381 | 0.9390 | 0.9391 |
| large_array_small_use | 0.1134 | 0.1136 | 0.1194 |
| marloes_ev_at_night | 0.2557 | 0.2562 | 0.2647 |
| marloes_ev_on_solar | 0.7572 | 0.7587 | 0.7661 |
| rob_fixed_contract | 0.3320 | 0.3327 | 0.3410 |
| sander_heat_pump | 0.5032 | 0.5041 | 0.4977 |

That splits cleanly and the split is the check on it. `hand_checkable` is the
only household with a perfectly flat demand, and it is the only one the centring
barely touches: a flat consumer cannot care what time the sun peaks, so its
whole move is the normalisation, and 0.29 percent less production against an
unchanged absorbed amount is a slightly higher rate. Every household with a
shape to its demand moves on the centring instead, by ten to thirty times as
much as the normalisation gave it.

`sander_heat_pump` is the one that goes the other way, and it is the one worth
reading rather than accepting. He is the only household home during the day, and
his heat pump draws on temperature, which lags sunrise by less than production
does. His demand therefore peaks before solar noon, so moving production 38
minutes later moves it away from him. The direction is the opposite of the other
five for a reason that is a property of the household and not of the change.

The gap between the two `marloes` rows is 0.5014 against 0.5015 before. That
pair is the one this file says must not collapse, and a tenth of a percentage
point is not a collapse: both rows moved up by almost exactly the same amount,
which is what a change to the production model rather than to the advice should
do to two households that differ only in when they charge.

## Not revised on 2026-08-27, engine 0.3.0

Engine 0.3.0 moved the production a visitor is shown by a full hour and not one
number in `households.json` changed. That is worth writing down, because a
golden file that stands still through an engine bump is the shape a stale golden
file also has.

The reason is the sentence four paragraphs up: these six households are computed
with the offline fallback table, on purpose, so that the suite needs no network.
0.3.0 repaired the other provider. PVGIS timestamps its hourly rows in UTC and
the grid runs in continuous winter time, which is UTC plus one, and nothing
converted between them, so hour i of the response was placed at hour i of the
grid and every kilowatt hour on the live path sat an hour early. The fallback
was never on UTC: its day is built around solar noon in winter time, which is
what the 2026-08-26 revision above is about, so there was nothing here to move.

What did move, measured on 2026-08-27 on the reference household of
`tests/test_calibration.py`, 3500 kWh and 3.5 kWp facing south at 35 degrees in
postcode 5401, weather year 2023 and profile year 2025, against a flat
consumption shape:

| | before | after |
|---|---|---|
| self consumption | 28.16 percent | 29.13 percent |
| export | 2583 kWh | 2548 kWh |
| offtake | 2487 kWh | 2452 kWh |
| end of net metering, 2027 tariffs | 665,21 euro | 656,20 euro |

Every one of those moves in the direction the physics predicts. A south facing
array put an hour early peaks at 11:00 instead of 12:00, which is further from
the evening a household is home in, so less of the year's production meets
demand: self consumption falls, and both meter directions rise because the
kilowatt hours that no longer meet each other have to travel. The euro figure
follows the export, which is what the 2027 regime prices.

Two consequences of this file not moving. The check that catches the same error
next time is not here but in `tests/test_calibration.py`, which now runs PVGIS's
own measured hour of the day back through the provider offline. And the golden
answers pinned in `tests/test_golden.py` carry a 0.3.0 row identical to the
0.2.0 one, which is the honest entry rather than a missing one.
