"""The settings decide security properties, so they are tested like code.

Production settings are never imported by any other test, so without this file
they would be measured at zero coverage and, worse, a typo in them would first
be discovered on the server.
"""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:  # the runtime import stays inside the function, like every
    from rest_framework.views import APIView  # other Django import in this file

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
    # Added 2026-08-23. It was set beside the seven above and asserted by
    # nothing: neither this file nor `manage.py check --deploy`, which only
    # warns when the policy is unset and not when it is a permissive value.
    # Measured: "unsafe-url" left the deploy check and the whole suite green.
    assert prod.SECURE_REFERRER_POLICY == "same-origin"


def test_django_trusts_the_forwarded_header_nginx_actually_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two files that have to agree, and only one of them was checked.

    prod.py decides a request is secure by reading one header name out of
    SECURE_PROXY_SSL_HEADER. infra/nginx/nginx.conf sets that header to a
    constant, and tests/test_nginx_config.py asserts the nginx half: that it is
    set rather than passed through, and that it is not $scheme. Nothing tied the
    two together, so renaming or dropping the setting broke the pairing quietly.

    Quietly is arguable in one direction and not the other. Dropping the setting
    makes Django see every request as insecure and SECURE_SSL_REDIRECT answers
    301 to the same URL, which the tunnel delivers back: a redirect loop that
    shows up on the first request. Pointing it at a header the proxy does not
    overwrite is the silent half, because then a caller can assert its own
    request is secure.

    The expected value is derived from the nginx file rather than written here,
    so this fails when the two disagree rather than when either one moves.
    """
    import re as _re
    from pathlib import Path as _Path

    conf = (_Path(__file__).resolve().parent.parent / "infra" / "nginx" / "nginx.conf").read_text(
        encoding="utf-8"
    )
    directives = chr(10).join(
        line for line in conf.splitlines() if not line.lstrip().startswith("#")
    )
    sent = _re.findall(r"proxy_set_header\s+(\S+)\s+([^;]+);", directives)
    proto = [(name, value.strip()) for name, value in sent if name == "X-Forwarded-Proto"]
    assert proto, "nginx no longer sets X-Forwarded-Proto, so there is nothing to trust"

    name, value = proto[0]
    expected = (f"HTTP_{name.upper().replace('-', '_')}", value)
    assert _load_prod(monkeypatch).SECURE_PROXY_SSL_HEADER == expected, (
        f"nginx sets {name}: {value} and prod.py trusts "
        f"{_load_prod(monkeypatch).SECURE_PROXY_SSL_HEADER}"
    )


def test_production_allows_only_the_hosts_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wildcard here defeats the Host header check entirely."""
    prod = _load_prod(monkeypatch)
    assert prod.ALLOWED_HOSTS == ["ampeer.nl", "www.ampeer.nl"]
    assert "*" not in prod.ALLOWED_HOSTS


def test_nothing_authenticates_because_there_is_nothing_to_log_in_to() -> None:
    """Sessions and admin stay absent, and so does an authentication class on
    the public endpoints, even though accounts now exist.

    `django.contrib.auth` itself is no longer absent: task 3 of
    docs/superpowers/plans/2026-09-04-accounts-auth.md adds it, because
    AUTH_USER_MODEL needs it to start. What CLAUDE.md and this test actually
    guard is narrower and still holds: no session middleware, no admin site,
    and REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] stays empty so the
    advice endpoints remain anonymous. A brute force defence with no login to
    defend was the old reading; from this commit there is a login, and axes
    defends it, which is test_authentication_never_arrives_without_its_defences,
    lower in this file.
    """
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == []
    assert "django.contrib.sessions" not in settings.INSTALLED_APPS
    assert "django.contrib.admin" not in settings.INSTALLED_APPS


def test_both_public_throttle_scopes_are_configured() -> None:
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["advice-compute"] == "20/hour"
    assert rates["advice-read"] == "120/hour"


#: The routes that answer without a rate limit, and the reason each is allowed to.
#:
#: The readiness endpoint is the only one. Its own docstring gives the reason:
#: in production the throttle counter lives in Postgres, so leaving the throttle
#: on would turn a check that runs every thirty seconds into the database query
#: it exists to avoid. Adding a second entry here is a decision that shows up in
#: a test diff rather than as an attribute somebody forgot to write.
UNTHROTTLED_ROUTES = frozenset({"api/advice/health/"})


