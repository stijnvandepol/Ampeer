"""The two handlings that have consequences outside their own request.

Kept out of views.py because both are a sequence with an order that matters, and
an order that matters belongs somewhere it can be read in one screen.
"""

from __future__ import annotations

import secrets
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import Consent, HourAggregate, MeterLink, QuarterReading, User
from advice.models import AuditEvent, StoredAdvice, token_digest

#: 32 bytes, 256 bits, 43 url-safe characters. Handed out once, in the answer
#: to the request that mints it, and never again: from that moment on this
#: service knows only `token_sha256`.
METER_TOKEN_BYTES = 32


def export_account(user: User) -> dict[str, Any]:
    """Everything this service holds about one account.

    `inputs` as well as `advice`, which repairs the gap docs/dpia.md chapter 7
    names: the token route returns the advice and not the answers it was made
    from, so a visitor sees the outcome and not the input. Structurally repaired
    here; materially it changes nothing until phase 2 attaches an advice to an
    account, because nothing in phase 1 writes `owner`.

    The stored JSON is passed through and never rebuilt. Every amount in it is a
    string, because JSON has only floats, and rebuilding is one more place a
    number could pass through a parser.
    """
    advices = StoredAdvice.objects.filter(owner=user).order_by("created_at")
    return {
        "email": user.email,
        "date_joined": user.date_joined.isoformat(),
        # Beside `date_joined` because it is the same kind of fact about the
        # account itself, and in here because article 15 owes a copy of every
        # personal datum the service holds, not of the ones a page happens to
        # render. `me/` already answers it; an export that left it out would be
        # a smaller answer than the screen.
        "email_verified_at": (
            None if user.email_verified_at is None else user.email_verified_at.isoformat()
        ),
        "consents": [
            {
                "kind": row.kind,
                "action": row.action,
                "occurred_at": row.occurred_at.isoformat(),
                "text_version": row.text_version,
            }
            for row in Consent.objects.filter(user=user).order_by("occurred_at")
        ],
        "advices": [{"inputs": row.inputs, "advice": row.advice} for row in advices],
        # `null` without an active link, and never the key: Ampeer only ever
        # knows the digest, so there is nothing to export that would open
        # anything. `hours` and `quarters` both, because a household may hold
        # readings younger than ninety days and older ones already folded, and
        # article 15 owes a copy of both shapes this service keeps.
        "meter": None if (link := MeterLink.active_for(user)) is None else _meter_export(link),
    }


def _meter_export(link: MeterLink) -> dict[str, Any]:
    return {
        "created_at": link.created_at.isoformat(),
        "last_seen_at": None if link.last_seen_at is None else link.last_seen_at.isoformat(),
        "hours": [
            {
                "hour_start": row.hour_start.isoformat(),
                "consumption_kwh": row.consumption_kwh,
                "feed_in_kwh": row.feed_in_kwh,
                "quarters": row.quarters,
            }
            for row in HourAggregate.objects.filter(link=link).order_by("hour_start")
        ],
        "quarters": [
            {
                "measured_at": row.measured_at.isoformat(),
                "consumption_kwh": row.consumption_kwh,
                "feed_in_kwh": row.feed_in_kwh,
            }
            for row in QuarterReading.objects.filter(link=link).order_by("measured_at")
        ],
    }


def delete_account(user: User) -> None:
    """Remove the account and everything that hangs off it, in one transaction.

    The audit line is written inside the transaction, not before and not after.
    Before, a failed deletion leaves a line saying something happened that did
    not; after, a failed write leaves a deletion nobody recorded. `AuditEvent` is
    the one table here that cannot be rebuilt from anything else.

    `user_id` is read before the delete because afterwards there is no row to
    read it from, and it is a plain integer in the context rather than a foreign
    key: a key would either block this deletion or be taken by it.
    """
    user_id = user.pk
    with transaction.atomic():
        AuditEvent.record(AuditEvent.ACCOUNT_DELETED, user_id=user_id)
        # CASCADE takes Consent, RefreshSession and every StoredAdvice with this
        # owner. An advice with owner NULL is not this account's and stays.
        # No tokens.revoke_all(user) here: the CASCADE two lines down removes
        # every RefreshSession row this account has, so revoking them first
        # only took row locks the delete was about to take anyway.
        user.delete()


def may_link_meter(user: User) -> bool:
    """A confirmed address and a granted METER_LINK consent, both.

    Read fresh on every call and cached nowhere: whichever of the two a
    household completes last is what flips this from `False` to `True`, and
    `MeterStatusView` calls this on every page load to know whether to show
    the button at all.
    """
    return user.email_verified_at is not None and Consent.current(user, Consent.METER_LINK)


def _erase_meter_data(link: MeterLink) -> None:
    """Remove every reading and hour a link has, without touching the log.

    Shared by `link_meter`, which supersedes a previous link silently as part
    of minting a new one, and `unlink_meter`, which calls this and then writes
    the one audit line a deliberate unlink earns. A relink's silent
    supersession is not itself an event worth a line of its own: the
    `METER_LINKED` line the new key gets already says a link changed hands,
    and a second line here would turn one action into two in the log.
    """
    QuarterReading.objects.filter(link=link).delete()
    HourAggregate.objects.filter(link=link).delete()


def link_meter(user: User) -> tuple[MeterLink, str]:
    """Mint one key, keep only its digest, revoke whatever came before.

    Returns the row and the raw key. The key is returned and never stored,
    which is why this is the only function that has both in the same scope.

    Superseding a previous link erases its data in the same transaction: a
    key that no longer works is a key whose readings a household can no
    longer point to either, and leaving them behind would make "koppel
    opnieuw" a smaller reset than revoking and relinking should be.
    """
    with transaction.atomic():
        previous = MeterLink.objects.select_for_update().filter(user=user, revoked_at__isnull=True)
        for link in previous:
            _erase_meter_data(link)
        previous.update(revoked_at=timezone.now())
        raw = secrets.token_urlsafe(METER_TOKEN_BYTES)
        link = MeterLink.objects.create(user=user, token_sha256=token_digest(raw))
        AuditEvent.record(AuditEvent.METER_LINKED, user_id=user.pk)
    return link, raw


def unlink_meter(user: User) -> bool:
    """Revoke and erase, in one transaction. `False` when there was nothing.

    Called both from a direct "ontkoppel" and from withdrawing the
    `METER_LINK` consent: a consent withdrawn has to be exactly as thorough as
    a link revoked, or one of the two routes would be the weaker promise.
    """
    with transaction.atomic():
        link = (
            MeterLink.objects.select_for_update().filter(user=user, revoked_at__isnull=True).first()
        )
        if link is None:
            return False
        _erase_meter_data(link)
        link.revoked_at = timezone.now()
        link.save(update_fields=["revoked_at"])
        AuditEvent.record(AuditEvent.METER_UNLINKED, user_id=user.pk)
    return True
