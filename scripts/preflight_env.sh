#!/usr/bin/env bash
# Check that the deploy has everything it needs, before anything restarts.
#
# INSTALLED BY HAND. Nothing in this repository can write to the LXC, so this
# file is copied to /srv/ampeer/preflight_env.sh by a person, next to
# docker-compose.yml and .env, and .github/workflows/deploy.yml runs the copy
# that is already there. A file that looks automatic and is not is worse than
# one that says so. When this script changes, the copy on the host has to be
# replaced by hand as well; nothing detects that it was not.
#
# Why it exists at all. prod.py requires thirteen variables and gives none of
# them a default, which is correct: a default for a secret is a secret in the
# repository with extra steps. The consequence is that a missing one does not
# produce a warning, it produces a container that exits, is restarted by the
# daemon, exits again, and keeps doing that. On a host nobody is logged in to,
# that is an outage that reads as a code fault, and the person debugging it
# starts in the wrong place. Reading the file first turns that into one line.
#
# It reports every missing name, not the first. Fixing one, redeploying, and
# being told about the next one is four deploys for one mistake.
#
# It never prints a value. Its output goes to a workflow log that anyone with
# read access to the repository can open, and GitHub masks only the secrets it
# knows about, which is none of these.
#
# Usage: preflight_env.sh [path to the env file]   (default /srv/ampeer/.env)

set -euo pipefail

ENV_FILE="${1:-/srv/ampeer/.env}"

# The thirteen names prod.py refuses to start without. Written out rather than
# derived from infra/.env.example, because a list that follows the file it is
# supposed to check cannot disagree with it; tests/test_deploy_workflow.py
# compares the two and fails on the drift instead.
#
# Deliberately not in this list:
#   AMPEER_VERSION           the deploy job exports it from the tag it is
#                            deploying, and the shell environment beats the env
#                            file in compose interpolation. Requiring it in the
#                            file would demand the host be edited per release,
#                            which is the manual step this pipeline removes.
REQUIRED=(
  DJANGO_SECRET_KEY
  DJANGO_ALLOWED_HOSTS
  DJANGO_CORS_ALLOWED_ORIGINS
  DJANGO_NUM_PROXIES
  AMPEER_NEDU_PROFILE_PATH
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_HOST
  AMPEER_MAIL_TRANSPORT
  RESEND_API_KEY
  AMPEER_MAIL_FROM
  AMPEER_SITE_ORIGIN
)

fail() {
  echo "preflight: $*" >&2
}

if [ ! -f "${ENV_FILE}" ]; then
  fail "no env file at ${ENV_FILE}"
  fail "copy infra/.env.example there and fill it in; it is deliberately outside git"
  exit 1
fi

# Parsed, never sourced. `source` on this file executes it, and it holds a
# signing key, a database password and a tunnel token: a stray backtick or a $(
# in any of them would become a command running as whoever deploys. Compose
# does not treat an env file as shell either, so parsing it is also the reading
# that matches what compose will do with it.
declare -A VALUES=()
carriage_returns=0
while IFS= read -r line || [ -n "${line}" ]; do
  # A file edited or copied from Windows arrives CRLF, and neither compose nor
  # this loop strips the carriage return: it becomes the last character of
  # every value. POSTGRES_PASSWORD then does not match the one the database was
  # created with, DJANGO_ALLOWED_HOSTS does not match the host header, and
  # every check below passes because a lone carriage return is not empty. It is
  # reported rather than trimmed, because trimming it here would make this
  # script agree the file is fine while compose still reads the values with it.
  case "${line}" in
    *$'\r') carriage_returns=$((carriage_returns + 1)) ;;
  esac
  case "${line}" in
    ''|'#'*) continue ;;
  esac
  name="${line%%=*}"
  # A line with no '=' is not an assignment; ignore it rather than storing the
  # whole line under its own name.
  if [ "${name}" = "${line}" ]; then
    continue
  fi
  # Trim the surrounding whitespace a hand-edited file collects. Nothing else
  # is interpreted: no quote stripping, no expansion.
  name="${name#"${name%%[![:space:]]*}"}"
  name="${name%"${name##*[![:space:]]}"}"
  VALUES["${name}"]="${line#*=}"
done < "${ENV_FILE}"

if [ "${carriage_returns}" -ne 0 ]; then
  fail "${ENV_FILE} has Windows line endings on ${carriage_returns} line(s)."
  fail "the carriage return becomes part of every value, so the password the"
  fail "database gets is not the password that was typed. Convert the file to LF."
  exit 1
fi

# Whitespace counts as empty. Measured on 2026-08-21: DJANGO_SECRET_KEY set to
# three spaces printed "9 variables set" and exited zero, and nothing
# downstream saves it either. prod.py tests `if not value`, and three spaces
# are truthy, so the process starts: the signing key is three spaces and
# ALLOWED_HOSTS becomes ["   "], which answers every request with 400
# DisallowedHost. That is not the restart loop this script was written for, it
# is worse, because the container reports itself as up and the failure looks
# like DNS or the tunnel.
#
# The trim is only used to decide emptiness. The value itself is never
# rewritten, because compose will read it with the spaces on it and a script
# that trimmed here would be agreeing the file is fine about a value compose
# still reads differently. Same reason the carriage return above is reported
# rather than stripped.
blank() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  [ -z "${value}" ]
}

