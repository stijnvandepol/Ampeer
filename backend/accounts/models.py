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
