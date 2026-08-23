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
  only. It also matters that nothing reaches the middle state any more: that
  household used to, at 9.69 years, and left it when the capacity curve stopped
  being priced on consumption the free routes had already claimed. Changing
  what a household is told is not mine to take.
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

- **What to do about the hourly calibration running at two percent of its
  ceiling.** The worst hourly bucket is 17:00 at 0.0490 against a
  `MAX_HOURLY_GAP` of 0.05. The model exports nothing at all after 17:00 while
  the country still exports 0.0295 at 18:00 and 0.0120 at 19:00, partly because
  the offline fallback spreads its day over a fixed twelve hour half sine and
  partly because the tails of that shape fall below the household's own baseline
  draw, so nothing is left to export. Widening the ceiling is forbidden by the
  file and would be the wrong repair anyway. The right one is a better evening
  tail, which is a modelling change on a path a visitor reaches whenever PVGIS
  is down, and it is worth knowing that the next unrelated improvement may turn
  this red first. Written down here because a near miss nobody has looked at
  reads exactly like a comfortable pass.

- **What a northeast or northwest roof is worth when PVGIS is unreachable.**
  `ORIENTATION_FACTORS` in `ampeer_sim/production/fallback_yield.py` holds six
  planes and neither of those two is among them. Both sit 45 degrees from east
  or west and 45 from north, so the nearest-entry search lands on a tie, and the
  tie is broken by the order the table is written in, which in this table hands
  them the higher of the two: 0.85 rather than 0.62. Neither figure is right. A
  plane at 35 degrees facing northeast is not as good as one facing east, and it
  is not as bad as one facing north.

  Left as it is, deliberately. Moving it changes what a real household with that
  roof is told by 27 percent, on a judgement call rather than on a measurement,
  and this is a path a visitor reaches whenever PVGIS is down. The honest repair
  is not a better tie-break but two more table entries, derived from the same
  PVGIS SARAH3 call over 2015 through 2023 that the rest of the table came from,
  which is a measurement somebody has to take. Today's outcome is pinned in
  `tests/test_pvgis_provider.py` so it cannot drift while the question is open.

- **The order the two open pull requests are merged in.** #23 carries this
  branch into `dev` and #22 carries `dev` into `main`, so #23 goes first and #22
  is rerun afterwards.
