"""The contract of the auth routes, read off the real response.

The cookie attributes are read out of `response.cookies` one by one and not
inferred from a 200. A test that only checks the status code says nothing about
SameSite, and SameSite is the whole CSRF defence in this deployment.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, TypedDict

import pytest
from django.conf import settings
from rest_framework.exceptions import NotAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import Consent, User
from accounts.nl import NL
from accounts.views import _AuthAPIView
from advice.models import AuditEvent

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

    A GET on `me/`, which answers 401 to a stranger and the cookie rides along
    on it anyway. That is the property `_AuthAPIView` exists for: the cookie is
    set in `finalize_response`, which DRF also runs for the response
    `handle_exception` builds, so somebody who is not logged in and has no
    token yet can still get one. This is the route a browser actually calls
    first, to learn whether anybody is signed in at all.
    """
    client.get("/api/auth/me/")
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
def test_registering_with_a_different_case_of_the_same_address_is_refused(client: Any) -> None:
    """Spec 4.1's claim proved at the HTTP layer and not only against the
    model: `test_accounts_models.py` already covers `Lower("email")` at the
    database constraint, but nothing before this exercised the same claim
    through `POST /api/auth/register/`. `iemand@voorbeeld.nl` and
    `IEMAND@VOORBEELD.NL` are the same address wearing different letters, and
    a second registration on it is a 400, not a second row."""
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    shouting = BODY | {"email": str(BODY["email"]).upper()}
    response = client.post(
        "/api/auth/register/", shouting, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_a_short_password_is_refused_in_dutch(client: Any) -> None:
    """Asserts the Dutch sentence itself, not merely that a `password` key
    exists: `MinimumLengthValidator.get_error_message()` raises a message
    keyed to no Dutch msgid in Django's shipped catalogue (Django's
    `django.po` does translate "too short", but only the differently
    formatted string `get_help_text()` raises; a mismatch inside Django
    5.2.17 itself, not a project settings problem; see `NL["password_too_short"]`
    in `accounts/nl.py` and the task 9 report), so a test that only checked
    for the key's presence would pass on the English text just as well.

    Red-proof, run manually and reverted (not committed, since it would
    require monkeypatching `MinimumLengthValidator.get_error_message` itself
    to fake a mismatch): temporarily changing `NL["password_too_short"]`'s
    `%(min_length)d` to `%(min_length)s` raises a `KeyError`-free but visibly
    different string, and reverting `RegisterSerializer.validate_password` to
    `raise serializers.ValidationError(list(error.messages)) from error` (the
    pre-fix-round body) makes this assertion fail with the English sentence.
    """
    body = BODY | {"password": "kort"}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert response.json()["password"] == [NL["password_too_short"] % {"min_length": 12}]


@pytest.mark.django_db
def test_a_password_failing_a_different_validator_still_translates(client: Any) -> None:
    """The `else` branch in `validate_password`: a code other than
    `password_too_short` is left to Django's own translation rather than
    routed through `NL["password_too_short"]`. An all-digit password fails
    `NumericPasswordValidator`, whose message Django's shipped Dutch
    catalogue does translate correctly (verified directly against
    `django.contrib.auth.password_validation` in this project's Django
    5.2.17), so this is also a real assertion and not merely a branch filler."""
    body = BODY | {"password": "123456789012"}
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 400
    assert response.json()["password"] == ["Dit wachtwoord bevat alleen cijfers."]


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
def test_logging_out_with_a_malformed_refresh_cookie_still_ends_the_session(client: Any) -> None:
    """`tokens.revoke` calls `RefreshToken(raw_refresh)`, which raises
    `rest_framework_simplejwt.exceptions.TokenError` on anything unparseable.
    `TokenError` is not a DRF `APIException`, so an uncaught one answers 500.
    A cookie can be malformed for reasons that have nothing to do with an
    attack (a stale build, a browser extension, a hand-edited cookie jar), and
    `revoke`'s own docstring already promises "a token that cannot be read
    ends nothing and says so": logout has to still end the session and clear
    both cookies, not 500."""
    User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)
    client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    client.cookies[settings.AMPEER_REFRESH_COOKIE] = "dit.is.geen.token"
    logout = client.post("/api/auth/logout/", content_type="application/json", **_csrf(client))
    assert logout.status_code == 204, logout.content
    assert logout.cookies[settings.AMPEER_ACCESS_COOKIE].value == ""
    assert logout.cookies[settings.AMPEER_REFRESH_COOKIE].value == ""


