#!/usr/bin/env bash
# Run the checks that CI runs, locally, and say which ones did not run here.
#
# Why this exists. Until 2026-08-21 there was no local runner, so every
# pre-push check was a command improvised at the prompt, and an improvised
# check tends to be a grep over what a tool printed. One of them, measured
# that day, filtered bandit's output for "High" while the finding was Medium:
# a red `sast` looked green locally and the mistake was found by pushing it.
# A grep over tool output is not a gate. An exit code is.
#
# So the two rules here are narrow and they are the whole point:
#
#   1. Every gate is judged by its exit status. Nothing in this file reads,
#      filters or pattern-matches what a tool prints. Output goes to the
#      terminal for a human; the verdict comes from the process.
#   2. A gate that cannot run here is reported as NOT RUN, never skipped
#      quietly and never counted as a pass. Postgres, node and the gitleaks
#      binary are not always present on a development machine, and a summary
#      that hid their absence would be the same defect this file was written
#      for, one layer up.
#
# It is a convenience, not an authority. The required checks live in
# .github/workflows/, they run on a clean machine, and they are what the
# ruleset reads. Green here means "worth pushing", never "will be green there".
# tests/test_pipeline_contract.py pairs the commands below with those files so
# this script cannot quietly come to cover less than it claims.
#
# Usage: scripts/gates.sh [name ...]     (no arguments runs every gate)
#
# A full run is not quick, and most of it is two gates. Measured on a Windows
# development machine on 2026-08-21, pip-audit took over twenty minutes because
# it builds every locked package in an isolated environment, against about a
# minute for the same command on the Linux runner; the frontend build is the
# other slow one. Naming the gates you want is the answer, and an unknown name
# is refused rather than quietly selecting nothing.

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PASSED=(); FAILED=(); SKIPPED=()

bold() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

# Run one gate and record the verdict. The command is run with its output
# attached to this terminal and its exit status is the only thing consulted.
gate() {
  local name="$1"; shift
  if [ "${#WANTED[@]}" -ne 0 ] && ! printf '%s\n' "${WANTED[@]}" | grep -qx "${name}"; then
    return 0
  fi
  bold "${name}"
  if "$@"; then
    PASSED+=("${name}")
  else
    FAILED+=("${name}")
  fi
}

# Record a gate that this machine cannot run, with the reason a human needs in
# order to decide whether to care. Never counted as a pass.
skip() {
  local name="$1" reason="$2"
  if [ "${#WANTED[@]}" -ne 0 ] && ! printf '%s\n' "${WANTED[@]}" | grep -qx "${name}"; then
    return 0
  fi
  SKIPPED+=("${name} -- ${reason}")
}

WANTED=("$@")

# Every name this script knows, read from its own gate, skip and fallback
# lines. A name that matches none of them would otherwise select nothing, print
# an empty verdict and exit zero, which is a green result for having checked
# nothing at all. That is the shape of failure this whole file exists to
# refuse, so it refuses it here too rather than only on behalf of the tools.
if [ "${#WANTED[@]}" -ne 0 ]; then
  KNOWN="$(
    grep -oE '^[[:space:]]*(gate|skip) [a-z0-9-]+' "${BASH_SOURCE[0]}" | awk '{ print $2 }'
    grep -oE '^[[:space:]]*for name in [a-z0-9 -]+' "${BASH_SOURCE[0]}" |
      sed 's/.*for name in //' | tr ' ' '\n'
  )"
  for wanted in "${WANTED[@]}"; do
    if ! printf '%s\n' "${KNOWN}" | grep -qx -- "${wanted}"; then
      printf 'gates: no gate named %s\n' "${wanted}" >&2
      exit 2
    fi
  done
fi

have() { command -v "$1" >/dev/null 2>&1; }

# A TCP connect, not pg_isready: psql is not installed everywhere the suite
# runs, and this only has to answer whether there is any point in starting. It
# proves that something is listening and nothing more.
something_listening_on_postgres() {
  (exec 3<>"/dev/tcp/${POSTGRES_HOST:-127.0.0.1}/${POSTGRES_PORT:-5432}") 2>/dev/null
}

# --- environment -------------------------------------------------------------
#
# --locked, so this is the same lockfile-drift check CI runs and not merely a
# way to get an environment. Every gate below borrows the result, which is why
# it is first: a stale environment turns every later verdict into a statement
# about code that is not the code in the commit.

gate sync uv sync --locked --group dev --group backend

# --- quality -----------------------------------------------------------------

gate ruff        uv run ruff check ampeer_sim ampeer_advice backend tests tools
gate ruff-format uv run ruff format --check ampeer_sim ampeer_advice backend tests tools
gate mypy        uv run mypy ampeer_sim ampeer_advice backend tools

# The deployment checklist under production settings. prod.py refuses to import
# without these, and the values are generated here for the same reason ci.yml
# generates them: nothing in a file that is read by a gate should look like a
# secret. They are never used against a real database; `check --deploy` reads
# settings and does not connect.
django_deploy_check() {
  DJANGO_SECRET_KEY="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(48))')" \
  POSTGRES_PASSWORD="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(16))')" \
  DJANGO_SETTINGS_MODULE=ampeer.settings.prod \
  DJANGO_ALLOWED_HOSTS=ampeer.nl \
  AMPEER_NEDU_PROFILE_PATH=/srv/ampeer/nedu-profiles-2025.csv \
  POSTGRES_DB=ampeer POSTGRES_USER=ampeer POSTGRES_HOST=db \
  DJANGO_NUM_PROXIES=1 \
  DJANGO_CORS_ALLOWED_ORIGINS=https://ampeer.nl \
    uv run python backend/manage.py check --deploy --fail-level WARNING
}
gate django-deploy-check django_deploy_check

