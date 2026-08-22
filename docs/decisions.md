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

**Lives in:** `tests/test_boundaries.py`, in `ALLOWED_HOSTS`.

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

## What was not decided here

Five belong to the controller and are written up with their trade-offs in
chapter 10 of `docs/dpia.md`: whether the conclusion of chapter 1 is adopted,
the legal basis, the seven day backup window, whether deletion on request
arrives before phase 1, and access to the host including whether `web2` becomes
ephemeral. They are not repeated here, because two lists of the same open
questions is how one of them gets answered twice and the other not at all.

Three sit outside that document.

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
- **The order the two open pull requests are merged in.** #23 carries this
  branch into `dev` and #22 carries `dev` into `main`, so #23 goes first and #22
  is rerun afterwards.
