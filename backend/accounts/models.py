"""The account, and nothing that is not needed to be one.

`backend/advice/models.py` opens by saying that none of its tables holds a
personal detail, and docs/dpia.md chapter 2 leans on that sentence. This file
is where that stops being true, which is exactly why it is a separate file: one
promise per module stays checkable, where a longer exception would not.
"""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager["User"]):
    """The only way an account is made, so normalisation cannot be skipped."""

    def create_user(self, email: str, password: str) -> User:
        if not email:
            raise ValueError("an account needs an email address")
        user = self.model(email=self.normalize_email(email).strip().lower())
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

    def __str__(self) -> str:
        """Deliberately not the address. A `__str__` reaches exception text and
        shell output, and neither is a place this project writes an address."""
        return f"user {self.pk}"
