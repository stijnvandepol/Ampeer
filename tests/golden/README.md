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
