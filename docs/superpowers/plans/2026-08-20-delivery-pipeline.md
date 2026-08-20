# Delivery Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `dev` the branch where work happens and `main` a branch nothing reaches without passing five automated gates, including the owner's own commits.

**Architecture:** Two GitHub Actions workflows publish six checks; a repository ruleset requires five of them on `main`. Dependencies move to uv with a committed lockfile so the developer machine, the CI runner and the future LXC install byte-identical sets. Fast checks also run locally through pre-commit; slow ones stay in CI where they cannot be skipped.

**Tech Stack:** uv 0.12, ruff, mypy, pytest with coverage, bandit, pip-audit, gitleaks 8.30, CycloneDX, pre-commit, GitHub Actions, GitHub repository rulesets.

**Spec:** `docs/superpowers/specs/2026-08-20-delivery-pipeline-design.md`

## Global Constraints

- Every `uses:` in a workflow is pinned to a full commit SHA with the version as a trailing comment. Never a tag.
- Every workflow declares `permissions:` explicitly at workflow level, defaulting to `contents: read`.
- Job names `quality`, `test`, `dependencies`, `sast` and `secrets` are a public interface: the ruleset on `main` requires them by exact name. Renaming one produces a check that never arrives and a pull request that hangs forever.
- Coverage threshold is 97 percent, the measured value on 2026-08-20. It may be raised, never lowered.
- Security tooling lives in the locked dev dependency group. An unpinned security scanner is itself a supply chain hole.
- Python 3.12 floor, type hints mandatory, `mypy --strict` must pass.
- Code identifiers, comments and commit messages in English. Dutch only in user-facing text, and this sub-project has none.
- No em-dashes in any Dutch text.
- `data/` stays gitignored. NEDU profile files are never committed.

---

## The multi-agent working model

This plan is written to be executed by several agents at once. The model below is
not specific to this sub-project: it is the way parallel work happens on Ampeer
from here on, and it matters far more for the backend and frontend sub-projects,
which are much wider than this one.

**Four rules, and they are what make concurrency safe:**

1. **A lane owns paths exclusively.** No two lanes may write the same file. The
   ownership map below is exhaustive; if a lane finds it needs a file it does not
   own, it stops and reports rather than reaching across.
2. **Implementation agents never run git.** No `add`, no `commit`, no `checkout`,
   no `branch`. They write files. The orchestrator commits after the integration
   gate. This removes the entire class of concurrent-index failures without any
   locking.
3. **Every lane carries its own verification command.** A lane is done when a
   command the agent ran itself came back green, not when the agent believes it is
   finished.
4. **Gates run after lanes, never alongside them.** Integration first, audit
   second. An audit of code that does not yet fit together finds the wrong things.

**Three phases, in order:**

```
Phase 0  foundation            1 agent, sequential, everything depends on it
Phase 1  four lanes            4 agents, concurrent, disjoint files
Phase 2  integration gate      1 agent, adversarial, checks the seams
Phase 3  audit                 3 agents, concurrent, distinct lenses
```

The audit agents are told to find problems, not to confirm the work. An agent
asked "is this secure" answers yes far too often; an agent asked "find three ways
this breaks" is useful.

### File ownership map

| Lane | Owns exclusively | May read |
|---|---|---|
| **0. Foundation** | `pyproject.toml`, `uv.lock` | everything |
| **A. Build gates** | `.github/workflows/ci.yml` | everything |
| **B. Security gates** | `.github/workflows/security.yml` | everything |
| **C. Local loop** | `.pre-commit-config.yaml`, `.gitattributes` | everything |
| **D. Policy** | `.github/dependabot.yml`, `CLAUDE.md`, `scripts/setup_rulesets.sh` | everything |

Lanes A through D all read `pyproject.toml` and none of them write it. That is why
Phase 0 is sequential and alone.

---

## Phase 0: foundation

### Task 1: Move to uv with a locked dev group

**Files:**
- Modify: `pyproject.toml`
- Create: `uv.lock` (generated, committed)

**Interfaces:**
- Consumes: nothing
- Produces: a dev dependency group named `dev` containing `pytest`, `pytest-cov`,
  `hypothesis`, `mypy`, `ruff`, `bandit[toml]`, `pip-audit`, `cyclonedx-bom`,
  `pre-commit`, `types-requests`. Every later lane invokes tools as
  `uv run <tool>` after `uv sync --locked --group dev`.
