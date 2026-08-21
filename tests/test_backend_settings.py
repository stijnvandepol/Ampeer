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
    # One proxy: the Cloudflare tunnel connector that fronts this deployment
    # appends the client address to X-Forwarded-For. The value is a property of
    # a deployment, which is exactly why prod.py has no default for it.
    "DJANGO_NUM_PROXIES": "1",
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


def test_production_refuses_a_proxy_count_that_is_not_a_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo must stop the process the same way an omission does.

    Accepting a value it cannot read would leave NUM_PROXIES at whatever the
    fallback was, and the fallback is the case this whole setting exists to
    remove.
    """
    with pytest.raises(RuntimeError, match="whole number of proxies"):
        _load_prod(monkeypatch, DJANGO_NUM_PROXIES="one")


def test_production_reads_the_proxy_count_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without NUM_PROXIES, DRF keys its rate limit on the whole client
    supplied X-Forwarded-For header, so a rotating header is a new client every
    request and the limit counts nothing. Zero is a valid answer and means the
    header is ignored, so the value is read rather than truth-tested."""
    prod = _load_prod(monkeypatch, DJANGO_NUM_PROXIES="0")
    assert prod.REST_FRAMEWORK["NUM_PROXIES"] == 0
    assert _load_prod(monkeypatch, DJANGO_NUM_PROXIES="2").REST_FRAMEWORK["NUM_PROXIES"] == 2


def test_production_counts_its_rate_limit_somewhere_shared_and_persistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Django's default is LocMemCache, and a throttle counter in a per-process
    dict is a limit per worker that resets on deploy and drops entries at
    random once it is full. The counter has to outlive one process."""
    prod = _load_prod(monkeypatch)
    assert prod.CACHES["default"]["BACKEND"] == "django.core.cache.backends.db.DatabaseCache"
    assert prod.CACHES["default"]["LOCATION"] == prod.AMPEER_CACHE_TABLE
    # Moving the counter into Postgres is only half of it. Django defaults
    # MAX_ENTRIES to 300 on every backend, DatabaseCache included, and past that
    # a write deletes a third of the table ordered by key, which is at random
    # with respect to who is being throttled. Expiry has to be what removes an
    # entry here, not culling.
    assert prod.CACHES["default"]["OPTIONS"]["MAX_ENTRIES"] > 300


def test_the_test_environment_states_a_proxy_count_too() -> None:
    """The value the spoofing test in tests/test_advice_api.py depends on.
    Inherited from dev.py rather than restated there, so this asserts what
    actually arrives instead of what a second literal claims."""
    from rest_framework.settings import api_settings

    assert api_settings.NUM_PROXIES == 0


def test_nothing_public_renders_html() -> None:
    """DRF's default renderer list holds BrowsableAPIRenderer, which renders a
    Django template, and TEMPLATES here is empty: every browser that opened a
    shared link sent Accept: text/html and got a 500. Pinning JSON also means a
    later TEMPLATES entry cannot publish an interactive console on three
    anonymous endpoints."""
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] == [
        "rest_framework.renderers.JSONRenderer"
    ]


def test_the_only_parser_is_the_one_that_bounds_recursion() -> None:
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"] == ["advice.parsers.BoundedJSONParser"]


def test_the_wsgi_entry_point_names_production_and_cannot_be_talked_out_of_it() -> None:
    """wsgi.py is on the coverage omit list, so this reads the file rather than
    importing it: importing it under the test settings would prove nothing
    about which module it names.

    Django's generated version uses setdefault, and with setdefault an exported
    DJANGO_SETTINGS_MODULE wins. A stray `ampeer.settings.dev` in a unit file
    would then serve public traffic with DEBUG on and a SECRET_KEY that is
    written out in this repository.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "backend/ampeer/wsgi.py").read_text(
        encoding="utf-8"
    )
    assert 'os.environ["DJANGO_SETTINGS_MODULE"] = "ampeer.settings.prod"' in source
    assert "os.environ.setdefault" not in source, "setdefault lets an exported dev module win"
