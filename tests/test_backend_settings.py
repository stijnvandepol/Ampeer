"""The settings decide security properties, so they are tested like code.

Production settings are never imported by any other test, so without this file
they would be measured at zero coverage and, worse, a typo in them would first
be discovered on the server.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any

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
    # The origins the browser may read an answer from. A property of a
    # deployment, like the two above, and with the same treatment: no default,
    # because a permissive fallback here is an API any page on the internet can
    # read a household's figures out of, and it fails silently from this side.
    "DJANGO_CORS_ALLOWED_ORIGINS": "https://ampeer.nl,https://www.ampeer.nl",
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


def test_production_never_opens_the_api_to_every_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The setting that would undo the whole list.

    django-cors-headers reads CORS_ALLOW_ALL_ORIGINS before the list, so one
    True anywhere in the settings chain makes every allowed-origin assertion in
    the API tests pass while the answer goes to anybody who asks.
    """
    prod = _load_prod(monkeypatch)
    assert prod.CORS_ALLOWED_ORIGINS == ["https://ampeer.nl", "https://www.ampeer.nl"]
    assert getattr(prod, "CORS_ALLOW_ALL_ORIGINS", False) is False
    assert getattr(prod, "CORS_ALLOW_CREDENTIALS", False) is False
    assert "*" not in prod.CORS_ALLOWED_ORIGINS


def test_the_cors_middleware_runs_before_anything_that_could_redirect() -> None:
    """Ordering, not presence.

    A preflight is an OPTIONS with no credentials. If SecurityMiddleware's
    SSL redirect or CommonMiddleware's slash append answers it first, the
    browser gets a 301 with no CORS header and blocks the request. The symptom
    is a working GET and a blocked POST, which is the hardest shape to
    diagnose because half the site keeps working.
    """
    from django.conf import settings

    middleware = list(settings.MIDDLEWARE)
    assert middleware[0] == "corsheaders.middleware.CorsMiddleware", middleware


def test_the_deploy_check_in_ci_knows_every_setting_production_requires() -> None:
    """The second copy of REQUIRED_ENV, and what happens when it goes stale.

    `manage.py check --deploy` runs in the quality job under production
    settings, so that job carries its own list of the environment variables
    prod.py insists on. Adding a required setting without adding it there turns
    a green pipeline red on a RuntimeError that reads like a bug in the settings
    rather than an omission in a workflow. That is what happened on 2026-08-21
    when CORS arrived: the setting refused to start, correctly, and the job had
    never been told about it.

    Two secrets are generated inside the step rather than written into the file,
    so this looks for every name anywhere in the step body.
    """
    import re
    from pathlib import Path

    workflow = (
        Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    ).read_text(encoding="utf-8")
    step = re.search(r"- name: Django deployment checklist.*?(?=\n      - )", workflow, re.DOTALL)
    assert step, "the deploy check step is gone from ci.yml"
    missing = [name for name in REQUIRED_ENV if name not in step.group(0)]
    assert not missing, (
        f"prod.py requires {missing} and the deploy check in ci.yml does not set them"
    )


#: A value that must never appear in a statement the server logs. Any string
#: with no other reason to be in a query plan.
PROBE_SECRET = "TESTtokenTESTtoken0000"


@pytest.mark.django_db
def test_the_database_never_receives_a_value_inside_the_statement_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres writes the failing statement into its own container log.

    Django 5 with psycopg 3 binds parameters client-side by default, so every
    value is interpolated into the SQL text before it is sent, and
    `log_min_error_statement=error` is on by default in the pinned image. Any
    statement that fails therefore lands in the db container's log with the
    token, the household's answers and the throttle key in it, and the db
    container is never recreated by a deploy, so that log lives about a year.

    This asks the server what it received rather than asking the settings what
    they say: `pg_stat_activity.query` for this backend is the statement text
    as it arrived. Client-side binding shows the value; server-side binding
    shows `$1`.
    """
    from django.conf import settings
    from django.db.utils import ConnectionHandler

    prod = _load_prod(monkeypatch)
    config: dict[str, Any] = dict(settings.DATABASES["default"])
    config["OPTIONS"] = dict(prod.DATABASES["default"].get("OPTIONS", {}))
    # A second handler and therefore a second physical connection, so this
    # measures a connection built the way production builds one instead of the
    # one pytest-django has already opened under the test settings.
    handler = ConnectionHandler({"default": config})
    connection = handler["default"]
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT query FROM pg_stat_activity "
                "WHERE pid = pg_backend_pid() AND %s::text <> ''",
                [PROBE_SECRET],
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    assert row is not None
    received: str = row[0]
    assert PROBE_SECRET not in received, (
        "the value reached the server inside the statement text, which is what "
        f"log_min_error_statement writes out on any failure: {received}"
    )
    assert "$1" in received, received


def test_production_binds_its_parameters_on_the_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The setting the test above measures the effect of, named here so a
    removal is a failure with the reason attached rather than a puzzle."""
    prod = _load_prod(monkeypatch)
    assert prod.DATABASES["default"]["OPTIONS"]["server_side_binding"] is True