- Produces: `[tool.coverage.report] fail_under = 97`
- Produces: `[tool.bandit]` so `bandit -c pyproject.toml` works

- [ ] **Step 1: Install uv**

Run: `python -m pip install uv`
Expected: uv 0.12 or newer. Verify with `uv --version`.

- [ ] **Step 2: Rewrite the dependency declaration**

Replace the `[project.optional-dependencies]` block in `pyproject.toml` with a PEP
735 dependency group, and add the tool configuration the gates need:

```toml
[project]
name = "ampeer-sim"
version = "0.1.0"
description = "Ampeer simulation core: synthetic household energy profiles and scenario simulation"
requires-python = ">=3.12"
dependencies = ["numpy>=2.0", "requests>=2.32"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "hypothesis>=6.100",
    "mypy>=1.10",
    "ruff>=0.5",
    "types-requests",
    "bandit[toml]>=1.7",
    "pip-audit>=2.7",
    "cyclonedx-bom>=4.4",
    "pre-commit>=3.7",
]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["ampeer_sim*", "tools*"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
filterwarnings = ["ignore::DeprecationWarning:pytest_asyncio.*"]

[tool.coverage.run]
source = ["ampeer_sim", "tools"]
branch = true

[tool.coverage.report]
# Equals the measured value on 2026-08-20. May be raised, never lowered:
# a threshold below the current level makes a regression invisible.
fail_under = 97
show_missing = true

[tool.bandit]
exclude_dirs = ["tests", ".venv", "build"]
```

- [ ] **Step 3: Generate and verify the lockfile**

Run: `uv lock`
Expected: `uv.lock` is created.

Run: `uv sync --locked --group dev`
Expected: the environment resolves without touching the network for versions.

- [ ] **Step 4: Prove the toolchain still works through uv**

Run: `uv run pytest -q`
Expected: 182 passed.

Run: `uv run ruff check ampeer_sim tests tools`
Expected: All checks passed.

Run: `uv run mypy ampeer_sim`
Expected: Success: no issues found.

Run: `uv run pytest --cov --cov-report=term`
Expected: PASS and a total of 97 percent or higher. If it reports lower, the
coverage source configuration is wrong; do not lower `fail_under` to compensate.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: move to uv with a locked dev group and a coverage floor"
```

---

## Phase 1: four concurrent lanes

Dispatch these four as separate agents at the same time. Each writes only the files
in its ownership row and runs no git commands.

### Task 2 (Lane A): the build workflow

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `uv sync --locked --group dev` from Task 1
- Produces: status checks named exactly `quality` and `test`

- [ ] **Step 1: Replace the workflow entirely**

The existing `ci.yml` uses pip and unpinned actions. Replace its whole contents:

```yaml
name: ci

