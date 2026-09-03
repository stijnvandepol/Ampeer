"""The three tables the advice API keeps.

None of them holds a personal detail. `StoredAdvice.inputs` holds the answers a
visitor gave, and the serializer that produces it accepts a four digit postcode
and nothing longer, so there is no address in here and no way to put one in.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any, ClassVar, Self

from django.conf import settings
from django.db import models
from django.utils import timezone

#: 16 random bytes rendered as 22 url-safe characters. At 128 bits a collision
#: is not something to write a retry loop for, and the unique constraint below
#: turns the impossible case into an error rather than an overwrite.
TOKEN_BYTES = 16


def token_digest(token: str) -> str:
    """The form of a token that may be written down somewhere permanent.

    Unsalted and unstretched on purpose, and that is safe here for a reason
    that would not hold for a password: the input is 128 bits from
    secrets.token_urlsafe, so there is no dictionary to run and no rainbow
    table to build. A salt would only break the one property this is for, which
    is that the same token always produces the same digest and a line stays
    findable by whoever legitimately holds the link.
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class StoredAdvice(models.Model):
    """One computed advice, retrievable by its token until it expires."""

    token = models.CharField(max_length=32, unique=True, db_index=True)
    #: Not auto_now_add. auto_now_add stamps a second, later clock reading, so
    #: expires_at - created_at came out a few hundred microseconds short of the
    #: retention window and the test for it passed or failed by luck. One clock
    #: reading fills both columns, and the retention promise is then exact and
    #: provable from the row itself rather than approximately true.
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    #: The validated answers, so the advice can be recomputed and defended.
    inputs = models.JSONField()
    #: The rendered advice, including engine_version and advice_version.
    advice = models.JSONField()

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at"]

    @classmethod
    def create(cls, inputs: dict[str, Any], advice: dict[str, Any]) -> Self:
        """Store one advice. The retention window is read from the setting and
        never carried here as a literal, so there is one place that decides how
        long a record about a household's day survives."""
        now = timezone.now()
        return cls.objects.create(
            token=secrets.token_urlsafe(TOKEN_BYTES),
            created_at=now,
            expires_at=now + timedelta(days=settings.AMPEER_ADVICE_TTL_DAYS),
            inputs=inputs,
            advice=advice,
        )

    @classmethod
    def get_live(cls, token: str) -> Self | None:
        """Return the advice for this token, or None if it never existed or has
        expired. Both cases answer the same way on purpose: telling a caller
        that a token used to exist is telling them something."""
        return cls.objects.filter(token=token, expires_at__gt=timezone.now()).first()


class AppendOnlyQuerySet(models.QuerySet["AuditEvent"]):
    """The instance guards below are the obvious half and the weaker half.

    `AuditEvent.objects.filter(...).delete()` never calls `Model.delete`, and
    that is the call a developer reaches for when a table is in the way.
    """

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValueError("the audit log is append-only: rows cannot be deleted")

    def update(self, **kwargs: Any) -> int:
        raise ValueError("the audit log is append-only: rows cannot be updated")


class AuditEvent(models.Model):
    """One line in the append-only log.

    Append-only is enforced in Python, not in the database. That is not a
    defence against anyone with a database connection and it is not meant to be.
    It is a defence against the ordinary way an audit log dies, which is a later
    developer running update_or_create over it without thinking about it.
    """

    ADVICE_GENERATED = "ADVICE_GENERATED"

    event_type = models.CharField(max_length=64, db_index=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    #: Context without a personal detail: the token and the four digit
    #: postcode, never the IP address of the visitor.
    context = models.JSONField(default=dict)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering: ClassVar[list[str]] = ["-occurred_at"]

    @classmethod
    def record(cls, event_type: str, **context: object) -> AuditEvent:
        return cls.objects.create(event_type=event_type, context=dict(context))

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None:
            raise ValueError("the audit log is append-only: rows cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValueError("the audit log is append-only: rows cannot be deleted")


class ProductionCache(models.Model):
    """One PVGIS answer, kept so a visitor never waits for an external service.

    The orientation columns are whole degrees and integers. A float key would
    miss its own entry on 35.000000001, and a rounded lookup against a float key
    would hand back a series computed for a different roof than the simulation
    then assumes. Rounding happens once, in the serializer.

    There is no expiry, and there is a sweep, which are two different things.
    PVGIS data about a closed weather year does not change, so no row here is
    ever wrong for being old and nothing about a read depends on `fetched_at`.
    What the column is for is bounding a table that otherwise only grows:
    `purge_expired_advice` drops rows past PRODUCTION_CACHE_MAX_AGE_DAYS and
    argues the age there. Until 2026-09-01 nothing read the column at all.
    """

    #: Two digits, not four, and named so nobody reads it as a postcode4. The
    #: location this row describes is a postcode century, because that is the
    #: resolution the data has: ampeer_sim's postcode4_to_latlon looks up
    #: postcode4[:2] and every postcode in one century therefore produces a
    #: byte-identical series. Keyed on four digits, the cache stored that same
    #: 60 kB series once per neighbourhood, forever, and the hit rate was two
    #: orders of magnitude below what it should be. The coupling is not
    #: assumed: tests/test_advice_providers.py fails if a finer resolution ever
    #: reaches postcode4_to_latlon.
    postcode_area = models.CharField(max_length=2)
    azimuth_deg = models.SmallIntegerField()
    tilt_deg = models.SmallIntegerField()
    weather_year = models.SmallIntegerField()
    production_w_per_kwp = models.BinaryField()
    temperature_c = models.BinaryField()
    source = models.CharField(max_length=16)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["postcode_area", "azimuth_deg", "tilt_deg", "weather_year"],
                name="unique_production_cache_key",
            )
        ]


