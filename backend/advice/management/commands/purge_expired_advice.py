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

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from advice.models import StoredAdvice

#: How long a row is allowed to sit past its expires_at before --check calls it
#: a failure. The timer fires daily, so a timer that has not run yet today is
#: normal and must not be reported as a broken retention promise. One day is the
#: smallest window that tells those two apart.
GRACE_DAYS = 1


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
