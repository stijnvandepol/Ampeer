"""The sweep of ProductionCache, which is the first thing that reads fetched_at.

The column has been on the model since the first migration, with a comment
saying it existed so a later cleanup remained possible. Nothing read it, so the
cleanup stayed possible and never happened, and a growing table with an unread
timestamp on it is a growing table.

Two properties, and the second matters as much as the first. Old rows go, and
nothing about this reaches --check. That mode reports one thing, the ninety day
retention promise in docs/dpia.md, and it exits non-zero on the host and in the
deploy. ProductionCache holds a postcode century and two roof angles and no
personal detail at all, so an unswept row here is a disk question. A deploy
turned red by housekeeping is a check somebody learns to ignore.

The retention tests for StoredAdvice and for the throttle counters stay in
tests/test_advice_models.py beside the models they are about.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from advice.management.commands.purge_expired_advice import PRODUCTION_CACHE_MAX_AGE_DAYS
from advice.models import ProductionCache, StoredAdvice

pytestmark = pytest.mark.django_db

INPUTS = {"postcode4": "5401", "peak_power_wp": 3500, "annual_consumption_kwh": 3500}
ADVICE = {"confidence": "INDICATIVE", "headline": {"p50": "700.08"}}


def _cached_roof(azimuth_deg: int, *, age_days: float) -> ProductionCache:
    """One cache row, backdated.

    fetched_at is auto_now_add, so it cannot be passed to create() and has to be
    written afterwards with an UPDATE. That is also the honest way to build the
    fixture: it is exactly how a row that has been sitting there since last year
    differs from one written this morning.
    """
    row = ProductionCache.objects.create(
        postcode_area="54",
        azimuth_deg=azimuth_deg,
        tilt_deg=35,
        weather_year=2023,
        production_w_per_kwp=b"production",
        temperature_c=b"temperature",
        source="PVGIS",
    )
    ProductionCache.objects.filter(pk=row.pk).update(
        fetched_at=timezone.now() - timedelta(days=age_days)
    )
    return row


def test_a_production_cache_row_past_its_age_is_deleted() -> None:
    """The table is bounded by advice/serializers.py and swept by this command.

    Those are two different jobs. Grouping the roof angles decides how many rows
    can ever exist, which is what keeps a stranger from holding a worker on a
    fresh PVGIS call forever. This decides how long one of them lives, which is
    only about the disk. Neither does the other's work.
    """
    old = _cached_roof(0, age_days=PRODUCTION_CACHE_MAX_AGE_DAYS + 1)
    recent = _cached_roof(45, age_days=PRODUCTION_CACHE_MAX_AGE_DAYS - 1)

    call_command("purge_expired_advice")

    remaining = set(ProductionCache.objects.values_list("pk", flat=True))
    assert remaining == {recent.pk}, f"{old.pk} survived and {recent.pk} should have"


def test_a_row_written_today_is_not_swept_by_the_daily_run() -> None:
    """The timer fires every day and this table's age is measured in months, so
    an ordinary run must leave an ordinary row alone. A sweep that emptied the
    cache daily would turn every first visitor of the day into a PVGIS call."""
    fresh = _cached_roof(0, age_days=0)
    call_command("purge_expired_advice")
    assert ProductionCache.objects.filter(pk=fresh.pk).exists()


def test_the_check_mode_stays_quiet_about_the_production_cache() -> None:
    """An ancient cache row is not a broken retention promise.

    --check exits non-zero on the host and in the deploy, and it says one thing:
    that the ninety day promise about StoredAdvice has stopped being kept. This
    row is a postcode century and two roof angles. If it could turn the check
    red, a deploy would fail over housekeeping and the check would stop being
    read.
    """
    ancient = _cached_roof(0, age_days=PRODUCTION_CACHE_MAX_AGE_DAYS * 10)
    StoredAdvice.create(inputs=INPUTS, advice=ADVICE)

    call_command("purge_expired_advice", "--check")

    assert ProductionCache.objects.filter(pk=ancient.pk).exists(), (
        "--check deleted something, and a check that repairs what it measures "
        "can never report a problem"
    )


def test_the_check_mode_still_fails_on_an_overdue_advice() -> None:
    """The guard on the test above: it has to be possible for --check to be red.

    Without this, `test_the_check_mode_stays_quiet_about_the_production_cache`
    would pass just as happily against a --check that could never fail at all.
    """
    stale = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    StoredAdvice.objects.filter(pk=stale.pk).update(expires_at=timezone.now() - timedelta(days=3))
    _cached_roof(0, age_days=PRODUCTION_CACHE_MAX_AGE_DAYS * 10)

    with pytest.raises(CommandError, match="not been purged"):
        call_command("purge_expired_advice", "--check")


def test_the_run_still_reports_the_two_tables_it_reported_before() -> None:
    """The output shape is read by a person looking at a container log, and the
    two lines that were there are unchanged. The third is added, not swapped
    in."""
    out = StringIO()
    _cached_roof(0, age_days=PRODUCTION_CACHE_MAX_AGE_DAYS + 1)
    call_command("purge_expired_advice", stdout=out)

    lines = out.getvalue().splitlines()
    expected = f"deleted 1 production cache row(s) past {PRODUCTION_CACHE_MAX_AGE_DAYS} day(s)"
    assert lines[0].endswith("expired advice(s)"), lines
    assert lines[1].endswith("expired throttle row(s)"), lines
    assert lines[2] == expected, lines
