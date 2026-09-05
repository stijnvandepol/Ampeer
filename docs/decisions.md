# Decisions taken under delegation

Stijn delegated design authority for this work on the condition that every
choice and its reason is written down, so that he can read it back afterwards
and reverse it. The reasons live in the commit messages, which is the right
place for them: they sit beside the diff that carries the change.

What they do not give is a way to find them. Twenty-seven commits on one branch
hold roughly ten decisions and seventeen findings, and telling those apart means
reading all of them. This file is the index. It holds no argument that the
commit does not already make; it says what was decided, where it lives, and what
undoing it costs.

It is not a task list and not a changelog. A finding, where the project stated a
rule and nothing enforced it, is not a decision and is not here. Those are in the
history under their own subjects.

## How to read an entry

**Decided** is the choice. **Because** is the short form of the argument, with
the commit holding the long one. **Lives in** is the file that carries it today,
which is what makes an entry checkable: `tests/test_decisions.py` asserts every
one of those paths exists, so a rename cannot quietly leave this file pointing
at nothing. **To reverse** is what it costs, honestly, including the cases where
it is more than one edit.

## The decisions

### 1. A household is addressed as "u", on every surface it reads

**Decided:** the advice texts, the API validation messages, the interface and
`docs/methodologie.md` all use "u" and "uw".

**Because:** Dutch has two registers and a product has to pick one. Both were in
use: an answer said "U levert een groot deel van uw opwek terug" beside "het
verlies in je installatie", and the methodology, which the site serves as a page
of itself, was on "je" for six hundred lines. Which register is a matter of
taste; using both in one reading session is not.

**Lives in:** `tests/test_advice_nl.py`, in the constant `ADVICE_REGISTER`.

**To reverse:** change that constant to "je" and the test names every string
still on the old form, so the work is mechanical but not small. The methodology
was 165 edits and most were not substitutions, because Dutch changes the verb
form in inversion between the two registers.

### 2. Exactly one module may open an outbound connection

**Decided:** `ampeer_sim/production/pvgis.py` is the only file in the Python
source allowed to import a network client, and a test pins that set to one.

**Because:** the project rules out server side request forgery as a category
rather than case by case, and the way to keep a categorical rule true is a
categorical check. Judged on the import rather than on a call, because a module
that imports requests can reach outward on any line added later.

**Lives in:** `tests/test_boundaries.py`, in `OUTBOUND_MODULE`.

**To reverse:** add the second module to that constant. Doing so is the point at
which somebody has to say why the backend now fetches.

### 3. The external allowlist is a module constant, not a settings entry

**Decided:** the one permitted host lives as `PVGIS_URL` in the module that
fetches it, with the test pinning the host, rather than in Django settings.

**Because:** `CLAUDE.md` asks for an allowlist "fixed in config", and a
configuration layer that exactly one caller reads hides where a value comes from
instead of showing it. Two of the three permitted sources, ENTSO-E and KNMI, are
not fetched at all today. A second real source is what makes the config question
worth answering.

That second source turned up on 2026-08-23, and it did not change the answer.
`tools/ingest_profiles.py` fetches the NEDU profiles from a fourth host, and it
too holds its URL as a module constant beside the code that uses it. The
allowlist in the test now maps each outbound module to the hosts it may reach,
which keeps the value visible in both places rather than moving either into a
settings layer that two callers would read.

**Lives in:** `tests/test_boundaries.py`, in `OUTBOUND_MODULES`.

**To reverse:** move the host into settings and have the test read it from
there. The check itself does not change shape.

### 4. The readiness endpoint is the only route without a rate limit

**Decided:** every route the resolver serves must name a throttle scope that has
a rate, except `api/advice/health/`, which switches its throttles off
explicitly.

**Because:** DRF answers a view with no `throttle_scope` without any limit at
all, silently. The health check runs every thirty seconds and its throttle
counter lives in Postgres in production, so leaving it on turns the check into
the database query it exists to avoid. Requiring the exemption to be written as
`throttle_classes = ()` is what keeps a deliberate exemption from looking like an
attribute somebody forgot.

**Lives in:** `tests/test_backend_settings.py`, in `UNTHROTTLED_ROUTES`.

**To reverse:** remove the entry and give the health view a scope with a rate
generous enough for the probe interval.

### 5. The type checker reads the tests

**Decided:** `mypy` runs over `tests` as well as the three source trees.

**Because:** `CLAUDE.md` makes type hints mandatory in Python, ruff and its
formatter already covered the tests, and mypy was the one that did not. Sixty
three files were checked where a hundred and six exist. It found fourteen
errors, two of which were annotations describing a shape the code had stopped
having.

**Lives in:** `.github/workflows/ci.yml`, `scripts/gates.sh`, and the
`GATE_FRAGMENTS` table in `tests/test_pipeline_contract.py` that keeps them
equal.

**To reverse:** drop `tests` from all three. The contract will not let you drop
it from one.

### 6. Shell scripts are linted, and shellcheck arrives as a Python package

**Decided:** `shellcheck` runs over every tracked `.sh` file, installed as
`shellcheck-py` through `uv add` and pinned in `uv.lock`.

**Because:** nothing looked at 945 lines of shell, two of which decide whether
anything else can be trusted: the local gate runner and the backup that runs
against the production database. The alternative was the copy preinstalled on
`ubuntu-latest`, which is a version that can change under us and turn CI red
without a commit.

**Lives in:** `pyproject.toml`, in the `dev` dependency group.

**To reverse:** remove the dependency and the three command sites. The finding
it caught, an unguarded `cd` in the gate runner, should be kept either way.

### 7. The security scanner does not read the tests, and the reason is recorded

**Decided:** `bandit` keeps excluding `tests`, with the measurement written
beside the exclusion.

**Because:** it reports 1210 assert_used findings there, one per assertion, and
41 hardcoded password hits that are all fixture tokens. A scan that noisy is one
nobody reads. What the tests get instead is ruff, mypy and gitleaks.

**Lives in:** `pyproject.toml`, in `[tool.bandit]`.

**To reverse:** remove `tests` from `exclude_dirs` and expect to add
suppressions for every assertion in the suite.

### 8. Moving a model constant means moving the engine version

**Decided:** `ENGINE_VERSION` is pinned to the twenty three default values in
`ampeer_sim` and to the twelve expected values of the golden households.

**Because:** every stored advice records which engine produced it, and that
answer is only worth anything if the version moves when the numbers do. It was a
hand written string that nothing forced.

**Lives in:** `tests/test_golden.py`.

**To reverse:** delete the two pins. Keeping them means a tariff revision costs
a version bump and a row in the table, which is friction on purpose.

### 9. One payback tolerance for all golden households, and it may only fall

**Decided:** every golden household carries the same
`MAX_PAYBACK_TOLERANCE_YEARS`, currently 0.25, and raising it means editing a
test rather than a data file.

**Because:** the figure used to sit per household beside the value it guards, so
widening one was a one character edit in a data file and the diff looked like a
golden file being updated, which legitimately happens.

**Lives in:** `tests/test_advise.py`.

**To reverse:** put the tolerances back in the data file. The rule that it may
fall and not rise follows the coverage floor in `pyproject.toml`.

### 10. The plans were marked delivered rather than having their boxes ticked

**Decided:** each of the six plans carries a status note saying it is delivered,
and none of the 288 checkboxes was ticked.

**Because:** every checkbox is a claim that a specific step was carried out, and
several are "run the test and watch it fail", which cannot be verified after the
fact. Writing them in would be manufacturing a record. What is checkable is that
every file the plans name is in the tree, and that is what the note points at.

**Lives in:** `tests/test_plans.py`.

**To reverse:** tick them, and accept that the ticks assert more than anything
can check.

### 11. A tariff set that says two things is refused, not read halfway

**Decided:** `annual_cost` raises when a `TariffSet` carries both `dynamic` and
`net_metering`, instead of taking the dynamic branch and dropping the netting
the way its if/elif did until 2026-08-23.

**Because:** the combination is not a caller's mistake. Saldering applies
whatever the contract until 1 January 2027, so for a 2026 household on a
dynamic contract it is the accurate description, and the flag was accepted and
then ignored without a word. The term is not small: measured on a household
taking 3500 kWh and feeding in 2600, exporting around midday and taking off in
the evening peak, the two readings of that one tariff set are 870 euro apart,
and the silent one is the higher, which is the direction that inflates the very
shock this product exists to quantify. Choosing the other branch instead would
be inventing an answer, because netting settles a volume over a year and the
dynamic path settles 35040 quarters, and which of those prices the netted
residual is worth is written in a supplier's terms rather than derivable here.

