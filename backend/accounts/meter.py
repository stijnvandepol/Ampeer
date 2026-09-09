"""The push route's authentication and storage, apart from the session routes.

A household's own device calls `POST /api/meter/readings/` with a key it was
handed once, never a cookie: the caller has no browser and this route changes
nothing about a session. `MeterTokenAuthentication` is therefore the whole of
what identifies it, and `store_readings` is the whole of what the route does
with what it is handed.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from accounts.models import MeterLink, QuarterReading, User
from accounts.nl import NL
from advice.models import token_digest


class MeterTokenAuthentication(BaseAuthentication):
    """The push route's whole notion of who is calling.

    No cookie and no CSRF: the caller is a device without a browser and the
    route changes nothing about a session. The header carries the key, this
    class carries its digest to the database, and the raw key is never
    written anywhere.

    A missing header, or one that does not start with `Meter`, answers `None`:
    that is not this route's business and DRF's `IsAuthenticated` turns it
    into a 401 on its own, in DRF's own English, because nobody sent a key to
    call wrong. Once the keyword matches, anything that fails to resolve to an
    active link (unknown, revoked, or too short to be one) is this route's
    business, and it is answered in the sentence a device's own log will show.

    `user__is_active=True` is checked here rather than left to
    `IsAuthenticated`, because it would not be caught there either:
    `AbstractBaseUser.is_authenticated` is a property that is always `True`
    and never consults `is_active`. `accounts/recovery.py` already honours
    `is_active` for a password reset, and Django's own `ModelBackend` honours
    it at login; without this clause the push route would be the one door
    a suspended account's device could still walk through, feeding a system
    that is supposed to have stopped processing for it.
    """

    keyword = "Meter"

    def authenticate(self, request: Request) -> tuple[User, MeterLink] | None:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        parts = header.split()
        if not parts or parts[0] != self.keyword:
            return None
        if len(parts) != 2:
            raise AuthenticationFailed(NL["meter_token_invalid"])
        link = (
            MeterLink.objects.filter(
                token_sha256=token_digest(parts[1]),
                revoked_at__isnull=True,
                user__is_active=True,
            )
            .select_related("user")
            .first()
        )
        if link is None:
            raise AuthenticationFailed(NL["meter_token_invalid"])
        return link.user, link

    def authenticate_header(self, request: Request) -> str:
        return self.keyword


def store_readings(link: MeterLink, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Write what is new, count what was already there, in one transaction.

    Counted by querying the affected moments before and after the write,
    never by trusting `bulk_create`'s return value, which is not the same
    across databases. Duplicate moments inside one request collapse to a
    single row before the write and count toward `skipped`: a device that
    sends the same quarter twice in one message is not sending two different
    realities, it is sending one twice.
    """
    duplicates_in_batch = len(rows) - len({row["measured_at"] for row in rows})
    by_moment = {row["measured_at"]: row for row in rows}
    moments = list(by_moment.keys())
    with transaction.atomic():
        before = QuarterReading.objects.filter(link=link, measured_at__in=moments).count()
        QuarterReading.objects.bulk_create(
            [
                QuarterReading(
                    link=link,
                    measured_at=moment,
                    consumption_kwh=row["consumption_kwh"],
                    feed_in_kwh=row["feed_in_kwh"],
                )
                for moment, row in by_moment.items()
            ],
            ignore_conflicts=True,
        )
        after = QuarterReading.objects.filter(link=link, measured_at__in=moments).count()
        link.last_seen_at = timezone.now()
        link.save(update_fields=["last_seen_at"])
    stored = after - before
    skipped = len(by_moment) - stored + duplicates_in_batch
    return stored, skipped
