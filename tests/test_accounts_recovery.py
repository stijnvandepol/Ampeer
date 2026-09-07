"""The four recovery handlings, as functions, before a route touches them.

Every assertion here is about a property a route may later rely on: one use
per token, the same refusal for every bad token, a password that is validated
before anything is spent, and tables that never hold a raw token.
"""

from __future__ import annotations

import ast
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import pytest
from django.utils import timezone
from helpers.accounts import OTHER_PASSWORD, TEST_PASSWORD

from accounts import recovery, tokens
from accounts.models import OneTimeToken, OutboundMail, RefreshSession, User
from accounts.nl import CONSENT_TEXT_VERSION, NL
from advice.models import AuditEvent, token_digest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECOVERY = REPO_ROOT / "backend" / "accounts" / "recovery.py"


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)


@pytest.mark.django_db
def test_minting_writes_a_digest_and_returns_the_token_once(_account: User) -> None:
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    assert len(raw) == len(secrets.token_urlsafe(recovery.TOKEN_BYTES))
    row = OneTimeToken.objects.get(user=_account)
    assert row.token_sha256 == token_digest(raw)
    assert row.is_usable
    assert row.expires_at - row.issued_at == OneTimeToken.LIFETIMES[OneTimeToken.PASSWORD_RESET]


@pytest.mark.django_db
def test_a_new_token_supersedes_the_older_unspent_one_of_the_same_kind(_account: User) -> None:
    """Spec 2.3: at most one usable link per person per kind."""
    first = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    second = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    rows = {row.token_sha256: row for row in OneTimeToken.objects.filter(user=_account)}
    assert rows[token_digest(first)].superseded_at is not None
    assert rows[token_digest(second)].is_usable
    verify = OneTimeToken.objects.get(user=_account, kind=OneTimeToken.EMAIL_VERIFY)
    assert verify.is_usable, "a reset token must not supersede a verification token"


@pytest.mark.django_db
def test_minting_an_unknown_kind_is_refused(_account: User) -> None:
    with pytest.raises(ValueError, match="kind"):
        recovery.mint(_account, "SOMETHING_ELSE")


@pytest.mark.django_db
def test_a_reset_request_for_a_known_address_enqueues_exactly_once(_account: User) -> None:
    recovery.request_password_reset("IEMAND@voorbeeld.nl")
    recovery.request_password_reset("iemand@voorbeeld.nl")
    assert OutboundMail.objects.filter(user=_account, kind=OneTimeToken.PASSWORD_RESET).count() == 1
    assert AuditEvent.objects.filter(event_type=AuditEvent.PASSWORD_RESET_REQUESTED).count() == 1
    line = AuditEvent.objects.get(event_type=AuditEvent.PASSWORD_RESET_REQUESTED)
    assert line.context == {"user_id": _account.pk}


@pytest.mark.django_db
def test_a_reset_request_for_an_unknown_or_inactive_address_writes_nothing(_account: User) -> None:
    """No row and no audit line: a line about an unknown address would have
    to carry the address to mean anything."""
    recovery.request_password_reset("niemand@voorbeeld.nl")
    _account.is_active = False
    _account.save(update_fields=["is_active"])
    recovery.request_password_reset("iemand@voorbeeld.nl")
    assert OutboundMail.objects.count() == 0
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_a_reset_token_can_be_used_exactly_once(_account: User) -> None:
    """The second use reads a row with `spent_at` filled and is refused; the
    password is set once. The lock that makes this hold under a real race is
    read off the source in the test below, because two threads inside one
    pytest-django transaction cannot see each other's rows at all."""
    tokens.issue(_account)
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(raw, OTHER_PASSWORD)
    with pytest.raises(recovery.TokenInvalid):
        recovery.confirm_password_reset(raw, TEST_PASSWORD)
    _account.refresh_from_db()
    assert _account.check_password(OTHER_PASSWORD)
    assert not _account.check_password(TEST_PASSWORD)


def _is_atomic_with(node: ast.With) -> bool:
    return any(
        isinstance(item.context_expr, ast.Call)
        and ast.unparse(item.context_expr.func) == "transaction.atomic"
        for item in node.items
    )


