"""The two handlings that have consequences outside their own request.

Kept out of views.py because both are a sequence with an order that matters, and
an order that matters belongs somewhere it can be read in one screen.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from accounts.models import Consent, User
from advice.models import AuditEvent, StoredAdvice


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