def _routed_views() -> list[tuple[str, type[APIView]]]:
    """Every route the URL configuration actually serves, with its view class.

    Read through the resolver rather than by listing views.py, because what
    matters is what is reachable. A view class that exists and is not routed
    cannot be called; a view that is routed is public whether or not anybody
    remembered to write it down.

    The class comes off the callback, so an attribute inherited from a base
    class resolves the way DRF will resolve it at request time. EstimateView
    declares no throttle_scope of its own and gets one from _ComputeView, which
    a scan of the source text would have to reimplement to see.
    """
    from django.urls import URLPattern, URLResolver, get_resolver

    def walk(patterns: list[object], prefix: str = "") -> list[tuple[str, type[APIView]]]:
        found: list[tuple[str, type[APIView]]] = []
        for entry in patterns:
            if isinstance(entry, URLResolver):
                found.extend(walk(list(entry.url_patterns), prefix + str(entry.pattern)))
            elif isinstance(entry, URLPattern):
                view = getattr(entry.callback, "cls", None)
                assert view is not None, (
                    f"{prefix}{entry.pattern} is served by {entry.callback}, which is not "
                    "a DRF view. DRF throttling runs inside APIView.initial, so a plain "
                    "Django view mounted here answers with no rate limit at all."
                )
                found.append((prefix + str(entry.pattern), view))
        return found

    return walk(list(get_resolver().url_patterns))


def test_every_public_route_is_rate_limited() -> None:
    """CLAUDE.md asks for rate limiting on all public endpoints. All is the word.

    The test above pins the two rates, which says the scopes are configured. It
    does not say anything answers under one. DRF decides that per view, and the
    way it decides is the problem:

        # If a view does not have a `throttle_scope` always allow the request
        if not self.scope:
            return True

    That is ScopedRateThrottle.allow_request, quoted from the installed version.
    A view added without throttle_scope is not throttled loosely, it is not
    throttled at all, and the omission is one missing attribute that raises
    nothing, logs nothing, and passes every test that checks what the endpoint
    returns. The endpoints here compute for about half a second of CPU each.

    So the guard is written to fail on the absence rather than on a wrong value:
    every route the resolver serves has to name a scope that has a rate, or be
    on the exemption list above with the throttle explicitly switched off.
    """
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    routes = _routed_views()
    assert len(routes) >= 4, f"the resolver walk found {routes}; it is not reading the URLconf"
    assert any(route.endswith("estimate/") for route, _ in routes), (
        "the estimate endpoint is not among the routes found, so this test is looking "
        "somewhere other than at this service"
    )

    for route, view in routes:
        if route in UNTHROTTLED_ROUTES:
            assert tuple(view.throttle_classes) == (), (
                f"{route} is on the exemption list but {view.__name__} still carries "
                f"{view.throttle_classes}. An exemption has to be switched off on "
                "purpose, so that it cannot be confused with an attribute nobody wrote."
            )
            continue
        scope = getattr(view, "throttle_scope", None)
        assert scope in rates, (
            f"{route} is served by {view.__name__} with throttle_scope={scope!r}, which "
            f"has no rate in {sorted(rates)}. DRF answers such a view without any limit."
        )
        assert view.throttle_classes, (
            f"{view.__name__} names a scope but has no throttle classes, so nothing reads the scope"
        )


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


def test_timestamps_are_stored_in_utc() -> None:
    """CLAUDE.md says every timestamp is stored in UTC. Two settings decide it.

    Neither was asserted anywhere, in a file that pins twelve other settings
    because they decide a security property. This one decides an integrity
    property, and the way it fails is quiet.

    With USE_TZ off, `timezone.now()` returns naive local time, and the four
    DateTimeFields in advice/models.py store that. Three of them are ordinary
    and would only drift by an hour twice a year. The fourth is `occurred_at` on
    the append-only audit log, and local time gives October an hour that happens
    twice: two rows an hour apart can carry the same wall clock and the ordering
    the model declares stops answering when something happened. An audit log
    that cannot order itself is the one table in this service that cannot be
    rebuilt from anything.

    Asserted as the effect rather than the constant. Reading TIME_ZONE back
    would prove the file says UTC; asking `timezone.now()` proves what the code
    actually writes.
    """
    from django.conf import settings
    from django.utils import timezone

    assert settings.USE_TZ is True, "USE_TZ is off, so datetimes are stored naive"
    assert settings.TIME_ZONE == "UTC", (
        f"TIME_ZONE is {settings.TIME_ZONE!r}; storage is UTC in this project"
    )

    now = timezone.now()
    assert now.tzinfo is not None, "timezone.now() is naive, whatever the settings say"
    offset = now.utcoffset()
    assert offset is not None and offset.total_seconds() == 0, (
        f"timezone.now() carries an offset of {offset}, so it is not UTC"
    )


