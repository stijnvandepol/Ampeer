"""What `accounts.lockout.client_ip` and `accounts.lockout.username` actually
return, exercised directly rather than through axes.

The settings reference both as dotted strings, `AXES_CLIENT_IP_CALLABLE` and
`AXES_USERNAME_CALLABLE`, so nothing at import time resolves them: a NameError
or a bad import inside accounts/lockout.py would ship silently and only
surface the first time somebody actually fails a login. This file is what
imports the module and calls both functions, so that failure mode fails here
instead.

A later task's own lockout test is where axes' behaviour is measured, once
axes is wired to something worth logging into. This file stays narrower on
purpose: it is about the two callables in isolation, not about whether a
lockout fires.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.test import RequestFactory

from accounts.lockout import DIGEST_CHARS, client_ip, username
from advice.throttling import IDENT_DIGEST_CHARS


def test_client_ip_returns_a_digest_and_not_the_address() -> None:
    """The whole point of not using axes' own `get_client_ip_address`: this
    has to be a value that means nothing to whoever reads the cache. The
    length comes from advice/throttling.py: `client_ip` reuses that
    throttle's own digest rather than salting a second one."""
    request = RequestFactory().post("/api/auth/login/", REMOTE_ADDR="203.0.113.7")

    ident = client_ip(request)

    assert "203.0.113.7" not in ident
    assert len(ident) == IDENT_DIGEST_CHARS


def test_client_ip_is_stable_for_the_same_caller() -> None:
    """Axes' lockout counts increments against this value, so two requests
    from the same address have to produce the same key or the counter never
    accumulates."""
    first = client_ip(RequestFactory().post("/", REMOTE_ADDR="203.0.113.7"))
    second = client_ip(RequestFactory().post("/", REMOTE_ADDR="203.0.113.7"))

    assert first == second


def test_client_ip_differs_for_a_different_caller() -> None:
    """Not a hash collision check, a sanity check: two distinct addresses have
    to land in two distinct lockout keys, or every caller shares one budget."""
    one = client_ip(RequestFactory().post("/", REMOTE_ADDR="203.0.113.7"))
    other = client_ip(RequestFactory().post("/", REMOTE_ADDR="198.51.100.9"))

    assert one != other


def test_username_collapses_capitalisation_to_one_lockout_key() -> None:
    """The case the review that added this file checked by hand: without this,
    five failed attempts against `Iemand@Voorbeeld.NL` and five against
    `iemand@voorbeeld.nl` count as five against two different accounts, which
    halves the brute force defence without anybody seeing it happen."""
    request = RequestFactory().post("/api/auth/login/")

    lower = username(request, {"email": "iemand@voorbeeld.nl"})
    upper = username(request, {"email": "Iemand@Voorbeeld.NL"})

    assert lower == upper
    assert "voorbeeld" not in lower
    assert len(lower) == DIGEST_CHARS


def test_username_reads_the_username_key_before_the_email_key() -> None:
    """`credentials.get("username", credentials.get("email", ""))`: whichever
    field the login serializer names its address under, axes still resolves
    the same account."""
    request = RequestFactory().post("/api/auth/login/")

    via_username = username(request, {"username": "iemand@voorbeeld.nl"})
    via_email = username(request, {"email": "iemand@voorbeeld.nl"})

    assert via_username == via_email


def test_username_with_no_credentials_still_returns_a_usable_digest() -> None:
    """axes calls the username callable even on a request that never reached
    the point of carrying credentials at all; this must not raise."""
    request = RequestFactory().post("/api/auth/login/")

    assert len(username(request, None)) == DIGEST_CHARS
    assert len(username(request, {})) == DIGEST_CHARS


def test_a_non_string_username_hashes_the_empty_string() -> None:
    """The `isinstance(value, str)` branch's false arm: axes can hand this
    callable whatever a request's credentials dict happens to carry."""
    request = HttpRequest()
    digest = username(request, {"username": 123})
    assert digest == username(request, {"username": ""})