def _lock_calls_inside_atomic(func: ast.FunctionDef) -> list[bool]:
    """For every call in `func` that locks a token row, directly with
    `select_for_update` or through `_lock`, whether it sits inside a `with`
    whose context expression is `transaction.atomic(...)`. Walks the function
    body itself, tracking atomic depth, rather than asking only whether the
    two node kinds both occur somewhere in the file: presence of both does not
    say the one is nested in the other."""
    results: list[bool] = []

    def visit(node: ast.AST, atomic_depth: int) -> None:
        if isinstance(node, ast.With) and _is_atomic_with(node):
            atomic_depth += 1
        if isinstance(node, ast.Call):
            target = node.func
            locks_the_row = (
                isinstance(target, ast.Attribute) and target.attr == "select_for_update"
            ) or (isinstance(target, ast.Name) and target.id == "_lock")
            if locks_the_row:
                results.append(atomic_depth > 0)
        for child in ast.iter_child_nodes(node):
            visit(child, atomic_depth)

    visit(func, 0)
    return results


def test_the_token_row_is_locked_before_it_is_read() -> None:
    """`select_for_update()`, direct or through `_lock`, nested inside a `with
    transaction.atomic():` in each confirm function. Read off recovery.py the
    way tests/test_dpia.py reads the views, and checked as containment rather
    than as two counts, so a refactor that lifts the lock above the `with`
    (still passing every behavioural test, since pytest-django wraps each test
    in its own transaction) cannot keep this one green."""
    tree = ast.parse(RECOVERY.read_text(encoding="utf-8"))
    confirm_functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name in {"confirm_password_reset", "confirm_email_verification"}
    }
    assert confirm_functions.keys() == {"confirm_password_reset", "confirm_email_verification"}
    for name, func in confirm_functions.items():
        results = _lock_calls_inside_atomic(func)
        assert results, f"{name} no longer locks the token row at all"
        assert all(results), f"{name} locks the token row outside its transaction"


@pytest.mark.django_db
def test_expired_spent_superseded_and_unknown_tokens_all_raise_the_same_class(
    _account: User,
) -> None:
    now = timezone.now()
    spent = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(spent, OTHER_PASSWORD)
    superseded = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    expired = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    OneTimeToken.objects.filter(token_sha256=token_digest(expired)).update(
        expires_at=now - timedelta(seconds=1)
    )
    for raw in (spent, superseded, "dit-token-bestaat-niet"):
        with pytest.raises(recovery.TokenInvalid):
            recovery.confirm_password_reset(raw, TEST_PASSWORD)
    with pytest.raises(recovery.TokenInvalid):
        recovery.confirm_email_verification(expired)
    with pytest.raises(recovery.TokenInvalid):
        # A verification token offered to the reset route: the kind is part
        # of the lookup, so a link for one purpose cannot serve the other.
        recovery.confirm_password_reset(
            recovery.mint(_account, OneTimeToken.EMAIL_VERIFY), OTHER_PASSWORD
        )
    with pytest.raises(recovery.TokenInvalid):
        # And the reverse: a reset token offered to the verification route.
        recovery.confirm_email_verification(recovery.mint(_account, OneTimeToken.PASSWORD_RESET))


@pytest.mark.django_db
def test_a_completed_reset_revokes_every_session_and_verifies_the_address(_account: User) -> None:
    tokens.issue(_account)
    tokens.issue(_account)
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    before = timezone.now()
    user = recovery.confirm_password_reset(raw, OTHER_PASSWORD)
    assert user.pk == _account.pk
    assert not RefreshSession.objects.filter(user=_account, revoked_at__isnull=True).exists()
    _account.refresh_from_db()
    assert _account.email_verified_at is not None
    assert _account.email_verified_at >= before
    kinds = list(AuditEvent.objects.order_by("id").values_list("event_type", flat=True))
    assert kinds == [AuditEvent.PASSWORD_RESET_COMPLETED, AuditEvent.EMAIL_VERIFIED]


@pytest.mark.django_db
def test_a_reset_on_an_already_verified_address_does_not_verify_it_again(_account: User) -> None:
    first = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    recovery.confirm_email_verification(first)
    _account.refresh_from_db()
    stamped = _account.email_verified_at
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(raw, OTHER_PASSWORD)
    _account.refresh_from_db()
    assert _account.email_verified_at == stamped
    assert AuditEvent.objects.filter(event_type=AuditEvent.EMAIL_VERIFIED).count() == 1


