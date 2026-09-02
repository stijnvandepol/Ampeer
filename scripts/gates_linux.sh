#!/usr/bin/env bash
# Run the gates on the operating system that decides them.
#
# Development happens on Windows and the pipeline runs on Linux, and the two do
# not agree about everything. Three differences have already cost something:
#
# - Three tests skip here with "this filesystem does not carry POSIX modes".
#   They are the ones asserting a backup file is 0600 inside a 0700 directory,
#   which docs/dpia.md states in its risk table, and until 2026-08-22 they had
#   never run anywhere. They pass on Linux.
# - A check that reads `git ls-files` passed here and failed on the commit,
#   because the suite had been run before `git add`. Rebuilding the tree from
#   `git archive` is what surfaced it, since that is the tree a checkout gets.
# - Case. Two names that differ only in their capitals are one file here and
#   two there. No example is spelled out, because tests/test_portability.py
#   scans for exactly that and would find the example.
#
# It exists because the pipeline is not free. Since 2026-08-21 GitHub refuses to
# start the jobs, and the annotation is about billing rather than minutes, so
# every run after that is paid for. A red one spent on something a container
# could have said for nothing is a wasted payment.
#
# It defines no gates of its own. It runs scripts/gates.sh inside the container,
# so there is one place that says what a gate is and the contract in
# tests/test_pipeline_contract.py still covers all of it. What this file decides
# is only where that runs.
#
# Usage: bash scripts/gates_linux.sh [gate ...]

set -uo pipefail

# Git Bash on Windows rewrites an argument that looks like a Unix path into a
# Windows one before the program sees it, which turns `-e PATH=/root/...` into
# something docker cannot resolve and produces `exec: "bash": executable file
# not found`. Measured on 2026-08-22: the same command works with this set and
# fails without it. Ignored by every other shell, so it costs nothing there.
export MSYS_NO_PATHCONV=1

cd "$(dirname "${BASH_SOURCE[0]}")/.." || {
  printf 'cannot enter the repository root from %s\n' "${BASH_SOURCE[0]}" >&2
  exit 1
}

# The gates that need only Python. The frontend half needs Node and pnpm, which
# this image does not have; adding them would double the setup for the half
# whose behaviour does not differ between the two systems. Left to CI, and said
# so rather than left to be noticed.
DEFAULT_GATES=(sync ruff ruff-format mypy shellcheck django-deploy-check bandit pytest)

# Both versions are read from the files that already pin them, so this script
# cannot drift from the pipeline it is imitating. That drift is the thing this
# repository keeps finding, and a hardcoded "3.12" here would be an instance of
# it in the tool built to prevent it.
PYTHON_VERSION="$(tr -d '[:space:]' < .python-version)"
UV_VERSION="$(
  awk '/astral-sh\/setup-uv/ { found = 1 }
       found && /version: "/ { gsub(/[^0-9.]/, "", $2); print $2; exit }' \
    .github/workflows/ci.yml
)"

if [ -z "${PYTHON_VERSION}" ] || [ -z "${UV_VERSION}" ]; then
  printf 'gates-linux: cannot read the python or uv version this project pins\n' >&2
  printf '  python: %s  uv: %s\n' "${PYTHON_VERSION:-<empty>}" "${UV_VERSION:-<empty>}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  printf 'gates-linux: NOT RUN -- docker is not on PATH, and there is no other way\n'
  printf '  to reach a Linux filesystem from here. CI decides these.\n'
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  printf 'gates-linux: NOT RUN -- docker is installed but not answering. Start it.\n'
  exit 0
fi

IMAGE="python:${PYTHON_VERSION}-slim"
NAME="ampeer-gates-linux"
if [ "$#" -gt 0 ]; then
  WANTED=("$@")
else
  WANTED=("${DEFAULT_GATES[@]}")
fi

# The database lives on this host, so the address the caller uses to reach it
# does not mean the same thing inside a container. Translated rather than
# documented, because a caller who exports the value scripts/gates.sh expects
# should not have to know that.
PG_HOST="${POSTGRES_HOST:-}"
case "${PG_HOST}" in
  127.0.0.1 | localhost | ::1 | "") PG_HOST="host.docker.internal" ;;
esac

printf 'gates-linux: %s, uv %s, gates: %s\n' "${IMAGE}" "${UV_VERSION}" "${WANTED[*]}"

# Streamed in rather than written to a file and copied. A temporary file means
# a path, and a path means the host and the container have to agree on what it
# spells: mktemp here produces /tmp/... which Windows docker reads as C:	mp
# and cannot find. A pipe has no name to disagree about.
trap 'docker rm -f "${NAME}" >/dev/null 2>&1 || true' EXIT

docker rm -f "${NAME}" >/dev/null 2>&1 || true
docker run -d --name "${NAME}" --add-host=host.docker.internal:host-gateway   "${IMAGE}" sleep infinity >/dev/null || {
  printf 'gates-linux: could not start %s
' "${IMAGE}" >&2
  exit 1
}
docker exec "${NAME}" mkdir -p /work

# The index, not the working tree and not HEAD.
#
# Not the working tree, because git archive applies the modes git records. A
# bind mount of this filesystem arrives as 0777 and made ruff report every
# Python file as an executable without a shebang: a hundred and ten findings
# that were all the harness.
#
# Not HEAD, because the checks that read git ls-files read the index, and on
# 2026-08-22 one of them passed on unstaged work and failed the moment it was
# committed. Archiving the index means that git add is enough to have a change
# judged, which is the point at which judging it becomes possible.
if ! git archive --format=tar "$(git write-tree)" |
  docker exec -i "${NAME}" tar -xf - -C /work; then
  printf 'gates-linux: could not put the index into the container
' >&2
  exit 1
fi

# The repository itself as well, because scripts/gates.sh runs tests that ask
# git what it tracks, and git archive carries the files and not the history.
if ! tar -cf - .git | docker exec -i "${NAME}" tar -xf - -C /work; then
  printf 'gates-linux: could not copy the git directory
' >&2
  exit 1
fi

docker exec "${NAME}" bash -c '
set -e
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq git curl >/dev/null 2>&1
git config --global --add safe.directory /work
curl -LsSf "https://astral.sh/uv/'"${UV_VERSION}"'/install.sh" | sh >/dev/null 2>&1
' || {
  printf 'gates-linux: preparing the container failed
' >&2
  exit 1
}

docker exec \
  -e "PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin" \
  -e "POSTGRES_HOST=${PG_HOST}" \
  -e "POSTGRES_PORT=${POSTGRES_PORT:-5432}" \
  -e "POSTGRES_DB=${POSTGRES_DB:-ampeer}" \
  -e "POSTGRES_USER=${POSTGRES_USER:-ampeer}" \
  -e "POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-}" \
  "${NAME}" bash -c 'cd /work && bash scripts/gates.sh '"${WANTED[*]}"
status=$?

printf '\ngates-linux: scripts/gates.sh exited %s inside %s\n' "${status}" "${IMAGE}"
exit "${status}"