missing=()
for name in "${REQUIRED[@]}"; do
  if blank "${VALUES[${name}]:-}"; then
    missing+=("${name}")
  fi
done

if [ "${#missing[@]}" -ne 0 ]; then
  fail "${#missing[@]} required variable(s) missing, empty or whitespace in ${ENV_FILE}:"
  for name in "${missing[@]}"; do
    fail "  ${name}"
  done
  fail "prod.py gives none of these a default, so the api container would"
  fail "restart in a loop instead of reporting this."
  exit 1
fi

# DJANGO_NUM_PROXIES is the one required value prod.py parses rather than
# reads. `_required_count` refuses anything str.isdigit() refuses, and it does
# so while the settings module is being imported, which is a container that
# exits, is restarted, and exits again: the exact outage this script exists to
# turn into one line. Set is not enough. Measured on 2026-08-21,
# DJANGO_NUM_PROXIES=two passed this preflight and produced that loop.
#
# The pattern is the shell's spelling of isdigit for ASCII, and it is one step
# stricter: it also refuses a value with a space in it, which isdigit refuses
# as well. It never echoes the value, for the reason at the top of this file.
PROXIES="${VALUES[DJANGO_NUM_PROXIES]}"
case "${PROXIES}" in
  *[!0-9]*)
    fail "DJANGO_NUM_PROXIES is not a whole number of proxies."
    fail "prod.py refuses anything else while importing settings, so the api"
    fail "container would restart in a loop instead of reporting this. Two here:"
    fail "the tunnel connector and nginx. Zero is legal and means neither."
    exit 1
    ;;
esac

# AMPEER_MAIL_TRANSPORT decides whether a household ever receives a mail.
# prod.py accepts `file` as well as `resend`, because the local stack runs
# under prod settings and its live checks read the mail out of a file. On a
# host `file` is the quietest outage there is: every reset mail is written
# to disk inside a container and nobody is told. So a host is held to
# `resend` here, before any container starts, and the local stack's env
# fixture is the only file in the repository that ever says `file`.
TRANSPORT="${VALUES[AMPEER_MAIL_TRANSPORT]}"
case "${TRANSPORT}" in
  resend) ;;
  *)
    fail "AMPEER_MAIL_TRANSPORT is not 'resend'."
    fail "prod.py would start and write every mail to a file inside the container,"
    fail "and no household would receive one. Set it to resend on a host."
    exit 1
    ;;
esac

# AMPEER_NEDU_PROFILE_PATH carries two meanings in docker-compose.yml on
# purpose. The value the API reads is fixed to /srv/profiles/nedu.csv, set in
# the compose file and not from here. The value in the env file is the *host*
# path used as the bind mount source, and that is the side that can be wrong.
#
# Checking that the name is set is not enough. A host path that does not exist
# makes the daemon create an empty directory there and mount it over the file,
# so the container starts, the setting is present, and every advice fails on a
# directory where a CSV should be. The readiness check catches that afterwards;
# this catches it before the old container has been replaced.
PROFILE="${VALUES[AMPEER_NEDU_PROFILE_PATH]}"

case "${PROFILE}" in
  */*) ;;
  *)
    fail "AMPEER_NEDU_PROFILE_PATH is '${PROFILE}', which has no directory separator."
    fail "compose reads a bind mount source with no slash as the name of a volume,"
    fail "creates it empty, and mounts it over the profile file. Use an absolute path."
    exit 1
    ;;
esac

if [ ! -f "${PROFILE}" ]; then
  fail "AMPEER_NEDU_PROFILE_PATH points at '${PROFILE}', which is not a file."
  exit 1
fi

if [ ! -r "${PROFILE}" ]; then
  fail "AMPEER_NEDU_PROFILE_PATH points at '${PROFILE}', which exists but is not readable."
  fail "the api container runs as uid 10001 and reads it read only."
  exit 1
fi

echo "preflight: ${#REQUIRED[@]} variables set, profile readable at the host path"