def test_every_stored_datetime_field_is_aware() -> None:
    """The other end of the same property, at the models rather than the clock.

    Django decides awareness per connection from USE_TZ, so this cannot drift
    from the test above on its own. It is here because it names the fields, and
    a fifth DateTimeField added later is covered without anybody remembering to
    add it.

    Nothing here asserts a display timezone. CLAUDE.md asks for Europe/Amsterdam
    on screen and the frontend currently renders no timestamp at all, so there
    is nothing to check and saying so is better than a test that passes because
    it looks at nothing.
    """
    import django

    django.setup()
    from django.apps import apps
    from django.db import models as django_models

    model_classes = apps.get_app_config("advice").get_models()
    fields = [
        (model.__name__, field.name)
        for model in model_classes
        for field in model._meta.get_fields()
        if isinstance(field, django_models.DateTimeField)
    ]
    assert len(fields) >= 4, f"only found {fields}; this test is no longer reading the models"

    from django.conf import settings

    assert settings.USE_TZ, f"these fields would all be stored naive: {fields}"


# ---------------------------------------------------------------------------
# The defences that arrive with the first account
# ---------------------------------------------------------------------------

#: The app whose presence means this service has something to log in to.
AUTH_APP = "django.contrib.auth"

#: What django-axes needs before it protects anything, from its own install
#: instructions: the app, its backend ahead of the others so a locked out
#: attempt never reaches them, and its middleware.
AXES_APP = "axes"
AXES_BACKEND = "axes.backends.AxesStandaloneBackend"
AXES_MIDDLEWARE = "axes.middleware.AxesMiddleware"


def _missing_login_defences(
    installed: set[str], backends: list[str], hashers: list[str], middleware: list[str]
) -> list[str]:
    """What CLAUDE.md requires of a service that has accounts, and is absent.

    A function rather than a chain of assertions, so that the branch which does
    not run today can still be exercised. A conditional test of the shape "if
    auth is installed then check the rest" is green on a service with no auth
    without having checked anything, and green-because-not-applicable is the
    failure this whole suite is written against.
    """
    if AUTH_APP not in installed:
        return []
    missing = []
    if AXES_APP not in installed:
        missing.append(f"{AXES_APP} is not in INSTALLED_APPS")
    if not backends or backends[0] != AXES_BACKEND:
        missing.append(f"{AXES_BACKEND} is not the first AUTHENTICATION_BACKENDS entry")
    if AXES_MIDDLEWARE not in middleware:
        missing.append(f"{AXES_MIDDLEWARE} is not in MIDDLEWARE")
    if not hashers or "Argon2" not in hashers[0]:
        missing.append("the first PASSWORD_HASHERS entry is not an Argon2 hasher")
    return missing


def test_the_rule_about_login_defences_recognises_a_setup_that_lacks_them() -> None:
    """Both branches of the check above, run rather than reasoned about.

    Without this the assertion below would be a statement about a condition
    that is false, which is the same as no statement at all. Here the rule is
    handed a service that has accounts and nothing else, and has to name all
    four; then one that has everything, and has to name none.
    """
    bare = _missing_login_defences({AUTH_APP}, [], [], [])
    assert len(bare) == 4, f"the rule found only {bare} wrong with a bare auth setup"

    complete = _missing_login_defences(
        {AUTH_APP, AXES_APP},
        [AXES_BACKEND, "django.contrib.auth.backends.ModelBackend"],
        ["django.contrib.auth.hashers.Argon2PasswordHasher"],
        [AXES_MIDDLEWARE],
    )
    assert complete == [], f"a correctly defended login is reported as missing {complete}"

    ordering = _missing_login_defences(
        {AUTH_APP, AXES_APP},
        ["django.contrib.auth.backends.ModelBackend", AXES_BACKEND],
        ["django.contrib.auth.hashers.Argon2PasswordHasher"],
        [AXES_MIDDLEWARE],
    )
    assert ordering, (
        "axes behind the model backend is reported as fine, and it is not: a lockout "
        "that runs second is a lockout the attempt has already got past"
    )


def test_authentication_never_arrives_without_its_defences() -> None:
    """The requirement, aimed at the phase that will introduce it.

    Phase 1 brings accounts. The day `django.contrib.auth` goes into
    INSTALLED_APPS, this fails unless axes and Argon2 go in with it, and it
    names each thing that is missing rather than leaving somebody to reread
    CLAUDE.md.

    Two of the four security requirements about logging in are checked here.
    The third, JWT in httpOnly SameSite=Strict cookies with refresh rotation,
    is not visible in settings alone and belongs with the view that issues
    them. Saying so is better than implying this covers it.
    """
    from django.conf import settings

    missing = _missing_login_defences(
        set(settings.INSTALLED_APPS),
        list(getattr(settings, "AUTHENTICATION_BACKENDS", [])),
        list(getattr(settings, "PASSWORD_HASHERS", [])),
        list(settings.MIDDLEWARE),
    )
    assert not missing, (
        "this service has accounts and CLAUDE.md asks for these before it does:\n  "
        + "\n  ".join(missing)
    )


