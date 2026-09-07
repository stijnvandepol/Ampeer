"""Delete refresh sessions whose token could not be used any more anyway.

A management command called by the same cron that runs `purge_expired_advice`,
and not a Celery task, for the reason section 5 of the advice API design gives:
a daily DELETE over an indexed column needs no queue.

Rows are removed on `expires_at` and not on `rotated_at`. A rotated row is the
evidence that a token was spent, and that evidence is what makes reuse
detectable; dropping it early would turn a stolen token into an unknown one.
The same holds for `OneTimeToken.spent_at`, so those rows go on `expires_at`
too. Failed outbox rows go seven days after `failed_at`: long enough to be
read when somebody asks why a mail never came, and no longer.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import OneTimeToken, OutboundMail, RefreshSession


class Command(BaseCommand):
    help = "Remove refresh sessions whose refresh token has expired."

    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()
        sessions, _ = RefreshSession.objects.filter(expires_at__lte=now).delete()
        tokens, _ = OneTimeToken.objects.filter(expires_at__lte=now).delete()
        mails, _ = OutboundMail.objects.filter(failed_at__lte=now - timedelta(days=7)).delete()
        self.stdout.write(
            f"removed {sessions} expired refresh sessions, {tokens} expired one-time tokens, "
            f"{mails} failed mails"
        )
