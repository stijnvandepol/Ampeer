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

    There is no expiry. PVGIS data about a closed weather year does not change.
    `fetched_at` exists so a later cleanup remains possible.
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