@pytest.mark.django_db
def test_the_password_validators_apply_on_a_reset_and_spend_nothing(_account: User) -> None:
    """A rejected password leaves the token usable: the household reads the
    message and tries again with the same link."""
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    with pytest.raises(recovery.PasswordRejected) as caught:
        recovery.confirm_password_reset(raw, "kort")
    assert any(error.code == "password_too_short" for error in caught.value.error.error_list)
    row = OneTimeToken.objects.get(token_sha256=token_digest(raw))
    assert row.is_usable
    _account.refresh_from_db()
    assert _account.check_password(TEST_PASSWORD)
    assert AuditEvent.objects.count() == 0


@pytest.mark.django_db
def test_the_password_validators_see_the_user_not_only_the_password(_account: User) -> None:
    """Spec 3.3: the validators run "met de gebruiker erbij", because
    `UserAttributeSimilarityValidator` compares against the address. A password
    built from the account's own address clears `MinimumLengthValidator` on
    its own (nineteen characters), so only passing the user along catches it:
    drop `, user` from the `validate_password` call in recovery.py and this is
    the one test in the suite that turns red."""
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    with pytest.raises(recovery.PasswordRejected) as caught:
        recovery.confirm_password_reset(raw, _account.email)
    assert any(error.code == "password_too_similar" for error in caught.value.error.error_list)
    row = OneTimeToken.objects.get(token_sha256=token_digest(raw))
    assert row.is_usable


@pytest.mark.django_db
def test_a_verification_confirms_once_and_writes_one_line(_account: User) -> None:
    raw = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    recovery.confirm_email_verification(raw)
    with pytest.raises(recovery.TokenInvalid):
        recovery.confirm_email_verification(raw)
    _account.refresh_from_db()
    assert _account.email_verified_at is not None
    assert AuditEvent.objects.filter(event_type=AuditEvent.EMAIL_VERIFIED).count() == 1


@pytest.mark.django_db
def test_a_verification_after_a_reset_already_confirmed_the_address_does_not_move_the_stamp(
    _account: User,
) -> None:
    """A verification token minted before a reset stays usable (the two kinds
    do not supersede each other, spec 2.3): confirming it after the reset has
    already set `email_verified_at` must not move that timestamp forward."""
    verify_raw = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    reset_raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    recovery.confirm_password_reset(reset_raw, OTHER_PASSWORD)
    _account.refresh_from_db()
    stamped = _account.email_verified_at
    assert stamped is not None
    recovery.confirm_email_verification(verify_raw)
    _account.refresh_from_db()
    assert _account.email_verified_at == stamped


@pytest.mark.django_db
def test_requesting_a_verification_dedupes_and_stops_once_verified(_account: User) -> None:
    recovery.request_email_verification(_account)
    recovery.request_email_verification(_account)
    assert OutboundMail.objects.filter(kind=OneTimeToken.EMAIL_VERIFY).count() == 1
    OutboundMail.objects.all().delete()
    _account.email_verified_at = timezone.now()
    _account.save(update_fields=["email_verified_at"])
    recovery.request_email_verification(_account)
    assert OutboundMail.objects.count() == 0


@pytest.mark.django_db
def test_no_column_anywhere_holds_a_raw_token(_account: User) -> None:
    """Value based, like test_no_session_row_carries_anything_that_opens_a_session:
    the raw token is searched for in every text column of the three tables."""
    recovery.request_password_reset(_account.email)
    raw = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    values: list[str] = []
    for row in OneTimeToken.objects.all():
        values.extend([row.kind, row.token_sha256])
    for mail in OutboundMail.objects.all():
        values.append(mail.kind)
    for line in AuditEvent.objects.all():
        values.append(line.event_type)
        values.extend(str(item) for pair in line.context.items() for item in pair)
    assert values, "nothing was read, so nothing was checked"
    assert all(raw not in value for value in values)
    assert token_digest(raw) in values, "the token table was not among what was read"


# ---------------------------------------------------------------------------
# The four routes
# ---------------------------------------------------------------------------


class _CsrfHeader(TypedDict):
    HTTP_X_CSRFTOKEN: str