class TestWhatTheProcessIsAllowedToWriteDown:
    """There was no LOGGING setting, so `DEBUG=False` meant a 500 produced no
    output at all, and the obvious repair writes the token instead."""

    def config(self) -> dict[str, Any]:
        """The configuration as written, not as `dictConfig` left it.

        `logging.config.dictConfig` mutates the dictionary it is given: it
        replaces every formatter and handler entry with the object it built,
        and Django hands it `settings.LOGGING` itself. Reading the setting back
        after startup therefore reads the leftovers, which is why base.py keeps
        a factory and the setting is a snapshot of it.
        """
        from ampeer.settings.base import logging_config

        return logging_config()

    def test_there_is_a_logging_configuration_at_all(self) -> None:
        from django.conf import settings

        assert settings.LOGGING, "no LOGGING setting: an unhandled exception writes nothing"
        assert set(settings.LOGGING) == set(self.config())

    def test_the_configuration_is_the_one_that_actually_took_effect(self) -> None:
        """The dictionary above is a claim until something reads it.

        Django calls dictConfig once at startup, so this asserts against the
        live logger: the handler is there, its formatter is the redacting one,
        and the record stops at that handler rather than travelling on to
        whatever else has attached itself to the root logger.
        """
        import logging

        from ampeer.settings.base import RedactedFormatter

        for name in ("django", "django.server"):
            logger = logging.getLogger(name)
            assert logger.propagate is False, name
            # pytest attaches handlers of its own to every non-propagating
            # logger so that caplog and its report keep working. They belong to
            # the test harness and are not present in the running service.
            writing = [
                handler
                for handler in logger.handlers
                if not type(handler).__module__.startswith("_pytest")
            ]
            assert writing, f"{name} has no handler: an error there writes nothing"
            for handler in writing:
                assert isinstance(handler.formatter, RedactedFormatter), (name, handler)

    def test_every_handler_formats_through_the_redacting_formatter(self) -> None:
        """One formatter, named by every handler.

        A second handler with the default formatter would write
        `Internal Server Error: /api/advice/<token>/` beside the redacted line
        and undo the whole thing, silently, because both lines look like logs.
        """
        config = self.config()
        formatters = set(config["formatters"])
        assert len(formatters) == 1, formatters
        (only,) = formatters
        for name, handler in config["handlers"].items():
            assert handler.get("formatter") == only, (name, handler)
            assert handler["class"] == "logging.StreamHandler", (name, handler)

    def test_no_logger_reaches_a_handler_this_file_did_not_configure(self) -> None:
        """Django's own default attaches `mail_admins` to the `django` logger
        and a `django.server` handler that writes the request line. Both have
        to be replaced rather than added to, and `propagate` has to be off, or
        a record travels to the root handler through a chain nothing here
        chose."""
        config = self.config()
        ours = set(config["handlers"])
        assert config["root"]["handlers"] and set(config["root"]["handlers"]) <= ours
        for name in ("django", "django.server"):
            logger = config["loggers"][name]
            assert set(logger["handlers"]) <= ours, (name, logger)
            assert logger["propagate"] is False, (name, logger)

    def test_the_formatter_drops_the_message_and_keeps_the_exception(self) -> None:
        """A record shaped exactly like the one Django writes for a 500.

        `django.request` logs `"Internal Server Error: %s" % request.path`,
        with the path in `record.args`, and the exception carried alongside it
        is whatever raised: a psycopg IntegrityError quotes the offending key
        in its own message. All three are values from the request, and none of
        them may reach the line.
        """
        import logging

        from ampeer.settings.base import RedactedFormatter

        formatter = RedactedFormatter()

        token = "TESTtokenTESTtoken0000"
        try:
            raise ValueError(f"duplicate key (token)=({token}) from 203.0.113.7")
        except ValueError as error:
            record = logging.LogRecord(
                name="django.request",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="Internal Server Error: %s",
                args=(f"/api/advice/{token}/",),
                exc_info=(type(error), error, error.__traceback__),
            )
            record.status_code = 500
            line = formatter.format(record)

        assert token not in line, line
        assert "203.0.113.7" not in line, line
        assert "/api/advice/" not in line, line
        assert "ValueError" in line, line
        assert "django.request" in line, line
        assert "500" in line, line
        assert "test_backend_settings.py" in line, line
