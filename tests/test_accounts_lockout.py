"""Does the lockout actually fire in a stack with no session middleware.

Axes is normally installed beside `AuthenticationMiddleware`, and this project
has no such middleware and cannot have one: it needs sessions, and there are
none here. `UNAUTHENTICATED_USER` is `None` besides, so `request.user` is not
the `AnonymousUser` most code assumes.

The failure this guards against is not an exception. It is a lockout that
quietly counts nothing, which looks exactly like a working login from every
angle except an attacker's.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth import authenticate
from django.test import RequestFactory
from helpers.accounts import TEST_PASSWORD as PASSWORD

from accounts.models import User


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password=PASSWORD)


@pytest.mark.django_db
def test_the_right_password_is_accepted_before_anything_else_is_claimed(_account: User) -> None:
    """The half without which every assertion below could pass on a stack where
    nothing authenticates at all."""
    request = RequestFactory().post("/api/auth/login/")
    user = authenticate(request, username="iemand@voorbeeld.nl", password=PASSWORD)
    assert user is not None and user.pk == _account.pk


@pytest.mark.django_db
def test_the_lockout_fires_without_authentication_middleware(_account: User) -> None:
    from axes.handlers.proxy import AxesProxyHandler

    factory = RequestFactory()
    for _ in range(settings.AXES_FAILURE_LIMIT):
        request = factory.post("/api/auth/login/")
        assert authenticate(request, username="iemand@voorbeeld.nl", password="fout") is None

    locked = factory.post("/api/auth/login/")
    assert not AxesProxyHandler.is_allowed(locked, {"username": "iemand@voorbeeld.nl"}), (
        f"after {settings.AXES_FAILURE_LIMIT} failed attempts axes still allows the next one. "
        "The lockout counts nothing in this stack, and design chapter 9.6 has to be reopened."
    )
    assert authenticate(locked, username="iemand@voorbeeld.nl", password=PASSWORD) is None, (
        "the right password is accepted while the account is locked out, so AxesStandaloneBackend "
        "is not running first in AUTHENTICATION_BACKENDS"
    )