on:
  push:
    branches: [dev, "feat/**"]
  pull_request:
    branches: [dev, main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # WARNING: this job name is a required status check in the main ruleset.
  # Renaming it makes that check never arrive, and every pull request to main
  # hangs forever waiting for it. Change scripts/setup_rulesets.sh at the same
  # time or not at all.
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      - run: uv run ruff check ampeer_sim tests tools
      - run: uv run ruff format --check ampeer_sim tests tools
      - run: uv run mypy ampeer_sim

  # WARNING: required status check. See the note on `quality`.
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      - run: uv run pytest --cov --cov-report=term-missing
```

Note that `uv sync --locked` fails when `uv.lock` is stale relative to
`pyproject.toml`. That is deliberate: a lockfile nobody regenerates is a lockfile
nobody trusts.

- [ ] **Step 2: Verify the workflow parses and every action is pinned**

Run:

```bash
python -c "import sys, tomllib" 2>/dev/null; python - <<'PY'
import re, pathlib, sys
text = pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
unpinned = [line.strip() for line in text.splitlines()
            if "uses:" in line and not re.search(r"@[0-9a-f]{40}", line)]
assert not unpinned, f"unpinned actions: {unpinned}"
for name in ("quality:", "test:"):
    assert name in text, f"missing required job {name}"
assert "permissions:" in text
print("ci.yml: jobs present, all actions pinned, permissions declared")
PY
```

Expected: the confirmation line, no assertion error.

- [ ] **Step 3: Verify the commands the workflow runs actually work locally**

Run: `uv run ruff format --check ampeer_sim tests tools`
Expected: PASS. If it fails, run `uv run ruff format ampeer_sim tests tools` once
and report that formatting changed files, because that is a real finding about the
existing code and not about this workflow.

- [ ] **Step 4: Report**

Report the two job names produced and whether `ruff format --check` was clean on the
existing tree. Do not commit.

---

### Task 3 (Lane B): the security workflow

**Files:**
- Create: `.github/workflows/security.yml`

**Interfaces:**
- Consumes: `uv sync --locked --group dev` from Task 1, which provides
  `pip-audit`, `bandit` and `cyclonedx-py`
- Produces: status checks named exactly `dependencies`, `sast`, `secrets` and `sbom`

- [ ] **Step 1: Write the workflow**

```yaml
name: security

on:
  pull_request:
    branches: [dev, main]
  schedule:
    # Monday 06:00 UTC. The CVE database changes daily and the code does not,
    # so a new advisory against an untouched dependency needs its own trigger.
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: security-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # WARNING: required status check in the main ruleset. Do not rename.
  dependencies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      - name: Export the locked set
        run: uv export --format requirements-txt --no-emit-project --all-groups > requirements-audit.txt
      - name: Audit the locked set
        run: uv run pip-audit --requirement requirements-audit.txt --strict

  # WARNING: required status check in the main ruleset. Do not rename.
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      - run: uv run bandit -c pyproject.toml -r ampeer_sim tools

  # WARNING: required status check in the main ruleset. Do not rename.
  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - name: Install gitleaks
        run: |
          curl -sSfL -o gitleaks.tar.gz \
            https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
          tar -xzf gitleaks.tar.gz gitleaks
          chmod +x gitleaks
      - name: Scan the commits this pull request adds
        if: github.event_name == 'pull_request'
        run: |
          ./gitleaks detect --source . --redact --no-banner \
            --log-opts "origin/${{ github.base_ref }}..HEAD"
      - name: Scan the full history and report only
        if: github.event_name != 'pull_request'
        run: ./gitleaks detect --source . --redact --no-banner || true

  sbom:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          enable-cache: true
      - run: uv sync --locked --group dev
      - run: uv export --format requirements-txt --no-emit-project --all-groups > requirements-sbom.txt
      - run: uv run cyclonedx-py requirements requirements-sbom.txt --output-format JSON --outfile sbom.json
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: sbom
          path: sbom.json
```

The two-mode `secrets` job is the point of this file. Scanning the whole history on
a pull request would let a finding from last year block a pull request that cannot
fix it, and a check like that gets dismissed within a week. Scanning only the
commits the pull request adds blocks exactly the finding its author can act on.

- [ ] **Step 2: Prove every command in the workflow works locally**

Run each of these and record the outcome. They are the actual commands the workflow
runs, so a wrong flag surfaces here rather than in a red pull request.

```bash
uv export --format requirements-txt --no-emit-project --all-groups > requirements-audit.txt
uv run pip-audit --requirement requirements-audit.txt --strict
uv run bandit -c pyproject.toml -r ampeer_sim tools
uv run cyclonedx-py requirements requirements-audit.txt --output-format JSON --outfile sbom.json
python -c "import json; d=json.load(open('sbom.json')); print('bomFormat:', d['bomFormat'], 'components:', len(d.get('components', [])))"
```

Expected: pip-audit reports no known vulnerabilities; bandit reports no issues of
medium severity or higher; the SBOM prints `bomFormat: CycloneDX` and a component
count above zero.

If `cyclonedx-py` rejects the subcommand, run `uv run cyclonedx-py --help`, use the
subcommand it actually offers for a requirements file, and report the correction so
the workflow can be updated to match. Do not leave the workflow with a command you
have not run.

If pip-audit or bandit reports a real finding, do not suppress it. Report it: a
finding on day one is the tool doing its job and is a result, not an obstacle.

- [ ] **Step 3: Verify pinning and permissions**

Run:

```bash
python - <<'PY'
import re, pathlib
text = pathlib.Path(".github/workflows/security.yml").read_text(encoding="utf-8")
unpinned = [line.strip() for line in text.splitlines()
            if "uses:" in line and not re.search(r"@[0-9a-f]{40}", line)]
assert not unpinned, f"unpinned actions: {unpinned}"
for name in ("dependencies:", "sast:", "secrets:", "sbom:"):
    assert name in text, f"missing job {name}"
assert "permissions:" in text
print("security.yml: four jobs, all actions pinned, permissions declared")
PY
```

- [ ] **Step 4: Clean up and report**

Delete `requirements-audit.txt`, `requirements-sbom.txt` and `sbom.json` from the
working tree; they are build outputs and must not be committed. Report the four job
names, the pip-audit and bandit outcomes, and any command correction you had to
make. Do not commit.

---

### Task 4 (Lane C): the local developer loop

**Files:**
- Create: `.pre-commit-config.yaml`
- Modify: `.gitattributes`

**Interfaces:**
- Consumes: `ruff` from the dev group in Task 1
- Produces: `pre-commit run --all-files` as a local command

- [ ] **Step 1: Write the hook configuration**

```yaml
# Fast hooks only. Anything over roughly two seconds belongs in CI: a slow hook
# gets skipped with --no-verify, and a bypassed gate is worse than no gate
# because you think it is there. That is why mypy is not in this list.
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=1024]
      - id: check-yaml
      - id: check-toml
      - id: mixed-line-ending
        args: [--fix=lf]

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
```

- [ ] **Step 2: Extend .gitattributes**

The file currently holds one line. Replace its contents with:

```
# Auto detect text files and perform LF normalization
* text=auto

