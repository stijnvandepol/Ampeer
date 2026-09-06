"""Password reset and address confirmation, as four handlings and a mint.

Beside service.py and not inside it, because the two modules speak two
vocabularies: service.py is about export and deletion and stays the two
function module it is, and everything that turns a token into a change of
state lives here. tests/test_dpia.py walks every file under backend/accounts/
for the keywords an audit line carries, so nothing about that check depends
on which of the two files a line is written from.

The raw token is returned by `mint` and never stored. It exists in the memory
of the command that sends the mail and in the mail itself, and the digest in
`OneTimeToken` is the only thing this table can hand anybody.
"""

from __future__ import annotations

import secrets
from typing import Final

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from accounts import tokens
from accounts.models import OneTimeToken, OutboundMail, User, _normalize_email
from advice.models import AuditEvent, token_digest

#: 32 bytes, 256 bits, 43 url-safe characters: twice the advice token, because
#: an advice token opens an advice that expires in ninety days and this one
#: sets a password. frontend/src/app/_account/fragment.ts accepts exactly
#: that length, and tests/test_frontend_contract.py holds the two together.
TOKEN_BYTES: Final = 32


class TokenInvalid(Exception):
    """Expired, spent, superseded, or never issued. One class on purpose: the
    difference between the four is only interesting to somebody trying tokens."""


class PasswordRejected(Exception):
    """Django's validators refused the new password. Carries their error so the
    view can translate it the way RegisterSerializer does, in one place."""

    def __init__(self, error: DjangoValidationError) -> None:
        super().__init__("the new password was refused by a validator")
        self.error = error


def mint(user: User, kind: str) -> str:
    """A fresh token of one kind, and the digest written down.

    Every older unspent token of the same kind for this user is superseded in
    the same statement, so there is at most one usable link per person per
    kind. Called by the command that sends the mail and by nothing else, so
    `issued_at` is the moment of sending.
    """
    if kind not in OneTimeToken.KINDS:
        raise ValueError(f"unknown token kind: {kind}")
    now = timezone.now()
    OneTimeToken.objects.filter(
        user=user, kind=kind, spent_at__isnull=True, superseded_at__isnull=True
    ).update(superseded_at=now)
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    OneTimeToken.objects.create(
        user=user,
        kind=kind,
        token_sha256=token_digest(raw),
        issued_at=now,
        expires_at=now + OneTimeToken.LIFETIMES[kind],
    )
    return raw


def enqueue(user: User, kind: str) -> bool:
    """One unsent row per user per kind. Returns whether a row was written."""
    if OutboundMail.objects.filter(user=user, kind=kind, failed_at__isnull=True).exists():
        return False
    OutboundMail.objects.create(user=user, kind=kind, next_attempt_at=timezone.now())
    return True


def request_password_reset(email: str) -> None:
    """Never says anything about the address, and never touches the network.

    Lowered the way `_normalize_email` lowers on every write, because the row
    is stored lowered and a lookup in other capitals would miss it. A blocked
    account (`is_active` False) gets no mail: a reset would not let it in.
    """
    user = User.objects.filter(email=_normalize_email(email), is_active=True).first()
    if user is None:
        return
    if enqueue(user, OneTimeToken.PASSWORD_RESET):
        AuditEvent.record(AuditEvent.PASSWORD_RESET_REQUESTED, user_id=user.pk)


def _lock(raw_token: str, kind: str) -> OneTimeToken:
    """The row for this token, locked, and usable. Inside the caller's atomic block.

    The lock is `select_for_update` on the one row, the same shape as
    `tokens.rotate`: two confirmations with the same token queue on it, the
    second reads `spent_at` filled and is refused. There is no `revoke_all`
    branch here, unlike a reused refresh token: a reused reset link is a
    refused link, not evidence that somebody else holds the session.
    """
    row = (
        OneTimeToken.objects.select_for_update()
        .filter(token_sha256=token_digest(raw_token), kind=kind)
        .first()
    )
    if row is None or not row.is_usable:
        raise TokenInvalid(kind)
    return row


def _spend(row: OneTimeToken) -> None:
    row.spent_at = timezone.now()
    row.save(update_fields=["spent_at"])


def confirm_password_reset(raw_token: str, password: str) -> User:
    """Token first, then the password, then everything at once or nothing.

    The validators run with the user, because `UserAttributeSimilarityValidator`
    compares against the address, and they run before anything is written: a
    rejected password leaves the token usable and the transaction untouched.
    Then, still under the lock: the password, every session revoked so
    nothing that started under the old password survives, the address
    confirmed if it was not, the token spent, and the audit line.
    """
    with transaction.atomic():
        row = _lock(raw_token, OneTimeToken.PASSWORD_RESET)
        user = row.user
        try:
            validate_password(password, user)
        except DjangoValidationError as error:
            raise PasswordRejected(error) from error
        user.set_password(password)
        verified_now = user.email_verified_at is None
        if verified_now:
            user.email_verified_at = timezone.now()
        user.save(update_fields=["password", "email_verified_at"])
        tokens.revoke_all(user)
        _spend(row)
        AuditEvent.record(AuditEvent.PASSWORD_RESET_COMPLETED, user_id=user.pk)
        if verified_now:
            AuditEvent.record(AuditEvent.EMAIL_VERIFIED, user_id=user.pk)
    return user


def request_email_verification(user: User) -> None:
    """One mail, unless the address is already confirmed or one is waiting."""
    if user.email_verified_at is not None:
        return
    enqueue(user, OneTimeToken.EMAIL_VERIFY)


def confirm_email_verification(raw_token: str) -> User:
    with transaction.atomic():
        row = _lock(raw_token, OneTimeToken.EMAIL_VERIFY)
        user = row.user
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
        _spend(row)
        AuditEvent.record(AuditEvent.EMAIL_VERIFIED, user_id=user.pk)
    return user