def _csrf(client: Any) -> _CsrfHeader:
    client.get("/api/auth/me/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _register(client: Any, email: str = "iemand@voorbeeld.nl") -> _CsrfHeader:
    headers = _csrf(client)
    response = client.post(
        "/api/auth/register/",
        {
            "email": email,
            "password": TEST_PASSWORD,
            "consent_meter_link": False,
            "consent_lead_generation": False,
            "text_version": CONSENT_TEXT_VERSION,
        },
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201, response.content
    return headers


@pytest.mark.django_db
def test_a_reset_request_answers_the_same_for_a_known_and_an_unknown_address(
    client: Any,
) -> None:
    """Byte-identical, and nothing logged for the unknown one. Red-proof: make
    ResetRequestView answer 404 when recovery finds no user."""
    _register(client)
    client.post("/api/auth/logout/", content_type="application/json", **_csrf(client))
    lines_before = AuditEvent.objects.count()
    headers = _csrf(client)
    known = client.post(
        "/api/auth/reset/request/",
        {"email": "iemand@voorbeeld.nl"},
        content_type="application/json",
        **headers,
    )
    unknown = client.post(
        "/api/auth/reset/request/",
        {"email": "niemand@voorbeeld.nl"},
        content_type="application/json",
        **headers,
    )
    assert known.status_code == 202 == unknown.status_code
    assert known.content == unknown.content == b"{}"
    assert OutboundMail.objects.filter(kind=OneTimeToken.PASSWORD_RESET).count() == 1
    assert AuditEvent.objects.count() == lines_before + 1


@pytest.mark.django_db
def test_a_reset_request_without_a_valid_address_is_a_400_under_email(client: Any) -> None:
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/request/",
        {"email": "geen adres"},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
    assert response.json() == {"email": [NL["email_invalid"]]}


@pytest.mark.django_db
def test_a_reset_confirm_sets_the_password_without_a_session(client: Any) -> None:
    _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    raw = recovery.mint(user, OneTimeToken.PASSWORD_RESET)
    client.cookies.clear()
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/confirm/",
        {"token": raw, "password": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 204, response.content
    assert "ampeer_access" not in response.cookies
    assert "ampeer_refresh" not in response.cookies
    old = client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": TEST_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert new.status_code == 200, new.content


@pytest.mark.django_db
@pytest.mark.parametrize("token", ["dit-bestaat-niet", ""])
def test_a_bad_token_is_one_sentence_under_token(client: Any, token: str) -> None:
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/confirm/",
        {"token": token, "password": OTHER_PASSWORD},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
    assert response.json() == {"token": [NL["token_invalid"]]}


@pytest.mark.django_db
def test_a_rejected_password_on_reset_reads_like_registration(client: Any) -> None:
    _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    raw = recovery.mint(user, OneTimeToken.PASSWORD_RESET)
    headers = _csrf(client)
    response = client.post(
        "/api/auth/reset/confirm/",
        {"token": raw, "password": "kort"},
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 400
    assert response.json()["password"][0] == NL["password_too_short"] % {"min_length": 12}
    assert OneTimeToken.objects.get(token_sha256=token_digest(raw)).is_usable


@pytest.mark.django_db
def test_a_verification_confirm_answers_204_and_me_carries_the_timestamp(client: Any) -> None:
    headers = _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    raw = recovery.mint(user, OneTimeToken.EMAIL_VERIFY)
    before = client.get("/api/auth/me/").json()
    assert before["email_verified_at"] is None
    response = client.post(
        "/api/auth/verify/confirm/", {"token": raw}, content_type="application/json", **headers
    )
    assert response.status_code == 204
    after = client.get("/api/auth/me/").json()
    assert datetime.fromisoformat(after["email_verified_at"]) is not None
    again = client.post(
        "/api/auth/verify/confirm/", {"token": raw}, content_type="application/json", **headers
    )
    assert again.status_code == 400
    assert again.json() == {"token": [NL["token_invalid"]]}


@pytest.mark.django_db
def test_the_export_carries_the_confirmation_timestamp(client: Any) -> None:
    """Spec 6.4 and the first bullet of the definition of done, and article 15
    behind both. `me/` has answered this field since the routes landed, so an
    export without it hands a household less than the screen already shows,
    and the export is the copy the law is about."""
    headers = _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    before = client.post("/api/auth/export/", content_type="application/json", **headers).json()
    assert "email_verified_at" in before, "the export no longer carries the timestamp at all"
    assert before["email_verified_at"] is None
    raw = recovery.mint(user, OneTimeToken.EMAIL_VERIFY)
    confirmed = client.post(
        "/api/auth/verify/confirm/", {"token": raw}, content_type="application/json", **headers
    )
    assert confirmed.status_code == 204
    after = client.post("/api/auth/export/", content_type="application/json", **headers).json()
    stamped = after["email_verified_at"]
    assert stamped is not None
    # The parse is the check: anything that is not a timestamp raises here.
    datetime.fromisoformat(stamped)
    assert stamped == client.get("/api/auth/me/").json()["email_verified_at"]


@pytest.mark.django_db
def test_registration_enqueues_a_verification_mail(client: Any) -> None:
    _register(client)
    user = User.objects.get(email="iemand@voorbeeld.nl")
    assert OutboundMail.objects.filter(user=user, kind=OneTimeToken.EMAIL_VERIFY).count() == 1


@pytest.mark.django_db
def test_resending_a_verification_requires_a_session_and_dedupes(client: Any) -> None:
    stranger = client.post(
        "/api/auth/verify/request/", content_type="application/json", **_csrf(client)
    )
    assert stranger.status_code == 401
    headers = _register(client)
    first = client.post("/api/auth/verify/request/", content_type="application/json", **headers)
    second = client.post("/api/auth/verify/request/", content_type="application/json", **headers)
    assert first.status_code == 202 == second.status_code
    assert first.content == b"{}"
    assert OutboundMail.objects.filter(kind=OneTimeToken.EMAIL_VERIFY).count() == 1


@pytest.mark.django_db
def test_the_public_recovery_routes_refuse_a_post_without_the_csrf_header(client: Any) -> None:
    from rest_framework.test import APIClient

    strict = APIClient(enforce_csrf_checks=True)
    strict.get("/api/auth/me/")
    for path, body in (
        ("/api/auth/reset/request/", {"email": "iemand@voorbeeld.nl"}),
        ("/api/auth/reset/confirm/", {"token": "x", "password": OTHER_PASSWORD}),
        ("/api/auth/verify/confirm/", {"token": "x"}),
    ):
        response = strict.post(path, body, format="json")
        assert response.status_code == 403, (path, response.content)


@pytest.mark.django_db
def test_the_eleventh_reset_request_in_an_hour_is_refused_in_dutch(client: Any) -> None:
    """The auth-reset scope was declared and counted, and no request ever
    reached its refusal; the review drove it by hand. Now the suite does,
    and asserts the Dutch sentence with the header's own number.

    Ten reset requests to real and fake addresses, the route answers alike
    with no audit line for unknown ones, consume the whole of `auth-reset`'s
    10/hour; the eleventh is throttled before the handler ever runs, so its
    `detail` owes nothing to whether the address is real or not.
    """
    headers = _csrf(client)
    for i in range(10):  # requests 1 through 10
        response = client.post(
            "/api/auth/reset/request/",
            {"email": f"iemand-{i}@voorbeeld.nl"},
            content_type="application/json",
            **headers,
        )
        assert response.status_code == 202, response.content
    eleventh = client.post(  # request 11
        "/api/auth/reset/request/",
        {"email": "iemand-10@voorbeeld.nl"},
        content_type="application/json",
        **headers,
    )
    assert eleventh.status_code == 429, eleventh.content
    seconds = int(eleventh["Retry-After"])
    assert eleventh.json()["detail"] == NL["throttled"] % {"seconds": seconds}


@pytest.mark.django_db
def test_the_thirteen_routes_each_carry_a_scope_with_a_rate() -> None:
    """Spec 3.5, beside tests/test_backend_settings.py's resolver walk: the
    four new views name `auth-reset` or `auth-write`, and nginx's ceiling
    still clears the summed per-visitor rate by fifty times."""
    from django.conf import settings

    from accounts import urls, views

    assert len(urls.urlpatterns) == 13
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["auth-reset"] == "10/hour"
    assert views.ResetRequestView.throttle_scope == "auth-reset"
    assert views.ResetConfirmView.throttle_scope == "auth-reset"
    assert views.VerifyConfirmView.throttle_scope == "auth-reset"
    assert views.VerifyRequestView.throttle_scope == "auth-write"
    per_hour = sum(int(rate.split("/")[0]) for rate in rates.values())
    assert per_hour == 490
    assert 10.0 >= 50 * (per_hour / 3600)
