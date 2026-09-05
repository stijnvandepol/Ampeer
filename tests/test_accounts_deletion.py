"""Export and deletion, the two rights CLAUDE.md puts in the phase that has accounts.

The advice list in an export is empty for every real account in v1, because
nothing in this phase writes `StoredAdvice.owner`. The shape is still asserted,
on a row these tests attach themselves, so that phase 2 lands in something whose
behaviour is already pinned rather than inventing it then.
"""

from __future__ import annotations

from typing import Any, TypedDict

import pytest
from django.conf import settings
from helpers.accounts import TEST_PASSWORD as PASSWORD
from rest_framework.test import APIClient

from accounts.models import Consent, RefreshSession, User
from advice.models import AuditEvent, StoredAdvice

BODY = {
    "email": "iemand@voorbeeld.nl",
    "password": PASSWORD,
    "consent_meter_link": True,
    "consent_lead_generation": False,
}


class _CsrfHeader(TypedDict):
    """See the identical type in tests/test_accounts_api.py: `APIClient.post`
    types its trailing `**extra` as `Any` but also carries narrower named
    keyword parameters ahead of it, so a plain `dict[str, str]` unpack fails
    `mypy --strict` (it is checked against every named parameter) while a
    `TypedDict` unpack is matched key by key and lands only in `**extra`."""

    HTTP_X_CSRFTOKEN: str


