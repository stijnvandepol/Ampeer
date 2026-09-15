#!/usr/bin/env bash
# Dump the Ampeer database, and answer whether a recent dump exists.
#
# INSTALLED BY HAND, like scripts/preflight_env.sh next to it. Nothing in this
# repository can write to the LXC, so this file is copied to
# /srv/ampeer/backup_db.sh by a person and the systemd unit in
# infra/systemd/ampeer-backup.service runs the copy that is already there. When
# this script changes, the copy on the host has to be replaced by hand as well;
# the deploy job compares its sha256 against the one pinned in
# .github/workflows/deploy.yml and refuses to deploy when they differ, which is
# the same treatment the preflight gets and for the same reason.
#
# WHY IT EXISTS. Three tables. StoredAdvice and ProductionCache can both be
# rebuilt: the first from the inputs it stores beside the answer, the second
# from PVGIS. AuditEvent cannot. It is append-only, it has no retention, and it
# is the record that a consent was given, an advice was generated and an export
# was made. Append-only defends it against being rewritten and does nothing at
# all about the disk going away, and the disk going away is the failure an audit
# log exists to survive. Until 2026-08-21 infra/README.md said in three places
# that nothing here takes a backup, and that was true.
#
# WHAT A BACKUP COSTS, because it is not free and hiding it would be worse.
# ninety days after an advice is made the purge deletes it and the service stops
# being able to find it. A dump taken before that deletion still holds it. Three
# things bound what that means, and all three are properties of this file rather
# than promises:
#
#   1. The timer runs after the purge, not before it, so a dump never contains
#      an advice that was already past its date when the dump was taken.
#   2. Dumps older than KEEP_DAYS are deleted here, on every run.
#   3. Restoring one does not extend anything permanently: the purge runs daily
#      and deletes whatever came back past its date within one cycle.
#
# So the question a backup actually raises is not how long a household's figures
# live in the service. It is who can read these files. They are written 0600
# into a directory this script creates 0700, and `--check` refuses to call a
# backup healthy when either is looser than that.
#
# Usage: backup_db.sh [--check] [directory]     (default /srv/ampeer/backups)

set -euo pipefail

#: How many daily dumps to keep. One week of restore points: short enough that
#: a copy of a purged advice does not outlive it by much, long enough that a
#: failure nobody looked at over a weekend is still recoverable on the Monday.
KEEP_DAYS=7

#: How old the newest dump may be before --check calls it stale, in hours.
#:
#: It has to be more than the timer's period or the check goes red every day in
#: the minutes before the run. Twenty six is the smallest number that clears a
#: daily timer with room for its AccuracySec and for a slow dump, and it still
#: fails on a single missed run, which is the whole point. Change the timer's
#: period and this has to move with it; infra/systemd/ampeer-backup.timer says
#: the same thing from the other side.
MAX_AGE_HOURS=26

#: The last thing pg_dump writes when it finished. A size threshold was the
#: first attempt here and it is the weaker check: measured on 2026-08-21
#: against PostgreSQL 16.15, a dump of an empty database is 643 bytes, so any
#: floor low enough not to reject a valid dump is also low enough to accept a
#: dump truncated at five kilobytes. This marker is written last and only on
#: success, so its absence is the question worth asking, and it catches an
#: empty file for free.
#:
#: Not the final line: 16.15 writes an `\unrestrict` line after it, so the tail is
#: searched rather than compared.
COMPLETE_MARKER="PostgreSQL database dump complete"
TAIL_LINES=20

STACK="${AMPEER_STACK:-/srv/ampeer}"

# Both default to the host layout and exist so this script can be run against a
# local stack without a copy of it that drifts. systemd gives the unit a clean
# environment and sets neither, so on the host these are the two paths below and
# nothing else can point them somewhere. See infra/systemd/ampeer-backup.service.
COMPOSE_FILE="${AMPEER_COMPOSE_FILE:-${STACK}/docker-compose.yml}"
ENV_FILE="${AMPEER_ENV_FILE:-${STACK}/.env}"

fail() {
  echo "backup: $*" >&2
}

check_mode=0
if [ "${1:-}" = "--check" ]; then
  check_mode=1
  shift
fi

DIR="${1:-${STACK}/backups}"

# --- the half that notices -----------------------------------------------------
#
# Deliberately reads nothing but the directory. It runs in the deploy job, on a
# runner that has docker but should not need the database to answer the question
# "is anything backing this up", and it runs in tests, where there is no stack at
# all. A check that needed the service it checks could not run in either place.

