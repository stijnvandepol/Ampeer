"""The three tables, and the two promises made about them.

A stored advice must hold nothing that identifies a person, and an audit log
must not be quietly rewritable. Neither is enforced by the database, so both are
enforced here.
"""

from __future__ import annotations

import re
from datetime import timedelta

# `advice` lives under backend/ rather than at the repository root, so from a
# test file ruff's isort classifies it as third party and sorts it into this
# block. Ordered the way the linter orders it rather than the way it reads.
import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone

from advice.models import AuditEvent, ProductionCache, StoredAdvice

pytestmark = pytest.mark.django_db

INPUTS = {"postcode4": "5401", "peak_power_wp": 3500, "annual_consumption_kwh": 3500}
ADVICE = {"confidence": "INDICATIVE", "headline": {"p50": "700.08"}}


def test_a_stored_advice_gets_an_unguessable_token() -> None:
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert len(stored.token) == 22, stored.token
    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", stored.token)


def test_two_stored_advices_never_share_a_token() -> None:
    first = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    second = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert first.token != second.token


def test_a_stored_advice_expires_ninety_days_after_it_was_made() -> None:
    """Ninety days is the retention promise in CLAUDE.md and in section 5 of the
    design. The model must read it from the setting rather than carry its own
    copy, and the setting must still say ninety."""
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert stored.expires_at - stored.created_at == timedelta(days=90)
    assert stored.expires_at - stored.created_at == timedelta(days=settings.AMPEER_ADVICE_TTL_DAYS)


def test_a_live_token_is_found_and_an_unknown_one_is_not() -> None:
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    assert StoredAdvice.get_live(stored.token) == stored
    assert StoredAdvice.get_live("nope-nope-nope-nope-no") is None


def test_an_expired_advice_is_gone_rather_than_stale() -> None:
    """Returning old content past its retention date is the worse failure of
    the two: nobody finds out, and the record was supposed to be deleted."""
    stored = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    StoredAdvice.objects.filter(pk=stored.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert StoredAdvice.get_live(stored.token) is None


def test_the_stored_record_holds_no_field_that_could_identify_a_person() -> None:
    """Quarter-hour energy data says when somebody is home. The four digit
    postcode is the deliberate limit; a fifth character, a name or an address
    would change what this table is."""
    forbidden = {
        "name",
        "naam",
        "email",
        "e_mail",
        "phone",
        "telefoon",
        "address",
        "adres",
        "ip",
    }
    field_names = {field.name for field in StoredAdvice._meta.get_fields()}
    assert not field_names & forbidden, sorted(field_names & forbidden)
    assert "postcode" not in field_names, "only postcode4 belongs here, and only inside inputs"


def test_the_purge_command_deletes_only_what_has_expired() -> None:
    live = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    dead = StoredAdvice.create(inputs=INPUTS, advice=ADVICE)
    StoredAdvice.objects.filter(pk=dead.pk).update(expires_at=timezone.now() - timedelta(days=1))
    call_command("purge_expired_advice")
    assert list(StoredAdvice.objects.values_list("pk", flat=True)) == [live.pk]


def test_an_audit_event_records_what_happened() -> None:
    event = AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc", postcode4="5401")
    assert event.event_type == "ADVICE_GENERATED"
    assert event.context == {"token": "abc", "postcode4": "5401"}
    assert event.occurred_at is not None


def test_an_audit_event_cannot_be_changed_after_the_fact() -> None:
    event = AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc")
    event.context = {"token": "rewritten"}
    with pytest.raises(ValueError, match="append-only"):
        event.save()


def test_an_audit_event_cannot_be_deleted() -> None:
    event = AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc")
    with pytest.raises(ValueError, match="append-only"):
        event.delete()


def test_an_audit_log_cannot_be_wiped_through_a_queryset() -> None:
    """The instance methods are the obvious guard and the useless one.
    `AuditEvent.objects.filter(...).delete()` never touches them, and that is
    the call somebody actually reaches for."""
    AuditEvent.record(AuditEvent.ADVICE_GENERATED, token="abc")
    with pytest.raises(ValueError, match="append-only"), transaction.atomic():
        AuditEvent.objects.all().delete()
    with pytest.raises(ValueError, match="append-only"), transaction.atomic():
        AuditEvent.objects.all().update(event_type="X")
    assert AuditEvent.objects.count() == 1


def test_the_audit_log_holds_no_ip_address() -> None:
    """An audit log is a record of what the service did, not of who visited."""
    field_names = {field.name for field in AuditEvent._meta.get_fields()}
    assert "ip" not in field_names and "ip_address" not in field_names


def test_a_production_cache_row_is_unique_per_roof_and_year() -> None:
    ProductionCache.objects.create(
        postcode4="5401",
        azimuth_deg=0,
        tilt_deg=35,
        weather_year=2023,
        production_w_per_kwp=b"a",
        temperature_c=b"b",
        source="PVGIS",
    )
    with pytest.raises(IntegrityError):
        ProductionCache.objects.create(
            postcode4="5401",
            azimuth_deg=0,
            tilt_deg=35,
            weather_year=2023,
            production_w_per_kwp=b"c",
            temperature_c=b"d",
            source="PVGIS",
        )
