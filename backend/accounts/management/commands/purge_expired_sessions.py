"""Delete refresh sessions whose token could not be used any more anyway.

A management command called by the same cron that runs `purge_expired_advice`,
and not a Celery task, for the reason section 5 of the advice API design gives:
a daily DELETE over an indexed column needs no queue.

Rows are removed on `expires_at` and not on `rotated_at`. A rotated row is the
evidence that a token was spent, and that evidence is what makes reuse
detectable; dropping it early would turn a stolen token into an unknown one.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import RefreshSession


class Command(BaseCommand):
    help = "Remove refresh sessions whose refresh token has expired."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted, _ = RefreshSession.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"removed {deleted} expired refresh sessions")