Nothing reaches this today. `backend/advice/assembly.py` keeps
`TariffSet.dynamic` False on every set it builds and models a dynamic contract
by its average net price, so no household is affected either way. It matters
because ENTSO-E is on the allowlist and pricing against a real series is the
obvious next use of this function.

**Lives in:** `ampeer_sim/economics/tariffs.py`, with three tests in
`tests/test_tariffs.py`: the refusal, a floor that each flag alone still
prices, and a floor that the dropped term is worth refusing over.

**To reverse:** decide which price settles the netted residual, cite it, and
implement the branch. Deleting the raise without doing that puts the silent
number back.

### 12. The monthly calibration ceiling is 0.03, and it was fitted rather than copied

**Decided:** `MAX_MONTHLY_GAP` in `tests/test_calibration.py` moves from 0.05 to
0.03. `MAX_HOURLY_GAP` stays at 0.05.

**Because:** both stood at 0.05 and only one of them was ever fitted to
anything. Measured on 2026-08-23 against the reference household: the worst
monthly bucket is July at 0.0230 and the worst hourly one is 17:00 at 0.0490. So
the hourly ceiling sat a fifth of a percentage point above the disagreement it
measures, and the monthly one sat at more than twice it, which is a ceiling a
regression does not have to get past. Shown rather than argued: modelling July
at 185 W per kWp instead of 197 pushes the worst monthly bucket to 0.0321, which
the new ceiling refuses and the old one waved through.

The file's own comment already says these may be tightened and must never be
widened, so the direction is the one it invites. 0.03 is the measured 0.0230
with room for ordinary movement and not much more.

**Lives in:** `tests/test_calibration.py`.

**To reverse:** raise the constant, which the comment above it forbids without
a reason recorded here.

### 13. The evening calibration test watches the worst bucket, not one chosen hour

**Decided:** `test_the_modelled_export_stops_earlier_in_the_day_than_the_country
_does` asserts over every hour from 15:00 onward and pins the worst of them,
instead of asserting on 18:00 alone.

**Because:** the test is named for the model's afternoon collapse and its
docstring says it is pinned so that a growing gap is found by a red test rather
than by a reader. It watched 18:00, where the gap is 0.0295 against a ceiling of
0.05. The decline peaks an hour earlier, at 17:00 and 0.0490. So the named test
had 41 percent of headroom while the same disagreement ran within two percent of
the ceiling in the bucket next door.

Shown rather than argued: shortening the fallback daylight window from twelve
hours to ten moves the worst afternoon bucket to 16:00 at 0.0852. The new form
is red on that and the old form is green.

No threshold moved. This only changes which bucket the threshold is applied to.

**Lives in:** `tests/test_calibration.py`.

**To reverse:** narrow the slice back to one hour, and accept that the test no
longer watches the peak of what it is named for.

### 14. The validation CLI refuses a statement it cannot honour

**Decided:** `load_statement` in `ampeer_sim/validate.py` raises on any field
outside `REQUIRED_FIELDS`, and reports missing and unknown fields in one
message. `main` prints on every run that it modelled a household with no
electric car and no heat pump.

**Because:** `check` has no way to model either, and every key it did not
recognise used to be dropped without a word. So a statement saying
`"heat_pump_kwh": 12000` produced a clean two line comparison against a
household that is not the one on the statement, and a typo in a field name was
indistinguishable from a field ignored by design: raising on the missing field
alone named the absence and never the typo that caused it.

It matters because of where it sends the reader. Measured on 2026-08-23 with a
flat profile, on a household of 6969 kWh of which 3469 is a heat pump: offtake
comes out 8.4 percent low and feed-in 23.2 percent low, against a default
tolerance of 10 percent. The feed-in line reads OFF, and somebody then goes
looking in the production model, which is not where the problem is. A validation
tool that points at the wrong subsystem is worse than one that refuses to run.

The note is printed unconditionally because the tool has no field to read. That
is the whole point: a household with a heat pump cannot say so, so the only
honest moment to mention it is always.

**Lives in:** `ampeer_sim/validate.py`, with four tests in
`tests/test_validate.py`.

**To reverse:** drop the unknown check, and accept that a statement describing
something the model ignores reads as a clean run. Anyone holding a statement
file with extra keys in it will see an error where they saw a comparison; that
is the intended effect and not a migration problem, since the comparison was
about a different household.

### 15. The wall clock budgets run outside the coverage invocation

**Decided:** `test_an_advice_arrives_within_a_second_once_production_is_cached`
carries a `perf` marker. `scripts/gates.sh` and the `test` job in
`.github/workflows/ci.yml` now run `pytest -m "not perf" --cov` and then
`pytest -m perf` with no coverage, and both report in every branch. The budget
itself is untouched at one second.

**Because:** it measured the promise divided by the profiler. Measured on
2026-08-24 over the whole suite, that request takes 0.58s uninstrumented and
1.62s under coverage, against a budget of 1.0s. So the check sat on its own
boundary and flipped: 1.129s and red on one run, green on the next, on the same
commit and the same machine. In isolation it passed every time either way,
which is why it read as noise rather than as a check measuring the wrong thing.

Two reasons that is worth a change rather than a retry. The budget is a promise
about what a visitor experiences and a visitor does not run coverage, so
instrumented it was roughly three times stricter than the sentence it
documents. And a gate that changes verdict while the code stands still teaches
people to re-run until green, which is the one habit that makes every other
gate here worthless.

Relaxing the budget was never a candidate: the file says it may be measured but
never relaxed, and a slower promise is a different product. Splitting the run
cost nothing measurable either, since coverage stayed at 98.88 percent against
a floor of 98, the perf test having exercised no line the rest of the suite
does not.

**Lives in:** `tests/test_advice_api.py` for the marker,
`scripts/gates.sh` and `.github/workflows/ci.yml` for the two invocations,
`pyproject.toml` for the marker's registration and the measurement behind it,
and `tests/test_pipeline_contract.py`, which holds the runner and the workflow
to the same two commands.

**To reverse:** drop the marker, merge the two invocations back into one in
both the runner and the workflow, and replace the two `GATE_FRAGMENTS` entries
with the single one they came from. The flake comes back with it, and on a
slower runner than this one it will be the common case rather than the
occasional one.

### 16. The offline yield table is a measurement, and it has a row for all eight directions

**Decided:** every entry of `ORIENTATION_FACTORS` is the ratio to south at 35
degrees measured from PVGIS SARAH3 over 2015 through 2023, and northeast,
northwest, southeast and southwest have rows of their own. Five of the eight
directions the form can send moved, all downwards: north 0.62 to 0.52, east and
west 0.85 to 0.79, northeast and northwest 0.85 to 0.61, southeast and southwest
1.00 to 0.94.

**Because:** the open entry this replaces asked for two more rows "derived from
the same PVGIS SARAH3 call over 2015 through 2023 that the rest of the table
came from". The measurement was taken and the premise turned out to be false:
the rest of the table did not come from that call. South at 35 reproduces
exactly, 1221.13 kWh per kWp against the 1221 the module has claimed since
2026-08-21, and nothing else does. PVGIS gives east 0.8020 where the table said
0.85 and north 0.5176 where it said 0.62, and no other reading of the same call
closes the gap: in-plane irradiance instead of PV output gives 0.8109 and
0.5553, and 2020 alone gives 0.8141 and 0.5103. The six values are the published
Dutch rule of thumb, which also has the two tilt entries the wrong way round,
since 60 degrees beats 15 at this latitude and the table said the reverse.

That is what forced the scope. A measured northeast is 0.61 and the unmeasured
north was 0.62, so adding only the two rows the entry asked for would have left
the table saying a northeast roof is worse than a north one. Southeast and
southwest are in for the same reason northeast and northwest are: they sat on
the same kind of tie, the tie went to south, and a southeast roof was priced as
a south roof. Mirrored pairs carry the mean of the two measurements rather than
the two figures, because the table is symmetric by construction and the measured
asymmetry, 2 to 3 percent, is one location's nine years of morning cloud.

**Lives in:** `ORIENTATION_FACTORS` in
`ampeer_sim/production/fallback_yield.py`, with the kilowatt hours each entry is
rounded from written above it, and three tests in
`tests/test_pvgis_provider.py`: the eight factors, that each step around the
compass away from south costs something, and that no whole azimuth lands on a
tie.