# Shell scripts must stay LF even in a Windows working tree. A script checked
# out with CRLF and then run inside a Linux container fails with an error that
# has nothing to do with its contents.
*.sh text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
```

- [ ] **Step 3: Install and run the hooks**

Run: `uv run pre-commit install`
Expected: hooks installed to `.git/hooks/pre-commit`.

Run: `uv run pre-commit run --all-files`
Expected: every hook passes, or reports files it fixed. If hooks modified files,
run it a second time and expect all green.

- [ ] **Step 4: Time the hooks**

Run:

```bash
python - <<'PY'
import subprocess, time
start = time.perf_counter()
result = subprocess.run(["uv", "run", "pre-commit", "run", "--all-files"],
                        capture_output=True, text=True)
elapsed = time.perf_counter() - start
print(f"pre-commit --all-files took {elapsed:.1f} s, exit {result.returncode}")
assert elapsed < 20.0, "too slow across the whole tree; a single commit must stay well under this"
PY
```

Expected: comfortably under twenty seconds across the entire tree, which puts a
normal single-file commit far below the two second rule.

- [ ] **Step 5: Report**

Report the hook run time, whether any files were modified, and whether
`mixed-line-ending` changed anything, since that reveals existing CRLF damage. Do
not commit.

---

### Task 5 (Lane D): policy, automation and the ruleset script

**Files:**
- Create: `.github/dependabot.yml`
- Create: `scripts/setup_rulesets.sh`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the job names `quality`, `test`, `dependencies`, `sast` and `secrets`
- Produces: an idempotent script that creates or updates the `main` ruleset

- [ ] **Step 1: Write the Dependabot configuration**

```yaml
# Pinning actions to a SHA stops a moved tag from changing what runs. It also
# means nothing ever updates unless something updates it, which is why this file
# is not optional: without it, SHA pinning trades one risk for another.
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    target-branch: "dev"

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    target-branch: "dev"
```

Dependabot opens its pull requests against `dev`, never `main`, so an automated
bump travels the same road as every other change.

- [ ] **Step 2: Write the ruleset script**

Infrastructure that only exists as clicks in a settings page cannot be reviewed and
cannot be restored. This script is the ruleset.

```bash
#!/usr/bin/env bash
# Create or update the branch rulesets for Ampeer. Idempotent: safe to re-run.
#
# The required checks below must match the job names in .github/workflows/ci.yml
# and .github/workflows/security.yml exactly. A renamed job produces a check that
# never arrives and a pull request that waits forever.
set -euo pipefail

REPO="${1:-stijnvandepol/Ampeer}"

apply_ruleset() {
  local name="$1" payload="$2"
  local existing
  existing=$(gh api "repos/${REPO}/rulesets" --jq \
    ".[] | select(.name == \"${name}\") | .id" || true)
  if [ -n "${existing}" ]; then
    echo "updating ruleset ${name} (id ${existing})"
    gh api "repos/${REPO}/rulesets/${existing}" -X PUT --input - <<<"${payload}" >/dev/null
  else
    echo "creating ruleset ${name}"
    gh api "repos/${REPO}/rulesets" -X POST --input - <<<"${payload}" >/dev/null
  fi
}

