"""The meter link and its two measurement tables, on their own, without a route."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db.utils import IntegrityError
from django.utils import timezone
from helpers.accounts import TEST_PASSWORD

from accounts.models import HourAggregate, MeterLink, QuarterReading, User


def _user(email: str = "iemand@voorbeeld.nl") -> User:
    return User.objects.create_user(email=email, password=TEST_PASSWORD)


@pytest.mark.django_db
def test_a_second_quarter_reading_for_the_same_link_and_moment_is_refused() -> None:
    """The unique constraint is what makes the ingest route idempotent.

    Red proof: drop `UniqueConstraint(fields=["link", "measured_at"], ...)`
    from `QuarterReading.Meta.constraints`, regenerate the migration, and this
    raises `AssertionError: DID NOT RAISE <class 'IntegrityError'>` instead.
    """
    link = MeterLink.objects.create(user=_user(), token_sha256="a" * 64)
    moment = datetime(2026, 9, 9, 10, 15, tzinfo=UTC)
    QuarterReading.objects.create(
        link=link, measured_at=moment, consumption_kwh=0.2, feed_in_kwh=0.0
    )
    with pytest.raises(IntegrityError):
        QuarterReading.objects.create(
            link=link, measured_at=moment, consumption_kwh=0.3, feed_in_kwh=0.0
        )


@pytest.mark.django_db
def test_a_second_hour_aggregate_for_the_same_link_and_hour_is_refused() -> None:
    """Same constraint, one table over.

    Red proof: drop `UniqueConstraint(fields=["link", "hour_start"], ...)` from
    `HourAggregate.Meta.constraints`, regenerate the migration, and this raises
    `AssertionError: DID NOT RAISE <class 'IntegrityError'>` instead.
    """
    link = MeterLink.objects.create(user=_user(), token_sha256="b" * 64)
    hour = datetime(2026, 9, 9, 10, 0, tzinfo=UTC)
    HourAggregate.objects.create(
        link=link, hour_start=hour, consumption_kwh=0.8, feed_in_kwh=0.0, quarters=4
    )
    with pytest.raises(IntegrityError):
        HourAggregate.objects.create(
            link=link, hour_start=hour, consumption_kwh=0.5, feed_in_kwh=0.0, quarters=2
        )


@pytest.mark.django_db
def test_is_active_is_true_until_revoked_at_is_set() -> None:
    """Red proof: make `is_active` return `True` unconditionally and this fails
    on the second assertion."""
    link = MeterLink.objects.create(user=_user(), token_sha256="c" * 64)
    assert link.is_active is True
    link.revoked_at = timezone.now()
    link.save(update_fields=["revoked_at"])
    assert link.is_active is False


@pytest.mark.django_db
def test_active_for_finds_the_one_active_link_and_nothing_revoked() -> None:
    """Red proof: remove `revoked_at__isnull=True` from `active_for`'s filter
    and the third assertion below fails, because it would then return the
    revoked row instead of `None`."""
    user = _user()
    assert MeterLink.active_for(user) is None

    link = MeterLink.objects.create(user=user, token_sha256="d" * 64)
    assert MeterLink.active_for(user) == link

    link.revoked_at = timezone.now()
    link.save(update_fields=["revoked_at"])
    assert MeterLink.active_for(user) is None


@pytest.mark.django_db
def test_deleting_the_user_removes_the_link_and_every_reading() -> None:
    """CASCADE all the way down, counted rather than assumed.

    Red proof: set `QuarterReading.link` to `on_delete=SET_NULL, null=True`
    and the counts after `user.delete()` stay at one instead of falling to
    zero.
    """
    user = _user()
    link = MeterLink.objects.create(user=user, token_sha256="e" * 64)
    QuarterReading.objects.create(
        link=link,
        measured_at=datetime(2026, 9, 9, 10, 15, tzinfo=UTC),
        consumption_kwh=0.2,
        feed_in_kwh=0.0,
    )
    HourAggregate.objects.create(
        link=link,
        hour_start=datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
        consumption_kwh=0.2,
        feed_in_kwh=0.0,
        quarters=1,
    )

    assert MeterLink.objects.count() == 1
    assert QuarterReading.objects.count() == 1
    assert HourAggregate.objects.count() == 1

    user.delete()

    assert MeterLink.objects.count() == 0
    assert QuarterReading.objects.count() == 0
    assert HourAggregate.objects.count() == 0