**To reverse:** put the rule of thumb back and give northeast and northwest its
0.70. That is a defensible table; it is not this call, and the file should then
stop saying it is.

### 17. The fallback's day is centred on solar noon, and is not lengthened

**Decided:** the offline daily shape is a half sine centred on 12:38 in
continuous winter time, solar noon at the location the yield table was measured
at, instead of on 12:00. It keeps its twelve hour length. `MAX_HOURLY_GAP` in
`tests/test_calibration.py` comes down from 0.05 to 0.04.

**Because:** the open entry this replaces recorded the worst hourly calibration
bucket at 0.0490 against a ceiling of 0.05 and asked for a better evening tail.
Most of that gap was not the shape's length but its placing: the window ran
06:00 to 18:00 while the sun at 5.61 degrees east peaks at 12:38, so the whole
modelled day sat 38 minutes early. Centring it moves the worst hourly bucket to
0.0333 and quadruples what the model exports at 17:00, from 0.0061 of the year
to 0.0234, for 0.0003 on the worst monthly bucket.

The longer day was measured and refused, and that is the part worth recording.
Widening to 13.28 hours, the mean day length weighted by the energy each day
carries, scores better against the national feed-in profile on both families,
0.0299 hourly and 0.0218 monthly. It scores worse against the thing this shape
stands in for. PVGIS's own hour of the day for this plane, over the same nine
years, is 0.0759 away from the twelve hour shape and 0.1576 away from the wider
one, summed over the 24 hours. The national profile is wide because it averages
every roof orientation in the country, which `tests/test_calibration.py` says in
as many words, and this shape describes one south facing plane, so fitting to it
would have made every test in the suite greener while the model moved away from
the physics. A shape whose length follows the season was refused outright: it
puts the worst monthly bucket at 0.0389, over its ceiling.

The ceiling comes down because 0.04 refuses the shape that was here, whose
0.0490 passed under 0.05 for a year, and because against the real NEDU
consumption profile rather than the flat one the committed test composes, that
shape scored 0.0518 and was already over.

This entry and the one above it are why `ENGINE_VERSION` moved to 0.2.0.
Decision 8 says the version moves when the numbers do, and both moved them:
every golden household's self consumption rate changed, five up and one down,
and `tests/golden/README.md` separates the two causes household by household.
It has since moved again, to 0.3.0, for the reason in decision 19.

**Lives in:** `FALLBACK_SOLAR_NOON_HOUR` and `FALLBACK_DAYLIGHT_HOURS` in
`ampeer_sim/production/pvgis.py`, with both measurements above them;
`PVGIS_HOUR_OF_DAY_WINTER_TIME` in `tests/test_pvgis_provider.py`, which is the
24 shares the second measurement is made against; and `MAX_HOURLY_GAP` in
`tests/test_calibration.py`.

**To reverse:** centre the shape on 12:00 again. The suite goes red in seven
places rather than one, which is the intent: the calibration ceiling, the
afternoon bucket, the evening floor and four checks in the provider tests all
name it.

### 18. The API's validation messages moved into a language layer of their own

**Decided:** the nine Dutch validation messages in
`backend/advice/serializers.py` move to a new `backend/advice/nl.py`, keyed by
an English id, and the serializers name the id. Not one of them was reworded.

**Because:** CLAUDE.md says Dutch text never sits hardcoded in the logic and
that what a reader sees lives in a layer keyed by an English id, so the rule
table stays language free. Six of these sentences sat in the same tuples as the
field names they govern, which made the table that decides what a form refuses
also the copy deck: a reword and a change of behaviour were edits to the same
lines. `ampeer_advice/nl.py` cannot take them, since that package must not know
an HTTP form exists and "onbekend veld" means nothing without the request that
carried the field. That is why this is a second language layer and not a move
into the first.

This was left open in the previous round because changing what a visitor reads
is not a delegate's call. Relocating is not changing, and that distinction is
checkable rather than promised: every message is byte for byte the string the
API answered before, three of them asserted verbatim in `frontend/tests` and
one in `tests/test_advice_api.py`, with the other five read back out of the
serializer the way a client reads them.

What is gained beyond tidiness is a check where there was none. The repo-wide
Dutch scan skips any file named nl.py and carried this one file as its named
exception, so the rule was agreed for it and enforced nowhere. That exception is
gone and `DUTCH_OUTSIDE_NL` in `tests/test_advise.py` is now empty.

Updated on 2026-08-27, and every correction runs the same way: this entry
claimed a property of the package and had checked one file.

The move was ten messages and not nine. `backend/advice/parsers.py` held "de
JSON is te diep genest" throughout, and it is now
`VALIDATION_MESSAGES["TOO_DEEPLY_NESTED"]` with the parser naming the id. It was
missed because the paragraph above is true of `serializers.py` and was read as
true of `backend/advice`, which is the same substitution twice: the scan that
was supposed to catch it read one named path.

So the boundary is enforced by a walk of `backend/advice` as of 2026-08-27,
twenty modules rather than one, and a third module joins by importing the
language layer rather than by being added to a list. The categorical allowlist
scan deliberately stayed on `serializers.py`: widened package-wide it would have
to admit forty-five JSON keys, some SQL fragments and the English constraint
messages, and an allowlist wide enough for those is wide enough for a Dutch
sentence.

And the empty `DUTCH_OUTSIDE_NL` was empty for two reasons, only one of which
was the good one. Run over the whole package before the message moved, the
widened scan still reported nothing, because its word list carried three of the
four Dutch articles and not the fourth. "de" and "te" were added that day, and
measured before adding they cost no false positive anywhere in the four scanned
trees. The honest price is written where the list is: `\b` treats a hyphen as a
word boundary, so an English "de-rate" written in those trees later is a false
positive. That the widening alone would not have caught this is the part worth
carrying forward, because "we widened the scan" is exactly what the previous
round reported.

The verbatim count in the paragraph above is also wrong and is left standing as
written, with the counted figures here: on 2026-08-27 `frontend/tests` asserts
two distinct messages and `tests/test_advice_api.py` asserts two, one of which
is the same message counted in both. The old sentence double counted.

**Lives in:** `backend/advice/nl.py`, in `VALIDATION_MESSAGES`, with the two
scans over the serializer source in `tests/test_advice_serializers.py`, whose
`_advice_modules` is the walk that replaced the named path.

**To reverse:** type the strings back at their call sites, delete the module
and the scans, and put the exception back in `tests/test_advise.py`. The
messages themselves survive either way, which was the condition for making the
move at all.

### 19. The PVGIS series is converted to winter time in the provider, not in the model

**Decided:** `PvgisProvider.hourly_series` rotates both the production and the
temperature column forward by `UTC_TO_WINTER_TIME_HOURS`, which is 1.
`production_series` is untouched and still places hour i at hour i.
`ENGINE_VERSION` moves to 0.3.0.

**Because:** PVGIS timestamps its hourly rows in UTC and `YearGrid` runs in
continuous winter time, which is UTC plus one, and nothing converted between
them, so the path a visitor normally gets placed every kilowatt hour a full hour
early. Measured on 2026-08-27 on the reference household of
`tests/test_calibration.py`, 3500 kWh and 3.5 kWp facing south at 35 degrees in
postcode 5401, weather year 2023: self consumption 28.16 percent against 29.13,
export 2583 kWh against 2548, offtake 2487 against 2452, and 665.21 euro against
656.20 for the end of net metering under the 2027 tariffs. Nine euro, and in the
direction that flatters storage, which is the bias this product exists against.

The provider and not the model, for three reasons that all point the same way.
"PVGIS stamps in UTC" is a fact about PVGIS and this is the module that knows
about PVGIS. `production_series` receives a bare array of watts per kWp with no
idea which source produced it, so a shift there would have to be told, and being
told means every call site carrying an answer that belongs to one provider. And
it would move the offline shape too, which decision 17 centred on 12:38 winter
time only the day before, putting it 38 minutes past solar noon instead of on
it. So the contract is that every provider answers on the grid's time base, and
only one of them has converting to do.

The wrap was chosen over a fill and the reason is measurable. A rotation drops
nothing and invents nothing, so PVGIS's annual total survives to the last digit;
what it does is put 31 December 23:00 UTC, which is midnight winter time, at the
grid's 1 January 00:00, strictly the following year's hour rather than this
one's. Measured on the same call: PVGIS puts 0.0 W per kWp there and 0.0 W at
the hour it displaces, because the sun is below the horizon at midwinter
midnight whatever the weather did.

