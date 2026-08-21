"""Delete advices past their retention date.

Called by cron, not by Celery. A daily DELETE over a table with an index on
expires_at does not need a task queue, and a task queue is four moving parts
that can fail silently while the deletion quietly stops happening.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from advice.models import StoredAdvice


class Command(BaseCommand):
    help = "Delete stored advices whose retention period has passed"

    def handle(self, *args: Any, **options: Any) -> None:
        deleted, _ = StoredAdvice.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"deleted {deleted} expired advice(s)")
