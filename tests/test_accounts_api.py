"""The contract of the auth routes, read off the real response.

The cookie attributes are read out of `response.cookies` one by one and not
inferred from a 200. A test that only checks the status code says nothing about
SameSite, and SameSite is the whole CSRF defence in this deployment.
"""

from __future__ import annotations

from typing import Any, TypedDict

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import Consent, User
from accounts.nl import NL

PASSWORD = "een-heel-lang-wachtwoord"
BODY = {
    "email": "iemand@voorbeeld.nl",
    "password": PASSWORD,
    "consent_meter_link": True,
    "consent_lead_generation": False,
}


class _CsrfHeader(TypedDict):
    """A `TypedDict` rather than a plain `dict[str, str]`.

    `APIClient.post` and `Client.post` both type their trailing `**extra` as
    `Any`, but they also carry named keyword parameters ahead of it
    (`content_type`, `follow`, `secure`, ...) with narrower types of their own.
    mypy checks a `**dict[str, str]` unpack against every one of those named
    parameters, since a plain dict could hold any key, and `follow: bool`
    rejects a `str` value. Unpacking a `TypedDict` is matched key by key
    instead, so the one key here lands in `**extra` and none of the named
    parameters are ever checked against it.
    """

    HTTP_X_CSRFTOKEN: str


