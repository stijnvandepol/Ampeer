"""The account, and nothing that is not needed to be one.

`backend/advice/models.py` opens by saying that none of its tables holds a
personal detail, and docs/dpia.md chapter 2 leans on that sentence. This file
is where that stops being true, which is exactly why it is a separate file: one
promise per module stays checkable, where a longer exception would not.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


def _normalize_email(email: str) -> str:
    """Lower-cased in full, in the one place every write path calls.

    `BaseUserManager.normalize_email` lowers only the domain, so the local
    part is lowered here too: without that, `A@voorbeeld.nl` and
    `a@voorbeeld.nl` would still be two different strings reaching the
    database, and two different lockout keys in accounts/lockout.py.
    """
    return BaseUserManager.normalize_email(email).strip().lower()


class UserManager(BaseUserManager["User"]):
    """The only way an account is made through the manager, but not the only
    way a row is written. See `User.save` below for the other one."""

    def create_user(self, email: str, password: str) -> User:
        if not email:
            raise ValueError("an account needs an email address")
        user = self.model(email=_normalize_email(email))
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """One household's identity, and the whole of it.

    No username, no first name, no last name and no postcode. The postcode stays
    where it belongs, in `StoredAdvice.inputs`, on four digits, refused rather
    than truncated. `PermissionsMixin` is absent on purpose: there is no admin
    and there are no roles, so its two join tables would hold nothing.
    """

    email = models.EmailField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    #: Not `auto_now_add`, for the same reason `StoredAdvice.created_at` is not.
    date_joined = models.DateTimeField(default=timezone.now, editable=False)

    #: When the address was confirmed as this person's, by a confirmation
    #: link or by a completed password reset. A timestamp and not a flag,
    #: because "when" is the question a privacy document asks and a flag
    #: cannot answer it. Null means never, which is true of every account
    #: made before this column existed. Nothing in phase 1 reads it; phase 2
    #: requires it before a meter is linked, and that is the only place it
    #: blocks anything.
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects = UserManager()

    class Meta:
        #: The property `create_user` and `save` below only ever *try* to
        #: uphold: this is what Postgres itself refuses. `unique=True` on the
        #: field above is a case-sensitive index and would let
        #: `iemand@voorbeeld.nl` and `IEMAND@VOORBEELD.NL` both exist as rows,
        #: which is two lockout keys for one account and, per
        #: ModelBackend.get_by_natural_key's exact match, an address that can
        #: no longer log in. `User.objects.create()`, a queryset `.update()`,
        #: `bulk_create`, and any serializer that assigns `email` onto an
        #: existing instance all reach the database without going through
        #: `create_user`, so this has to be enforced here and not only there.
        #: Kept in the first migration rather than a later one: this
        #: constraint is a migration that cannot run once two such rows
        #: already exist, and the model must never say something the schema
        #: has not always said.
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_lower_unique"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Normalise on every write, not only the one `create_user` makes.

        The database constraint in `Meta.constraints` is what actually stops
        two case variants from coexisting; this is what keeps the common path
        (`User.objects.create()`, an existing instance's own `.save()`) from
        ever reaching that constraint with mixed case in the first place.
        `bulk_create` and a queryset `.update()` still bypass this, which is
        exactly why the database constraint above is the one that has to hold
        regardless.
        """
        if self.email:
            self.email = _normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Deliberately not the address. A `__str__` reaches exception text and
        shell output, and neither is a place this project writes an address."""
        return f"user {self.pk}"


class Consent(models.Model):
    """One thing a household said yes or no to, and when.

    An event table rather than two nullable datetime columns on `User`. A column
    that can be filled twice cannot say what happened in between, and withdrawing
    and granting again is exactly the sequence a consent record has to survive.

    Deliberately not append-only in the `AuditEvent` sense: a row here is deleted
    when the account is, through CASCADE. Once there is nobody left to process
    data about, there is nothing left to demonstrate consent for, and the audit
    log keeps the fact that the consent existed.
    """

    METER_LINK = "METER_LINK"
    LEAD_GENERATION = "LEAD_GENERATION"
    KINDS: ClassVar[frozenset[str]] = frozenset({METER_LINK, LEAD_GENERATION})

    GRANTED = "GRANTED"
    WITHDRAWN = "WITHDRAWN"
    ACTIONS: ClassVar[frozenset[str]] = frozenset({GRANTED, WITHDRAWN})

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=32, db_index=True)
    action = models.CharField(max_length=16)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    #: Which wording was accepted. See accounts/nl.py.
    text_version = models.CharField(max_length=32)

    class Meta:
        ordering: ClassVar[list[str]] = ["-occurred_at", "-id"]

    @classmethod
    def record(cls, user: User, kind: str, action: str) -> Consent:
        """Write one row. A refusal writes nothing at all, which is why there is
        no third action: absence is what never granted looks like."""
        if kind not in cls.KINDS:
            raise ValueError(f"unknown consent kind: {kind}")
        if action not in cls.ACTIONS:
            raise ValueError(f"unknown consent action: {action}")
        from accounts.nl import CONSENT_TEXT_VERSION

        return cls.objects.create(
            user=user, kind=kind, action=action, text_version=CONSENT_TEXT_VERSION
        )

    @classmethod
    def current(cls, user: User, kind: str) -> bool:
        """The latest word on one kind. No row means never granted.

        Ordered by `occurred_at` and then by `id`, because two rows written in
        the same request can share a timestamp to the microsecond and then the
        order would be whatever the database felt like.
        """
        latest = cls.objects.filter(user=user, kind=kind).order_by("-occurred_at", "-id").first()
        return latest is not None and latest.action == cls.GRANTED


class RefreshSession(models.Model):
    """One refresh token's life, without the token and without its identifier.

    simplejwt's own rotation needs the `token_blacklist` app, and that app writes
    the whole refresh JWT into `OutstandingToken.token`. That is a working
    credential in a column, which CLAUDE.md forbids and which docs/dpia.md
    chapter 2 already refused for the advice token in the same words: the token
    is not a reference to the record, it is the only key that opens it.

    `rotated_at` is what makes reuse visible. A token that was exchanged and is
    offered again is the one reliable sign that somebody else has a copy, and the
    answer to it is to end every session this account has, not only this one.
    """

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="refresh_sessions"
    )
    jti_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-issued_at"]

    @property
    def is_spent(self) -> bool:
        return self.rotated_at is not None or self.revoked_at is not None


class OneTimeToken(models.Model):
    """One link that works once, without the link.

    The same shape as `RefreshSession` above, for a second vocabulary: the
    row holds the sha256 of the token and never the token, so a copy of this
    table hands nobody a working link. `token_digest` is the same unsalted
    sha256 the advice token and the refresh session use, with the same
    argument: the input is 256 bits from `secrets.token_urlsafe`, so there
    is no dictionary to run and no salt that adds anything.

    Why not `django.contrib.auth.tokens.PasswordResetTokenGenerator`, which
    decision 31 pointed at: it hashes `last_login` into the token, so a
    confirmation link would die the moment the new account signs in, and it
    has no notion of "spent", so a reset link would stay valid until the
    password changed. `spent_at` answers that in one column.
    """

    #: B105 matches this constant's name, not a credential: the value is a token kind.
    PASSWORD_RESET = "PASSWORD_RESET"  # nosec B105
    EMAIL_VERIFY = "EMAIL_VERIFY"
    KINDS: ClassVar[frozenset[str]] = frozenset({PASSWORD_RESET, EMAIL_VERIFY})

    #: One hour for a link that sets a password, seven days for a link that
    #: confirms a fact about an address. Counted from `issued_at`, which is
    #: the moment of sending and not the moment of asking.
    LIFETIMES: ClassVar[dict[str, timedelta]] = {
        PASSWORD_RESET: timedelta(hours=1),
        EMAIL_VERIFY: timedelta(days=7),
    }

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="one_time_tokens"
    )
    kind = models.CharField(max_length=16, db_index=True)
    token_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)
    spent_at = models.DateTimeField(null=True, blank=True)
    #: Set on every older unspent token of the same kind when a new one is
    #: minted, so a person has at most one usable link per kind at a time.
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-issued_at"]

    @property
    def is_usable(self) -> bool:
        """The one question the three routes that read a token ask."""
        return (
            self.spent_at is None
            and self.superseded_at is None
            and self.expires_at > timezone.now()
        )


class OutboundMail(models.Model):
    """One message waiting to leave, described by what it is and not by what it says.

    No address (it is on `User`, read at the moment of sending), no subject,
    no body and no token: the token does not exist yet when this row is
    written, because it is minted by the command that sends the mail, so the
    only two places a raw token ever is are that command's memory and the
    mail itself. `tests/test_dpia.py` keeps asserting that no table has an
    address column, and this table keeps that true.

    CASCADE, so an account deleted before its mail left takes the row with
    it: nothing goes out to an address that no longer belongs to an account.
    """

    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="outbound_mails"
    )
    kind = models.CharField(max_length=16, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    #: From when the command may pick this row up again. Now on creation,
    #: later after a failed attempt.
    next_attempt_at = models.DateTimeField(db_index=True)
    #: The HTTP status of the last attempt, 0 for no answer at all.
    last_status = models.PositiveSmallIntegerField(null=True, blank=True)
    #: When the command gave up. A row with this set is never retried and is
    #: removed seven days later by `purge_expired_sessions`.
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["id"]


class MeterLink(models.Model):
    """One household's authorisation for its own meter to push readings in.

    The same shape as `RefreshSession` and `OneTimeToken` above, and for the
    same reason: `token_sha256` is what this table can hand anybody, the raw
    key exists only in the request that mints it and in the answer to that
    request, and is never written down again.

    No EAN, no meter number and no address. Ampeer does not need one to attach
    a series of numbers to an account, and an identifying detail that serves
    no purpose is a detail that should not be collected in the first place;
    docs/dpia.md chapter 3 makes the same call about the postcode.

    One row per account is active at a time. A second `link_meter` call
    revokes whatever came before it in the same transaction, which is also
    what a household expects "koppel opnieuw" to do; see `service.link_meter`.
    """

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="meter_links")
    token_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    #: The one thing a household sees on its account page about this link.
    #: Set on every accepted push and nowhere else, so it answers exactly the
    #: question "did anything arrive" and nothing more.
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering: ClassVar[list[str]] = ["-created_at", "-id"]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    @classmethod
    def active_for(cls, user: User) -> MeterLink | None:
        """The one active link this account has, or `None`.

        Filtered on `user` and on `revoked_at`, never on a bare primary key: a
        link is only ever reached through the account it belongs to. `Meta.ordering`
        already puts the newest row first, and "one active link per account" is
        the rule that makes it the only one this filter could return.
        """
        return cls.objects.filter(user=user, revoked_at__isnull=True).first()


class QuarterReading(models.Model):
    """One quarter hour of consumption and feed-in, pushed by a household's own device.

    Two floats and not two `Decimal`: this is energy, not money, and it carries
    the same percent-level uncertainty every meter reading in this project
    does. The euro conversion happens at the edge of the simulation kernel and
    nowhere near this table.

    `(link, measured_at)` is unique so a device replaying its buffer after an
    outage never writes the same quarter twice; `accounts.meter.store_readings`
    relies on that constraint to make the push idempotent.
    """

    link = models.ForeignKey(
        "accounts.MeterLink", on_delete=models.CASCADE, related_name="quarter_readings"
    )
    measured_at = models.DateTimeField(db_index=True)
    consumption_kwh = models.FloatField()
    feed_in_kwh = models.FloatField()

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["link", "measured_at"],
                name="accounts_quarterreading_link_moment_unique",
            )
        ]
        ordering: ClassVar[list[str]] = ["measured_at"]


class HourAggregate(models.Model):
    """What a quarter hour becomes once it is older than the retention window.

    `quarters` records how many of the four quarters that made up this hour
    actually arrived. An hour with fewer than four is kept as what it is
    rather than discarded: a partial truth is still a truth, and
    `purge_meter_readings` never invents the missing quarters to make it four.
    """

    link = models.ForeignKey(
        "accounts.MeterLink", on_delete=models.CASCADE, related_name="hour_aggregates"
    )
    hour_start = models.DateTimeField(db_index=True)
    consumption_kwh = models.FloatField()
    feed_in_kwh = models.FloatField()
    quarters = models.PositiveSmallIntegerField()

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["link", "hour_start"], name="accounts_houraggregate_link_hour_unique"
            )
        ]
        ordering: ClassVar[list[str]] = ["hour_start"]
