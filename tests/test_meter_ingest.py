"""The push route, over real HTTP, against a real database.

A household's own device is the caller here, never a browser: no cookie, no
CSRF, and the one thing that identifies it is the header this file sends by
hand on every request.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone
from helpers.accounts import TEST_PASSWORD

from accounts.meter import store_readings
from accounts.models import MeterLink, QuarterReading, User
from accounts.nl import NL
from advice.models import token_digest

RAW_KEY = "a-raw-key-that-only-this-test-knows-about"

BODY = {
    "readings": [
        {"measured_at": "2026-09-09T10:15:00Z", "consumption_kwh": 0.2, "feed_in_kwh": 0.0},
        {"measured_at": "2026-09-09T10:30:00Z", "consumption_kwh": 0.3, "feed_in_kwh": 0.1},
    ]
}


def _user(email: str = "iemand@voorbeeld.nl") -> User:
    return User.objects.create_user(email=email, password=TEST_PASSWORD)


def _link(user: User, raw: str = RAW_KEY, revoked: bool = False) -> MeterLink:
    return MeterLink.objects.create(
        user=user,
        token_sha256=token_digest(raw),
        revoked_at=timezone.now() if revoked else None,
    )


def _push(client: Any, body: dict[str, Any], raw: str | None = RAW_KEY) -> Any:
    extra = {"HTTP_AUTHORIZATION": f"Meter {raw}"} if raw is not None else {}
    return client.post(
        "/api/meter/readings/", json.dumps(body), content_type="application/json", **extra
    )


@pytest.mark.django_db
def test_a_request_with_no_authorization_header_is_refused(client: Any) -> None:
    """Red proof: set `MeterReadingsView.permission_classes` to `(AllowAny,)`."""
    response = _push(client, BODY, raw=None)
    assert response.status_code == 401


@pytest.mark.django_db
def test_a_key_that_belongs_to_no_link_is_refused_in_dutch(client: Any) -> None:
    """Red proof: make `MeterTokenAuthentication.authenticate` return `None`
    instead of raising when the digest matches nothing, and the sentence
    disappears from the body along with the 401."""
    response = _push(client, BODY, raw="something-nobody-ever-issued")
    assert response.status_code == 401
    assert NL["meter_token_invalid"] in response.content.decode()


@pytest.mark.django_db
def test_a_revoked_links_key_no_longer_works(client: Any) -> None:
    """Red proof: drop `revoked_at__isnull=True` from the lookup in
    `MeterTokenAuthentication.authenticate`."""
    _link(_user(), revoked=True)
    response = _push(client, BODY)
    assert response.status_code == 401


@pytest.mark.django_db
def test_a_deactivated_accounts_key_no_longer_works(client: Any) -> None:
    """`is_active` is the one switch this project has for suspending an
    account without deleting it, and `AbstractBaseUser.is_authenticated` never
    consults it, so this route has to.

    Red proof: drop `user__is_active=True` from the lookup in
    `MeterTokenAuthentication.authenticate`.
    """
    link = _link(_user())
    link.user.is_active = False
    link.user.save(update_fields=["is_active"])

    response = _push(client, BODY)

    assert response.status_code == 401


@pytest.mark.django_db
def test_a_valid_key_stores_its_readings_and_marks_the_link_seen(client: Any) -> None:
    """Red proof: make `store_readings` a no-op that always returns `(0, 0)`."""
    link = _link(_user())
    response = _push(client, BODY)
    assert response.status_code == 202, response.content
    assert response.json() == {"stored": 2, "skipped": 0}
    assert QuarterReading.objects.filter(link=link).count() == 2
    link.refresh_from_db()
    assert link.last_seen_at is not None


@pytest.mark.django_db
def test_the_same_batch_pushed_twice_stores_nothing_the_second_time(client: Any) -> None:
    """Idempotent on `(link, measured_at)`.

    Red proof: drop `ignore_conflicts=True` from the `bulk_create` call in
    `store_readings` and the second push raises `IntegrityError` instead of
    answering 202.
    """
    link = _link(_user())
    first = _push(client, BODY)
    assert first.status_code == 202
    second = _push(client, BODY)
    assert second.status_code == 202, second.content
    assert second.json() == {"stored": 0, "skipped": 2}
    assert QuarterReading.objects.filter(link=link).count() == 2


@pytest.mark.django_db
def test_a_batch_over_the_limit_is_refused(client: Any) -> None:
    """Red proof: raise `MAX_READINGS_PER_REQUEST` in accounts/serializers.py."""
    _link(_user())
    start = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
    readings = [
        {
            "measured_at": (start + timedelta(minutes=15 * i)).isoformat().replace("+00:00", "Z"),
            "consumption_kwh": 0.1,
            "feed_in_kwh": 0.0,
        }
        for i in range(101)
    ]
    response = _push(client, {"readings": readings})
    assert response.status_code == 400
    assert NL["meter_batch_too_large"] in response.content.decode()


@pytest.mark.django_db
def test_an_empty_batch_is_refused(client: Any) -> None:
    _link(_user())
    response = _push(client, {"readings": []})
    assert response.status_code == 400


@pytest.mark.django_db
def test_a_reading_off_the_quarter_grid_is_refused_in_dutch(client: Any) -> None:
    """Red proof: remove `validate_measured_at` from `ReadingSerializer`."""
    _link(_user())
    body = {
        "readings": [
            {"measured_at": "2026-09-09T10:07:00Z", "consumption_kwh": 0.1, "feed_in_kwh": 0.0}
        ]
    }
    response = _push(client, body)
    assert response.status_code == 400
    assert NL["meter_reading_invalid"] in response.content.decode()


@pytest.mark.django_db
def test_a_negative_consumption_is_refused(client: Any) -> None:
    """Red proof: drop `min_value=0` from `ReadingSerializer.consumption_kwh`."""
    _link(_user())
    body = {
        "readings": [
            {"measured_at": "2026-09-09T10:15:00Z", "consumption_kwh": -0.1, "feed_in_kwh": 0.0}
        ]
    }
    response = _push(client, body)
    assert response.status_code == 400


@pytest.mark.django_db
def test_one_households_key_never_writes_into_another_households_link(client: Any) -> None:
    """Red proof: make `store_readings` write against `MeterLink.objects.first()`
    instead of the link the header's key resolved to."""
    owner = _user("eigenaar@voorbeeld.nl")
    other = _user("ander@voorbeeld.nl")
    owner_link = _link(owner, raw=RAW_KEY)
    other_link = _link(other, raw="a-different-raw-key")

    _push(client, BODY, raw=RAW_KEY)

    assert QuarterReading.objects.filter(link=owner_link).count() == 2
    assert QuarterReading.objects.filter(link=other_link).count() == 0


@pytest.mark.django_db
def test_the_response_is_never_cached_anywhere_in_between(client: Any) -> None:
    """Red proof: inherit `MeterReadingsView` from `APIView` directly instead of
    `_NoStoreAPIView`."""
    _link(_user())
    response = _push(client, BODY)
    assert response["Cache-Control"] == "private, no-store"


@pytest.mark.django_db
def test_readings_carry_the_kwh_they_were_sent_and_the_right_moment() -> None:
    """A sanity check the ones above never look at: the stored row is the row
    that was sent, not merely present."""
    link = MeterLink.objects.create(user=_user(), token_sha256=token_digest(RAW_KEY))
    stored, skipped = store_readings(
        link,
        [
            {
                "measured_at": datetime(2026, 9, 9, 10, 15, tzinfo=UTC),
                "consumption_kwh": 0.25,
                "feed_in_kwh": 0.0,
            }
        ],
    )
    assert (stored, skipped) == (1, 0)
    row = QuarterReading.objects.get(link=link)
    assert row.consumption_kwh == 0.25
    assert row.measured_at == datetime(2026, 9, 9, 10, 15, tzinfo=UTC)