None of the six golden households moved, and that is the finding rather than an
omission: they run on `FallbackProvider` so the suite needs no network, and the
fallback was already in winter time. That is exactly why the defect survived a
year, and it is why the version bump below arrives with an identical golden row
rather than a new one. `tests/test_calibration.py` now runs PVGIS's own measured
hour of the day back through the provider offline, so the primary path has a
check at last.

What did move outside the engine, all of it re-derived on 2026-08-27 rather than
assumed: `frontend/tests/fixtures/advice-response.json` was regenerated and one
line changed in it, the version; chapters 6 and 7 of `docs/methodologie.md`; and
nothing at all in `docs/analysis/2026-08-24-double-counting.md`, whose euro
columns were recomputed on both sides of this change and came back identical to
three decimals because they rest on `FallbackProvider`.

**Lives in:** `UTC_TO_WINTER_TIME_HOURS` in `ampeer_sim/production/pvgis.py`,
with the measurement above it; four tests in `tests/test_pvgis_provider.py`;
`MAX_HOUR_OF_DAY_GAP` and two placement tests in `tests/test_calibration.py`;
and `test_the_model_places_hour_i_at_hour_i_and_moves_nothing_in_time` in
`tests/test_production_model.py`, which pins the half that stayed put.

**To reverse:** set the constant to 0. Six tests go red and two of them print
the distance from PVGIS's own day, 0.2698 against a ceiling of 0.05, and the
hour the year peaks in, 11:00 against a solar noon of 12:38.

### 20. Every module level constant in ampeer_sim is pinned to the engine version

**Decided:** `tests/test_golden.py` gains
`test_the_module_constants_are_pinned_to_the_engine_version`, which parses each
`ampeer_sim` module's own source for module level upper case assignments and
pins a digest of each value. It carries one row, 0.3.0.

**Because:** a review on 2026-08-26 found decision 8's enforcement reads
dataclass field defaults only, and the values that actually decide a household's
answer mostly are not dataclass defaults. Measured on 2026-08-27: 44 module
level constants were unpinned, among them `ORIENTATION_FACTORS`,
`MONTHLY_MEAN_PRODUCTION_W_PER_KWP`, `FALLBACK_SOLAR_NOON_HOUR`,
`DEGRADATION_PER_YEAR` and `_POSTCODE_CENTROIDS`. The size of the hole is
visible in the pin itself: three engine versions now carry an identical
dataclass row while the numbers underneath moved twice, at 0.2.0 and again at
decision 19.

Found by parsing each file rather than by walking `dir()`, because a `dir()`
walk cannot tell a constant a module defines from one it imports and would make
moving an import look like a constant moving. Pinned as a digest rather than as
the value because four of the 44 are tables and `_POSTCODE_CENTROIDS` reprs to
1873 characters; the failure message reads the live value back out of the
module, so the half a reader needs is still named.

One row and not three. The values these names held at 0.1.0 and 0.2.0 were
never recorded, and reconstructing them from the history to fill the table in
would be manufacturing a record of a check that did not run, which is the
argument decision 10 already makes about the plan checkboxes.

**Lives in:** `_engine_module_constants` and `_live_constant_values` in
`tests/test_golden.py`.

**To reverse:** delete the test. Moving a table, a threshold or a location in
`ampeer_sim` then stops costing a version bump again, which is the friction
decision 8 is for.

### 21. The PVGIS series' last twenty minutes, stated and then repaired

**Decided:** on 2026-08-27, that `PvgisProvider` keeps its whole hour rotation
and the twenty minutes it cannot reach is written down with what it costs rather
than resampled away. On 2026-08-29 the repair this entry named in its own To
reverse was carried out instead: the anchor is an argument on
`YearGrid.hourly_to_quarters`, `production_series` hands it PVGIS's stamp, and
`ENGINE_VERSION` moved to 0.4.0.

Both halves are kept because the second rests on the first. The measurement
below is what ruled out the two repairs that looked cheaper, and it is why the
anchor was the only place left to put it.

**Because:** PVGIS stamps a row ten minutes past the hour and
`YearGrid.hourly_to_quarters` anchors an hourly value half past, so the series
sits twenty minutes late and no whole rotation can move it by a third of an
hour; n=1 is already the smallest displacement available. Measured on
2026-08-27 against a live SARAH3 call on the reference household: 29,13 percent
self consumption and 656,20 euro against 28,71 and 660,12 correctly placed, so
0,42 points and 3,92 euro, understating the shock.

The ten past belongs in the anchor and nowhere else, and that was measured
rather than reasoned. Resampling in the provider means interpolating twice, and
the second low pass flattens the midday peak into self consumption, giving
650,71 euro, off by 9,41 against the 3,92 it was correcting. A Catmull-Rom
resample keeps the peak, still misses by 1,92, and puts 904 of 8760 hours below
zero. Placing it at the anchor costs nothing in smoothing because it replaces
the interpolation the model already performs, and it is one argument on
`YearGrid.hourly_to_quarters` plus its two call sites in
`ampeer_sim/production/model.py` and `ampeer_sim/profiles/assets.py`. Shipping a
correction measurably further from the truth than the defect is the one thing
this project's rules rule out, so the residual is written down with its price
instead.

Two things fell out of measuring it. The distance `tests/test_calibration.py`
records is small for the wrong reason: its comment claimed all of it was the
hour-to-quarter interpolation, and placing the same series on its own stamps
turns 0,0171 into 0,0904, because the metric buckets on the hour while the
reference rows carry ten past, so the lag cancels against it. Whoever repairs
the placement has to re-found that comparison or it will call the repair a
regression. And the reading the residual rests on is corroborated rather than
asserted: split at solar noon, PVGIS's hour-of-day table gives morning over
afternoon 1,065 read at the stamp and 0,889 read as an hour mean, while the same
call gives east 979,35 against west 948,91 kWh per kWp. Only the stamp reading
agrees with the yield table, and it is also the smaller of the two corrections.

What the prediction cost, since it was made here: all three consequences it
named arrived. `MAX_HOUR_OF_DAY_GAP` did read 0,0904 and call the repair a
regression, and the fault was in the ruler rather than in the series: a PVGIS
row speaks for the hour centred on its stamp, so `_modelled_hour_of_day` now
integrates over `[4k - 1,333, 4k + 2,667)` instead of over clock hours, and the
distance came back under the 0,02 ceiling without the ceiling being touched. The
0,0171 that stood before any of this was two errors of opposite sign.

**Lives in:** `HOURLY_MEAN_ANCHOR_MINUTES` and the `anchor_minutes_past_hour`
argument in `ampeer_sim/timebase.py`, `PVGIS_STAMP_MINUTES_PAST_HOUR` in
`ampeer_sim/production/pvgis.py`, the default in
`ampeer_sim/production/model.py`, `test_the_pvgis_series_sits_where_pvgis_stamped_it`
in `tests/test_pvgis_provider.py`, `_modelled_hour_of_day` in
`tests/test_calibration.py`, and chapter 7 of `docs/methodologie.md`.

**To reverse:** return the model's default to the grid's neutral anchor. The
series goes twenty minutes late again, which
`test_the_pvgis_series_sits_where_pvgis_stamped_it` prices in its last two
assertions rather than merely refusing, and `ENGINE_VERSION` moves because every
household's answer does.

### 22. The Dutch boundary is enforced by listing the English, not by guessing the Dutch

**Decided:** every non-docstring string literal in `backend/advice` except
`nl.py` that reads as prose must consist entirely of words in
`ENGLISH_PROSE_WORDS`. Whether a literal is prose is decided by shape, in
`PROSE_RULE`, which the failure message prints verbatim.

**Because:** decision 18 has now been corrected twice and falsified twice. The
wordlist half could not work in principle: a list of the words of the language
being excluded has to be finished before the next sentence is written. On
2026-08-27 a review demonstrated it in one line, adding
`SERVICE_UNAVAILABLE_MESSAGE = "Aanvraag mislukt, probeer straks opnieuw"` to
`advice/views.py`; the wordlist held none of its five words and the categorical
scan was still bound to `serializers.py` by name, so both guards passed.
Inverting the vocabulary removes the guess. CLAUDE.md sends everything a visitor
reads to a language layer, so what is left behind is only what an operator or a
developer reads, and that is closed and small: measured on 2026-08-27, 26 prose
literals holding 110 distinct words, all of them SQL, `manage.py` output, or an
internal error message.

