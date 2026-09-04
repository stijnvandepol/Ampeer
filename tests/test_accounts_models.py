"""What an account is, and what it deliberately is not."""

from __future__ import annotations

import pytest
from django.db.utils import IntegrityError

from accounts.models import User


@pytest.mark.django_db
def test_an_email_address_is_stored_in_lower_case() -> None:
    """`BaseUserManager.normalize_email` lowers only the domain.

    With the local part left as typed, `A@voorbeeld.nl` and `a@voorbeeld.nl` are
    two accounts and, in accounts/lockout.py, two lockout keys, so five failed
    attempts against one address count as five against two. That halves the
    brute force defence without anybody seeing it happen.
    """
    user = User.objects.create_user(email="Iemand@Voorbeeld.NL", password="een-lang-wachtwoord")
    assert user.email == "iemand@voorbeeld.nl"


@pytest.mark.django_db
def test_the_same_address_in_other_capitals_is_not_a_second_account() -> None:
    """The database constraint itself, not `save()` normalising the case away
    before either address reaches it.

    `create_user` lowers its input, and `User.save` now normalises on every
    write, so a version of this test that goes through `create_user`, plain
    `.create()`, or an existing instance's own `.save()` would stay green even
    with `Meta.constraints` deleted from accounts/models.py entirely, because
    the plain per-column `unique=True` already catches two identical,
    normalised strings by the time either one reaches Postgres.

    `bulk_create` is the one write path Django never routes through
    `Model.save()` at all: it writes the field values exactly as given, in one
    INSERT. That is what actually asks Postgres whether it enforces
    case-insensitive uniqueness on its own, and it is exactly the bypass the
    review that added this rewrite named. Proven by deleting the
    `UniqueConstraint(Lower("email"), ...)` from `Meta.constraints` locally and
    rerunning this test: it fails with "DID NOT RAISE <class
    'django.db.utils.IntegrityError'>", because with that constraint gone the
    only remaining index is the case-sensitive one on the raw column, and
    `iemand@voorbeeld.nl` and `IEMAND@VOORBEELD.NL` are different strings to
    it. See the fix report for the transcript.
    """
    User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    with pytest.raises(IntegrityError):
        User.objects.bulk_create(
            [User(email="IEMAND@VOORBEELD.NL", password="unused-in-this-test")]
        )


@pytest.mark.django_db
def test_the_password_is_never_stored_as_typed() -> None:
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    assert "een-lang-wachtwoord" not in user.password
    assert user.password.startswith("argon2$argon2id$"), (
        f"the stored hash begins {user.password[:24]!r}, which is not Argon2id"
    )
    assert user.check_password("een-lang-wachtwoord")


@pytest.mark.django_db
def test_the_string_form_of_a_user_never_carries_the_address() -> None:
    """A model's `__str__` ends up in exception text and in shell output, and
    `RedactedFormatter` in the settings drops messages precisely because nobody
    can predict which ones carry a secret. Not putting it there is cheaper."""
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")
    assert "voorbeeld" not in str(user)


def test_creating_a_user_without_an_email_address_is_refused() -> None:
    """The branch `create_user` takes before it ever reaches the database.

    Django's own `createsuperuser` management command calls `create_user` with
    whatever `USERNAME_FIELD` resolves to, and on a model with no username that
    is nothing unless this raises first. No `@pytest.mark.django_db`: the point
    is that this never gets as far as a query.
    """
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password="een-lang-wachtwoord")


def test_an_account_carries_no_name_and_no_username() -> None:
    """Django's default User forces three columns this product never fills, and
    two of them are called a name in a document that says there is no name."""
    fields = {field.name for field in User._meta.get_fields()}
    assert not fields & {"username", "first_name", "last_name"}, (
        f"the user model grew {sorted(fields & {'username', 'first_name', 'last_name'})}"
    )
