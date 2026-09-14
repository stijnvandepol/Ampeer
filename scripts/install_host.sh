#!/usr/bin/env bash
# Put on the host the five things the deploy refuses to run without.
#
# RUN FROM A CHECKOUT, BY A PERSON, AND NEVER FROM CI. Nothing in this
# repository may write to the LXC on its own: .github/workflows/deploy.yml
# checks nothing out, holds no token that can read this repository, and that is
# one of the four properties that make a self-hosted runner defensible at all.
# This script does not change that. It is a thing you run from your own machine
# over your own ssh, and every byte it sends comes from the checkout you are
# standing in.
#
# It exists because the list is five items long, one of them cannot come from
# git, and a deploy that stops on the one somebody missed costs a release
# cycle. It has done so three times: v0.2.0, v0.3.0 and v0.4.0 all stopped on
# `no preflight at /srv/ampeer/preflight_env.sh`.
#
# WHAT IT WILL NOT DO, and this is deliberate:
#
#   * It never writes .env. That file holds a signing key, a database password
#     and a mail API key, so it belongs on one machine and is not something to
#     copy between them. What this script does is run the preflight afterwards,
#     which names every variable that is still missing, in one pass, without
#     printing a value.
#   * It never restarts anything. Bringing the stack up is the deploy's job and
#     it does more than `up -d`: it pins the image digests to the ones CI built,
#     migrates, and falls back to the previous release if the new one does not
#     become healthy.
#   * It refuses to copy a file whose digest is not the one this release pins,
#     which cannot happen from a clean checkout and can happen from a dirty one.
#     A host that takes a file the deploy will then reject is a worse outcome
#     than doing nothing.
#
# Usage: install_host.sh <ssh-target> [path to the NEDU profile]
#
#   scripts/install_host.sh ampeer-lxc
#   scripts/install_host.sh root@10.0.0.8 /d/data/nedu-profiles-2025.csv

set -euo pipefail

HOST="${1:-}"
PROFILE="${2:-data/nedu-profiles-2025.csv}"
STACK=/srv/ampeer
PROFILE_DIR=/srv/profiles

if [ -z "${HOST}" ]; then
  echo "usage: $(basename "$0") <ssh-target> [path to the NEDU profile]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

DEPLOY=.github/workflows/deploy.yml

# The pins are read out of the workflow rather than repeated here. Two literals
# that must agree are one literal that eventually will not, and this is the
# same argument preflight_env.sh makes about its own list of names.
pin_for() {
  sed -n "s/^[[:space:]]*$1:[[:space:]]*\([0-9a-f]\{64\}\).*/\1/p" "${DEPLOY}" | head -1
}

fail() { echo "install_host: $*" >&2; }

copy_pinned() {
  local source="$1" name="$2" pin_name="$3"
  local expected actual
  expected="$(pin_for "${pin_name}")"
  if [ -z "${expected}" ]; then
    fail "no ${pin_name} in ${DEPLOY}; this script cannot tell a good copy from a bad one"
    exit 1
  fi
  actual="$(sha256sum "${source}" | cut -d' ' -f1)"
  if [ "${actual}" != "${expected}" ]; then
    fail "${source} is not what this release pins as ${pin_name}"
    fail "  in this checkout: ${actual}"
    fail "  this release:     ${expected}"
    fail "the deploy would refuse it; check out the tag you mean to install"
    exit 1
  fi
  scp -q "${source}" "${HOST}:${STACK}/${name}"
  echo "  ${name}  ${actual}"
}

echo "making ${STACK} and ${PROFILE_DIR} on ${HOST}"
ssh "${HOST}" "mkdir -p ${STACK} ${PROFILE_DIR}"

echo "copying the three files the deploy checks by digest"
copy_pinned infra/docker-compose.yml docker-compose.yml COMPOSE_SHA256
copy_pinned scripts/preflight_env.sh preflight_env.sh PREFLIGHT_SHA256
copy_pinned scripts/backup_db.sh backup_db.sh BACKUP_SHA256

# The fifth thing, and the only one that cannot come from a git tag: data/ is
# gitignored, so the deploy's own "copy it from this tag" message has nothing
# to point at for this one. An absent bind mount source is not an error either:
# the Docker daemon creates an empty DIRECTORY at the path and mounts it over
# the place the CSV should be, the container starts, and every advice fails.
if [ ! -f "${PROFILE}" ]; then
  fail "no consumption profile at ${PROFILE}"
  fail "it is gitignored, so it is not in this checkout unless you put it there"
  fail "pass its path as the second argument"
  exit 1
fi
echo "copying the consumption profile, which is not in git"
scp -q "${PROFILE}" "${HOST}:${PROFILE_DIR}/$(basename "${PROFILE}")"
echo "  $(basename "${PROFILE}")  $(sha256sum "${PROFILE}" | cut -d' ' -f1)"

# Ahead of the deploy rather than after it, because Docker does not share a
# port: a container that cannot bind simply does not start, and meeting that
# for the first time during a release is expensive. Advisory only; ss is not on
# every image and a missing tool is not a reason to stop.
echo "checking the published port is free"
if ! ssh "${HOST}" "command -v ss >/dev/null && ss -lntH 'sport = :8080' | grep -q . && echo BUSY || echo FREE" | grep -q BUSY; then
  echo "  8080 is free, or ss is not installed and could not say"
else
  fail "something on ${HOST} is already listening on 8080; the stack will not start"
  exit 1
fi

echo "checking the environment file"
if ! ssh "${HOST}" "test -f ${STACK}/.env"; then
  fail "no ${STACK}/.env, and this script will not write one"
  fail "it holds a signing key, a database password and a mail API key"
  fail "write it on the host from infra/.env.example, then run this again"
  exit 1
fi
ssh "${HOST}" "bash ${STACK}/preflight_env.sh ${STACK}/.env"

echo
echo "the host is ready. The deploy is still the thing that starts it:"
echo "  gh run rerun <the failed run> --failed     (or push the tag again)"
