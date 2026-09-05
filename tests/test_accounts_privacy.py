"""What the account layer may and may not have written down.

The claims in docs/dpia.md chapter 2 are checked against values here and not
against a field list, for the reason section 13.9 of the advice API design
gives: a field list is fixed at import and can never contain what came in at
runtime, so a test over one cannot fail.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from accounts.models import Consent, RefreshSession, User
from advice.models import AuditEvent

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", re.IGNORECASE)


def _values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.items() for entry in item for text in _values(entry)]
    if isinstance(value, (list, tuple)):
        return [text for entry in value for text in _values(entry)]
    return [str(value)]


@pytest.mark.django_db
def test_no_audit_line_the_account_layer_writes_carries_an_address(client: Any) -> None:
    body = {
        "email": "iemand@voorbeeld.nl",
        "password": "een-heel-lang-wachtwoord",
        "consent_meter_link": True,
        "consent_lead_generation": True,
    }
    client.get("/api/auth/me/")
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    client.post("/api/auth/register/", body, content_type="application/json", **csrf)
    client.post("/api/auth/logout/", content_type="application/json", **csrf)
    client.post(
        "/api/auth/login/",
        {"email": "iemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **csrf,
    )

    assert AuditEvent.objects.count() >= 4, "this test is no longer exercising the routes"
    for line in AuditEvent.objects.all():
        for text in _values(line.context):
            assert not EMAIL.search(text), (
                f"{line.event_type} wrote {text!r} into a table with no retention"
            )


@pytest.mark.django_db
def test_a_failed_login_for_an_unknown_address_records_nothing_identifying(client: Any) -> None:
    """The address of somebody who may not even be a customer, permanently."""
    client.get("/api/auth/me/")
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    client.post(
        "/api/auth/login/",
        {"email": "niemand@voorbeeld.nl", "password": "verkeerd"},
        content_type="application/json",
        **csrf,
    )
    line = AuditEvent.objects.filter(event_type=AuditEvent.LOGIN_FAILED).get()
    assert line.context.get("user_id") is None


@pytest.mark.django_db
def test_no_session_row_carries_anything_that_opens_a_session() -> None:
    from accounts import tokens

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    _, refresh = tokens.issue(user)
    session = RefreshSession.objects.get(user=user)
    assert refresh not in session.jti_sha256
    for part in refresh.split("."):
        assert part not in session.jti_sha256


@pytest.mark.django_db
def test_a_consent_row_holds_no_free_text() -> None:
    """The wording lives in nl.py under a version. A copy of the sentence in
    every row would be a second place it can drift from the one people read."""
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    row = Consent.record(user, Consent.METER_LINK, Consent.GRANTED)
    assert " " not in row.text_version
    assert len(row.text_version) <= 32
