"""The account, and nothing that is not needed to be one.

`backend/advice/models.py` opens by saying that none of its tables holds a
personal detail, and docs/dpia.md chapter 2 leans on that sentence. This file
is where that stops being true, which is exactly why it is a separate file: one
promise per module stays checkable, where a longer exception would not.
"""

from __future__ import annotations

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
