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
