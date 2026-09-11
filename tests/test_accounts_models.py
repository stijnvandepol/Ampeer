"""What an account is, and what it deliberately is not."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db.utils import IntegrityError
from django.utils import timezone
from helpers.accounts import OTHER_PASSWORD, TEST_PASSWORD

from accounts import models as accounts_models
from accounts.models import OneTimeToken, OutboundMail, User
from advice.models import AuditEvent, token_digest


@pytest.mark.django_db
def test_an_email_address_is_stored_in_lower_case() -> None:
    """`BaseUserManager.normalize_email` lowers only the domain.

    With the local part left as typed, `A@voorbeeld.nl` and `a@voorbeeld.nl` are
    two accounts and, in accounts/lockout.py, two lockout keys, so five failed
    attempts against one address count as five against two. That halves the
    brute force defence without anybody seeing it happen.
    """
    user = User.objects.create_user(email="Iemand@Voorbeeld.NL", password=TEST_PASSWORD)
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
    User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    with pytest.raises(IntegrityError):
        User.objects.bulk_create(
            [User(email="IEMAND@VOORBEELD.NL", password="unused-in-this-test")]
        )


@pytest.mark.django_db
def test_the_password_is_never_stored_as_typed() -> None:
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    assert TEST_PASSWORD not in user.password
    assert user.password.startswith("argon2$argon2id$"), (
        f"the stored hash begins {user.password[:24]!r}, which is not Argon2id"
    )
    assert user.check_password(TEST_PASSWORD)


@pytest.mark.django_db
def test_the_string_form_of_a_user_never_carries_the_address() -> None:
    """A model's `__str__` ends up in exception text and in shell output, and
    `RedactedFormatter` in the settings drops messages precisely because nobody
    can predict which ones carry a secret. Not putting it there is cheaper."""
    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    assert "voorbeeld" not in str(user)


def test_creating_a_user_without_an_email_address_is_refused() -> None:
    """The branch `create_user` takes before it ever reaches the database.

    Django's own `createsuperuser` management command calls `create_user` with
    whatever `USERNAME_FIELD` resolves to, and on a model with no username that
    is nothing unless this raises first. No `@pytest.mark.django_db`: the point
    is that this never gets as far as a query.
    """
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", password=TEST_PASSWORD)


@pytest.mark.django_db
def test_saving_a_user_only_normalizes_an_email_that_is_actually_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `if self.email:` branch's false arm, proven by its effect and not
    only by the branch arc it closes: `BaseUserManager.normalize_email` is
    idempotent on an empty string, so a test that only checked
    `user.email == ""` stayed green even with the guard deleted, because
    normalising nothing looked exactly like normalising. This patches
    `_normalize_email` itself: never called when there is nothing to
    normalise, called once with the address when there is one."""
    calls: list[str] = []
    original = accounts_models._normalize_email

    def _spy(email: str) -> str:
        calls.append(email)
        return original(email)

    monkeypatch.setattr(accounts_models, "_normalize_email", _spy)

    empty = User(email="")
    empty.set_unusable_password()
    empty.save()
    assert calls == []
    assert empty.email == ""

    filled = User(email="Iemand@Voorbeeld.NL")
    filled.set_unusable_password()
    filled.save()
    assert calls == ["Iemand@Voorbeeld.NL"]
    assert filled.email == "iemand@voorbeeld.nl"


def test_an_account_carries_no_name_and_no_username() -> None:
    """Django's default User forces three columns this product never fills, and
    two of them are called a name in a document that says there is no name.

    The set also guards spec 4.1 and 11's other promise: no `PermissionsMixin`.
    `is_staff`, `is_superuser`, `groups` and `user_permissions` are what that
    mixin adds, and none of them belongs on a model with no admin and no
    Django session to be superuser inside.
    """
    forbidden = {
        "username",
        "first_name",
        "last_name",
        "is_staff",
        "is_superuser",
        "groups",
        "user_permissions",
    }
    fields = {field.name for field in User._meta.get_fields()}
    assert not fields & forbidden, f"the user model grew {sorted(fields & forbidden)}"