@pytest.mark.django_db
def test_a_failed_login_for_an_unknown_address_audits_nothing_identifying(client: Any) -> None:
    """The audit log is append-only and never purged (advice/models.py), so a
    personal detail written into it never expires. A failed login for an
    address with no account must write `LOGIN_FAILED` with `user_id: None`
    and nothing else, never the address that was tried: that address may
    belong to somebody who has never been a customer."""
    client.post(
        "/api/auth/login/",
        {"email": "niemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    event = AuditEvent.objects.filter(event_type=AuditEvent.LOGIN_FAILED).latest("occurred_at")
    assert event.context == {"user_id": None}


@pytest.mark.django_db
def test_a_successful_login_audits_an_integer_id_and_no_email(client: Any) -> None:
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)
    client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    event = AuditEvent.objects.filter(event_type=AuditEvent.LOGIN_SUCCEEDED).latest("occurred_at")
    assert event.context == {"user_id": user.pk}
    assert isinstance(event.context["user_id"], int)
    assert "iemand@voorbeeld.nl" not in str(event.context)


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
    current = client.cookies[settings.AMPEER_REFRESH_COOKIE].value
    client.cookies[settings.AMPEER_REFRESH_COOKIE] = spent
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 401
    assert response.json() == {"detail": NL["session_expired"]}
    assert response.cookies[settings.AMPEER_ACCESS_COOKIE].value == ""

    # The reuse above does not merely refuse the spent token: `tokens.rotate`
    # revokes the whole chain, so the session that was legitimate a moment
    # ago (`current`, minted by the first refresh above) must be refused too.
    # Without this, the test above would still be green if `rotate` only ever
    # revoked the one token it was offered.
    client.cookies[settings.AMPEER_REFRESH_COOKIE] = current
    also_revoked = client.post(
        "/api/auth/refresh/", content_type="application/json", **_csrf(client)
    )
    assert also_revoked.status_code == 401
    assert also_revoked.json() == {"detail": NL["session_expired"]}


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
def test_refreshing_a_genuinely_expired_token_is_refused(client: Any) -> None:
    """Spec 13.3 case four: `RefreshView`'s `except (TokenReuse, TokenError)`
    arm also has to catch simplejwt's own expiry, not only this project's own
    `TokenReuse`. `RefreshToken(raw_refresh)` raises `TokenError` once the
    token's own `exp` claim is in the past, before `tokens.rotate` ever looks
    up a `RefreshSession` row, so this is a different branch from the reuse
    case in `test_refreshing_a_spent_refresh_token_ends_the_session` above.

    `override_settings(SIMPLE_JWT={...})` cannot manufacture this case:
    `RefreshToken.lifetime = api_settings.REFRESH_TOKEN_LIFETIME` is a class
    attribute, bound once when `rest_framework_simplejwt.tokens` is imported,
    so a later `setting_changed` signal updates the module-level
    `api_settings` object and leaves the already-bound class attribute exactly
    as it was (checked directly: `RefreshToken.lifetime` is unchanged inside
    the `override_settings` block). What does force a real, signature-valid
    expiry on one specific token is calling `set_exp` on the instance with a
    negative lifetime before it is stringified, which is exactly what
    `RefreshToken.for_user` calls internally with the real one.
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    refresh = RefreshToken(client.cookies[settings.AMPEER_REFRESH_COOKIE].value)
    refresh.set_exp(from_time=refresh.current_time, lifetime=timedelta(seconds=-1))
    client.cookies[settings.AMPEER_REFRESH_COOKIE] = str(refresh)
    response = client.post("/api/auth/refresh/", content_type="application/json", **_csrf(client))
    assert response.status_code == 401
    assert response.json() == {"detail": NL["session_expired"]}
    assert response.cookies[settings.AMPEER_ACCESS_COOKIE].value == ""
    assert response.cookies[settings.AMPEER_REFRESH_COOKIE].value == ""


def test_registering_without_the_csrf_token_is_refused() -> None:
    """`enforce_csrf(request)` at the top of `RegisterView.post` (views.py),
    proven live: the earlier version of this test file only ran `-k
    csrf_token`, which selects the two `logout/` tests and never calls
    `RegisterView` at all, so "the register check has a red-proof" was
    unverified. This one calls register directly, with no prior request on
    this client at all, so there is no CSRF cookie for the header to match
    even if one were sent."""
    strict = APIClient(enforce_csrf_checks=True)
    response = strict.post("/api/auth/register/", BODY, format="json")
    assert response.status_code == 403, (
        "register went through with no CSRF token at all, so login CSRF (being signed "
        "into an account somebody else controls) is not actually blocked"
    )


@pytest.mark.django_db
def test_registering_with_the_csrf_token_is_accepted() -> None:
    """The other half, on the same strict client and the same route: without
    this, a version of `enforce_csrf` that always raised would still pass the
    test above, for the wrong reason."""
    strict = APIClient(enforce_csrf_checks=True)
    response = strict.post("/api/auth/register/", BODY, format="json", **_csrf(strict))
    assert response.status_code == 201, response.content


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
    rather than over the source, because what matters is what is reachable.

    The `continue` below skips anything that is not `api/advice/`, and if that
    prefix is ever remounted elsewhere the loop body never runs at all: a
    vacuous pass that asserts nothing, exactly the shape
    `tests/test_backend_settings.py::test_every_public_route_is_rate_limited`
    already guards against with a count and a named route. Same fix here:
    assert at least the number of routes `advice/urls.py` names today
    (`health/`, `count/`, `estimate/`, `refine/`, the token detail route) and
    that one of them is specifically `estimate/`.
    """
    from django.conf import settings as django_settings
    from django.urls import URLResolver, get_resolver

    assert django_settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    checked: list[str] = []
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
            checked.append(str(route.pattern))
    assert len(checked) >= 5, (
        f"only found {checked}; api/advice/ was not reached at all, so nothing above was "
        "actually asserted"
    )
    assert any(pattern.endswith("estimate/") for pattern in checked), (
        "the estimate endpoint is not among the routes checked, so this test is looking "
        "somewhere other than at the advice API"
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
    plays no part in the answer. `_csrf` above primes on `me/`, which throttles
    under `auth-read` and spends nothing from the `auth-login` scope, so the
    loop below is the whole of the ten `auth-login` allows per hour, and the
    eleventh request this visitor makes is the one this test is about.

    Written to go red on its own: raise `auth-login` from 10/hour to 100/hour
    and every one of these eleven requests answers 401, none of them 429.
    """
    headers = _csrf(client)
    for i in range(10):  # requests 1 through 10
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


@pytest.mark.django_db
def test_axes_locks_out_a_login_over_http_after_five_failed_attempts(client: Any) -> None:
    """This task is the first place `axes` is wired to an HTTP view at all;
    nothing before it proved the lockout actually fires through
    `LoginView.post` rather than only against
    `django.contrib.auth.authenticate()` called directly in a unit test.
    Removing `AxesMiddleware`, or widening `AXES_LOCKOUT_PARAMETERS`, would
    silently disable brute force protection under an otherwise green suite.

    One account, five wrong passwords, then the correct one: `AXES_FAILURE_LIMIT`
    is 5, so the fifth wrong attempt is the one that crosses the threshold and
    is itself refused with 429, and the correct password afterwards is refused
    the same way with no access cookie, because axes answers before
    `ModelBackend` ever checks it. Budget: one priming GET plus five wrong
    attempts plus one correct attempt is seven of `auth-login`'s ten allows
    per hour, well clear of the throttle in
    `test_the_login_route_throttles_before_axes_contention_could_matter` above.

    Red-proof, run manually and reverted (not committed as a permanent
    `override_settings`, since this test's whole point is that axes normally
    runs): wrapping the body in `@override_settings(AXES_ENABLED=False)` and
    rerunning makes every one of the six login attempts answer on its own
    merits (401 for a wrong password, 200 for the right one), and the final
    assertion of 429 fails.
    """
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    headers = _csrf(client)
    for _ in range(4):
        wrong = client.post(
            "/api/auth/login/",
            {"email": BODY["email"], "password": "helemaal-verkeerd"},
            content_type="application/json",
            **headers,
        )
        assert wrong.status_code == 401, wrong.content
    fifth = client.post(
        "/api/auth/login/",
        {"email": BODY["email"], "password": "helemaal-verkeerd"},
        content_type="application/json",
        **headers,
    )
    assert fifth.status_code == 429, fifth.content
    correct = client.post(
        "/api/auth/login/",
        {"email": BODY["email"], "password": PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert correct.status_code == 429, correct.content
    assert settings.AMPEER_ACCESS_COOKIE not in correct.cookies


def test_the_user_property_raises_rather_than_returning_none_under_dash_o() -> None:
    """Ruling 14's `_AuthAPIView.user` property, guarded against `python -O`:
    the brief's original body was a bare `assert isinstance(...)`, which `-O`
    strips, and with `REST_FRAMEWORK["UNAUTHENTICATED_USER"] = None` the
    stripped version would return `None` typed as `User` rather than fail
    loudly. `LogoutView` is on `IsAuthenticated` so this branch never runs
    there in practice; `_AuthAPIView` is still the base every later view
    inherits, including this task's own `AllowAny` ones, so the property has
    to defend itself regardless of who ends up calling it.

    Built directly against the view rather than through HTTP, because no
    route reachable today leaves `request.user` as `None` while still calling
    into a handler that reads `self.user`.
    """
    view = _AuthAPIView()
    view.request = Request(APIRequestFactory().get("/"))
    # `request.user` is typed as `AbstractBaseUser | AnonymousUser`, never
    # `None`; assigning `None` here reproduces exactly what
    # `REST_FRAMEWORK["UNAUTHENTICATED_USER"] = None` actually puts there at
    # runtime for an unauthenticated request, which is the case this property
    # exists to refuse.
    view.request.user = None  # type: ignore[assignment]
    with pytest.raises(NotAuthenticated):
        _ = view.user


@pytest.mark.django_db
def test_me_answers_401_to_a_stranger_and_still_hands_out_a_csrf_token(client: Any) -> None:
    """The property `_AuthAPIView.finalize_response` exists for. Without it the
    only route that sets a CSRF cookie sits behind the login that needs one."""
    response = client.get("/api/auth/me/")
    assert response.status_code == 401
    assert "csrftoken" in response.cookies


@pytest.mark.django_db
def test_me_answers_the_address_and_both_consents(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json() == {
        "email": "iemand@voorbeeld.nl",
        "consents": {"METER_LINK": True, "LEAD_GENERATION": False},
    }


@pytest.mark.django_db
def test_a_consent_can_be_withdrawn_and_given_again(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    user = User.objects.get(email="iemand@voorbeeld.nl")

    withdraw = client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN"},
        content_type="application/json",
        **_csrf(client),
    )
    assert withdraw.status_code == 200
    assert Consent.current(user, Consent.METER_LINK) is False

    again = client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "GRANTED"},
        content_type="application/json",
        **_csrf(client),
    )
    assert again.status_code == 200
    assert Consent.current(user, Consent.METER_LINK) is True
    assert Consent.objects.filter(user=user, kind=Consent.METER_LINK).count() == 3


@pytest.mark.django_db
def test_a_consent_row_can_only_be_written_for_the_caller(client: Any) -> None:
    """Object level permissions: the queryset filters on request.user and there
    is no field in the body that names a user at all."""
    other = User.objects.create_user(email="ander@voorbeeld.nl", password=PASSWORD)
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN", "user": other.pk},
        content_type="application/json",
        **_csrf(client),
    )
    assert Consent.objects.filter(user=other).count() == 0


@pytest.mark.django_db
def test_an_unknown_consent_kind_is_refused(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    response = client.post(
        "/api/auth/consent/",
        {"kind": "SELL_MY_DATA", "action": "GRANTED"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 400
    assert "kind" in response.json()


@pytest.mark.django_db
def test_a_withdrawal_is_written_to_the_audit_log(client: Any) -> None:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    client.post(
        "/api/auth/consent/",
        {"kind": "METER_LINK", "action": "WITHDRAWN"},
        content_type="application/json",
        **_csrf(client),
    )
    line = AuditEvent.objects.filter(event_type=AuditEvent.CONSENT_WITHDRAWN).get()
    assert line.context["kind"] == "METER_LINK"
    assert "voorbeeld" not in str(line.context), "the audit log carries the address"


@pytest.mark.django_db
def test_an_access_token_in_a_header_is_not_accepted(client: Any) -> None:
    """One accepted place for a credential, so there is one place it can leak.

    A header reaches a proxy log more easily than a cookie does, which is the
    same argument docs/dpia.md chapter 8 makes about the advice token sitting in
    a path. simplejwt's own JWTAuthentication reads the header by default, so
    this is a property of the override and not of the package.
    """
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    raw = client.cookies[settings.AMPEER_ACCESS_COOKIE].value
    client.cookies.clear()
    response = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {raw}")
    assert response.status_code == 401, (
        "an access token was accepted out of a header, so there are two places it can be "
        "replayed from and only one of them was designed for"
    )