Entry 18's argument for keeping the categorical scan on one file was that an
allowlist wide enough for the 45 JSON keys of `rendering.py` would be wide
enough for a Dutch sentence. That is true of an allowlist of strings and false
of a rule about shape: a JSON key is one whitespace chunk and a sentence is not,
so all 45 pass without being listed anywhere.

Calibrated against Dutch the test did not write and did not choose, which is
what keeps a vocabulary derived from the package under test from being
circular: over the 34 strings in `ampeer_advice.nl`'s six tables and
`advice.nl.VALIDATION_MESSAGES`, 31 are refused, none reads as English, and 3
are invisible. Those 3 are "Indicatief", "Goed" and "Precies", one word each,
and the honest edge of the rule is that a single word is a token. One real
instance sits inside that edge: `advice/apps.py` holds
`verbose_name = "Advies"`, which renders nowhere because
`django.contrib.admin` is not installed.

Shown failing rather than assumed to work: three sentences sharing no words were
written into `views.py`, `rendering.py` and `service.py` on 2026-08-27 and each
turned the suite red while the repo-wide wordlist in `tests/test_advise.py`
stayed green on all three. All three files were restored and the restoration
checked by digest.

**Lives in:** `PROSE_RULE`, `ENGLISH_PROSE_WORDS`, `_prose_words` and
`_words_that_are_not_english` in `tests/test_advice_serializers.py`.

**To reverse:** delete the vocabulary and go back to matching Dutch words. The
cost is that the boundary again holds only for sentences somebody thought of in
advance, which is the state it was reported closed in twice.

### 23. The year field carries its provenance, and the refusal was built before the data exists

**Decided:** the optional `year` object in the advice payload carries a
`provenance` of `SYNTHETIC` or `MEASURED`, and `year_field` refuses to build the
object when a measured series is paired with a shareable token.
`advice.series.EncodedYear` deliberately has no method that produces the wire
dict, so that door is the only one.

**Because:** in phase 0.5 the series is a national NEDU profile scaled to the
annual figure a visitor typed, plus modelled assets, so it holds nothing about
that household the household did not enter. In phase 2 the identical field
carries a series off their own meter, and `docs/dpia.md` chapter 1 names
quarter-hour consumption as the datum from which it can be derived when somebody
is home. An advice is retrievable for ninety days through a bearer token with no
account behind it and no way to tell who was given the link.

Built now the control is three lines and costs nothing, because nothing can
produce a measured series to be refused. Added when the first measured series
exists it needs a migration over every stored advice, and between those two
moments the rule lives in a document and is enforced nowhere. That gap is the
entire argument.

The refusal is a `ValueError` subclass and not a DRF validation error on
purpose: nothing a stranger posts chooses a provenance, so if it ever fires it
is server code and should read as a fault rather than as a 400 blaming a
visitor's form.

`shareable_token=False` is the phase 2 exit, for an advice reached through an
account rather than through a forwardable link. Nothing passes it today and a
test scans the package to keep that sentence true rather than remembered.

Stated plainly because the entry would otherwise read as a shipped feature: as
of this commit nothing emits the field. `advice/rendering.py` returns no `year`
key, `ampeer_sim` returns no quarter-hour arrays for one to be built from, and
the frontend has no decoder. What is decided here is the shape and the control,
both of which exist and are tested; the wiring is open work, and
`test_only_the_two_named_modules_reach_into_the_wire_format` is what keeps the
door singular while somebody does it.

**Lives in:** `SHAREABLE_PROVENANCE` in `backend/advice/series.py`,
`YearSerializer` and `year_field` in `backend/advice/serializers.py`, chapter 6
of `docs/dpia.md`, and
`test_a_measured_series_is_never_served_on_the_token_route` in
`tests/test_advice_series.py`.

**To reverse:** delete the `provenance` key and the check. The field then
becomes a shape that is safe today and unsafe on the day the meter coupling
lands, with nothing in between to notice.

### 24. The ceilings on the wire are maxima, and the clipping belongs to the renderer

**Decided:** `encode_year` scales each series to its own maximum, and export and
offtake carry separate ceilings rather than sharing one.

**Because:** a percentile ceiling makes a prettier plate and throws the
brightest quarters away irreversibly. Measured on 2026-08-27 on the reference
household: at p99 that is 205 quarters of own use, 120 of export and 231 of
offtake out of 35040. The wire carries data and the renderer makes it legible,
so clipping belongs where it can be undone. Separate ceilings because export
peaks roughly three times higher than offtake, so one shared ceiling would spend
the meter byte's seven bits on export and leave offtake a third of the
resolution it can have for free.

The choice is checkable rather than argued: replacing the maxima with p99 turns
five tests red, and the worst annual total drift goes from 0,008 percent to
0,242 percent.

Checked across two implementations rather than one, on 2026-08-27, because a
format read back by the code that wrote it proves only that rounding twice is
rounding once. A decoder written in JavaScript from the published contract alone
returns all 35040 quarters of all three series bit-identical to
`advice.series.decode_year`, with annual totals -0,00433, -0,00369 and -0,00812
percent from the engine's own. The same exercise measures what the format's one
trap costs: reading the meter byte as a whole byte over 255, which is what a
reader ported from a three-array prototype would do, halves offtake to 1132,3
kWh against 2273,8 and inflates export to 4007,8 against 2447,8, silently,
because the direction flag is read as magnitude.

**Lives in:** `encode_year` in `backend/advice/series.py`, with
`MIN_WORST_QUARTER_RATIO` in `tests/test_advice_series.py`.

**To reverse:** scale to a percentile and accept that the year's brightest
quarters are gone from the payload rather than from the picture.

### 25. The plate's colours are named inside the check, not beside it

**Decided:** the year plate declares `--colour-carpet-ground`,
`--colour-carpet-own`, `--colour-carpet-offtake`, `--colour-carpet-export` and
`--colour-on-carpet` in the same bare `:root` block as every other colour, and
its three states are rows in `GRAPHIC_PAIRS`. Each token is the FLOOR of its
state: `cellColour` only ever lightens towards white, so the token is the
dimmest cell that state can draw.

**Because:** this was the open question recorded under "What was not decided
here" until 2026-08-30, and it was open because the two cheaper spellings were
both the check being switched off. `--carpet-own` sits outside the
`--colour-([a-z0-9-]+)` pattern the contrast test parses. A second bare `:root`
block hides from the same test, whose block regex is not global and reads the
first one only. Either leaves a green suite and three unmeasured colours, on the
one plate where colour is the entire encoding: a cell is one pixel with no
label, no shape and no position of its own.

The floor rule is what makes three token rows a worst case rather than three
samples, and it is not free. The prototype blended each state towards the
instrument's ground by its magnitude, which draws a low quarter approaching
1,2:1 while the token it derives from measures fine, so the check agreed with
the stylesheet and not with the screen.

Measured on 2026-08-30 over every colour the format can express: export 3,09 to
4,07, offtake 6,70 to 7,59, own 11,90 to 13,57, worst neighbouring pair
1,5691:1. All three clear the 3:1 of SC 1.4.11; export clears it by 0,09 and is
the one a darker ground would push under. They cannot also be 3:1 from each
other, and that is arithmetic: three states each 3:1 above a ground of
luminance 0,0049 would need 0,115, 0,444 and 1,432, and relative luminance stops
at 1. So a ground and two states is the most a pairwise ladder holds, and the
third is told apart by hue and by the bands not overlapping.

Those figures replace the ones that stood in two source comments from
2026-08-27 to 2026-08-30, which named `tests/carpet/palette.test.ts` as pinning
them while that file did no such walk. Export's top was given as 4,53 against a
real 4,07 and offtake's as 7,63 against 7,59. A claim nobody re-derives is the
subject of this project's last six commits, and this one was mine.

**Lives in:** `CARPET_TOKENS` and `STATE_LIFT` in
`frontend/src/components/carpet/palette.ts`, the five tokens in
`frontend/src/app/globals.css`, `GRAPHIC_PAIRS` in
`frontend/tests/design/contrast.test.ts`, the shared ratio in
`frontend/tests/design/wcag.ts`, and the walk in
`frontend/tests/carpet/palette.test.ts`.

**To reverse:** rename the tokens outside the `--colour-` pattern, or let
`cellColour` blend towards the ground. Either makes the three rows in
`GRAPHIC_PAIRS` measure a colour that is in the stylesheet rather than the worst
one on screen, so both would have to remove those rows in the same commit rather
than leave them measuring nothing.

### 26. The consumption question asks for the figure without the car and the pump

