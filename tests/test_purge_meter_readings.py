"""Folding quarter readings into hours under a fixed clock.

There is no `freeze` helper in this repository, so every row below is written
with `measured_at` set explicitly far in the past rather than backdated
through a frozen `timezone.now()`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from helpers.accounts import TEST_PASSWORD

from accounts.management.commands.purge_meter_readings import RETENTION
from accounts.models import HourAggregate, MeterLink, QuarterReading, User
from advice.models import AuditEvent

pytestmark = pytest.mark.django_db

NOW = timezone.now()
OLD_HOUR = (NOW - RETENTION - timedelta(days=5)).replace(minute=0, second=0, microsecond=0)
RECENT_MOMENT = NOW - timedelta(days=89)


def _link(email: str = "iemand@voorbeeld.nl") -> MeterLink:
    user = User.objects.create_user(email=email, password=TEST_PASSWORD)
    return MeterLink.objects.create(user=user, token_sha256=f"digest-for-{email}")


def _reading(link: MeterLink, moment: datetime, consumption: float = 0.2) -> QuarterReading:
    return QuarterReading.objects.create(
        link=link, measured_at=moment, consumption_kwh=consumption, feed_in_kwh=0.0
    )


def test_four_old_quarters_in_one_hour_become_one_aggregate() -> None:
    """Red proof: make the command not delete the folded quarters."""
    link = _link()
    for minute in (0, 15, 30, 45):
        _reading(link, OLD_HOUR + timedelta(minutes=minute), consumption=0.1)

    call_command("purge_meter_readings")

    assert QuarterReading.objects.filter(link=link).count() == 0
    aggregate = HourAggregate.objects.get(link=link, hour_start=OLD_HOUR)
    assert aggregate.quarters == 4
    assert aggregate.consumption_kwh == pytest.approx(0.4)


def test_a_reading_eighty_nine_days_old_is_left_alone() -> None:
    """Red proof: set `RETENTION` to `timedelta(days=1)`."""
    link = _link()
    _reading(link, RECENT_MOMENT)

    call_command("purge_meter_readings")

    assert QuarterReading.objects.filter(link=link).count() == 1
    assert HourAggregate.objects.filter(link=link).count() == 0


def test_two_old_quarters_in_one_hour_sum_into_one_aggregate_with_two_quarters() -> None:
    """Red proof: hardcode `quarters` at 4 instead of counting the group."""
    link = _link()
    _reading(link, OLD_HOUR, consumption=0.1)
    _reading(link, OLD_HOUR + timedelta(minutes=15), consumption=0.3)

    call_command("purge_meter_readings")

    aggregate = HourAggregate.objects.get(link=link, hour_start=OLD_HOUR)
    assert aggregate.quarters == 2
    assert aggregate.consumption_kwh == pytest.approx(0.4)


def test_a_second_run_over_an_already_folded_hour_adds_rather_than_collides() -> None:
    """A quarter that arrives late for an hour already folded once.

    The first run folds two quarters into an hour. Before the second run, a
    third quarter for that same old hour appears, exactly what a device that
    buffers and retries after an outage would still produce. The second run
    has to add to the existing aggregate, not collide with it.

    Red proof: use `create` in `_fold_link` instead of `update_or_create` and
    the second run raises `IntegrityError` on the unique `(link, hour_start)`
    constraint instead of growing the row to three quarters.
    """
    link = _link()
    _reading(link, OLD_HOUR, consumption=0.1)
    _reading(link, OLD_HOUR + timedelta(minutes=15), consumption=0.3)
    call_command("purge_meter_readings")

    _reading(link, OLD_HOUR + timedelta(minutes=30), consumption=0.2)
    call_command("purge_meter_readings")

    assert HourAggregate.objects.filter(link=link, hour_start=OLD_HOUR).count() == 1
    aggregate = HourAggregate.objects.get(link=link, hour_start=OLD_HOUR)
    assert aggregate.quarters == 3
    assert aggregate.consumption_kwh == pytest.approx(0.6)


def test_two_links_old_quarters_never_mix() -> None:
    """Red proof: group all links' quarters into one aggregation pass keyed
    only on hour_start."""
    link_a = _link("a@voorbeeld.nl")
    link_b = _link("b@voorbeeld.nl")
    _reading(link_a, OLD_HOUR, consumption=0.1)
    _reading(link_b, OLD_HOUR, consumption=0.9)

    call_command("purge_meter_readings")

    assert HourAggregate.objects.get(link=link_a, hour_start=OLD_HOUR).consumption_kwh == 0.1
    assert HourAggregate.objects.get(link=link_b, hour_start=OLD_HOUR).consumption_kwh == 0.9


def test_check_is_clean_on_an_empty_tree_and_red_with_old_quarters() -> None:
    """Red proof: make `--check` always exit 0."""
    call_command("purge_meter_readings", check=True)

    link = _link()
    _reading(link, OLD_HOUR)
    with pytest.raises(CommandError):
        call_command("purge_meter_readings", check=True)


def test_check_folds_nothing() -> None:
    """Red proof: let `--check` call `_fold` before reporting."""
    link = _link()
    _reading(link, OLD_HOUR)

    before = QuarterReading.objects.filter(link=link).count()
    with pytest.raises(CommandError):
        call_command("purge_meter_readings", check=True)
    after = QuarterReading.objects.filter(link=link).count()

    assert before == after == 1


def test_the_command_writes_no_audit_event() -> None:
    """Red proof: add an `AuditEvent.record(...)` call to the command and this
    fails on the count."""
    link = _link()
    for minute in (0, 15, 30, 45):
        _reading(link, OLD_HOUR + timedelta(minutes=minute))

    call_command("purge_meter_readings")

    assert AuditEvent.objects.count() == 0
