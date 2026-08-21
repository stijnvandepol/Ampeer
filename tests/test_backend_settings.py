"""The settings decide security properties, so they are tested like code.

Production settings are never imported by any other test, so without this file
they would be measured at zero coverage and, worse, a typo in them would first
be discovered on the server.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest

REQUIRED_ENV = {
    "DJANGO_SECRET_KEY": "x" * 50,
    "DJANGO_ALLOWED_HOSTS": "ampeer.nl,www.ampeer.nl",
    "AMPEER_NEDU_PROFILE_PATH": "/srv/ampeer/nedu-profiles-2025.csv",
    "POSTGRES_DB": "ampeer",
    "POSTGRES_USER": "ampeer",
    "POSTGRES_PASSWORD": "secret",
    "POSTGRES_HOST": "db",
}


def _load_prod(monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> ModuleType:
    env = REQUIRED_ENV | overrides
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    sys.modules.pop("ampeer.settings.prod", None)
    return importlib.import_module("ampeer.settings.prod")


@pytest.mark.parametrize("missing", sorted(REQUIRED_ENV))
def test_production_refuses_to_start_without_any_required_secret(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    """A default for any of these is a service running in the open."""
    with pytest.raises(RuntimeError, match=missing):
        _load_prod(monkeypatch, **{missing: None})


def test_production_never_runs_with_debug_on(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _load_prod(monkeypatch).DEBUG is False


def test_production_sets_the_transport_and_framing_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prod = _load_prod(monkeypatch)
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SECURE_HSTS_SECONDS >= 31_536_000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"


def test_production_allows_only_the_hosts_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wildcard here defeats the Host header check entirely."""
    prod = _load_prod(monkeypatch)
    assert prod.ALLOWED_HOSTS == ["ampeer.nl", "www.ampeer.nl"]
    assert "*" not in prod.ALLOWED_HOSTS


def test_nothing_authenticates_because_there_is_nothing_to_log_in_to() -> None:
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    assert "django.contrib.auth" not in settings.INSTALLED_APPS
    assert "django.contrib.sessions" not in settings.INSTALLED_APPS
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


def test_both_public_throttle_scopes_are_configured() -> None:
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["advice-compute"] == "20/hour"
    assert rates["advice-read"] == "120/hour"


def test_the_root_urlconf_named_in_the_settings_actually_loads() -> None:
    """ROOT_URLCONF is a string, so a typo in it is a runtime error on the first
    request and nothing at all before that. Resolving it here turns that into a
    test failure, and it is also the only thing that imports ampeer/urls.py, so
    without this the root URL configuration would sit at zero coverage."""
    from django.conf import settings
    from django.urls import get_resolver

    assert settings.ROOT_URLCONF == "ampeer.urls"
    assert isinstance(get_resolver().url_patterns, list)