**Decided:** on 2026-08-31, by Stijn, that round one's consumption question
names what it excludes rather than the model carving those assets back out of
the answer. The question is now "Hoeveel stroom verbruikt u per jaar, zonder
auto en warmtepomp?", with a note under it saying to subtract them if they are
on the annual bill, that we ask about them separately, and that an estimate is
enough.

**Because:** the model scales the base profile to the figure entered and then
ADDS the car and the heat pump on top, so the figure being asked for was always
consumption without them, and nothing said so. A visitor who charges at home
reads the total off their annual bill, the car is in it, and it is counted
twice. Measured over the six golden households and the reference household of
chapter 17: between 26,5 and 59,2 percent of the answer, always understating
the shock, and four of six households also lose a fired rule.

The alternative was to read the answer as the total and carve the modelled
asset out of it. `docs/analysis/2026-08-24-double-counting.md` measures both and
finds they give the same figure to the cent, so this was never an accuracy
argument. It is an argument about failure modes, and that document recommends
the carve-out and then makes the stronger argument against its own
recommendation, which is the one that decided this: the carve-out raises what
every asset-owning household is told by 36 to 145 percent entirely inside the
model, where the visitor cannot see it, resting on an asset size the model
guesses. Chapter 17 already has the sentence for that situation, which is that
being careful in the direction that suits us is not careful, it is convenient.
Under this repair the visitor owns the subtraction and can check it.

**What it costs round one, measured on 2026-08-31 and not part of the analysis
document.** Round one models no car and no heat pump at all. So for a household
that owns one, the answer moves:

| round one, no asset modelled | truth from round two | now | before |
|---|---|---|---|
| car charging at night | 623,71 | 623,71 | 447,27 |
| heat pump, 12000 kWh heat demand | 470,63 | 623,71 | 363,55 |
| car on its own surplus | 202,22 | 623,71 | 447,27 |

The night charger becomes exactly right, because charging at night draws
nothing while the sun is up and the whole error was scaling the base profile to
5660 instead of 3500. The heat pump goes from 23 percent low to 33 percent
high, and that is the direction this product can least afford. It is not a
modelling error: round one does not know about the assets, which is what
INDICATIVE means and what round two is for. It is recorded here because the
question has to mean one thing in both rounds, round two is the one that must
be right, and the price of that is on this table rather than nowhere.

**The failure mode this repair does not close, and what was built for it.** A
visitor who enters the bill total anyway is indistinguishable from a correct
one. So the response now carries `modelled_consumption_kwh`, the consumption
the model actually used, in the bandless shape with a Dutch sentence saying
whether that is the figure entered or the figure entered plus the assets. It
does not repair the reading and is not meant to. It makes it visible, which is
the difference between a wrong answer a household can catch and one nobody can.

**Lives in:** `ROUND_ONE_NOTES` in
`frontend/src/app/berekenen/page.tsx`, the `note` prop in
`frontend/src/components/form/QuestionShell.tsx`,
`MODELLED_CONSUMPTION_BASIS_TEXTS` in `ampeer_advice/nl.py`,
`_modelled_consumption` in `backend/advice/rendering.py`, chapters 4, 5 and 19
of `docs/methodologie.md`, and
`test_the_question_really_says_what_chapters_four_and_five_claim_it_says` in
`tests/test_methodology.py`.

**To reverse:** take the exclusion back out of the question and carve the
assets out inside the model instead. That needs the floor the analysis derives,
2550 kWh of residual base, and a rule for what happens below it, and it moves
every asset-owning household's figure up by 36 to 145 percent in one commit.

### 27. The account model was decided in the same task that created the app

**Decided:** `AUTH_USER_MODEL = "accounts.User"` is set in the first commit
that adds the `accounts` app, before `accounts/migrations/0001_initial.py`
exists, rather than left on Django's default with a swap planned for later.

**Because:** every foreign key any later task points at the user model bakes
the target into its own migration's state at the moment that migration is
written, not at the moment it runs. `Consent.user`, `RefreshSession.user` and
`StoredAdvice.owner` all arrived in tasks after this one, and each of their
migrations records `accounts.User` as the model it points at. Setting
`AUTH_USER_MODEL` after any of those three migrations existed would have meant
starting them against Django's own `auth.User` and then swapping, which
Django's own documentation calls out by name as something to avoid once
migrations exist: doing it means regenerating every migration that references
the user model and recreating the database behind it, in production the same
outage decision 8's version bump is designed to make visible rather than
silent. There was never a point after task 3 where deferring this stayed free.

**Lives in:** `AUTH_USER_MODEL` in `backend/ampeer/settings/base.py`,
`backend/accounts/migrations/0001_initial.py`.

**To reverse:** there is no cheap reverse. Moving to a different user model now
means writing the same migrations Django's documentation warns about, against
a database that already holds `Consent`, `RefreshSession` and `StoredAdvice`
rows pointing at this one.

### 28. An account's advice rows are deleted with it, not orphaned

**Decided:** `StoredAdvice.owner` is `on_delete=models.CASCADE`, not
`SET_NULL`.

**Because:** the advice a household made is the only thing this product keeps
about that household, so deleting the account and leaving the advice behind
under a cleared `owner` would still answer the token for the rest of the
ninety days. `SET_NULL` turns a deletion request into a rename: the row
survives, readable exactly as before, only the link back to the account is
gone. `CASCADE` is what makes "delete my account" and "delete what you hold
about me" the same request rather than two, which is the sentence
`docs/dpia.md` chapter 7 now makes about `POST /api/auth/delete/`. Nothing
writes this column in phase 1, so today's choice affects nobody yet; it is
recorded now because adding the column later, the way `year_field`'s
`shareable_token` argument was, is a migration over every stored advice and
this decision has to be settled before that migration runs, not after.

**Lives in:** `owner` in `backend/advice/models.py`,
`backend/accounts/service.py`.

**To reverse:** change the field to `SET_NULL` and add a second, explicit
delete of the household's own advice rows to `delete_account`, since leaving
them ownerless is exactly the behaviour this decision rules out.

### 29. Refresh tokens are tracked by a digest of their own app, not simplejwt's blacklist

**Decided:** `backend/accounts/models.py` defines `RefreshSession`, storing
only `jti_sha256`, rather than enabling simplejwt's `token_blacklist` app.

**Because:** `token_blacklist`'s `OutstandingToken.token` column stores the
whole refresh JWT in plaintext, which is a working credential sitting in a
database column. CLAUDE.md forbids exactly that, in the same words
`docs/dpia.md` chapter 2 already used for the advice token: the thing stored
must not be a usable key to the thing it protects. `RefreshSession` carries the
sha256 of the token's `jti` instead, which lets rotation and reuse detection
work (`rotated_at` records an exchange, and a second exchange of the same
token revokes every session the account has) without a column anyone could
present as a bearer token if the database ever leaked.

**Lives in:** `RefreshSession` in `backend/accounts/models.py`.

**To reverse:** add `rest_framework_simplejwt.token_blacklist` to
`INSTALLED_APPS` and drop `RefreshSession`. The plaintext column comes back
with it, so this reverse is also the one decision 27's user model constraint
would not have blocked but this project's own security rule does.

### 30. The axes cache handler was measured before it was trusted, twice

**Decided:** `AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"` stays,
with `AXES_CLIENT_IP_CALLABLE` and `AXES_USERNAME_CALLABLE` pointed at
`accounts.lockout`, rather than the default database handler that would create
an `AccessAttempt` table with an `ip_address` column.

**Because:** two separate properties had to hold for a shared cache counter to
be trustworthy for a lockout, and both were measured rather than assumed.

Measurement 1, `tests/test_accounts_lockout_store.py`, asks whether
`DatabaseCache.incr`, which Django implements as an unlocked get-then-set,
loses so many concurrent increments that a lockout threshold is never reached.
Measured on 2026-09-04 against Postgres, 8 threads each writing 25 increments
to one key: about 25 to 27 of the 200 writes survived across four independent
runs (25, 25, 26 and, on a fourth run, 27). The spread is tight because
`200 / 8 = 25` is close to a fixed point of this race for equal, non-
overlapping worker batches; the fourth run reading 27 rather than 25 or 26 is
what shows this is a real race with run-to-run variance and not an arithmetic
identity that happens to equal 25 every time. `DatabaseCache.incr`'s loss
scales with the concurrency of the writer, which is the wrong direction for a
defence built to survive an attacker sending more requests, not fewer. What
bounds the damage is that axes keys on `(username, visitor digest)` rather
than on a global counter, so attackers arriving from different addresses never
collide on the same key, and the one case that does collide, a single identity
hammering a single account, is capped upstream at 10 attempts an hour by the
`auth-login` throttle scope, far below the 25 to 27 the cache still carries
correctly under 8-way contention. So the design is layered rather than resting
on the cache alone: nginx limits the whole service to 10 requests a second,
DRF's `auth-login` scope limits one visitor to 10 an hour, and axes sits behind
both as defence in depth rather than as the only thing standing between an
attacker and the account. `test_the_login_route_throttles_before_axes_contention_could_matter`,
added in task 9, is the mechanical form of this argument: it asserts the
throttle refuses an attacker long before contention on the cache key could.
Anyone who raises `AXES_FAILURE_LIMIT` past 5, or loosens `auth-login` well
above 10 an hour, changes the numbers this paragraph relies on and should
re-run this measurement rather than assume it still holds; the two settings
are coupled through this argument and not through any code that enforces it.