@pytest.mark.django_db
def test_a_session_stores_a_digest_and_never_the_identifier() -> None:
    """The same call `advice/service.py` makes about the advice token, and for
    the same reason: what is written down must not be what opens the door."""
    from accounts.models import RefreshSession
    from advice.models import token_digest

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    jti = "4f0b2c1d9e8a47f0b2c1d9e8a47f0b2c"
    session = RefreshSession.objects.create(
        user=user,
        jti_sha256=token_digest(jti),
        issued_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=14),
    )
    assert jti not in session.jti_sha256
    assert session.jti_sha256 == token_digest(jti)
    assert session.rotated_at is None and session.revoked_at is None


@pytest.mark.django_db
def test_the_purge_removes_only_what_has_expired() -> None:
    from django.core.management import call_command

    from accounts.models import RefreshSession

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    now = timezone.now()
    RefreshSession.objects.create(
        user=user, jti_sha256="a" * 64, issued_at=now, expires_at=now - timedelta(seconds=1)
    )
    live = RefreshSession.objects.create(
        user=user, jti_sha256="b" * 64, issued_at=now, expires_at=now + timedelta(days=1)
    )
    call_command("purge_expired_sessions")
    assert list(RefreshSession.objects.values_list("pk", flat=True)) == [live.pk]


@pytest.mark.django_db
def test_is_spent_is_true_once_either_timestamp_is_set() -> None:
    """The one property `tokens.py` (task 8) will read before rotating a token.

    Three branches, not one: a live row (neither timestamp set), a rotated row,
    and a revoked row. `rotated_at` and `revoked_at` are independent columns, so
    a test that only ever set one of the two would leave the other arm of the
    `or` unexercised.
    """
    from accounts.models import RefreshSession

    user = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    now = timezone.now()
    live = RefreshSession.objects.create(
        user=user, jti_sha256="a" * 64, issued_at=now, expires_at=now + timedelta(days=14)
    )
    rotated = RefreshSession.objects.create(
        user=user, jti_sha256="b" * 64, issued_at=now, expires_at=now + timedelta(days=14)
    )
    revoked = RefreshSession.objects.create(
        user=user, jti_sha256="c" * 64, issued_at=now, expires_at=now + timedelta(days=14)
    )
    rotated.rotated_at = now
    revoked.revoked_at = now

    assert live.is_spent is False
    assert rotated.is_spent is True
    assert revoked.is_spent is True


@pytest.mark.django_db
def test_presenting_a_rotated_token_is_the_signal_to_revoke_the_whole_chain() -> None:
    """The security property this model exists for, demonstrated at the model
    level, since the lookup-then-refuse-then-revoke flow itself is `tokens.py`
    in task 8 and does not exist yet.

    `rotated_at` already set is what a stolen, already-exchanged token looks
    like on reuse. The only correct response is to end every session the
    account holds, not only the one presented, because the row on offer no
    longer distinguishes the thief from the legitimate holder who rotated it.
    A second user's session must be untouched: this is a per-account response,
    not a global one.
    """
    from accounts.models import RefreshSession

    victim = User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)
    bystander = User.objects.create_user(email="ander@voorbeeld.nl", password=OTHER_PASSWORD)
    now = timezone.now()
    presented = RefreshSession.objects.create(
        user=victim,
        jti_sha256="d" * 64,
        issued_at=now,
        expires_at=now + timedelta(days=14),
        rotated_at=now,
    )
    other_session = RefreshSession.objects.create(
        user=victim, jti_sha256="e" * 64, issued_at=now, expires_at=now + timedelta(days=14)
    )
    unrelated = RefreshSession.objects.create(
        user=bystander, jti_sha256="f" * 64, issued_at=now, expires_at=now + timedelta(days=14)
    )

    # The refusal: a session whose rotated_at is already set is spent, and a
    # caller must not accept it as proof of identity.
    looked_up = RefreshSession.objects.get(jti_sha256=presented.jti_sha256)
    assert looked_up.is_spent is True

    # The response: revoke every row this account holds, not only the one that
    # was presented.
    revoked_at = timezone.now()
    RefreshSession.objects.filter(user=victim, revoked_at__isnull=True).update(
        revoked_at=revoked_at
    )

    other_session.refresh_from_db()
    unrelated.refresh_from_db()
    assert other_session.revoked_at == revoked_at, "the victim's other session must be revoked too"
    assert unrelated.revoked_at is None, "a different account's session must be left alone"


