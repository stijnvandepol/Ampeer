"""The three session routes, over real HTTP, plus unlink and export.

Follows the shape tests/test_accounts_api.py already uses: a Django test
`client`, a CSRF header read off `me/`, and JSON bodies.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

import pytest
from django.utils import timezone
from helpers.accounts import TEST_PASSWORD

from accounts.models import Consent, HourAggregate, MeterLink, QuarterReading, User
from accounts.nl import CONSENT_TEXT_VERSION, NL
from advice.models import AuditEvent


class _CsrfHeader(TypedDict):
    HTTP_X_CSRFTOKEN: str


def _csrf(client: Any) -> _CsrfHeader:
    client.get("/api/auth/me/")
    return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}


def _register(
    client: Any, email: str = "iemand@voorbeeld.nl", password: str = TEST_PASSWORD
) -> User:
    """Register, and log the household in: `RegisterView` sets the cookies
    this file's other calls ride on."""
    body = {
        "email": email,
        "password": password,
        "consent_meter_link": True,
        "consent_lead_generation": False,
        "text_version": CONSENT_TEXT_VERSION,
    }
    response = client.post(
        "/api/auth/register/", body, content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 201, response.content
    return User.objects.get(email=email)


def _verify(user: User) -> None:
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])


def _linked(client: Any, email: str = "iemand@voorbeeld.nl") -> tuple[User, str]:
    """A registered, verified household with a granted consent and a key."""
    user = _register(client, email=email)
    _verify(user)
    response = client.post(
        "/api/auth/meter/link/", content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 201, response.content
    return user, response.json()["token"]


def _push(raw: str, body: dict[str, Any] | None = None) -> Any:
    from django.test import Client

    payload = body or {
        "readings": [
            {"measured_at": "2026-09-09T10:15:00Z", "consumption_kwh": 0.2, "feed_in_kwh": 0.0}
        ]
    }
    return Client().post(
        "/api/meter/readings/",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Meter {raw}",
    )


@pytest.mark.django_db
def test_all_three_meter_routes_refuse_a_stranger(client: Any) -> None:
    """Red proof: set `permission_classes = (AllowAny,)` on one of the three."""
    assert client.get("/api/auth/meter/").status_code == 401
    assert client.post("/api/auth/meter/link/", content_type="application/json").status_code == 401
    assert (
        client.post("/api/auth/meter/unlink/", content_type="application/json").status_code == 401
    )


@pytest.mark.django_db
def test_an_unconfirmed_address_may_not_link(client: Any) -> None:
    """Red proof: drop the `email_verified_at` check from `may_link_meter`."""
    _register(client)
    status_response = client.get("/api/auth/meter/")
    assert status_response.json()["may_link"] is False

    link_response = client.post(
        "/api/auth/meter/link/", content_type="application/json", **_csrf(client)
    )
    assert link_response.status_code == 403
    assert NL["meter_not_allowed"] in link_response.content.decode()


@pytest.mark.django_db
def test_a_withheld_consent_may_not_link(client: Any) -> None:
    """Red proof: drop the `Consent.current` check from `may_link_meter`."""
    user = _register(
        client,
    )
    _verify(user)
    Consent.record(user, Consent.METER_LINK, Consent.WITHDRAWN)

    status_response = client.get("/api/auth/meter/")
    assert status_response.json()["may_link"] is False

    link_response = client.post(
        "/api/auth/meter/link/", content_type="application/json", **_csrf(client)
    )
    assert link_response.status_code == 403
    assert NL["meter_not_allowed"] in link_response.content.decode()


@pytest.mark.django_db
def test_linking_hands_back_a_forty_three_character_key_stored_nowhere(client: Any) -> None:
    """Red proof: store the raw key in a column and this fails on the second
    assertion; drop the actual push and it fails on the third."""
    _, raw = _linked(client)
    assert len(raw) == 43
    assert raw not in MeterLink.objects.values_list("token_sha256", flat=True)
    assert _push(raw).status_code == 202


@pytest.mark.django_db
def test_linking_twice_leaves_only_the_newest_key_working(client: Any) -> None:
    """Red proof: drop the `.update(revoked_at=...)` call from `link_meter`."""
    _, first_raw = _linked(client)
    second = client.post("/api/auth/meter/link/", content_type="application/json", **_csrf(client))
    assert second.status_code == 201, second.content

    assert _push(first_raw).status_code == 401
    assert MeterLink.objects.filter(revoked_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_unlinking_after_a_push_erases_the_readings(client: Any) -> None:
    """Red proof: make `unlink_meter` only set `revoked_at`."""
    user, raw = _linked(client)
    assert _push(raw).status_code == 202

    response = client.post(
        "/api/auth/meter/unlink/", content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 204

    link = MeterLink.objects.get(user=user)
    assert QuarterReading.objects.filter(link=link).count() == 0
    assert HourAggregate.objects.filter(link=link).count() == 0
    status_response = client.get("/api/auth/meter/")
    assert status_response.json()["linked"] is False


@pytest.mark.django_db
def test_unlinking_with_nothing_to_unlink_writes_no_audit_line(client: Any) -> None:
    """Red proof: write the audit line unconditionally in `unlink_meter`."""
    _register(client)
    response = client.post(
        "/api/auth/meter/unlink/", content_type="application/json", **_csrf(client)
    )
    assert response.status_code == 204
    assert not AuditEvent.objects.filter(event_type=AuditEvent.METER_UNLINKED).exists()


@pytest.mark.django_db
def test_withdrawing_the_consent_unlinks_and_erases_too(client: Any) -> None:
    """Red proof: remove the `unlink_meter` call from the consent withdrawal path."""
    user, raw = _linked(client)
    assert _push(raw).status_code == 202
    link = MeterLink.objects.get(user=user)

    response = client.post(
        "/api/auth/consent/",
        {"kind": Consent.METER_LINK, "action": Consent.WITHDRAWN},
        content_type="application/json",
        **_csrf(client),
    )
    assert response.status_code == 200, response.content

    link.refresh_from_db()
    assert link.revoked_at is not None
    assert QuarterReading.objects.filter(link=link).count() == 0


@pytest.mark.django_db
def test_link_and_unlink_each_write_exactly_one_line_with_only_a_user_id(client: Any) -> None:
    """Red proof: add another keyword to either `AuditEvent.record` call and
    `tests/test_dpia.py` fails over the context keys; this test fails first,
    over the count and the keys."""
    _, _ = _linked(client)
    linked_lines = AuditEvent.objects.filter(event_type=AuditEvent.METER_LINKED)
    assert linked_lines.count() == 1
    assert set(linked_lines.get().context) == {"user_id"}

    client.post("/api/auth/meter/unlink/", content_type="application/json", **_csrf(client))
    unlinked_lines = AuditEvent.objects.filter(event_type=AuditEvent.METER_UNLINKED)
    assert unlinked_lines.count() == 1
    assert set(unlinked_lines.get().context) == {"user_id"}


@pytest.mark.django_db
def test_one_households_link_is_invisible_to_another(client: Any) -> None:
    """Red proof: drop the `user=user` filter from `MeterLink.active_for`."""
    from django.test import Client

    _linked(client, email="a@voorbeeld.nl")

    other_client = Client()
    _register(other_client, email="b@voorbeeld.nl")
    status_response = other_client.get("/api/auth/meter/")
    assert status_response.json()["linked"] is False


@pytest.mark.django_db
def test_the_export_carries_the_meter_and_never_the_key(client: Any) -> None:
    """Red proof for absence: drop `meter` from `export_account`, the first
    assertion fails. Red proof for the key: add `token_sha256` to the
    export, the last assertion fails."""
    user, raw = _linked(client)
    assert _push(raw).status_code == 202

    response = client.post("/api/auth/export/", content_type="application/json", **_csrf(client))
    assert response.status_code == 200, response.content
    payload = response.json()
    assert payload["meter"] is not None
    assert payload["meter"]["quarters"], "the export carries no quarters to check"
    assert payload["meter"]["hours"] == []
    assert raw not in json.dumps(payload)
    link = MeterLink.objects.get(user=user)
    assert link.token_sha256 not in json.dumps(payload)
