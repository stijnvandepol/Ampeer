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
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from advice.models import StoredAdvice

#: How long a row is allowed to sit past its expires_at before --check calls it
#: a failure. The timer fires daily, so a timer that has not run yet today is
#: normal and must not be reported as a broken retention promise. One day is the
#: smallest window that tells those two apart.
GRACE_DAYS = 1

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
