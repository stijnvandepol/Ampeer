"""The one module that reaches api.resend.com, and the two that do not.

`requests.post` is patched at the call, never the network: what is asserted
is the exact request the transport builds, which is the whole of what a
reviewer can check about an outbound call without a key.
"""

from __future__ import annotations

import io
import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import requests
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone
from helpers.accounts import TEST_PASSWORD

from accounts import mailer, recovery
from accounts.models import OneTimeToken, OutboundMail, User
from accounts.nl import NL
from advice.models import AuditEvent, token_digest

COMMAND = (
    Path(__file__).resolve().parent.parent
    / "backend"
    / "accounts"
    / "management"
    / "commands"
    / "send_outbound_mail.py"
)

MESSAGE = mailer.Message(
    to="iemand@voorbeeld.nl",
    subject="Onderwerp",
    text="Tekst met een link.\n",
    idempotency_key="outbox-7",
)


def _answer(status: int, body: dict[str, Any] | None = None) -> mock.Mock:
    response = mock.Mock()
    response.status_code = status
    response.json.return_value = {} if body is None else body
    return response


def test_the_mailer_posts_one_literal_url_with_the_bearer_the_key_and_the_timeout() -> None:
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with mock.patch.object(requests, "post", return_value=_answer(200, {"id": "abc"})) as post:
        provider_id = transport.send(MESSAGE)
    assert provider_id == "abc"
    post.assert_called_once()
    args, kwargs = post.call_args
    assert args == (mailer.RESEND_ENDPOINT,)
    assert mailer.RESEND_ENDPOINT == "https://api.resend.com/emails"
    assert kwargs["timeout"] == mailer.TIMEOUT_SECONDS == 10
    assert kwargs["headers"] == {
        "Authorization": "Bearer sleutel",
        "Idempotency-Key": "outbox-7",
    }
    assert kwargs["json"] == {
        "from": "noreply@ampeer.nl",
        "to": ["iemand@voorbeeld.nl"],
        "subject": "Onderwerp",
        "text": "Tekst met een link.\n",
    }


@pytest.mark.parametrize("status", [429, 500, 401])
def test_a_refused_answer_is_a_transport_error_carrying_the_status(status: int) -> None:
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with (
        mock.patch.object(requests, "post", return_value=_answer(status)),
        pytest.raises(mailer.TransportError) as caught,
    ):
        transport.send(MESSAGE)
    assert caught.value.status == status


def test_no_answer_at_all_is_a_transport_error_with_status_zero() -> None:
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with (
        mock.patch.object(requests, "post", side_effect=requests.ConnectionError("down")),
        pytest.raises(mailer.TransportError) as caught,
    ):
        transport.send(MESSAGE)
    assert caught.value.status == 0


def test_a_success_without_an_id_is_refused_rather_than_logged_as_sent() -> None:
    """Resend answers `{"id": ...}` on 200. A 200 without it is not a delivery
    this command can point at afterwards, so it is not a delivery."""
    transport = mailer.ResendTransport(api_key="sleutel", sender="noreply@ampeer.nl")
    with (
        mock.patch.object(requests, "post", return_value=_answer(200, {})),
        pytest.raises(mailer.TransportError) as caught,
    ):
        transport.send(MESSAGE)
    assert caught.value.status == 200


def test_the_file_transport_writes_one_readable_file_per_message(tmp_path: Path) -> None:
    transport = mailer.FileTransport(tmp_path / "mail")
    provider_id = transport.send(MESSAGE)
    assert provider_id == "file-outbox-7"
    written = (tmp_path / "mail" / "outbox-7.txt").read_text(encoding="utf-8")
    assert written == "To: iemand@voorbeeld.nl\nSubject: Onderwerp\n\nTekst met een link.\n"


def test_the_memory_transport_keeps_what_it_was_handed() -> None:
    transport = mailer.MemoryTransport()
    assert transport.send(MESSAGE) == "memory-outbox-7"
    assert transport.sent == [MESSAGE]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("resend", mailer.ResendTransport),
        ("file", mailer.FileTransport),
        ("memory", mailer.MemoryTransport),
    ],
)
def test_the_setting_chooses_the_transport(name: str, expected: type[object]) -> None:
    with override_settings(
        AMPEER_MAIL_TRANSPORT=name, RESEND_API_KEY="sleutel", AMPEER_MAIL_FILE_DIR="/tmp/mail"
    ):
        assert isinstance(mailer.transport(), expected)


def test_an_unknown_transport_name_is_refused() -> None:
    with override_settings(AMPEER_MAIL_TRANSPORT="smtp"), pytest.raises(RuntimeError, match="smtp"):
        mailer.transport()


