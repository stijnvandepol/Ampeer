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

This entry and the one above it are why `ENGINE_VERSION` is 0.2.0. Decision 8
says the version moves when the numbers do, and both moved them: every golden
household's self consumption rate changed, five up and one down, and
`tests/golden/README.md` separates the two causes household by household.

**Lives in:** `FALLBACK_SOLAR_NOON_HOUR` and `FALLBACK_DAYLIGHT_HOURS` in
`ampeer_sim/production/pvgis.py`, with both measurements above them;
`PVGIS_HOUR_OF_DAY_WINTER_TIME` in `tests/test_pvgis_provider.py`, which is the
24 shares the second measurement is made against; and `MAX_HOURLY_GAP` in
`tests/test_calibration.py`.

**To reverse:** centre the shape on 12:00 again. The suite goes red in seven
places rather than one, which is the intent: the calibration ceiling, the
afternoon bucket, the evening floor and four checks in the provider tests all
name it.

## What was not decided here

Five belong to the controller and are written up with their trade-offs in
chapter 10 of `docs/dpia.md`: whether the conclusion of chapter 1 is adopted,
the legal basis, the seven day backup window, whether deletion on request
arrives before phase 1, and access to the host including whether `web2` becomes
ephemeral. They are not repeated here, because two lists of the same open
questions is how one of them gets answered twice and the other not at all.

Four sit outside that document.

- **Whether `feat/**` stays in the push trigger of `.github/workflows/ci.yml`.**
  Removing it roughly halves the minutes a branch costs, and rewrites five
  passages that explain why the security workflow does not run on a feature
  push. That explanation is bound up with the runner question, so it is not
  mine to settle.
- **Whether the Dutch validation messages in `backend/advice/serializers.py`
  move to a language layer.** The project rule says Dutch text never sits
  hardcoded in the logic, and ten messages do. `ampeer_advice/nl.py` is the
  wrong home, since that package must not know about the API, so the fix needs a
  new module on the Django side. That is a change to code that ships, with no
  test to gain, and the register decision above already went further into
  user-facing text than I would want to go twice without a word back.
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
  BATTERY_DEPENDS_ON_PRICE. Nobody is being told to buy anything and the
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
  licence forbids committing them.

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

- **What to do about a visitor entering the figure from their annual bill.**
  "Verbruik per jaar" is asked in round one. Whether the household has a car or
  a heat pump is asked in round two, and the model adds those on top of the
  answer to the first question. So the figure being asked for is consumption
  without them, and nothing at the question says so. A visitor who charges at
  home reads the total off their bill, the car is already in it, and the model
  counts it twice.

  Measured on 2026-08-23 on the reference household of chapter 17, comparing
  what the visitor is told against what the model itself would say for the same
  household described correctly: a car charging at night gives 456 euro instead
  of 634, a heat pump with a 12000 kWh heat demand gives 291 instead of 479, and
  a car charging on its own surplus gives 97 instead of 212. Between 28 and 54
  percent of the answer, always understating the shock.

  Two repairs and they are different products. Say at the question which figure
  is wanted, which is honest but asks for a number many people cannot produce:
  somebody with a heat pump usually has one meter and one total. Or read the
  answer as the total and carve the modelled asset out of it, which needs a rule
  for what happens when the carve-out leaves too little and changes what every
  such household is told. Not mine to pick. docs/methodologie.md chapters 4, 5
  and 19 now describe the behaviour, and two pairings in
  `tests/test_methodology.py` hold the description against the model.

- **The order the two open pull requests are merged in.** #23 carries this
  branch into `dev` and #22 carries `dev` into `main`, so #23 goes first and #22
  is rerun afterwards.
