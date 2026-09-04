"""Issuing, rotating and refusing a refresh token.

Rotation is written here rather than taken from simplejwt, because simplejwt's
own rotation needs the token_blacklist app and that app stores the whole refresh
JWT in a column. What is stored here is a digest of the token's `jti`, so the
table can say which session a token belongs to and cannot hand anybody a working
credential.
"""

from __future__ import annotations

import pytest
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts import tokens
from accounts.models import RefreshSession, User

PASSWORD = "een-heel-lang-wachtwoord"


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)


@pytest.mark.django_db
def test_issuing_records_a_session_without_the_token(_account: User) -> None:
    access, refresh = tokens.issue(_account)
    assert access and refresh and access != refresh
    session = RefreshSession.objects.get(user=_account)
    assert refresh not in session.jti_sha256
    assert session.rotated_at is None


@pytest.mark.django_db
def test_a_refresh_token_may_be_exchanged_once(_account: User) -> None:
    _, refresh = tokens.issue(_account)
    access, rotated = tokens.rotate(refresh)
    assert access and rotated != refresh
    assert RefreshSession.objects.filter(user=_account, rotated_at__isnull=False).count() == 1
    assert RefreshSession.objects.filter(user=_account).count() == 2


@pytest.mark.django_db
def test_offering_a_spent_token_again_ends_every_session(_account: User) -> None:
    """The one reliable sign that somebody else has a copy. The answer to it is
    not to refuse this request, it is to end every session this account has."""
    _, refresh = tokens.issue(_account)
    tokens.rotate(refresh)
    with pytest.raises(tokens.TokenReuse):
        tokens.rotate(refresh)
    assert not RefreshSession.objects.filter(user=_account, revoked_at__isnull=True).exists()


@pytest.mark.django_db
def test_a_token_this_service_never_issued_is_refused(_account: User) -> None:
    """A bare `pytest.raises(Exception)` here would pass on a bug in `rotate`
    just as easily as on the real behaviour. `TokenError` is what
    `RefreshToken(raw_refresh)` actually raises on a string it cannot parse,
    and it raises before the session lookup runs at all."""
    with pytest.raises(TokenError):
        tokens.rotate("dit.is.geen.token")


@pytest.mark.django_db
def test_a_well_formed_token_with_no_recorded_session_is_refused(_account: User) -> None:
    """`rotate`'s other branch into `TokenReuse`: the signature verifies fine,
    there is simply no `RefreshSession` row for it, because this token was
    minted with `RefreshToken.for_user` directly and never passed through
    `tokens.issue`. The malformed-token test above cannot reach this branch:
    `RefreshToken(raw_refresh)` already raises before `session is None` is
    ever evaluated.
    """
    orphan = RefreshToken.for_user(_account)
    with pytest.raises(tokens.TokenReuse):
        tokens.rotate(str(orphan))


@pytest.mark.django_db
def test_revoking_ends_only_the_session_that_was_offered(_account: User) -> None:
    _, first = tokens.issue(_account)
    _, second = tokens.issue(_account)
    tokens.revoke(first)
    assert RefreshSession.objects.filter(revoked_at__isnull=True).count() == 1
    tokens.rotate(second)


@pytest.mark.django_db
def test_revoking_a_token_with_no_recorded_session_does_nothing_and_raises_nothing(
    _account: User,
) -> None:
    """`revoke`'s "nothing to revoke" branch. A visitor who logs out twice, or
    whose cookie already pointed at a purged session, gets the same quiet
    success either way, not an exception that a logout route would have to
    catch."""
    orphan = RefreshToken.for_user(_account)
    tokens.revoke(str(orphan))
    assert not RefreshSession.objects.filter(user=_account).exists()