def test_the_deployment_computes_the_weather_year_the_model_was_validated_on() -> None:
    """One year, and until 2026-08-23 it was written down three times.

    ampeer_sim/simulate.py holds it as the weather year the model relies on,
    ampeer_sim/validate.py held its own copy as the default for the validation
    CLI, and base.py held a third as the year every request is computed for.
    Raising one alone was measured to leave the whole suite green.

    That is the shape this repository has been bitten by before. The product
    would compute one year while `python -m ampeer_sim.validate` checked
    another, and the difference would read as a model that had drifted from
    reality rather than as two years being compared. A validation tool pointing
    at the wrong subsystem is the failure that module already carries a note
    about.

    The other two copies are gone: both now import the kernel constant. This is
    what keeps a fourth from being written here as a literal, which the import
    alone cannot prevent. A deployment that genuinely needs another year changes
    this test in the same commit, and that is the point.
    """
    from ampeer.settings import base
    from ampeer_sim.simulate import DEFAULT_WEATHER_YEAR

    assert base.AMPEER_WEATHER_YEAR == DEFAULT_WEATHER_YEAR, (
        f"the deployment computes {base.AMPEER_WEATHER_YEAR} and the model relies on "
        f"{DEFAULT_WEATHER_YEAR}"
    )


def test_the_argon2_hasher_is_the_id_variant() -> None:
    """CLAUDE.md asks for Argon2id, and that is the `type` field of the
    hasher's own encoding parameters, rather than its class name. Assuming the
    variant is right because the class is called Argon2 is a check that cannot
    go red.

    Deviation from the plan text: it reads `getattr(hasher, "type", None)`,
    which is `None` on the installed Django 5.2.17. That version moved the
    Argon2 type out of an instance attribute and into `Argon2PasswordHasher.
    params()`, which always returns `argon2.Parameters(type=Type.ID, ...)`.
    Read as written, the assertion compares None to Type.ID and is red no
    matter how PASSWORD_HASHERS is ordered, which is not a check that can go
    green on a correct configuration. Reading `hasher.params().type` instead
    is what the docstring above already asks for.
    """
    import argon2
    from django.contrib.auth.hashers import Argon2PasswordHasher, get_hasher

    hasher = get_hasher("argon2")
    assert getattr(hasher, "algorithm", "") == "argon2"
    # Narrows the type for mypy, and is itself part of what this test is
    # checking: `params()` is specific to this hasher class, not to every
    # `BasePasswordHasher`.
    assert isinstance(hasher, Argon2PasswordHasher), type(hasher)
    configured_type = hasher.params().type
    assert configured_type is argon2.low_level.Type.ID, (
        f"the configured Argon2 hasher uses {configured_type}, not Argon2id"
    )


def test_production_never_lets_a_cookie_cross_an_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """dev.py turns CORS_ALLOW_CREDENTIALS on so a developer can log in at all.
    That line copied one file up is an API whose cookies any allowed origin can
    ride, and the allowed origins in production come from the environment.

    Routed through `_load_prod(monkeypatch)`, like every other prod.py
    assertion in this file. A bare `import ampeer.settings.prod` reads
    whatever is already in `sys.modules`: it only imports fresh, and raises
    `RuntimeError: DJANGO_SECRET_KEY is not set`, the first time anything
    imports this module in the process. In the full file that first import
    happens inside an earlier `_load_prod` call and this test then reads that
    cached module object, so it passes here but dies under `-k`, under a
    single-test rerun, or under any reordering of this file.
    """
    prod = _load_prod(monkeypatch)

    assert prod.CORS_ALLOW_CREDENTIALS is False
    assert prod.AMPEER_COOKIE_SECURE is True


def test_development_still_allows_the_cookie_a_developer_needs() -> None:
    """The other half of the pin in ampeer/settings/test.py.

    That file pins CORS_ALLOW_CREDENTIALS back to False so the test
    environment mirrors production, per Ruling 21, and nothing else in this
    file reads dev.py directly. Without this, a later edit that quietly
    deleted dev.py's own `CORS_ALLOW_CREDENTIALS = True` would leave the
    whole suite green while a developer's browser dropped every
    SameSite=Strict cookie: localhost:3000 to 127.0.0.1:8000 is cross-site
    and this is the one setting that lets it through.
    """
    from ampeer.settings import dev

    assert dev.CORS_ALLOW_CREDENTIALS is True