Measurement 2, `tests/test_accounts_lockout.py`, asks a different question:
whether axes counts anything at all in a stack with no
`AuthenticationMiddleware` and no session, which this project has neither of.
Measured on 2026-09-04 with `RequestFactory` requests carrying no middleware
at all: `AXES_FAILURE_LIMIT` failed calls to `django.contrib.auth.authenticate`
left the next attempt refused by `AxesProxyHandler.is_allowed`, and the correct
password was refused with it, confirming the lockout fires exactly at the
configured limit independent of session middleware.

Together the two measurements are why the cache handler stands: it loses
writes under heavy contention and still crosses the threshold that matters,
and it fires correctly in the session-less stack this project actually runs.

**Lives in:** `AXES_HANDLER` in `backend/ampeer/settings/base.py`,
`backend/accounts/lockout.py`, `tests/test_accounts_lockout_store.py`,
`tests/test_accounts_lockout.py`.

**To reverse:** switch to the database handler and accept the `ip_address`
column decision 27's sibling settings were written to avoid, or re-measure
after any change to `AXES_FAILURE_LIMIT` or `auth-login` before trusting this
argument again.

### 31. There is no password reset route, and the delete endpoint inherits the consequence

**Decided:** phase 1 ships registration, login, refresh, logout, consent,
export and delete, and no route to reset a forgotten password.

**Because:** every one of the seven routes that exists has a place to hand a
visitor who forgot their password: none, because none of them is the recovery
flow. `DeleteView` asks for the current password before it acts, which is
exactly right when the caller still knows it and leaves no route at all for a
caller who does not. That is accepted here rather than treated as a bug: a
password reset needs an outbound channel this project has never built, and
`django.contrib.auth.tokens.PasswordResetTokenGenerator` already ships with
`django.contrib.auth`, which decision 27 already added to `INSTALLED_APPS`.
What is missing is not the token generator, it is an `EMAIL_BACKEND` and
somewhere to send the mail, and adding those without adding the flow around
them would be building half a feature. A household that forgets its password
today cannot delete its own account through this API and has no self-service
way to regain access either; both wait on the same missing channel.

**Lives in:** `DeleteView` in `backend/accounts/views.py`, and
`django.contrib.auth` in `backend/ampeer/settings/base.py`, which is present
while no email backend is configured beside it.

**To reverse:** configure an `EMAIL_BACKEND`, add a request-reset and
confirm-reset route built on `PasswordResetTokenGenerator`, and update
`docs/dpia.md` chapter 7 to describe the new route the same way it describes
the other eight.

### 32. The login trap fired exactly as designed, and its neighbour lost one assertion

**Decided:** `test_authentication_never_arrives_without_its_defences` in
`tests/test_backend_settings.py`, laid before this branch existed as a trap
aimed at the day accounts arrived, fired when task 3 added
`django.contrib.auth` to `INSTALLED_APPS`, and named exactly what was missing
until axes, Argon2 and the backend ordering landed with it in the same commit.
Its neighbour, `test_nothing_authenticates_because_there_is_nothing_to_log_in_to`,
had its assertion that `"django.contrib.auth" not in settings.INSTALLED_APPS`
removed rather than reworded, and its docstring narrowed to the three claims
that are still true: no session middleware, no admin site, and
`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` stays empty.

**Because:** `AUTH_USER_MODEL` needs `django.contrib.auth` in
`INSTALLED_APPS` to exist at all, so the neighbour's fourth assertion was
never going to survive accounts landing; keeping it and reworking it to test
something else would have hidden that this specific claim, not a nearby one,
became false. Removing it rather than flipping its polarity is what makes the
trap test's own green result mean something: the trap is what now stands guard
over the requirement the removed assertion used to state on its own, so the
coverage is not thinner, it moved to the test built to catch exactly this.

**Lives in:** `test_authentication_never_arrives_without_its_defences` and
`test_nothing_authenticates_because_there_is_nothing_to_log_in_to` in
`tests/test_backend_settings.py`.

**To reverse:** put the removed assertion back and accept that it is
permanently red for as long as accounts exist, which is the state this entry
exists to explain rather than let a reader rediscover from a red CI run.

### 33. The global rate ceiling moved from 5 to 10 requests a second when accounts arrived

**Decided:** `limit_req_zone` in `infra/nginx/nginx.conf` raises its rate from
5r/s to 10r/s.

**Because:** `test_something_ahead_of_django_limits_the_rate` in
`tests/test_nginx_config.py` sums every `DEFAULT_THROTTLE_RATES` scope into a
per-visitor rate and requires the nginx ceiling to clear it by at least 50
times. Before this branch, three advice scopes summed to 0.0722 requests a
second, and 5r/s cleared that by 69 times. The six new `auth-*` scopes this
branch adds bring the total to 0.13333 requests a second, and 5r/s against
that new sum is only 37.5 times, under the 50x the test demands. Raising the
ceiling to 10r/s restores a 75x margin.

Three cheaper alternatives were measured and rejected before raising the
ceiling. Halving `auth-read` to 60 an hour still leaves the sum high enough
that 5r/s only clears it 42.9 times, still under the line. Deleting
`auth-read` entirely brings the sum to exactly 0.1 requests a second, which
5r/s clears at exactly 50 times: technically passing and not a margin anybody
should ship, since it depends on no other scope ever moving by a single
request an hour. Lowering `auth-login` was not measured because it was refused
outright: decision 30's whole argument that a lockout counter's measured loss
is safe rests on `auth-login` capping one identity at 10 attempts an hour, so
this is the one scope this task will not touch to make a different test pass.
The next scope this service adds will run the same arithmetic again, and
`infra/nginx/nginx.conf`'s own comment beside `limit_req_zone` names both
figures so whoever changes one finds the other.

**Lives in:** `limit_req_zone` in `infra/nginx/nginx.conf`,
`DEFAULT_THROTTLE_RATES` in `backend/ampeer/settings/base.py`,
`test_something_ahead_of_django_limits_the_rate` in
`tests/test_nginx_config.py`.

**To reverse:** lower the rate back to 5r/s and expect
`test_something_ahead_of_django_limits_the_rate` to fail at 37.5x against the
50x floor it asks for, exactly as it did before this decision.

## What was not decided here

Four belong to the controller and are written up with their trade-offs in
chapter 10 of `docs/dpia.md`: whether the conclusion of chapter 1 is adopted,
the legal basis, the seven day backup window, and access to the host including
whether `web2` becomes ephemeral. They are not repeated here, because two
lists of the same open questions is how one of them gets answered twice and
the other not at all. A fifth used to stand beside them, whether deletion on
request arrives before phase 1, and it is answered rather than dropped: decision
28 and `docs/dpia.md` chapter 7 both describe `POST /api/auth/delete/`, which
is what answered it.

Six sit outside that document.

- **Whether `feat/**` stays in the push trigger of `.github/workflows/ci.yml`.**
  Removing it roughly halves the minutes a branch costs, and rewrites five
  passages that explain why the security workflow does not run on a feature
  push. That explanation is bound up with the runner question, so it is not
  mine to settle.