def _strict_csrf(client: APIClient) -> _CsrfHeader:
    """Same token as `_csrf` below, typed for use with `APIClient`."""
    client.get("/api/auth/me/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _csrf(client: Any) -> dict[str, str]:
    client.get("/api/auth/me/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _registered(client: Any) -> User:
    client.post("/api/auth/register/", BODY, content_type="application/json", **_csrf(client))
    return User.objects.get(email="iemand@voorbeeld.nl")


@pytest.mark.django_db
def test_an_export_carries_the_account_and_an_empty_advice_list(client: Any) -> None:
    _registered(client)
    response = client.post("/api/auth/export/", content_type="application/json", **_csrf(client))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "iemand@voorbeeld.nl"
    assert [row["kind"] for row in body["consents"]] == ["METER_LINK"]
    assert body["advices"] == [], (
        "nothing in phase 1 writes StoredAdvice.owner, so a real account cannot have one yet"
    )


@pytest.mark.django_db
def test_an_export_hands_back_the_stored_json_unchanged(client: Any) -> None:
    """Amounts are strings because JSON has only floats. An export that rebuilt
    the answer would be one more place a number passes through a parser."""
    user = _registered(client)
    stored = StoredAdvice.create(
        inputs={"postcode4": "5401"}, advice={"headline": {"p50": "700.08"}}
    )
    stored.owner = user
    stored.save(update_fields=["owner"])

    body = client.post("/api/auth/export/", content_type="application/json", **_csrf(client)).json()
    assert body["advices"] == [
        {"inputs": {"postcode4": "5401"}, "advice": {"headline": {"p50": "700.08"}}}
    ]


@pytest.mark.django_db
def test_an_export_reaches_only_the_caller(client: Any) -> None:
    other = User.objects.create_user(email="ander@voorbeeld.nl", password=PASSWORD)
    stranger = StoredAdvice.create(inputs={"postcode4": "1011"}, advice={})
    stranger.owner = other
    stranger.save(update_fields=["owner"])
    _registered(client)

    body = client.post("/api/auth/export/", content_type="application/json", **_csrf(client)).json()
    assert body["advices"] == []


@pytest.mark.django_db
def test_an_export_is_written_to_the_audit_log(client: Any) -> None:
    user = _registered(client)
    client.post("/api/auth/export/", content_type="application/json", **_csrf(client))
    line = AuditEvent.objects.filter(event_type=AuditEvent.DATA_EXPORTED).get()
    assert line.context == {"user_id": user.pk}


@pytest.mark.django_db
def test_deleting_takes_the_account_its_consents_its_sessions_and_its_advice(
    client: Any,
) -> None:
    user = _registered(client)
    owned = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={})
    owned.owner = user
    owned.save(update_fields=["owner"])
    anonymous = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={})

    response = client.post(
        "/api/auth/delete/",
        {"password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()
    assert not Consent.objects.filter(user_id=user.pk).exists()
    assert not RefreshSession.objects.filter(user_id=user.pk).exists()
    assert not StoredAdvice.objects.filter(pk=owned.pk).exists()
    assert StoredAdvice.objects.filter(pk=anonymous.pk).exists(), (
        "an advice that belongs to nobody was taken with an account it never belonged to"
    )


@pytest.mark.django_db
def test_deleting_clears_both_auth_cookies(client: Any) -> None:
    """The one destructive route in the API has to leave the browser signed
    out, or a deleted account's access cookie keeps validating against a user
    that no longer exists for up to its own lifetime. `LogoutView`'s cookies
    are covered by `test_logging_in_and_out_moves_the_cookies` in
    tests/test_accounts_api.py; `DeleteView` calls the same `clear_tokens`
    helper but had no test of its own reading the response cookies directly."""
    _registered(client)
    response = client.post(
        "/api/auth/delete/",
        {"password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 204

    access_cookie = response.cookies[settings.AMPEER_ACCESS_COOKIE]
    assert access_cookie.value == ""
    assert access_cookie["max-age"] == 0
    assert access_cookie["path"] == "/api/"

    refresh_cookie = response.cookies[settings.AMPEER_REFRESH_COOKIE]
    assert refresh_cookie.value == ""
    assert refresh_cookie["max-age"] == 0
    assert refresh_cookie["path"] == "/api/auth/"


@pytest.mark.django_db
def test_deleting_one_account_leaves_another_accounts_rows_untouched(client: Any) -> None:
    """Object-level permission in the destructive direction: this is the one
    request in the whole API that removes rows, so the scoping that keeps a
    caller's queryset to `request.user` everywhere else has to hold here too,
    against a real account and not only against ownerless data."""
    other = User.objects.create_user(email="ander@voorbeeld.nl", password=PASSWORD)
    theirs = StoredAdvice.create(inputs={"postcode4": "1011"}, advice={})
    theirs.owner = other
    theirs.save(update_fields=["owner"])
    _registered(client)

    client.post(
        "/api/auth/delete/",
        {"password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    assert User.objects.filter(pk=other.pk).exists()
    assert StoredAdvice.objects.filter(pk=theirs.pk).exists(), (
        "another account's advice was taken with an account it never belonged to"
    )


@pytest.mark.django_db
def test_deleting_leaves_the_audit_log_standing(client: Any) -> None:
    """An append-only log that records a deletion and wipes itself doing so
    records nothing."""
    user = _registered(client)
    client.post(
        "/api/auth/delete/",
        {"password": PASSWORD},
        content_type="application/json",
        **_csrf(client),
    )
    kinds = set(AuditEvent.objects.values_list("event_type", flat=True))
    assert AuditEvent.ACCOUNT_CREATED in kinds
    assert AuditEvent.ACCOUNT_DELETED in kinds
    line = AuditEvent.objects.filter(event_type=AuditEvent.ACCOUNT_DELETED).get()
    assert line.context == {"user_id": user.pk}


@pytest.mark.django_db
def test_deleting_needs_the_password_again(client: Any) -> None:
    """Without it one stolen session is enough to wipe somebody's data, and it
    is the other reason this route is a POST: a DELETE with a body is something
    proxies and clients disagree about."""
    user = _registered(client)
    response = client.post(
        "/api/auth/delete/",
        {"password": "verkeerd"},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 403
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_deleting_without_the_csrf_token_is_refused() -> None:
    """The strict CSRF pair task 10's review asked for, on `delete/`
    specifically. The existing pair covers only `logout/`, and this is the
    route where a missing check costs the most: it is the one that removes
    data. The default `client` fixture cannot prove this, because
    `enforce_csrf` never raises under its default settings (see
    `test_an_unsafe_request_without_the_csrf_token_is_refused` in
    tests/test_accounts_api.py), so this uses `APIClient(enforce_csrf_checks=True)`."""
    strict = APIClient(enforce_csrf_checks=True)
    strict.post("/api/auth/register/", BODY, format="json", **_strict_csrf(strict))
    response = strict.post("/api/auth/delete/", {"password": PASSWORD}, format="json")
    assert response.status_code == 403
    assert User.objects.filter(email="iemand@voorbeeld.nl").exists()


@pytest.mark.django_db
def test_deleting_with_the_csrf_token_is_accepted() -> None:
    """The other half of the same claim, on the same strict client: without
    this, an `enforce_csrf` that raised unconditionally would still pass the
    test above, for the wrong reason."""
    strict = APIClient(enforce_csrf_checks=True)
    strict.post("/api/auth/register/", BODY, format="json", **_strict_csrf(strict))
    response = strict.post(
        "/api/auth/delete/", {"password": PASSWORD}, format="json", **_strict_csrf(strict)
    )
    assert response.status_code == 204


@pytest.mark.django_db
def test_deleting_refuses_a_body_that_is_not_an_object(client: Any) -> None:
    """`DeleteView`'s `isinstance(request.data, dict)` guard. A JSON body that
    parses to a list has no `.get`, and calling it anyway would be an
    `AttributeError` reaching a visitor as a 500 instead of the same refusal a
    wrong password gets."""
    user = _registered(client)
    response = client.post(
        "/api/auth/delete/",
        data='["verkeerd soort lichaam"]',
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 403
    assert User.objects.filter(pk=user.pk).exists()
