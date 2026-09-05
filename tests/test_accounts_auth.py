"""Issuing, rotating and refusing a refresh token.

Rotation is written here rather than taken from simplejwt, because simplejwt's
own rotation needs the token_blacklist app and that app stores the whole refresh
JWT in a column. What is stored here is a digest of the token's `jti`, so the
table can say which session a token belongs to and cannot hand anybody a working
credential.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts import cookies, tokens
from accounts.authentication import (
    CookieJWTAuthentication,
    _never_called_callback,
    _never_called_get_response,
)
from accounts.models import RefreshSession, User
from accounts.nl import NL

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
def test_revoking_an_already_revoked_session_touches_nothing_a_second_time(
    _account: User,
) -> None:
    """`revoke`'s `session.revoked_at is None` half of the short-circuit: a
    session already ended stays exactly as it was, rather than getting its
    `revoked_at` bumped forward on a second logout for the same cookie."""
    _, refresh = tokens.issue(_account)
    tokens.revoke(refresh)
    first = RefreshSession.objects.get(user=_account).revoked_at
    tokens.revoke(refresh)
    assert RefreshSession.objects.get(user=_account).revoked_at == first


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


# ---------------------------------------------------------------------------
# cookies.py: attributes asserted one by one off the real Morsel objects on a
# real rest_framework.response.Response, not inferred from a 200.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_set_tokens_writes_every_attribute_on_the_real_response(_account: User) -> None:
    access, refresh = tokens.issue(_account)
    response = Response()
    cookies.set_tokens(response, access, refresh)

    access_cookie = response.cookies[settings.AMPEER_ACCESS_COOKIE]
    assert access_cookie["httponly"] is True
    assert access_cookie["samesite"] == "Strict"
    assert access_cookie["path"] == "/api/"
    assert access_cookie["max-age"] == 900
    # AMPEER_COOKIE_SECURE is False in ampeer.settings.test, and Django's
    # HttpResponseBase.set_cookie only ever writes the "secure" attribute when
    # its argument is truthy, so the Morsel here reads '' rather than False:
    # byte-identical to a set_cookie call that never passed secure= at all.
    # Asserting falsy is therefore the honest claim; a literal `is False`
    # would pass by coincidence, not because this code path was exercised.
    assert not access_cookie["secure"]

    refresh_cookie = response.cookies[settings.AMPEER_REFRESH_COOKIE]
    assert refresh_cookie["httponly"] is True
    assert refresh_cookie["samesite"] == "Strict"
    assert refresh_cookie["path"] == "/api/auth/"
    assert refresh_cookie["max-age"] == 1209600
    assert not refresh_cookie["secure"]


@pytest.mark.django_db
def test_set_tokens_writes_secure_true_when_the_setting_says_so(_account: User) -> None:
    """The other half of the `secure` claim above. Without this test, a
    `secure=settings.AMPEER_COOKIE_SECURE` that had silently become
    `secure=False` (a hardcoded literal, ignoring the setting entirely) would
    still pass the falsy assertion in the test above."""
    access, refresh = tokens.issue(_account)
    with override_settings(AMPEER_COOKIE_SECURE=True):
        response = Response()
        cookies.set_tokens(response, access, refresh)
    assert response.cookies[settings.AMPEER_ACCESS_COOKIE]["secure"] is True
    assert response.cookies[settings.AMPEER_REFRESH_COOKIE]["secure"] is True


@pytest.mark.django_db
def test_clear_tokens_empties_both_cookies_at_their_own_paths(_account: User) -> None:
    access, refresh = tokens.issue(_account)
    response = Response()
    cookies.set_tokens(response, access, refresh)
    cookies.clear_tokens(response)

    access_cookie = response.cookies[settings.AMPEER_ACCESS_COOKIE]
    assert access_cookie.value == ""
    assert access_cookie["max-age"] == 0
    assert access_cookie["path"] == "/api/"

    refresh_cookie = response.cookies[settings.AMPEER_REFRESH_COOKIE]
    assert refresh_cookie.value == ""
    assert refresh_cookie["max-age"] == 0
    assert refresh_cookie["path"] == "/api/auth/"


# ---------------------------------------------------------------------------
# authentication.py: the cookie is the only accepted location, and CSRF is
# enforced on unsafe methods only, both against real DRF Request objects.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_valid_bearer_token_alone_does_not_authenticate(_account: User) -> None:
    """docs/dpia.md chapter 8's invariant: a valid, well-formed access token
    in the Authorization header, with no cookie at all, must not authenticate
    the request. Sending garbage in the header would prove nothing about this
    claim, since garbage is refused for an unrelated reason; this token is
    genuinely valid for this account, minted the same way `tokens.issue`
    mints one, and it is still refused because it never reached the cookie."""
    access = str(AccessToken.for_user(_account))
    django_request = APIRequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {access}")
    request = Request(django_request)
    assert CookieJWTAuthentication().authenticate(request) is None


@pytest.mark.django_db
def test_a_cookie_with_no_csrf_token_is_refused_on_an_unsafe_method(_account: User) -> None:
    """`APIRequestFactory(enforce_csrf_checks=True)` is required here: the
    default factory sets `request._dont_enforce_csrf_checks = True`, which
    makes `CsrfViewMiddleware.process_view` (and so `enforce_csrf`) return
    without ever raising, regardless of what this test asserts."""
    access = str(AccessToken.for_user(_account))
    factory = APIRequestFactory(enforce_csrf_checks=True)
    django_request = factory.post("/", HTTP_COOKIE=f"{settings.AMPEER_ACCESS_COOKIE}={access}")
    request = Request(django_request)
    with pytest.raises(PermissionDenied) as excinfo:
        CookieJWTAuthentication().authenticate(request)
    assert str(excinfo.value.detail) == NL["csrf_failed"]


@pytest.mark.django_db
def test_a_cookie_with_no_csrf_token_authenticates_on_a_safe_method(_account: User) -> None:
    """The other half: `enforce_csrf` is only ever called for unsafe methods,
    so the same missing-CSRF-token request that raises above must succeed
    here for a GET, under the same `enforce_csrf_checks=True` factory."""
    access = str(AccessToken.for_user(_account))
    factory = APIRequestFactory(enforce_csrf_checks=True)
    django_request = factory.get("/", HTTP_COOKIE=f"{settings.AMPEER_ACCESS_COOKIE}={access}")
    request = Request(django_request)
    result = CookieJWTAuthentication().authenticate(request)
    assert result is not None
    user, validated = result
    assert user == _account
    assert validated is not None


def test_authenticate_header_names_the_cookie_realm() -> None:
    """So DRF answers 401 and not 403 to a visitor who never signed in at all;
    without this header DRF cannot tell the two apart, and the frontend needs
    the difference to decide whether to show a login form."""
    request = Request(APIRequestFactory().get("/"))
    assert CookieJWTAuthentication().authenticate_header(request) == 'Cookie realm="api"'


def test_the_dummy_get_response_is_never_meant_to_run() -> None:
    """`_never_called_get_response` exists only to satisfy `CSRFCheck.__init__`'s
    parameter type; `enforce_csrf` never lets `CSRFCheck` actually call it. This
    proves the claim rather than leaving it asserted only in a comment."""
    with pytest.raises(AssertionError):
        _never_called_get_response(APIRequestFactory().get("/"))


def test_the_dummy_callback_is_never_meant_to_run() -> None:
    """Same claim, for the view callback `process_view` is handed but never
    invokes."""
    with pytest.raises(AssertionError):
        _never_called_callback()