class DailyCounter(models.Model):
    """One number per day per named event, and nothing else.

    Phase 0 of this product exists, in CLAUDE.md's own words, to validate
    whether the question exists at all. Until 2026-09-02 nothing measured that:
    there was no analytics of any kind, so the phase could not answer its own
    question. This is the smallest thing that can.

    What makes it safe is the shape rather than a policy. A row is a date, a
    name out of a fixed list, and an integer. There is no visitor identifier,
    no session, no address, not even a hashed one, and no foreign key to an
    advice. Two visitors who do the same thing on the same day are the same
    increment, so there is nothing here to correlate and nothing to subject
    access. That is why this needs no consent banner under article 11.7a of the
    Telecommunicatiewet: it is not reading anything from the visitor's device.

    Deliberately NOT a time series at finer than a day. An hour column would
    make a single visitor visible on a quiet day, which is exactly the property
    this table is built not to have. Deliberately not purged either, for the
    same reason the audit log is not: an aggregate with no personal datum in it
    has nothing to expire.
    """

    #: The events this table will store. A name outside this list is refused
    #: rather than created, so a typo in the frontend cannot silently open a new
    #: column of behaviour, and nobody can widen what is collected by sending a
    #: different string. The funnel names are the four questions of round one
    #: plus the two ends, because per-question abandonment is the one number
    #: that says whether the form is the problem.
    FUNNEL_STARTED = "funnel_started"
    FUNNEL_QUESTION_1 = "funnel_question_1"
    FUNNEL_QUESTION_2 = "funnel_question_2"
    FUNNEL_QUESTION_3 = "funnel_question_3"
    FUNNEL_QUESTION_4 = "funnel_question_4"
    FUNNEL_SUBMITTED = "funnel_submitted"
    FUNNEL_REFINE_STARTED = "funnel_refine_started"
    FUNNEL_REFINE_SUBMITTED = "funnel_refine_submitted"

    #: Accepted from the browser. The outcome names below are NOT in here: they
    #: are recorded by the server when it computes an advice, so no caller can
    #: inflate the one distribution this product would be tempted to flatter.
    CLIENT_NAMES: ClassVar[frozenset[str]] = frozenset(
        {
            FUNNEL_STARTED,
            FUNNEL_QUESTION_1,
            FUNNEL_QUESTION_2,
            FUNNEL_QUESTION_3,
            FUNNEL_QUESTION_4,
            FUNNEL_SUBMITTED,
            FUNNEL_REFINE_STARTED,
            FUNNEL_REFINE_SUBMITTED,
        }
    )

    #: Written by the server only, from what it actually decided.
    ADVICE_GENERATED = "advice_generated"
    SERVER_PREFIXES: ClassVar[tuple[str, ...]] = ("verdict_", "confidence_", "route_")

    day = models.DateField()
    name = models.CharField(max_length=64)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["day", "name"], name="one_row_per_day_per_name")
        ]

    def __str__(self) -> str:
        return f"{self.day} {self.name}={self.count}"

    @classmethod
    def bump(cls, name: str) -> None:
        """Add one to today's row for `name`, creating it if it is the first.

        An upsert rather than a read followed by a write, because two workers
        counting the same event at the same moment must not lose one of them.
        `update_or_create` would do exactly that read-then-write; `F("count")
        + 1` is resolved by the database.
        """
        day = timezone.localdate()
        if cls.objects.filter(day=day, name=name).update(count=models.F("count") + 1):
            return
        # First event of the day for this name, or a race with another worker
        # doing the same. `get_or_create` alone is not enough: when it loses the
        # race it returns the row the winner created and increments nothing, so
        # one event would be dropped every time a day's first two arrived
        # together. Increment again when it did not create.
        _, created = cls.objects.get_or_create(day=day, name=name, defaults={"count": 1})
        if not created:
            cls.objects.filter(day=day, name=name).update(count=models.F("count") + 1)