def _csrf(client: Any) -> _CsrfHeader:
    """The token every unsafe request carries.

    A GET on a route that only answers POST, so the response is a 405 and the
    cookie rides along on it anyway. That is the property `_AuthAPIView` exists
    for: the cookie is set in `finalize_response`, which DRF also runs for the
    response `handle_exception` builds, so somebody who is not logged in and has
    no token yet can still get one. Task 10 changes this helper to `me/`, which
    is the route a browser actually calls first.
    """
    client.get("/api/auth/login/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


@pytest.mark.django_db
def test_registering_creates_an_account_and_logs_it_in(client: Any) -> None:
    response = client.post(
        "/api/auth/register/", BODY, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 201, response.content
    assert User.objects.filter(email="iemand@voorbeeld.nl").exists()
    assert settings.AMPEER_ACCESS_COOKIE in response.cookies
    assert settings.AMPEER_REFRESH_COOKIE in response.cookies


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cookie", "path"),
    [
        (settings.AMPEER_ACCESS_COOKIE, settings.AMPEER_ACCESS_COOKIE_PATH),
        (settings.AMPEER_REFRESH_COOKIE, settings.AMPEER_REFRESH_COOKIE_PATH),
    ],
)
def test_every_token_cookie_carries_the_attributes_that_protect_it(
    client: Any, cookie: str, path: str
) -> None:
    response = client.post(
        "/api/auth/register/", BODY, content_type="application/json", **_csrf(client)
    )
    morsel = response.cookies[cookie]
    assert morsel["httponly"], f"{cookie} is readable from JavaScript"
    assert morsel["samesite"] == "Strict", f"{cookie} is SameSite={morsel['samesite']!r}"
    assert morsel["path"] == path, f"{cookie} is scoped to {morsel['path']!r}"


@pytest.mark.django_db
def test_registering_records_only_the_consent_that_was_given(client: Any) -> None:
    """A refusal writes nothing. WITHDRAWN for something never granted would be
    an untruth in a table kept as evidence."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    user = User.objects.get(email="iemand@voorbeeld.nl")
    assert Consent.current(user, Consent.METER_LINK) is True
    assert Consent.current(user, Consent.LEAD_GENERATION) is False
    assert Consent.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_a_refused_meter_link_still_creates_the_account(client: Any) -> None:
    """Article 7(4): a service made conditional on consent it does not need is a
    service whose consent is not freely given. Phase 2 checks the consent before
    a single reading arrives; registration does not."""
    body = BODY | {"consent_meter_link": False}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 201, response.content
    assert Consent.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("missing", ["consent_meter_link", "consent_lead_generation"])
def test_a_consent_field_that_is_absent_is_a_refusal_to_answer(client: Any, missing: str) -> None:
    """Not pre-ticked is a property of the serializer and not of the screen: the
    field has no default, so a frontend that forgets the checkbox gets an error
    rather than a consent."""
    body = {key: value for key, value in BODY.items() if key != missing}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert missing in response.json()


@pytest.mark.django_db
def test_registering_with_an_email_already_in_use_is_refused(client: Any) -> None:
    """`RegisterSerializer.validate_email`'s other branch: a second account on
    an address that already exists is a 400, not a second row, and not the
    500 an unhandled `IntegrityError` from the database constraint would be."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post(
        "/api/auth/register/", BODY, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert User.objects.filter(email="iemand@voorbeeld.nl").count() == 1


@pytest.mark.django_db
def test_a_short_password_is_refused_in_dutch(client: Any) -> None:
    body = BODY | {"password": "kort"}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.django_db
def test_logging_in_and_out_moves_the_cookies(client: Any) -> None:
    User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)
    login = client.post(
        "/api/auth/login/",
        {"email": "IEMAND@Voorbeeld.nl", "password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    assert login.status_code == 200, login.content
    assert client.cookies[settings.AMPEER_ACCESS_COOKIE].value

    logout = client.post("/api/auth/logout/", content_type="application/json", **_csrf(client))
    assert logout.status_code == 204
    assert logout.cookies[settings.AMPEER_ACCESS_COOKIE].value == ""


@pytest.mark.django_db
def test_a_wrong_password_says_the_same_thing_as_an_unknown_address(client: Any) -> None:
    """Telling a caller that an address exists tells them something, which is
    the same reason an unknown and an expired advice token answer alike."""
    User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)
    wrong = client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    unknown = client.post(
        "/api/auth/login/",
        {"email": "niemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.django_db
def test_refreshing_hands_out_a_new_pair(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    before = client.cookies[settings.AMPEER_REFRESH_COOKIE].value
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 200
    assert client.cookies[settings.AMPEER_REFRESH_COOKIE].value != before


@pytest.mark.django_db
def test_refreshing_a_spent_refresh_token_ends_the_session(client: Any) -> None:
    """`RefreshView`'s `except (tokens.TokenReuse, TokenError)` branch: a
    refresh cookie already exchanged once is exactly the reuse `tokens.rotate`
    exists to catch, and the answer is `session_expired` with both cookies
    cleared, not a 500 leaking whatever `rotate` raised."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    spent = client.cookies[settings.AMPEER_REFRESH_COOKIE].value
    client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    client.cookies[settings.AMPEER_REFRESH_COOKIE] = spent
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 401
    assert response.json() == {"detail": NL["session_expired"]}
    assert response.cookies[settings.AMPEER_ACCESS_COOKIE].value == ""


@pytest.mark.django_db
def test_refreshing_without_a_refresh_cookie_is_refused(client: Any) -> None:
    """`RefreshView`'s other branch: no `not_signed_in` error is raised by
    `tokens.rotate`, because `tokens.rotate` is never called at all when there
    is no cookie to hand it. A visitor with no session and a stale CSRF cookie
    should read the same "you are not signed in" as one whose refresh token
    expired, not a 500 from a missing argument."""
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 401
    assert response.json() == {"detail": NL["not_signed_in"]}


@pytest.mark.django_db
def test_an_unsafe_request_without_the_csrf_token_is_refused() -> None:
    """The default `client` fixture cannot prove this. `enforce_csrf` never
    raises under `APIRequestFactory` or `APIClient`'s default settings, because
    Django's own `CsrfViewMiddleware.process_view` short-circuits on
    `request._dont_enforce_csrf_checks`, which the default client sets. A test
    written against that client would pass whether or not the check ran at
    all, so this uses `APIClient(enforce_csrf_checks=True)`, which is the one
    setting that turns that flag off."""
    strict = APIClient(enforce_csrf_checks=True)
    strict.post("/api/auth/register/", BODY, format="json", **_csrf(strict))
    response = strict.post("/api/auth/logout/", format="json")
    assert response.status_code == 403, (
        "a state changing request went through without a CSRF token, so SameSite is the "
        "only thing standing between this API and a cross site POST"
    )


@pytest.mark.django_db
def test_an_unsafe_request_with_the_csrf_token_is_accepted() -> None:
    """The other half of the same claim, on the same strict client: without
    this, a version of `enforce_csrf` that raised unconditionally would still
    pass the test above, for the wrong reason."""
    strict = APIClient(enforce_csrf_checks=True)
    strict.post("/api/auth/register/", BODY, format="json", **_csrf(strict))
    response = strict.post("/api/auth/logout/", format="json", **_csrf(strict))
    assert response.status_code == 204, response.content


def test_the_advice_endpoints_did_not_quietly_gain_an_identity() -> None:
    """`DEFAULT_AUTHENTICATION_CLASSES` stays empty and the class is named per
    view, so the three anonymous endpoints cannot start accepting a cookie
    identity because somebody changed a default. Asserted over the resolver
    rather than over the source, because what matters is what is reachable."""
    from django.conf import settings as django_settings
    from django.urls import URLResolver, get_resolver

    assert django_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    for entry in get_resolver().url_patterns:
        # `isinstance` and `getattr(..., "cls", None)` rather than a straight
        # `entry.url_patterns` / `route.callback.cls`: `url_patterns` only
        # exists on `URLResolver`, not on `URLPattern`, and `.cls` is an
        # attribute Django attaches to `as_view()`'s callback at runtime, which
        # no stub declares. `tests/test_backend_settings.py::_routed_views`
        # resolves the same walk the same way.
        if not isinstance(entry, URLResolver) or str(entry.pattern) != "api/advice/":
            continue
        for route in entry.url_patterns:
            view = getattr(getattr(route, "callback", None), "cls", None)
            assert view is not None, f"{route.pattern} is not served by a DRF view"
            assert list(view.authentication_classes) == [], (
                f"api/advice/{route.pattern} is served by {view.__name__}, which now "
                f"authenticates with {view.authentication_classes}"
            )


@pytest.mark.django_db
def test_the_login_route_throttles_before_axes_contention_could_matter(client: Any) -> None:
    """Controller ruling 20. Measurement 1 found the axes cache counter can lose
    some of its own increments under 8-way contention on one (username,
    ip_address) key, so a lockout can be delayed rather than immediate. The
    controller accepted that delay only because the one case it matters for,
    one visitor hammering one account, is bounded by something else entirely:
    `auth-login`'s throttle counts the caller and not the account, so it stops
    an attacker long before axes' own AXES_FAILURE_LIMIT of 5 would need to.

    Each attempt below names a different, nonexistent account, so axes never
    has one (username, ip_address) key to accumulate five failures against and
    plays no part in the answer. `_csrf` above already spends one request on the
    scope (its GET to prime the cookie also runs through `initial()`, which
    checks the throttle before the view even inspects the method), so the loop
    below spends nine more to reach the ten `auth-login` allows per hour, and
    the eleventh request this visitor makes is the one this test is about.

    Written to go red on its own: raise `auth-login` from 10/hour to 100/hour
    and every one of these eleven requests answers 401, none of them 429.
    """
    headers = _csrf(client)  # request 1: the priming GET
    for i in range(9):  # requests 2 through 10
        response = client.post(
            "/api/auth/login/",
            {"email": f"visitor-{i}@voorbeeld.nl", "password": "verkeerd-wachtwoord"},
            content_type="application/json",
            **headers,
        )
        assert response.status_code == 401, response.content
    eleventh = client.post(  # request 11
        "/api/auth/login/",
        {"email": "visitor-9@voorbeeld.nl", "password": "verkeerd-wachtwoord"},
        content_type="application/json",
        **headers,
    )
    assert eleventh.status_code == 429, eleventh.content