def test_the_test_suite_runs_on_the_memory_transport() -> None:
    """The suite never reaches the network, and this is the line that says so."""
    from django.conf import settings

    assert settings.AMPEER_MAIL_TRANSPORT == "memory"


def test_prod_settings_refuse_the_memory_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """A container on the memory transport would report every mail as sent
    and deliver none. prod.py refuses to import under it."""
    import importlib
    import sys

    for name in (
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "AMPEER_NEDU_PROFILE_PATH",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "AMPEER_MAIL_FROM",
        "AMPEER_SITE_ORIGIN",
    ):
        monkeypatch.setenv(name, "set")
    monkeypatch.setenv("DJANGO_NUM_PROXIES", "2")
    monkeypatch.setenv("AMPEER_MAIL_TRANSPORT", "memory")
    sys.modules.pop("ampeer.settings.prod", None)
    with pytest.raises(RuntimeError, match="memory"):
        importlib.import_module("ampeer.settings.prod")
    sys.modules.pop("ampeer.settings.prod", None)


def test_prod_settings_require_the_key_only_on_resend(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import sys

    for name in (
        "DJANGO_SECRET_KEY",
        "DJANGO_ALLOWED_HOSTS",
        "DJANGO_CORS_ALLOWED_ORIGINS",
        "AMPEER_NEDU_PROFILE_PATH",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "AMPEER_MAIL_FROM",
        "AMPEER_SITE_ORIGIN",
    ):
        monkeypatch.setenv(name, "set")
    monkeypatch.setenv("DJANGO_NUM_PROXIES", "2")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("AMPEER_MAIL_TRANSPORT", "resend")
    sys.modules.pop("ampeer.settings.prod", None)
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        importlib.import_module("ampeer.settings.prod")
    monkeypatch.setenv("AMPEER_MAIL_TRANSPORT", "file")
    sys.modules.pop("ampeer.settings.prod", None)
    module = importlib.import_module("ampeer.settings.prod")
    assert module.AMPEER_MAIL_TRANSPORT == "file"
    assert module.AMPEER_MAIL_FILE_DIR == "/srv/mail"
    sys.modules.pop("ampeer.settings.prod", None)


# ---------------------------------------------------------------------------
# The command that empties the outbox
# ---------------------------------------------------------------------------


def _run(*args: str) -> str:
    out = io.StringIO()
    call_command("send_outbound_mail", *args, stdout=out)
    return out.getvalue()


class _Failing:
    """A transport that answers one status, for every message."""

    def __init__(self, status: int) -> None:
        self.status = status
        self.attempts = 0

    def send(self, message: mailer.Message) -> str:
        self.attempts += 1
        raise mailer.TransportError(self.status)


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=TEST_PASSWORD)


@pytest.fixture(autouse=True)
def _empty_memory() -> None:
    mailer.MEMORY.sent.clear()


@pytest.mark.django_db
def test_the_command_mints_sends_deletes_and_logs(_account: User) -> None:
    recovery.request_password_reset(_account.email)
    before = timezone.now()
    output = _run()
    assert "sent 1" in output
    assert OutboundMail.objects.count() == 0
    [message] = mailer.MEMORY.sent
    assert message.to == _account.email
    assert message.subject == NL["MAIL_RESET_SUBJECT"]
    link = re.search(r"http://127\.0\.0\.1:3000/account/#herstel=([A-Za-z0-9_-]{43})", message.text)
    assert link, message.text
    row = OneTimeToken.objects.get(user=_account, kind=OneTimeToken.PASSWORD_RESET)
    assert row.token_sha256 == token_digest(link.group(1))
    assert row.issued_at >= before
    line = AuditEvent.objects.get(event_type=AuditEvent.MAIL_SENT)
    assert line.context["user_id"] == _account.pk
    assert line.context["kind"] == OneTimeToken.PASSWORD_RESET
    assert line.context["provider_id"].startswith("memory-outbox-")
    assert set(line.context) == {"user_id", "kind", "provider_id"}


@pytest.mark.django_db
def test_a_verification_mail_carries_the_other_link(_account: User) -> None:
    recovery.request_email_verification(_account)
    _run()
    [message] = mailer.MEMORY.sent
    assert message.subject == NL["MAIL_VERIFY_SUBJECT"]
    assert re.search(r"/account/#verificatie=[A-Za-z0-9_-]{43}", message.text)
    assert "%(link)s" not in message.text


