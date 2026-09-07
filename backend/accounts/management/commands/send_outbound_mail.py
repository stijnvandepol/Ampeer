"""Send what is waiting in the outbox, minting each token at the moment of sending.

Called every minute by infra/systemd/ampeer-mail.timer, and not by Celery,
for the reason the two purge commands give: a small amount of work on a
schedule needs a timer and not a queue. This is the only process in this
repository that opens a connection to the mail provider, and it never runs
inside a request.

The order inside one row is exact, and it is one transaction with a
savepoint inside it, not two transactions. The outer `atomic()` takes the
row's lock with SKIP LOCKED and holds it across the send, so a second run of
this command never claims the same row. Inside it, the mint and the send
share a savepoint: a transport error leaves that savepoint with an exception,
which rolls the mint back, so no digest of a token nobody received survives,
while the row itself is still locked and is then updated with the attempt
and the wait. Two writes, in that order, and the first commits only if the
transport took the message. Spec 4.4 describes the same property in the
words "two transactions"; the savepoint is how it is delivered without
letting go of the row in between.

A row is claimed one at a time, so one row's failure cannot be allowed to
stop every row after it: a mailer bug that raises something other than
`TransportError` (fix round 1 found one such gap, in `ResendTransport.send`)
must not wedge the whole outbox behind a row nobody can move past. Such a
row is therefore deferred exactly like a transport failure, the run moves on
to the next row, and only once the whole batch is done does the command
report the count and exit non-zero, so the unit shows failed while the next
tick still drains everything after the poison row. Only the exception's
class name reaches the journal, never `str(error)`, which could carry an
address if the failure happened while composing the message.

Every run, with `--check` and without it, ends by counting two kinds of
trouble and exiting non-zero on either. A row still unsent after
`OVERDUE_AFTER` is a timer that has stopped or a transport that refuses
everything. A row already stamped `failed_at` inside the last
`GIVE_UP_AFTER` is the opposite shape and the one the first version of this
command could not see: a status the sender will never retry, a wrong
`RESEND_API_KEY` being the likeliest, makes every row fail on its first
attempt and leaves the outbox empty of anything overdue, so a check that
only asked the first question stayed green while no mail was reaching
anybody. Counting the given-up rows makes that state loud for a day, every
minute; the purge removes such a row after seven days, which is fine,
because by then the day of red has been seen.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts import mailer, recovery
from accounts.models import OneTimeToken, OutboundMail
from accounts.nl import NL
from advice.models import AuditEvent

#: After the first, second, third and every later failed attempt.
BACKOFF: Final = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(minutes=60),
)
#: A row older than this is marked failed on its next failure rather than
#: deferred again. A reset link a day late is a link somebody stopped waiting for.
GIVE_UP_AFTER: Final = timedelta(hours=24)
#: `--check` exits non-zero when an unsent row is older than this. The timer
#: runs every minute; a quarter of an hour is fifteen missed runs.
OVERDUE_AFTER: Final = timedelta(minutes=15)

_SUBJECT: Final = {
    OneTimeToken.PASSWORD_RESET: "MAIL_RESET_SUBJECT",
    OneTimeToken.EMAIL_VERIFY: "MAIL_VERIFY_SUBJECT",
}
_BODY: Final = {
    OneTimeToken.PASSWORD_RESET: "MAIL_RESET_BODY",
    OneTimeToken.EMAIL_VERIFY: "MAIL_VERIFY_BODY",
}
#: The word after `#` in the link. frontend/src/app/_account/fragment.ts reads
#: exactly these two.
_FRAGMENT: Final = {
    OneTimeToken.PASSWORD_RESET: "herstel",
    OneTimeToken.EMAIL_VERIFY: "verificatie",
}


def _compose(row: OutboundMail, raw_token: str) -> mailer.Message:
    link = f"{settings.AMPEER_SITE_ORIGIN}/account/#{_FRAGMENT[row.kind]}={raw_token}"
    return mailer.Message(
        to=row.user.email,
        subject=NL[_SUBJECT[row.kind]],
        text=NL[_BODY[row.kind]] % {"link": link},
        idempotency_key=f"outbox-{row.pk}",
    )


def _retryable(status: int) -> bool:
    """A network fault, a timeout, a 429 or a 5xx is worth another attempt. A
    wrong key or an address the provider refuses is not."""
    return status == 0 or status == 429 or status >= 500


class Command(BaseCommand):
    help = "Send what is waiting in the outbox; with --check only report what is stuck."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--check",
            action="store_true",
            help=(
                "Send nothing; exit non-zero if an unsent mail is older than fifteen "
                "minutes or a mail was given up on in the last day."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["check"]:
            sent, deferred, faulted = self._deliver()
            self.stdout.write(f"sent {sent} messages, deferred {deferred}")
            if faulted:
                raise CommandError(
                    f"{faulted} row(s) raised something other than a transport failure; "
                    "deferred like any other and left for the next run"
                )
        self._report_what_is_stuck()

    def _report_what_is_stuck(self) -> None:
        """Two counts, not one. Waiting too long and given up on are different
        failures with different causes, so the message names them apart."""
        now = timezone.now()
        overdue = OutboundMail.objects.filter(
            failed_at__isnull=True, created_at__lte=now - OVERDUE_AFTER
        ).count()
        abandoned = OutboundMail.objects.filter(failed_at__gte=now - GIVE_UP_AFTER).count()
        if overdue or abandoned:
            raise CommandError(
                f"{overdue} mails have been waiting longer than {OVERDUE_AFTER} and "
                f"{abandoned} were given up on in the last {GIVE_UP_AFTER}; "
                "the timer has stopped, or the transport refuses everything"
            )

    def _deliver(self) -> tuple[int, int, int]:
        sender = mailer.transport()
        sent = deferred = faulted = 0
        while True:
            with transaction.atomic():
                row = (
                    OutboundMail.objects.select_for_update(skip_locked=True)
                    .filter(failed_at__isnull=True, next_attempt_at__lte=timezone.now())
                    .order_by("id")
                    .first()
                )
                if row is None:
                    return sent, deferred, faulted
                try:
                    with transaction.atomic():
                        raw = recovery.mint(row.user, row.kind)
                        provider_id = sender.send(_compose(row, raw))
                except mailer.TransportError as error:
                    self._defer(row, error.status)
                    deferred += 1
                    continue
                except Exception as error:  # noqa: BLE001
                    # Anything else is a bug, in this command or in the
                    # transport, and not a signal about this particular
                    # address. The savepoint above still rolled the mint
                    # back; this row is deferred exactly like a transport
                    # failure, so it does not wedge every row after it. Blind
                    # on purpose: whatever this raises, one poison row must
                    # defer and let the claim move to the next row rather
                    # than kill the whole run.
                    self.stdout.write(f"row {row.pk} deferred after {type(error).__name__}")
                    self._defer(row, 0)
                    deferred += 1
                    faulted += 1
                    continue
                AuditEvent.record(
                    AuditEvent.MAIL_SENT,
                    user_id=row.user_id,
                    kind=row.kind,
                    provider_id=provider_id,
                )
                row.delete()
                sent += 1

    def _defer(self, row: OutboundMail, status: int) -> None:
        now = timezone.now()
        row.attempts += 1
        row.last_status = status
        if not _retryable(status) or now - row.created_at >= GIVE_UP_AFTER:
            row.failed_at = now
        else:
            row.next_attempt_at = now + BACKOFF[min(row.attempts, len(BACKOFF)) - 1]
        row.save(update_fields=["attempts", "last_status", "failed_at", "next_attempt_at"])
