"""The one module that reaches api.resend.com, and the two that do not.

`requests.post` is patched at the call, never the network: what is asserted
is the exact request the transport builds, which is the whole of what a
reviewer can check about an outbound call without a key.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import requests
from django.test import override_settings

from accounts import mailer

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