if [ "${check_mode}" -eq 1 ]; then
  if [ ! -d "${DIR}" ]; then
    # THE FIRST DEPLOY, which this check could not previously survive.
    #
    # It refuses a release that has no recent backup, and a backup is a
    # pg_dump out of the running db container. On a host that has never
    # deployed there is no container, so there can be no dump, so the check
    # refuses forever and the database it is protecting never comes into
    # existence. Measured on 2026-09-15: the v0.6.1 deploy cleared the
    # checkout, the preflight, the pull and the digest comparison, and stopped
    # here on a host where nothing had ever run.
    #
    # An absent database is not a broken backup. It is nothing to protect, and
    # saying so is the honest answer rather than a way past the check: the
    # refusal exists so that a migration cannot run over data with no copy of
    # it, and there is no data. Every later deploy meets a running container
    # and the demand holds in full.
    #
    # "Cannot tell" is not "no", deliberately. If docker is missing, or the
    # compose file is not there, or the command errors for any other reason,
    # this falls through and refuses exactly as before. That is also what keeps
    # the tests meaningful: they run where there is no stack at all, and they
    # still see the refusal they assert.
    if running="$(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps -q db 2>/dev/null)"       && [ -z "${running}" ]; then
      echo "backup: no database is running yet, so there is nothing to back up."
      echo "backup: this is a first deploy. The next one will find a container"
      echo "backup: and this check applies in full from then on."
      exit 0
    fi
    fail "no backup directory at ${DIR}"
    fail "nothing has ever run backup_db.sh here; see infra/README.md section 8"
    exit 1
  fi

  newest="$(find "${DIR}" -maxdepth 1 -name '*.sql' -type f -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -n 1 | cut -d' ' -f2-)"
  if [ -z "${newest}" ]; then
    fail "no dump in ${DIR}"
    fail "the directory exists, so the unit has run and produced nothing, or"
    fail "somebody deleted them. Check: systemctl status ampeer-backup"
    exit 1
  fi

  if ! tail -n "${TAIL_LINES}" "${newest}" | grep -q "${COMPLETE_MARKER}"; then
    fail "$(basename "${newest}") does not end the way a finished dump ends."
    fail "it is empty or it was truncated, which is worse than no dump at all,"
    fail "because it is the file somebody would restore from."
    exit 1
  fi
  size="$(stat -c '%s' "${newest}")"

  age_seconds=$(( $(date +%s) - $(stat -c '%Y' "${newest}") ))
  age_hours=$(( age_seconds / 3600 ))
  if [ "${age_hours}" -gt "${MAX_AGE_HOURS}" ]; then
    fail "the newest dump is ${age_hours} hours old, and the timer runs daily."
    fail "  ${newest}"
    fail "the backup has stopped. Check: systemctl list-timers ampeer-backup.timer"
    exit 1
  fi

  # Permissions last, and that ordering is deliberate. The question this check
  # exists to answer is whether anything is backing the database up, and a
  # directory somebody left at 755 must not be the answer that comes back when
  # there is no dump in it at all. Both are reported; only the order changes,
  # and it changes which one an operator reads first.
  dir_mode="$(stat -c '%a' "${DIR}")"
  case "${dir_mode}" in
    700|500) ;;
    *)
      fail "${DIR} is mode ${dir_mode}, so somebody other than its owner can read it."
      fail "these dumps hold every stored advice, including advice the purge has"
      fail "already deleted from the service. chmod 700 the directory."
      exit 1
      ;;
  esac

  file_mode="$(stat -c '%a' "${newest}")"
  if [ "${file_mode}" != "600" ]; then
    fail "$(basename "${newest}") is mode ${file_mode}, expected 600."
    fail "the directory is closed and the file inside it is not."
    exit 1
  fi

  echo "backup: newest dump is ${age_hours}h old and ${size} bytes"
  exit 0
fi

# --- the half that takes the dump ----------------------------------------------

if [ ! -f "${COMPOSE_FILE}" ]; then
  fail "no compose file at ${COMPOSE_FILE}"
  exit 1
fi

mkdir -p "${DIR}"
chmod 700 "${DIR}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${DIR}/ampeer-${stamp}.sql"
partial="${target}.partial"

# Written to .partial and renamed only after pg_dump succeeded. A dump killed
# halfway would otherwise sit in the directory looking like the newest good one,
# which is the exact failure --check above is unable to tell apart by age.
umask 077

# The credentials never leave the container. `sh -c` runs inside it, so
# POSTGRES_USER and POSTGRES_DB expand from the environment compose already put
# there, and neither the command line on the host nor the journal entry for this
# unit ever carries them. That is why the inner quotes are single: expanding
# them here is exactly what must not happen.
if ! docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
  exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "${partial}"; then
  fail "pg_dump failed; leaving no file behind rather than a partial one"
  rm -f "${partial}"
  exit 1
fi

# pg_dump exiting zero is not the same as pg_dump having finished. A full disk
# truncates the redirect and the exit status says nothing about it, so the file
# is asked whether it ends the way a finished dump ends.
if ! tail -n "${TAIL_LINES}" "${partial}" | grep -q "${COMPLETE_MARKER}"; then
  fail "pg_dump exited zero and wrote a file that does not end the way a finished"
  fail "dump ends. Out of disk is the usual reason. Leaving no file behind."
  rm -f "${partial}"
  exit 1
fi
size="$(stat -c '%s' "${partial}")"

mv "${partial}" "${target}"
chmod 600 "${target}"

# Pruned after the new dump is in place, never before: a prune that ran first
# and a dump that then failed would leave fewer backups than there were.
removed=0
while IFS= read -r old; do
  rm -f "${old}"
  removed=$((removed + 1))
done < <(find "${DIR}" -maxdepth 1 -name '*.sql' -type f -mtime "+${KEEP_DAYS}" 2>/dev/null)

echo "backup: wrote $(basename "${target}"), ${size} bytes, removed ${removed} older than ${KEEP_DAYS} days"