# main: nothing lands here except through a green pull request. bypass_actors is
# empty on purpose, including for the repository owner. A rule with an exception
# for the only person who works on the project is not a rule.
apply_ruleset "protect-main" "$(cat <<'JSON'
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "required_linear_history"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": true,
      "allowed_merge_methods": ["squash", "merge"]
    }},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false,
      "required_status_checks": [
        {"context": "quality"},
        {"context": "test"},
        {"context": "dependencies"},
        {"context": "sast"},
        {"context": "secrets"}
      ]
    }}
  ]
}
JSON
)"

# dev: you work here, so direct commits are allowed. What is forbidden is losing
# history, because that is the one mistake nothing else can undo.
apply_ruleset "protect-dev" "$(cat <<'JSON'
{
  "name": "protect-dev",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"}
  ]
}
JSON
)"

echo
echo "rulesets now on ${REPO}:"
gh api "repos/${REPO}/rulesets" --jq '.[] | "  \(.name): \(.enforcement)"'
```

- [ ] **Step 3: Verify the script is syntactically valid without running it**

Run: `bash -n scripts/setup_rulesets.sh`
Expected: no output, exit 0.

Run:

```bash
python - <<'PY'
import json, pathlib, re
text = pathlib.Path("scripts/setup_rulesets.sh").read_text(encoding="utf-8")
blocks = re.findall(r"<<'JSON'\n(.*?)\nJSON", text, re.S)
assert len(blocks) == 2, f"expected two JSON payloads, found {len(blocks)}"
main = json.loads(blocks[0])
contexts = [c["context"] for r in main["rules"]
            if r["type"] == "required_status_checks"
            for c in r["parameters"]["required_status_checks"]]
assert contexts == ["quality", "test", "dependencies", "sast", "secrets"], contexts
assert main["bypass_actors"] == [], "main must have no bypass actors"
json.loads(blocks[1])
print("both ruleset payloads are valid JSON and require the five checks")
PY
```

Expected: the confirmation line. Do not execute the script itself; Phase 3 does
that, and only with the owner's go-ahead.

- [ ] **Step 4: Add the working rules to CLAUDE.md**

Insert this block immediately after the `## Fasering` section:

