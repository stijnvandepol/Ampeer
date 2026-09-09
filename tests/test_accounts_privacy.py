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
from django.conf import settings
from helpers.accounts import TEST_PASSWORD

from accounts.models import Consent, RefreshSession, User
from accounts.nl import CONSENT_TEXT_VERSION
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
        "password": TEST_PASSWORD,
        "consent_meter_link": True,
        "consent_lead_generation": True,
        "text_version": CONSENT_TEXT_VERSION,
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

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    _, refresh = tokens.issue(user)
    session = RefreshSession.objects.get(user=user)
    assert refresh not in session.jti_sha256
    for part in refresh.split("."):
        assert part not in session.jti_sha256


@pytest.mark.django_db
def test_a_consent_row_holds_no_free_text() -> None:
    """The wording lives in nl.py under a version. A copy of the sentence in
    every row would be a second place it can drift from the one people read."""
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    row = Consent.record(user, Consent.METER_LINK, Consent.GRANTED)
    assert " " not in row.text_version
    assert len(row.text_version) <= 32


@pytest.mark.django_db
def test_the_axes_tables_stay_empty_under_the_cache_handler(client: Any) -> None:
    """`axes` in INSTALLED_APPS ships ten migrations regardless of which
    handler is configured, so `AccessAttempt`, `AccessLog` and
    `AccessFailureLog` EXIST on this database with an `ip_address` column
    each. docs/dpia.md chapter 2 and the design spec do not (any more) claim
    those tables are absent; the claim that survives is narrower and this is
    what enforces it: with `AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"`
    (base.py), nothing ever writes a row into any of the three, no matter how
    many logins fail.

    `tests/test_dpia.py::test_no_table_has_a_column_for_an_address` cannot see
    this: it reads only first-party models by AST, so a third-party app's
    tables are invisible to it. This test is the guard that covers exactly
    that blind spot, over real HTTP and not `RequestFactory`.

    Re-proving this red: `AxesProxyHandler.get_implementation` memoizes its
    result, so swapping `AXES_HANDLER` with `override_settings` alone changes
    nothing already resolved. Force a re-resolution in the same breath:

        with override_settings(AXES_HANDLER="axes.handlers.database.AxesDatabaseHandler"):
            AxesProxyHandler.get_implementation(force=True)
            ... run the same six failed logins ...
            AxesProxyHandler.get_implementation(force=True)  # restore

    Done by hand against this test body: the failed logins never reach the
    three assertions at all. `AXES_CLIENT_IP_CALLABLE` (accounts.lockout) hands
    axes a salted digest, not a real address, and `AccessAttempt.ip_address`
    is a `GenericIPAddressField`. `AxesDatabaseHandler` tries to write that
    digest into it and Postgres's adapter rejects it outright:
    `ValueError: 'c25f5168c56abbc493a4c86efd3cf343' does not appear to be an
    IPv4 or IPv6 address`, raised from
    `django/db/backends/postgresql/operations.py:adapt_ipaddressfield_value`
    while handling the login POST. That is the failure this test exists to
    catch: under the cache handler nothing is ever written, so the mismatch
    between a hashed identifier and an `ip_address` column never surfaces; the
    database handler cannot even accept the write. The handler is forced back
    to the cache implementation in a `finally` immediately afterward so no
    other test observes the swap.
    """
    from axes.models import AccessAttempt, AccessFailureLog, AccessLog

    User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    client.get("/api/auth/me/")
    csrf = {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}
    for _ in range(settings.AXES_FAILURE_LIMIT + 1):
        client.post(
            "/api/auth/login/",
            {"email": "iemand@voorbeeld.nl", "password": "verkeerd"},
            content_type="application/json",
            **csrf,
        )

    assert AccessAttempt.objects.count() == 0
    assert AccessLog.objects.count() == 0
    assert AccessFailureLog.objects.count() == 0


@pytest.mark.django_db
def test_deleting_an_account_removes_its_meter_link_and_every_reading() -> None:
    """CASCADE takes the whole chain: the link, its hours and its quarters.

    Counted rather than assumed, the same way this file already counts every
    other table a deletion has to empty. No route involved: `delete_account`
    needs nothing meter-specific, because `on_delete=CASCADE` on
    `MeterLink.user` already does the work.
    """
    from django.utils import timezone

    from accounts import service
    from accounts.models import HourAggregate, MeterLink, QuarterReading

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    link, _ = service.link_meter(user)
    QuarterReading.objects.create(
        link=link,
        measured_at=timezone.now().replace(minute=0, second=0, microsecond=0),
        consumption_kwh=0.2,
        feed_in_kwh=0.0,
    )
    HourAggregate.objects.create(
        link=link,
        hour_start=timezone.now().replace(minute=0, second=0, microsecond=0),
        consumption_kwh=0.2,
        feed_in_kwh=0.0,
        quarters=1,
    )

    assert MeterLink.objects.count() == 1
    assert QuarterReading.objects.count() == 1
    assert HourAggregate.objects.count() == 1

    service.delete_account(user)

    assert MeterLink.objects.count() == 0
    assert QuarterReading.objects.count() == 0
    assert HourAggregate.objects.count() == 0