gate pre-commit uv run pre-commit run --all-files --show-diff-on-failure

# --- test --------------------------------------------------------------------

# The suite needs Postgres. Roughly a tenth of it does; the rest passes without
# one, which is exactly why a partial run must not be reported as a pass.
#
# The password has to be supplied and this file writes no default for it. Two
# reasons, and the weaker one is that a password written into a file a gate
# reads is a credential in the repository however worthless it is; GitGuardian
# said so about the previous version of this line on 2026-08-21 and it was
# right. The stronger one is that a default here is a guess that the Postgres
# on this port is ours. Measured the same day: a Postgres belonging to another
# project answers the probe above and refuses the login, and the whole suite
# then goes red for a reason that has nothing to do with the commit. Asking for
# the credentials is how this script finds out it is talking to the right
# database instead of assuming it.
#
# The other four have defaults because a host, a port, a database name and a
# user name are not secrets and getting one of them wrong fails loudly.
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  skip pytest "POSTGRES_PASSWORD is not set, so there is no way to tell a scratch database from someone else's. infra/README.md section 7 has the two commands that start one and run against it"
elif something_listening_on_postgres; then
  gate pytest env POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}" POSTGRES_PORT="${POSTGRES_PORT:-5432}" \
    POSTGRES_DB="${POSTGRES_DB:-ampeer}" POSTGRES_USER="${POSTGRES_USER:-ampeer}" \
    POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
    uv run pytest --cov --cov-report=term-missing
else
  skip pytest "nothing is listening on ${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}; the database tests and the coverage gate cannot run"
fi

# --- sast --------------------------------------------------------------------

gate bandit  uv run bandit -c pyproject.toml -r ampeer_sim ampeer_advice backend tools
gate semgrep uv run semgrep --config .semgrep/frontend.yml --error --quiet frontend/src

# --- dependencies ------------------------------------------------------------

# The export and the audit are one gate here and two steps in CI, because an
# export that fails is not a finding, it is the audit never having run.
pip_audit() {
  uv export --format requirements-txt --no-emit-project --all-groups --output-file requirements-audit.txt \
    && uv run pip-audit --requirement requirements-audit.txt --strict
}
gate pip-audit pip_audit

sbom() {
  uv export --format requirements-txt --no-emit-project --all-groups --output-file requirements-sbom.txt \
    && uv run cyclonedx-py requirements requirements-sbom.txt --output-format JSON --output-file sbom.json
}
gate sbom sbom

# --- frontend ----------------------------------------------------------------

# Run from frontend/ rather than with --dir, so the command text here is the
# command text in the workflow and tests/test_pipeline_contract.py can pair
# the two without having to understand either shell.
in_frontend() { ( cd frontend && "$@" ); }

if have pnpm; then
  gate frontend-install   in_frontend pnpm install --frozen-lockfile
  gate frontend-lint      in_frontend pnpm lint
  gate frontend-typecheck in_frontend pnpm typecheck
  gate frontend-format    in_frontend pnpm format:check
  gate frontend-test      in_frontend pnpm test
  gate frontend-build     in_frontend pnpm build
  gate pnpm-audit         in_frontend pnpm audit --audit-level low
  # Playwright drives a real browser it has to download first, which is a
  # deliberate choice to leave to CI rather than to every clone.
  skip e2e "playwright downloads a browser first, which is left to CI; run pnpm exec playwright install --with-deps chromium and then pnpm e2e from frontend/"
else
  for name in frontend-install frontend-lint frontend-typecheck frontend-format frontend-test frontend-build pnpm-audit e2e; do
    skip "${name}" "pnpm is not on PATH; run corepack enable in frontend/"
  done
fi

# --- secrets -----------------------------------------------------------------

# The same scan the pull request gets, against the branch it will be merged
# into. CI runs it as ./gitleaks from a release it downloads and verifies by
# checksum; here it is whatever is on PATH, which is a weaker claim, and is
# part of why the summary names every gate it ran rather than totalling them.
gitleaks_scan() {
  gitleaks detect --source . --redact --no-banner \
    --log-opts "origin/${GITLEAKS_BASE:-dev}..HEAD"
}
if have gitleaks; then
  gate gitleaks gitleaks_scan
else
  skip gitleaks "the binary is not installed; CI fetches a pinned, checksummed release"
fi

# --- verdict -----------------------------------------------------------------
#
# Printed as three counts rather than one word. "Everything passed" is a
# sentence this script is not able to say honestly when part of it did not run,
# and the failure it was written to prevent was exactly a reassuring summary
# over a check that had not looked.

printf '\n\033[1m== verdict\033[0m\n'
for n in "${PASSED[@]:-}";  do [ -n "${n}" ] && printf '  pass     %s\n' "${n}"; done
for n in "${SKIPPED[@]:-}"; do [ -n "${n}" ] && printf '  NOT RUN  %s\n' "${n}"; done
for n in "${FAILED[@]:-}";  do [ -n "${n}" ] && printf '  FAIL     %s\n' "${n}"; done

printf '\n%d passed, %d failed, %d not run here\n' \
  "${#PASSED[@]}" "${#FAILED[@]}" "${#SKIPPED[@]}"

if [ "${#SKIPPED[@]}" -ne 0 ]; then
  printf 'the gates marked NOT RUN are decided in CI only.\n'
fi

[ "${#FAILED[@]}" -eq 0 ]