```markdown
## Werkwijze en poorten

- Werk op `dev` of op een `feat/**`-branch, nooit direct op `main`
- Naar `main` gaat alleen een pull request waarvan alle vereiste checks groen zijn
- Elke nieuwe afhankelijkheid gaat via `uv add`, en `uv.lock` wordt meegecommit
- Elke GitHub Action staat op een commit-SHA, met de versie als comment erachter
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` zijn een
  interface met de rulesets. Hernoem er nooit een zonder
  `scripts/setup_rulesets.sh` in dezelfde commit mee te wijzigen
- De dekkingsdrempel mag omhoog en nooit omlaag
```

- [ ] **Step 5: Report**

Report the five required check names as they appear in the script, and confirm the
CLAUDE.md block was inserted after `## Fasering`. Do not commit.

---

## Phase 2: the integration gate

### Task 6: Verify the four lanes fit together

**Files:**
- Modify: none. This task reads and reports.

**Interfaces:**
- Consumes: everything produced in Phase 0 and Phase 1

This runs after all four lanes report, never alongside them. Its job is the seams:
each lane verified itself, so what is left is whether their assumptions about each
other hold.

- [ ] **Step 1: Check the job name contract in both directions**

Run:

```bash
python - <<'PY'
import json, pathlib, re

ci = pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
sec = pathlib.Path(".github/workflows/security.yml").read_text(encoding="utf-8")
script = pathlib.Path("scripts/setup_rulesets.sh").read_text(encoding="utf-8")

defined = set(re.findall(r"^  ([a-z][a-z0-9_-]*):$", ci + "\n" + sec, re.M))
payload = json.loads(re.findall(r"<<'JSON'\n(.*?)\nJSON", script, re.S)[0])
required = {c["context"] for r in payload["rules"]
            if r["type"] == "required_status_checks"
            for c in r["parameters"]["required_status_checks"]}

missing = required - defined
assert not missing, f"ruleset requires checks no workflow publishes: {missing}"
print(f"jobs defined: {sorted(defined)}")
print(f"checks required: {sorted(required)}")
print("every required check is published by a workflow")
PY
```

This is the failure this whole gate exists for. A ruleset requiring a check that no
workflow publishes does not error anywhere: it produces a pull request that waits
forever, with no message explaining why.

- [ ] **Step 2: Check that every tool a workflow calls is in the lockfile**

Run:

```bash
python - <<'PY'
import pathlib, re
lock = pathlib.Path("uv.lock").read_text(encoding="utf-8")
workflows = "\n".join(p.read_text(encoding="utf-8")
                      for p in pathlib.Path(".github/workflows").glob("*.yml"))
tools = set(re.findall(r"uv run ([a-z0-9_-]+)", workflows))
alias = {"cyclonedx-py": "cyclonedx-bom", "pip-audit": "pip-audit"}
missing = [t for t in tools if f'name = "{alias.get(t, t)}"' not in lock]
assert not missing, f"workflows call tools that are not locked: {missing}"
print(f"tools invoked: {sorted(tools)}, all present in uv.lock")
PY
```

- [ ] **Step 3: Check that nothing outside its lane was touched**

Run: `git status --porcelain`

Expected: exactly these paths and no others.

```
 M .gitattributes
 M CLAUDE.md
 M .github/workflows/ci.yml
 M pyproject.toml
?? .github/dependabot.yml
?? .github/workflows/security.yml
?? .pre-commit-config.yaml
?? scripts/setup_rulesets.sh
?? uv.lock
```

Any other path means a lane reached outside its ownership row, which is a process
failure worth reporting even when the change itself looks harmless.

- [ ] **Step 4: Run the gates locally exactly as CI will**

Run:

```bash
uv sync --locked --group dev
uv run ruff check ampeer_sim tests tools
uv run ruff format --check ampeer_sim tests tools
uv run mypy ampeer_sim
uv run pytest --cov --cov-report=term
uv run bandit -c pyproject.toml -r ampeer_sim tools
uv run pre-commit run --all-files
```

Expected: all green, coverage at or above 97 percent.

- [ ] **Step 5: Report and commit**

Report each check with its outcome. Only after every check is green does the
orchestrator commit:

```bash
git add -A
git commit -m "ci: add blocking quality and security gates with uv and pinned actions"
```

---

## Phase 3: three concurrent audits

Dispatch these three as separate agents at the same time, after Phase 2 has
committed. Each is asked to find problems, not to confirm the work. None of them
modifies files: they report findings, and fixes are decided afterwards.

### Task 7: Audit lens one, supply chain

**Files:** none, this task reads and reports.

- [ ] **Step 1: Answer these questions with evidence from the repository**

1. Is every `uses:` in every workflow pinned to a 40 character SHA? Name any that
   are not.
2. Does the SHA actually correspond to the version in the trailing comment? Verify
   at least one with `gh api repos/<owner>/<repo>/commits/<sha> --jq .sha`.
3. Does `uv.lock` contain hashes, and does `uv sync --locked` fail when
   `pyproject.toml` is edited without relocking? Prove the second by making a
   temporary edit, running the command, and restoring the file.
4. Can a dependency enter the project without appearing in `uv.lock`? Look for any
   `pip install` or `uv run --with` left in a workflow or a script.
5. Does Dependabot cover both ecosystems that can introduce code, and does it
   target `dev` rather than `main`?

- [ ] **Step 2: Report findings ranked by severity**

For each finding: what is wrong, what an attacker or an accident could do with it,
and the smallest change that fixes it. If you find nothing, say so plainly and name
the two things you checked hardest.

---

### Task 8: Audit lens two, workflow permissions and the runner

**Files:** none, this task reads and reports.

- [ ] **Step 1: Answer these questions with evidence**

1. Does every workflow declare `permissions:` at workflow level, and is the default
   `contents: read`? Name any job that receives more than it needs.
2. Does any workflow use `pull_request_target`, or check out code from a pull
   request and then execute it with elevated permissions? This is the pattern that
   turns a fork pull request into code execution with write access.
3. Is any secret referenced in a workflow that runs on `pull_request`? A secret
   available to a pull request from a fork is a secret you have published.
4. Could a contributor change a workflow file in a pull request and have that
   changed workflow run against the repository? Explain what actually happens on
   this repository and why.
5. Read the `## 8. Wat dit deelproject expliciet niet doet` section of the spec.
   The next sub-project adds a self-hosted runner on the owner's own network. List
   the specific things in the current workflow files that would become dangerous
   the moment a self-hosted runner exists, so the next design starts from a real
   list rather than a general worry.

- [ ] **Step 2: Report findings ranked by severity, with question five as its own section**

---

### Task 9: Audit lens three, does this hold up as engineering

**Files:** none, this task reads and reports.

- [ ] **Step 1: Answer these questions with evidence**

1. Is there any gate that can be silently skipped? Consider `--no-verify`, a job
   that reports success when its tool is missing, a `continue-on-error`, or a
   `|| true` that swallows a real failure. The `|| true` in the scheduled gitleaks
   run is deliberate; say whether any others are.
2. Is the coverage threshold enforced in a way that a future contributor cannot
   lower without it showing up in a diff someone reads?
3. Is anything configured in two places that could drift apart? Name each pair and
   say which one wins if they disagree.
4. Does the repository still work for someone who clones it fresh? Verify by
   reading, not running: what exactly must a new developer install before
   `uv sync --locked --group dev` works, and is that written down anywhere?
5. What is the single most likely way this pipeline gets weakened over the next six
   months, and what would make that harder?

- [ ] **Step 2: Report findings ranked by severity**

---

## Phase 4: activation, requires the owner's go-ahead

These steps change the remote repository and cannot be undone by editing a file.
Stop and ask before running any of them.

### Task 10: Create the branches and apply the rulesets

**Files:** none, this task runs commands against GitHub.

- [ ] **Step 1: Push the current main**

Run: `git push origin main`
Expected: the thirteen local commits reach `origin/main`. This must happen before
`dev` is created, or `dev` starts from a stale base.

- [ ] **Step 2: Create dev and make it the default branch**

```bash
git checkout -b dev
git push -u origin dev
gh repo edit stijnvandepol/Ampeer --default-branch dev
```

- [ ] **Step 3: Apply the rulesets**

Run: `bash scripts/setup_rulesets.sh`
Expected: two rulesets listed, both `active`.

- [ ] **Step 4: Prove main is actually closed**

Run:

```bash
git checkout main
git commit --allow-empty -m "test: this push must be rejected"
git push origin main
```

Expected: the push is **rejected** by the ruleset. If it succeeds, the protection is
not working and everything after this is theatre.

Then undo the local commit:

```bash
git reset --hard origin/main
git checkout dev
```

- [ ] **Step 5: Prove the gates actually block a pull request**

```bash
git checkout -b feat/prove-the-gate
printf '\ndef broken(:\n' >> ampeer_sim/validate.py
git add ampeer_sim/validate.py
git commit -m "test: deliberately broken syntax to prove the gate blocks"
git push -u origin feat/prove-the-gate
gh pr create --base main --head feat/prove-the-gate \
  --title "Prove the gate blocks" \
  --body "Deliberately broken. This pull request must not be mergeable."
```

Expected: `quality` and `test` fail, the pull request reports it cannot be merged,
and the merge button is unavailable. Record a screenshot or the output of
`gh pr checks feat/prove-the-gate` as evidence, then close the pull request and
delete the branch:

```bash
gh pr close feat/prove-the-gate --delete-branch
git checkout dev
git branch -D feat/prove-the-gate
```

This step is the only thing in the plan that proves the gates work. Everything
before it proves they are configured, which is not the same claim.

---

## Self-review

**Spec coverage.** Section 3 of the spec maps onto Tasks 5 and 10; section 4 onto
Tasks 2, 3 and 5; section 5 onto Tasks 5 and 6; section 6 onto Tasks 1 and 4;
section 7 onto Task 5; section 9 onto Tasks 6 and 10.

**One gap found and closed while reviewing.** The spec's definition of done requires
proving that a direct push to `main` is rejected and that a red pull request cannot
merge. Neither is provable by writing files, so both became explicit steps in
Task 10 rather than assumptions.

**Two things an executor should not mistake for defects.**

- The `|| true` in the scheduled gitleaks run is deliberate and is called out in
  Task 9 question one so an auditor confirms it rather than flags it.
- `requirements-audit.txt`, `requirements-sbom.txt` and `sbom.json` are build
  outputs. Task 3 deletes them; if they appear in Task 6 step 3 the lane did not
  clean up.

**Known risk in the plan itself.** Task 3 depends on the exact `cyclonedx-py`
subcommand for a requirements file. The task requires the agent to run the command
locally and correct the workflow if the CLI disagrees, rather than shipping a
command nobody executed.
