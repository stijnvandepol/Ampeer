"""The one module under backend/ that reaches outside this machine, and where.

Resend is one endpoint with four fields, so it is spoken to with `requests`
and not with its SDK: the SDK would open connections from a package
tests/test_boundaries.py never reads. The destination is a literal on the
line where a reviewer sees it, the client is the one that test allows, and
the same test now holds this file to the rule pvgis.py has always been held
to, that a URL is named and never assembled.

Three transports, one interface. `resend` is production, `file` is the local
stack and a developer machine, `memory` is the test suite. prod.py refuses
`memory`, and scripts/preflight_env.sh refuses anything but `resend` on a
host, so the two that deliver nothing can never be the one a household's
mail depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import requests
from django.conf import settings

#: The destination, on the allowlist in tests/test_boundaries.py.
RESEND_ENDPOINT: Final = "https://api.resend.com/emails"
#: Seconds. The command runs every minute; a send that takes longer than
#: this is a send that is retried, not waited for.
TIMEOUT_SECONDS: Final = 10


@dataclass(frozen=True)
class Message:
    """One mail, fully composed. Never stored: it exists between the command
    building it and the transport accepting it."""

    to: str
    subject: str
    text: str
    #: `outbox-<id>`. Resend keeps it 24 hours, so a retry after a timeout is
    #: not a second mail. The outbox id is never reused.
    idempotency_key: str


class TransportError(Exception):
    """The transport did not accept the message. `status` is the HTTP status
    it answered, 0 when it answered nothing at all."""

    def __init__(self, status: int) -> None:
        super().__init__(f"the mail transport answered {status}")
        self.status = status


class Transport(Protocol):
    def send(self, message: Message) -> str:
        """Deliver, and return the provider's id for it. Raise TransportError otherwise."""


class ResendTransport:
    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, message: Message) -> str:
        try:
            response = requests.post(
                RESEND_ENDPOINT,
                json={
                    "from": self._sender,
                    "to": [message.to],
                    "subject": message.subject,
                    "text": message.text,
                },
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Idempotency-Key": message.idempotency_key,
                },
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as error:
            raise TransportError(0) from error
        if response.status_code != 200:
            raise TransportError(response.status_code)
        try:
            body = response.json()
        except ValueError as error:
            # A 200 whose body cannot be parsed is not a delivery this
            # command can point at in MAIL_SENT, so it is a transport
            # failure and not an exception the caller has to guard against.
            raise TransportError(response.status_code) from error
        provider_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(provider_id, str) or not provider_id:
            # A 200 that names no delivery is not a delivery this command
            # can point at in MAIL_SENT, so it is not one.
            raise TransportError(response.status_code)
        return provider_id


class FileTransport:
    """One text file per message, for the local stack and a developer machine.

    tests/test_stack_smoke.py reads the link out of that file, which is how
    the live checks close the loop without a key and without Resend.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def send(self, message: Message) -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{message.idempotency_key}.txt"
        path.write_text(
            f"To: {message.to}\nSubject: {message.subject}\n\n{message.text}",
            encoding="utf-8",
        )
        return f"file-{message.idempotency_key}"


class MemoryTransport:
    """The test suite's. Keeps every message so a test can read it back."""

    def __init__(self) -> None:
        self.sent: list[Message] = []

    def send(self, message: Message) -> str:
        self.sent.append(message)
        return f"memory-{message.idempotency_key}"


#: One instance for the whole process, so a test that reads `mailer.MEMORY.sent`
#: sees what the command handed to `mailer.transport()`.
MEMORY = MemoryTransport()


def transport() -> Transport:
    """The transport `AMPEER_MAIL_TRANSPORT` names. Anything else is a refusal,
    not a fallback: a fallback here would be the silent failure prod.py exists
    to prevent."""
    name = settings.AMPEER_MAIL_TRANSPORT
    if name == "resend":
        return ResendTransport(settings.RESEND_API_KEY, settings.AMPEER_MAIL_FROM)
    if name == "file":
        return FileTransport(Path(settings.AMPEER_MAIL_FILE_DIR))
    if name == "memory":
        return MEMORY
    raise RuntimeError(f"AMPEER_MAIL_TRANSPORT is {name!r}; it must be resend, file or memory")