@pytest.mark.django_db
def test_a_transport_failure_leaves_no_token_behind(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 4.4: the mint and the send share a savepoint inside the command's
    transaction, so a mail that never left leaves no digest of a token nobody
    received."""
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(503))
    recovery.request_password_reset(_account.email)
    before = timezone.now()
    output = _run()
    assert "deferred 1" in output
    assert OneTimeToken.objects.count() == 0
    row = OutboundMail.objects.get()
    assert row.attempts == 1
    assert row.last_status == 503
    assert row.failed_at is None
    assert timedelta(seconds=55) <= row.next_attempt_at - before <= timedelta(seconds=65)
    assert AuditEvent.objects.filter(event_type=AuditEvent.MAIL_SENT).count() == 0


@pytest.mark.django_db
def test_the_backoff_is_one_five_fifteen_sixty_and_then_failed(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Driven by moving the row's own clock rather than the wall clock: each
    round sets `next_attempt_at` into the past and `created_at` further back,
    which is what a row looks like after that much waiting."""
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(0))
    recovery.request_email_verification(_account)
    row = OutboundMail.objects.get()
    expected = [1, 5, 15, 60, 60]
    for minutes in expected:
        OutboundMail.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now())
        before = timezone.now()
        _run()
        row.refresh_from_db()
        assert row.failed_at is None
        waited = row.next_attempt_at - before
        assert (
            timedelta(minutes=minutes) - timedelta(seconds=5)
            <= waited
            <= timedelta(minutes=minutes) + timedelta(seconds=5)
        ), (minutes, waited)
    OutboundMail.objects.filter(pk=row.pk).update(
        next_attempt_at=timezone.now(), created_at=timezone.now() - timedelta(hours=25)
    )
    _run()
    row.refresh_from_db()
    assert row.failed_at is not None
    assert row.attempts == 6


@pytest.mark.django_db
def test_a_four_hundred_other_than_429_fails_at_once(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(401))
    recovery.request_password_reset(_account.email)
    _run()
    row = OutboundMail.objects.get()
    assert row.failed_at is not None
    assert row.last_status == 401
    assert row.attempts == 1


@pytest.mark.django_db
def test_a_429_is_retried_like_a_network_fault(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(429))
    recovery.request_password_reset(_account.email)
    _run()
    row = OutboundMail.objects.get()
    assert row.failed_at is None
    assert row.attempts == 1


@pytest.mark.django_db
def test_a_failed_row_is_never_picked_up_again(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = _Failing(401)
    monkeypatch.setattr(mailer, "transport", lambda: transport)
    recovery.request_password_reset(_account.email)
    _run()
    _run()
    assert transport.attempts == 1


@pytest.mark.django_db
def test_the_command_exits_nonzero_when_something_is_overdue(
    _account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half that notices. `--check` sends nothing and asks one question:
    is anything unsent older than fifteen minutes?"""
    monkeypatch.setattr(mailer, "transport", lambda: _Failing(0))
    recovery.request_password_reset(_account.email)
    _run("--check")
    OutboundMail.objects.update(created_at=timezone.now() - timedelta(minutes=16))
    with pytest.raises(CommandError, match="waiting"):
        _run("--check")
    assert mailer.MEMORY.sent == []
    with pytest.raises(CommandError, match="waiting"):
        _run()


@pytest.mark.django_db
def test_two_overlapping_runs_never_send_one_row_twice(_account: User) -> None:
    """`FOR UPDATE SKIP LOCKED`, read off the source like the lock in
    recovery.py: the behavioural half is that a row locked by another run is
    skipped, which two processes on Postgres provide and one test process
    cannot stage."""
    source = COMMAND.read_text(encoding="utf-8")
    assert "select_for_update(skip_locked=True)" in source


@pytest.mark.django_db
def test_the_purge_removes_expired_tokens_and_old_failures(_account: User) -> None:
    now = timezone.now()
    live = recovery.mint(_account, OneTimeToken.EMAIL_VERIFY)
    dead = recovery.mint(_account, OneTimeToken.PASSWORD_RESET)
    OneTimeToken.objects.filter(token_sha256=token_digest(dead)).update(
        expires_at=now - timedelta(seconds=1)
    )
    OutboundMail.objects.create(
        user=_account,
        kind=OneTimeToken.EMAIL_VERIFY,
        next_attempt_at=now,
        failed_at=now - timedelta(days=8),
    )
    OutboundMail.objects.create(
        user=_account,
        kind=OneTimeToken.PASSWORD_RESET,
        next_attempt_at=now,
        failed_at=now - timedelta(days=6),
    )
    out = io.StringIO()
    call_command("purge_expired_sessions", stdout=out)
    assert "1 expired one-time tokens" in out.getvalue()
    assert "1 failed mails" in out.getvalue()
    assert OneTimeToken.objects.get().token_sha256 == token_digest(live)
    assert OutboundMail.objects.count() == 1
