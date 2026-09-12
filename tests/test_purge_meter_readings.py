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
from django.db import connection
from django.test.utils import CaptureQueriesContext
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


@pytest.mark.parametrize("cap", ["0", "-1"])
def test_a_cap_below_one_is_refused_rather_than_quietly_folding_nothing(cap: str) -> None:
    """The same silent outage send_outbound_mail's own cap could be.

    A cap below one walks no links, writes "folded 0 quarter reading(s) into 0
    hour aggregate(s)" and exits zero, so a timer installed with that flag
    looks healthy while quarter readings outlive the ninety days
    docs/dpia.md promises they do not. The retention promise is the one thing
    this command exists for, so a way to switch it off without saying so is
    worth a refusal.

    Red proof: delete the `options["max"] < 1` guard in `handle` and both
    cases pass with the old quarter still in the table.
    """
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    link = MeterLink.objects.create(user=user, token_sha256="a" * 64)
    _reading(link, OLD_HOUR)

    with pytest.raises(CommandError, match="would fold nothing"):
        call_command("purge_meter_readings", "--max", cap)

    assert QuarterReading.objects.count() == 1
    assert HourAggregate.objects.count() == 0


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


def test_folding_does_not_ask_the_database_once_per_hour() -> None:
    """The guard on the shape of the fold, not on its speed.

    Asserting a duration would measure the machine. This measures what the
    code does: one link with eight times the hours must cost the same number
    of queries, because the fold reads every hour it touches at once and
    writes the new and the changed ones in one statement each.

    It is worth a test because the per-hour version was invisible under a
    nightly timer, which folds twenty-four hours, and expensive exactly once:
    on the first run after a timer installed late, where one link can hold
    ninety days, and a run takes up to two hundred links.
    """
    old = timezone.now() - RETENTION - timedelta(days=1)

    few = _link("weinig@voorbeeld.nl")
    for hour in range(3):
        _reading(few, old - timedelta(hours=hour))
    with CaptureQueriesContext(connection) as small:
        call_command("purge_meter_readings")

    many = _link("veel@voorbeeld.nl")
    for hour in range(24):
        _reading(many, old - timedelta(hours=hour))
    with CaptureQueriesContext(connection) as large:
        call_command("purge_meter_readings")

    assert HourAggregate.objects.filter(link=few).count() == 3
    assert HourAggregate.objects.filter(link=many).count() == 24
    assert len(large) == len(small), (
        f"twenty-four hours cost {len(large)} queries and three cost "
        f"{len(small)}; the fold is asking per hour again"
    )
