"""Fold quarter readings older than ninety days into hour totals, and say so.

Called by a systemd timer on the host, not by Celery, for the same reason
`purge_expired_advice` and `send_outbound_mail` give: a daily sweep over an
indexed column does not need a task queue.

Folding, not deleting outright: docs/dpia.md's retention table promises hour
totals survive where raw quarters do not, so this command's job is a
transformation and the deletion is only the second half of it. An hour that
never saw all four of its quarters is written with `quarters` at whatever
count it actually has; discarding it would make a gap where a partial truth
belongs.

The --check mode exists for the reason the other two commands' does: the
silence is the danger. With no scheduler at all, the only observable
behaviour is a household's export carrying quarters a hundred days old, which
docs/dpia.md says never happens. Without a check, the first person to find
out is whoever reads a database dump.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import HourAggregate, QuarterReading

#: How long a quarter reading survives before it is folded into an hour and
#: removed. docs/dpia.md's retention table quotes this in words.
RETENTION = timedelta(days=90)

#: How long past `RETENTION` a quarter may sit before --check calls the
#: timer dead. The timer fires daily, so a timer that has not run yet today is
#: normal and must not be reported as a broken retention promise; one day is
#: the smallest window that tells those two apart, the same argument
#: `purge_expired_advice.GRACE_DAYS` makes for its own daily sweep.
GRACE_DAYS = 1

#: How many links one run folds before it stops. A household's own quarters
#: are bounded by how often it pushes, so this bounds how much of the whole
#: fleet one invocation walks, not how much of one household's backlog it
#: clears; the same knob `send_outbound_mail --max` gives its own daily cap.
DEFAULT_MAX_LINKS = 200


class Command(BaseCommand):
    help = "Fold quarter readings older than ninety days into hour totals."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help=(
                "Fold nothing; exit non-zero if a quarter reading is older than the "
                "retention window by more than one day."
            ),
        )
        parser.add_argument(
            "--max",
            type=int,
            default=DEFAULT_MAX_LINKS,
            help=f"Stop after this many links in one run. Default {DEFAULT_MAX_LINKS}.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # Refused rather than clamped, for the reason written out in
        # send_outbound_mail.handle: a cap below one walks no links, reports
        # "folded 0" and exits zero, so a timer installed with that flag looks
        # healthy while quarter readings quietly outlive the retention window
        # this command exists to enforce.
        if options["max"] < 1:
            raise CommandError(
                f"--max is {options['max']}, so this run would fold nothing and say so "
                "as though that were normal. Pass 1 or more, or leave it out."
            )
        if options["check"]:
            self._check()
            return
        quarters, hours = self._fold(options["max"])
        self.stdout.write(f"folded {quarters} quarter reading(s) into {hours} hour aggregate(s)")

    def _check(self) -> None:
        """Measure without repairing, the same shape `purge_expired_advice._check` uses.

        This folds nothing on purpose. A check that repairs what it measures
        can never report a problem: it would clear the evidence that the
        scheduler is dead and then exit zero, which is the exact failure this
        mode exists to make visible.
        """
        cutoff = timezone.now() - RETENTION - timedelta(days=GRACE_DAYS)
        overdue = QuarterReading.objects.filter(measured_at__lt=cutoff)
        oldest = overdue.order_by("measured_at").first()
        if oldest is None:
            self.stdout.write(
                f"no quarter reading is more than {GRACE_DAYS} day(s) past the retention window"
            )
            return
        count = overdue.count()
        raise CommandError(
            f"{count} quarter reading(s) have not been folded into hours; "
            f"the oldest was measured at {oldest.measured_at.isoformat()}, "
            f"which is more than {RETENTION.days + GRACE_DAYS} day(s) ago. "
            "The meter purge timer on the host is not running."
        )

    def _fold(self, max_links: int) -> tuple[int, int]:
        cutoff = timezone.now() - RETENTION
        link_ids = (
            QuarterReading.objects.filter(measured_at__lt=cutoff)
            .order_by("link_id")
            .values_list("link_id", flat=True)
            .distinct()[:max_links]
        )
        quarters_total = 0
        hours_total = 0
        for link_id in list(link_ids):
            with transaction.atomic():
                quarters, hours = self._fold_link(link_id, cutoff)
            quarters_total += quarters
            hours_total += hours
        return quarters_total, hours_total

    def _fold_link(self, link_id: int, cutoff: datetime) -> tuple[int, int]:
        """Every quarter of one link older than `cutoff`, grouped by hour and
        written once per hour.

        Grouped before any write happens: writing straight from the quarter
        loop would call `update_or_create` (or worse, `create`) once per
        quarter, and a second quarter landing in an hour a first quarter just
        created would either double-write it or collide with the unique
        constraint on `(link, hour_start)`. One upsert per hour is what keeps
        two quarters in the same hour a single row rather than a race.
        """
        rows = list(
            QuarterReading.objects.filter(link_id=link_id, measured_at__lt=cutoff).order_by(
                "measured_at"
            )
        )
        # No early return for an empty `rows`. `_fold` only ever names links
        # that have a quarter past the cutoff, so the only way to arrive here
        # with nothing is a race: an unlink erasing this link's readings
        # between the id being selected and this transaction opening. That
        # case needs no branch of its own. An empty `buckets` skips the loop,
        # and Django resolves `pk__in=[]` to an empty queryset without
        # issuing a DELETE at all, so the early return saved no query and
        # only added an arm nothing could reach through this command.
        buckets: dict[datetime, list[QuarterReading]] = {}
        for row in rows:
            hour_start = row.measured_at.replace(minute=0, second=0, microsecond=0)
            buckets.setdefault(hour_start, []).append(row)
        for hour_start, group in buckets.items():
            existing = HourAggregate.objects.filter(link_id=link_id, hour_start=hour_start).first()
            base_consumption = existing.consumption_kwh if existing else 0.0
            base_feed_in = existing.feed_in_kwh if existing else 0.0
            base_quarters = existing.quarters if existing else 0
            HourAggregate.objects.update_or_create(
                link_id=link_id,
                hour_start=hour_start,
                defaults={
                    "consumption_kwh": base_consumption + sum(r.consumption_kwh for r in group),
                    "feed_in_kwh": base_feed_in + sum(r.feed_in_kwh for r in group),
                    "quarters": base_quarters + len(group),
                },
            )
        QuarterReading.objects.filter(pk__in=[row.pk for row in rows]).delete()
        return len(rows), len(buckets)
