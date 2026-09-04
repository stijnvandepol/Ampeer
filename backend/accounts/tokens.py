"""Issuing and rotating refresh tokens against a table that holds no credential.

`RefreshSession` stores the sha256 of the token's `jti` and nothing else, using
the same `token_digest` the advice API applies to its own token, with the same
argument: the input is high entropy from a cryptographic source, so there is no
dictionary to run and no salt worth adding.
"""

from __future__ import annotations

from datetime import UTC, datetime

from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import RefreshSession, User
from advice.models import token_digest


class TokenReuse(Exception):
    """A refresh token that had already been spent was offered again."""


def issue(user: User) -> tuple[str, str]:
    """A fresh pair, with the refresh side written down as a digest."""
    refresh = RefreshToken.for_user(user)
    RefreshSession.objects.create(
        user=user,
        jti_sha256=_digest(refresh),
        issued_at=timezone.now(),
        expires_at=datetime.fromtimestamp(float(refresh.payload["exp"]), tz=UTC),
    )
    return str(refresh.access_token), str(refresh)


def rotate(raw_refresh: str) -> tuple[str, str]:
    """Exchange one refresh token for a new pair, exactly once.

    `RefreshToken(raw)` raises `TokenError` on a token this service did not
    issue, on one whose signature does not verify and on an expired one, so the
    cryptographic half is handled before the row is looked up at all.

    The reused-token branch below calls `revoke_all` *inside* the `atomic()`
    block, while the `select_for_update` lock on this session's row is still
    held, and only raises `TokenReuse` after the block has closed normally.
    Two things follow from that ordering, and both are load-bearing:

    - `revoke_all`'s writes must not share a transaction with a `raise`: an
      exception that propagates out of `transaction.atomic()` rolls back
      everything written inside it, so raising from inside the block, after
      `revoke_all`, would undo the very revocation it just made. Hence the
      block is left to close on its own (a plain fall-through, no exception),
      and `TokenReuse` is raised only once that commit has happened.
    - `revoke_all` runs *before* the block closes, not after, so the
      `select_for_update` lock on this row is held for the whole revocation
      rather than released first and reacquired never. Releasing the lock
      before calling `revoke_all` (an earlier version of this function did
      exactly that) leaves a window, microseconds wide, in which a concurrent
      `rotate()` on a different, still-live session for the same user can
      read "not spent", write its own new session and commit, all before
      `revoke_all`'s `UPDATE` runs, and that new session then survives the
      revocation with `revoked_at IS NULL`. Running `revoke_all` under the
      lock does not make the two rows atomic with each other, since the lock
      is only ever held on this one row, but it removes the specific gap
      where the lock is provably not held by anybody at all.
    """
    # simplejwt's own stub types Token.__init__'s parameter as Optional["Token"],
    # which is an upstream annotation bug: at runtime it accepts the raw JWT
    # string, exactly as simplejwt's own documentation constructs it.
    token = RefreshToken(raw_refresh)  # type: ignore[arg-type]
    with transaction.atomic():
        session = (
            RefreshSession.objects.select_for_update().filter(jti_sha256=_digest(token)).first()
        )
        if session is None:
            raise TokenReuse("no session was ever recorded for this token")
        if not session.is_spent:
            session.rotated_at = timezone.now()
            session.save(update_fields=["rotated_at"])
            return issue(session.user)
        revoke_all(session.user)
    raise TokenReuse("this refresh token was already exchanged")


def revoke(raw_refresh: str) -> None:
    """End one session. A token that cannot be read ends nothing and says so."""
    session = RefreshSession.objects.filter(
        jti_sha256=_digest(RefreshToken(raw_refresh))  # type: ignore[arg-type]
    ).first()
    if session is not None and session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])


def revoke_all(user: User) -> None:
    RefreshSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def _digest(token: RefreshToken) -> str:
    return token_digest(str(token.payload["jti"]))