# ---------------------------------------------------------------------------
# The two recovery tables and the one new column, before any route exists.
#
# Asserted on the model and on the schema rather than through a request,
# because the properties below decide what a route may say later: a token
# that reads usable after it was spent is a token that opens something twice.
# ---------------------------------------------------------------------------


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)


@pytest.mark.django_db
def test_a_new_account_has_no_verified_address(_account: User) -> None:
    """Null means never confirmed, which is true of every account that exists
    before this cycle and of every account at the moment it is made."""
    assert _account.email_verified_at is None


@pytest.mark.django_db
def test_a_token_is_usable_until_spent_superseded_or_expired(_account: User) -> None:
    now = timezone.now()
    row = OneTimeToken.objects.create(
        user=_account,
        kind=OneTimeToken.PASSWORD_RESET,
        token_sha256=token_digest("een-ruw-token"),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert row.is_usable
    row.spent_at = now
    assert not row.is_usable
    row.spent_at = None
    row.superseded_at = now
    assert not row.is_usable
    row.superseded_at = None
    row.expires_at = now - timedelta(seconds=1)
    assert not row.is_usable


def test_the_two_lifetimes_are_one_hour_and_seven_days() -> None:
    """Spec 2.1. A reset link is a password; a confirmation link is a fact
    about an address that does not change. Read off the model so a later edit
    of either number shows up here and not only in a mail nobody rereads."""
    assert OneTimeToken.LIFETIMES[OneTimeToken.PASSWORD_RESET] == timedelta(hours=1)
    assert OneTimeToken.LIFETIMES[OneTimeToken.EMAIL_VERIFY] == timedelta(days=7)
    assert set(OneTimeToken.LIFETIMES) == OneTimeToken.KINDS


@pytest.mark.django_db
def test_an_outbox_row_starts_unsent_and_due_now(_account: User) -> None:
    before = timezone.now()
    row = OutboundMail.objects.create(
        user=_account, kind=OneTimeToken.EMAIL_VERIFY, next_attempt_at=before
    )
    assert row.attempts == 0
    assert row.failed_at is None
    assert row.last_status is None
    assert row.created_at >= before


@pytest.mark.django_db
def test_deleting_the_account_takes_its_tokens_and_its_outbox_rows(_account: User) -> None:
    """A mail to an address that no longer belongs to an account must not
    leave, and a token for a user who is gone must not be findable."""
    now = timezone.now()
    OneTimeToken.objects.create(
        user=_account,
        kind=OneTimeToken.EMAIL_VERIFY,
        token_sha256=token_digest("nog-een-token"),
        issued_at=now,
        expires_at=now + timedelta(days=7),
    )
    OutboundMail.objects.create(user=_account, kind=OneTimeToken.EMAIL_VERIFY, next_attempt_at=now)
    _account.delete()
    assert OneTimeToken.objects.count() == 0
    assert OutboundMail.objects.count() == 0


def test_the_audit_log_knows_the_four_new_handlings() -> None:
    """Every entry on AuditEvent is a handling that exists, and these four
    arrive with this cycle. tests/test_dpia.py binds the same four to
    docs/dpia.md chapter 2; this pins the constants' own spelling."""
    for name in (
        "PASSWORD_RESET_REQUESTED",
        "PASSWORD_RESET_COMPLETED",
        "EMAIL_VERIFIED",
        "MAIL_SENT",
    ):
        assert getattr(AuditEvent, name) == name


@pytest.mark.django_db
def test_the_migrations_describe_the_models_exactly() -> None:
    """`makemigrations --check` exits non-zero when a model has drifted from
    its migrations. Run here rather than remembered, because a model edit
    without a migration passes every other test in this suite and fails on
    the first deploy."""
    call_command("makemigrations", "accounts", "--check", "--dry-run", verbosity=0)
