"""Delete advices past their retention date, and say when that stopped happening.

Called by a systemd timer on the host, not by Celery. A daily DELETE over a
table with an index on expires_at does not need a task queue, and a task queue
is four moving parts that can fail silently while the deletion quietly stops
happening.

The --check mode exists because the silence is the danger. With no scheduler at
all the only observable behaviour is a link returning 404 after ninety days,
which is exactly what correct looks like: get_live filters on expires_at, so an
unpurged row is invisible rather than absent. Those are two different promises
and CLAUDE.md makes the stronger one. Without a check, the first person to find
out that nothing was deleted is whoever reads a database backup.

Three tables and one promise. StoredAdvice is the promise; the throttle counters
and ProductionCache are here because they are the two tables beside it that
nothing else ever deletes, and a retention that only covers the table somebody
remembered is not a retention. Only the first of the three is in --check, and
the reason is written above each of the other two.
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from advice.models import ProductionCache, StoredAdvice

#: How long a row is allowed to sit past its expires_at before --check calls it
#: a failure. The timer fires daily, so a timer that has not run yet today is
#: normal and must not be reported as a broken retention promise. One day is the
#: smallest window that tells those two apart.
GRACE_DAYS = 1

#: How old a ProductionCache row may get before this command drops it.
#:
#: The reason is not staleness, and saying so is the point. PVGIS data about a
#: closed weather year does not change, so a row written a year ago is exactly
#: as correct as one written this morning and deleting it buys no accuracy. The
#: reason is that ProductionCache is the one table in this schema that only ever
#: grows: nothing expires it, nothing reads fetched_at, and every row holds two
#: compressed year-long series. It is bounded now, because advice/serializers.py
#: groups the two roof angles and there are 41,040 reachable keys rather than
#: 2,956,590, but bounded is not the same as swept, and the bound is still
#: gigabytes of series that no request will ever ask for again.
#:
#: A year rather than a month because a year is the period on which the keys
#: themselves turn over. AMPEER_WEATHER_YEAR advances roughly annually, and the
#: moment it does every row carrying the old value is unreachable forever, since
#: weather_year is part of the unique key. A yearly sweep therefore spends most
#: of its deletions on rows nothing could read.
#:
#: What it costs when it is wrong is one PVGIS call. fetched_at is stamped once
#: at write and never touched on a read, so this is an age and not a last-used
#: time: a roof that is asked about every week is deleted on the same schedule
#: as one nobody has asked about since. The next visitor who asks for it waits
#: for the fetch and fills the row again, which is the cost the cache exists to
#: pay once rather than a wrong answer.
PRODUCTION_CACHE_MAX_AGE_DAYS = 365

#: base.py already names this, precisely so the migration that creates the
#: table and the code that reads it cannot drift. Imported rather than
#: repeated for the same reason.
CACHE_TABLE = settings.AMPEER_CACHE_TABLE


class Command(BaseCommand):
    help = "Delete stored advices whose retention period has passed"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help=(
                "Report overdue advices and exit non-zero instead of deleting them. "
                "Used as the container healthcheck."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["check"]:
            self._check()
            return
        deleted, _ = StoredAdvice.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"deleted {deleted} expired advice(s)")
        self.stdout.write(f"deleted {self._purge_throttle_counters()} expired throttle row(s)")
        self.stdout.write(
            f"deleted {self._purge_production_cache()} production cache row(s) past "
            f"{PRODUCTION_CACHE_MAX_AGE_DAYS} day(s)"
        )

    def _purge_production_cache(self) -> int:
        """Give fetched_at its first reader.

        The column has existed since the first migration and models.py said what
        it was for in as many words: a later cleanup remains possible. Nothing
        read it, so "possible" was the whole of it, and a table that only grows
        with a timestamp nobody looks at is indistinguishable from a table that
        only grows.

        Not in --check. That mode reports one thing, which is that the ninety
        day retention promise in docs/dpia.md has stopped being kept, and it
        exits non-zero on the host and in the deploy. This table carries no
        personal detail at all, only a postcode century and two roof angles, so
        an unswept row here is a disk question and not a broken promise. Putting
        it in --check would turn a deploy red over housekeeping and teach
        somebody to stop reading the check.
        """
        cutoff = timezone.now() - timedelta(days=PRODUCTION_CACHE_MAX_AGE_DAYS)
        deleted, _ = ProductionCache.objects.filter(fetched_at__lt=cutoff).delete()
        return int(deleted)

    def _purge_throttle_counters(self) -> int:
        """Delete the rate limiter's expired rows, which nothing else does.

        The throttle counter lives in the database so it survives a restart and
        is shared across workers, which was the right call and is not the
        problem. The problem is that Django's DatabaseCache only removes an
        expired row when that same key is read again, and culls only above
        100,000 entries. A visitor who never returns leaves a row forever.

        Measured on 2026-08-21: rows backdated four hundred days survived fresh
        traffic and a full run of this command, because it filtered StoredAdvice
        and nothing else. The ninety day promise covered the advice and not the
        table beside it, which is in every volume snapshot and every backup.

        The key is a keyed digest of the caller rather than an address now, so
        what survives is no longer a visitor log. It is still a row nobody
        chose to keep, and a retention that only covers the table somebody
        remembered is not a retention.
        """
        # A table name cannot be a bound parameter in SQL, so it has to be
        # interpolated, and bandit flags any interpolation into something that
        # looks like a statement. Django's own DatabaseCache._cull builds this
        # exact shape for the same reason.
        #
        # What makes it safe here, and what a reader should check rather than
        # take on trust: CACHE_TABLE is settings.AMPEER_CACHE_TABLE, a literal
        # in base.py that no request can reach, and it still goes through the
        # backend's own quote_name. The only value is bound.
        #
        # The explanation sits above the marker and never spells the marker
        # out, because bandit reads every word after that token on the same
        # line as a test id and warns once per word. It happened here on
        # 2026-08-21 and printed seventeen warnings a run, and it happened
        # again while this very comment was being written, which is why the
        # token appears nowhere in this paragraph.
        statement = f"DELETE FROM {connection.ops.quote_name(CACHE_TABLE)} WHERE expires < %s"  # nosec B608
        with connection.cursor() as cursor:
            cursor.execute(statement, [timezone.now()])
            return int(cursor.rowcount)

    def _check(self) -> None:
        """Measure without repairing.

        This deletes nothing on purpose. A check that repairs what it measures
        can never report a problem: it would clean up the evidence of the
        scheduler being dead and then exit zero, which is the exact failure this
        mode was written to make visible.
        """
        overdue = StoredAdvice.objects.filter(
            expires_at__lte=timezone.now() - timedelta(days=GRACE_DAYS)
        )
        oldest = overdue.order_by("expires_at").first()
        if oldest is None:
            self.stdout.write(f"no advice is more than {GRACE_DAYS} day(s) past its expiry")
            return
        count = overdue.count()
        # Loudly, and with the numbers a person needs to judge how long the
        # timer has been dead. No token and no inputs: this text reaches a
        # container log, and the retention promise is about exactly that data.
        raise CommandError(
            f"{count} advice(s) have not been purged; "
            f"the oldest expired at {oldest.expires_at.isoformat()}, "
            f"which is more than {GRACE_DAYS} day(s) ago. "
            "The purge timer on the host is not running."
        )