- **Whether a battery verdict may be refused on the middle of its band alone.**
  `_storage_verdict` in `ampeer_advice/advise.py` recommends only when the
  whole payback band clears twelve years, and refuses as soon as the middle
  misses it. A household whose band runs from well inside the limit to well
  outside hears a flat no rather than that it depends on the quote. Measured on
  2026-08-23: `large_array_small_use` pays back between 6.99 and 18.89 years
  with a middle of 12.05 and is told the battery does not pay back, while at
  450 euro per kWh it pays for itself in seven. The asymmetry is deliberate and
  tested. The argument for it is that this product should be reluctant to
  recommend and free to refuse, since refusing sells nothing. The argument
  against is the one the function's own docstring makes about a single number
  deciding the most consequential sentence in the product, applied to one side
  only. Changing what a household is told is not mine to take.

  Updated on 2026-08-26, and the update is why this is now a live question
  rather than a theoretical one. This entry used to close by saying that nothing
  reaches the middle state any more, that household having left it at 9.69 years
  when the capacity curve stopped being priced on consumption the free routes
  had already claimed. It reaches it again. Decisions 16 and 17 above moved the
  offline production model, `large_array_small_use` came from 12.05 years to
  11.46, and its verdict went from BATTERY_DOES_NOT_PAY_BACK to
  BATTERY_DEPENDS_ON_PRICE.

  Re-measured on 2026-09-02, because the paragraph above still carried the band
  it was written with. The two ends moved with the middle and were never
  brought along: 6.99 and 18.89 are the 2026-08-23 figures, and today the same
  household pays back between **6.65 and 17.98** years with a middle of
  **11.47**. The sentence about 450 euro per kWh moved too, from seven years to
  **6.65**. None of it changes the question this entry asks, which is about the
  asymmetry and not about where the band happens to sit; it is corrected here
  because a reader checking the argument would otherwise check it against three
  numbers the model stopped producing. The same measurement corrected six
  recorded figures in `tests/golden/advice_households.json`, which had drifted
  in the last decimal for the same reason and were held by a tolerance wide
  enough not to notice. Nobody is being told to buy anything and the
  asymmetry above is untouched; what changed is that the middle state is no
  longer empty, so whether it should be reachable is being answered in practice
  by a physics correction rather than by a decision. All three storage verdicts
  are recorded in `tests/test_advise.py`, which used to assert a single id and
  now asserts the set, because a household moving into the middle state and a
  household being sold a battery are not the same event and one assertion could
  not tell them apart.
- **Whether the allowlist in CLAUDE.md should name a fourth source.** It names
  PVGIS, ENTSO-E and KNMI as the external sources this project may reach. The
  repository reaches a fourth: `tools/ingest_profiles.py` downloads the NEDU
  standard profiles from energiedatawijzer.nl, which it has to, since their
  redistribution terms are unconfirmed.

  That last clause was corrected on 2026-09-02 and it used to read "since their
  licence forbids committing them". It was checked and there is no such licence.
  The profiles for toepassingsjaar 2025 are established by the Platform
  Verbruiksprofielen and published by MFFBAS, and neither the publication page nor
  the files carry a licence, a copyright line or a reuse condition of any kind.
  `docs/superpowers/specs/2026-08-20-simulation-core-design.md` said exactly that
  when the decision was taken, "Gebruik is onproblematisch, herdistributie niet
  bevestigd", and the docstring of `nedu_profile_path` in
  `tests/helpers/profiles.py` still says it. Somewhere between the spec and this
  entry a caution became a finding. Nothing about the behaviour changes: the files
  stay out of the tree and the ingest step stays. What changes is that this entry
  no longer cites a prohibition that does not exist, in a document whose whole
  purpose is that a later reader can tell what was established from what was
  assumed. The same sentence in `docs/analysis/2026-08-24-tou-tariff-2029.md` and
  the same phrase in the comment above `IGNORED_ROOTS` in
  `tests/test_analysis_docs.py` were corrected in the same pass.

  While that was being checked, one further thing came out that belongs here
  rather than in a spec: PVGIS is settled and in the other direction. The JRC
  states on its own user manual page that PVGIS "is completely free to use, with
  no restrictions on what the results can be used for, and with no registration
  necessary". So of the two open licence questions the spec recorded, one is
  answered permissively and one is genuinely still open, and they should stop
  being carried as a pair.

  Not a hole. The rule in that document is written about the backend, which
  never fetches, and this is a build time command somebody runs by hand. Its URL
  is one https constant, the only thing substituted into it is the CLI's year,
  and argparse types that as an int, so nothing from the command line can reach
  the host or the path as text. All four of those are now asserted in
  `tests/test_boundaries.py`, and that file's scan reaches `tools/` as of
  2026-08-23, having walked only the two packages and `backend/` before while
  its failure message said the rule allows one file and nothing else.

  What is left is a sentence in CLAUDE.md that lists three sources while the
  repository uses four. Editing that document is not mine.

- **Whether the opening paragraph of CLAUDE.md should carry its own sources.** It
  states four facts about the Netherlands and none of them says where it comes
  from. Three were checked against primary sources on 2026-09-02 and are now cited
  in `docs/methodologie.md`, chapters 1, 6, 10 and 11: the end of netting on
  1 January 2027, which is Staatsblad 2025, 17; the three to eight cent against
  roughly 27 cent, which are two figures containing different things rather than
  two prices for one thing; and what NEDU profiles and PVGIS are. The fourth is
  the population figure, "ruim 3 miljoen huishoudens met zonnepanelen", and it
  does not appear anywhere in `docs/` so there was nothing to cite it in.

  What CBS publishes is close and not the same sentence. StatLine 85005NED counts
  installations on or around **woningen**, not households, and the CBS longread of
  17 February 2026 puts that at "van ongeveer 70 duizend tot bijna 3 miljoen in
  **2024**". So the primary figure is *bijna* 3 million for 2024, where CLAUDE.md
  says *ruim* 3 million. Secondary analyses of the 2025 StatLine update do reach
  "ruim drie miljoen woningen", about 37 percent of the housing stock, but that is
  a press reading of CBS rather than CBS. Two edits would fix it, a vintage and a
  noun, and both are in a document that is not mine: it should say woningen rather
  than huishoudens, and it should carry the year the figure is for, because a
  headcount with no year is the one kind of number that cannot go stale visibly.

- **Whether the run count beside the band should report cells or distinct
  outcomes.** `HeadlineBand.tsx` shows the visitor "{band.runs} doorrekeningen"
  and the screen reader text says the midpoint comes "uit 243 doorrekeningen".
  For a household on a dynamic contract that figure is three times what the
  band rests on. `scenario_2027_tariffs(dynamic=True)` sets
  `feed_in_cost_per_kwh` to zero, because on that contract the compensation is
  already net of charges, and `_apply_variations` moves that assumption by
  multiplying it. Zero times either factor is zero, so the fifth dimension of
  the grid is constant and each answer is computed three times.

  Measured on 2026-08-23 on the reference household: 243 cells, 81 distinct
  outcomes, every one appearing exactly three times. The percentiles are
  identical either way, so the band itself is right and only the count beside
  it overstates.

  Both readings are defensible, which is why this is not mine. 243 is honestly
  the number of combinations priced. 81 is honestly the number of different
  answers they gave. `scenario_2027_levels` in `ampeer_advice/tariffs.py`
  already takes the second position for the other band, in as many words:
  naming an input that does not actually differ would make the band claim a
  width it does not have. Applying that here changes a number a visitor reads.
  Pinned in `tests/test_sensitivity.py` so it cannot drift while the question
  is open.

- **Whether the 2029 sentence in CLAUDE.md is corrected.** It says "een
  tijdsafhankelijk nettarief bij met vier prijsniveaus en vijf tijdsblokken".
  Read from the source on 2026-08-26, the proposal (Netbeheer Nederland
  BR-2026-2242, 1 May 2026, annex 5, fifth and sixth members) fixes **five**
  weighting factors in the code text, 0,0 / 0,3 / 0,5 / 0,7 / 1,0, and says four
  is a maximum per day: "maximaal vier tariefhoogten gedurende een dag".
  Measured from the table: a summer day uses four distinct levels and a winter
  day uses three. Five blocks per day holds only if the winter 23:00 to 01:00
  block is read as one block wrapping midnight, which is why a scan for
  contiguous runs finds six.

  Not a hole in the sentence's intent. It describes the regime accurately enough
  for a document that sets direction, and the module it points at does not
  exist. It matters because a model built literally on four levels cannot
  express the year, and because the sentence states 1 January 2029 as fact where
  the document states it as a request carrying two written escape hatches to
  1 January 2030, one of which falls due on 1 December 2026.

  The full reading, with the block tables, the offtake-only finding and eight
  named gaps, is `docs/analysis/2026-08-24-tou-tariff-2029.md`. Editing CLAUDE.md
  is not mine.

- **The order the two open pull requests are merged in.** #23 carries this
  branch into `dev` and #22 carries `dev` into `main`, so #23 goes first and #22
  is rerun afterwards.
