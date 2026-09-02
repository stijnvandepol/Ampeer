"""Settings shared by every environment.

Nothing here reads an environment variable that decides a security property.
Those live in prod.py, where a missing value stops the process instead of
falling back to something permissive.
"""

from __future__ import annotations

import logging
import os
import time
import traceback
from pathlib import Path
from typing import Any

from ampeer_sim.simulate import DEFAULT_WEATHER_YEAR

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "advice.apps.AdviceConfig",
]

# No auth, no sessions, no admin. There is nothing to log in to in this phase,
# and an installed app is an attack surface whether or not a URL points at it.

MIDDLEWARE = [
    # First, and above SecurityMiddleware, because it has to answer a preflight
    # OPTIONS before anything else redirects or rejects it. django-cors-headers
    # says so in its own README and it is the ordering mistake that produces a
    # working GET and a blocked POST, which is the hardest kind to diagnose.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Section 9 of the design says this middleware stays even though the advice
    # endpoints do not need it, and until 2026-08-21 it said so about a list it
    # was not in. It protects nothing today: DRF wraps every APIView in
    # csrf_exempt, and there is no session to ride on anyway. It is here for the
    # first view that is neither of those, which is a view somebody will add
    # without thinking about this file. `manage.py check --deploy` in the
    # quality job refuses a deployment without it.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ampeer.urls"
WSGI_APPLICATION = "ampeer.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Stored in UTC, shown in Europe/Amsterdam. The engine works on a grid in
# continuous winter time and never sees a Django timestamp, so this setting
# governs the audit log and nothing in the model.
TIME_ZONE = "UTC"
USE_TZ = True
LANGUAGE_CODE = "nl-nl"

STATIC_URL = "static/"

#: Annotated rather than inferred. Without it mypy reads the value types of
#: this literal as the whole domain, and dev.py and prod.py, which each add an
#: integer NUM_PROXIES, become assignment errors about a dict shape nobody
#: intended to declare.
REST_FRAMEWORK: dict[str, Any] = {
    # Anonymous by design. There is no account to authenticate.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    # JSON only. DRF's default list also holds BrowsableAPIRenderer, which
    # renders a Django template, and TEMPLATES here is empty: every browser
    # that opened a shared advice link sent Accept: text/html and got a
    # TemplateDoesNotExist, so the product's core flow answered 500. Pinning
    # this also means that configuring TEMPLATES later cannot silently publish
    # an interactive API console on three anonymous public endpoints.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # JSON only again, and through a parser that turns a RecursionError into a
    # 400. The frontend posts JSON; a form encoded body was never a supported
    # input, and FormParser and MultiPartParser are parsing surface that no
    # caller needs. See advice/parsers.py.
    "DEFAULT_PARSER_CLASSES": ["advice.parsers.BoundedJSONParser"],
    # Not DRF's ScopedRateThrottle directly. That one keys its counter on the
    # caller's address, so the counter table becomes "this address was here at
    # these times" and rows outlive the visitor. See advice/throttling.py.
    "DEFAULT_THROTTLE_CLASSES": ["advice.throttling.HashedIdentScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        # A computation costs about half a second of CPU. Twenty an hour is
        # generous for a real visit and far too little to occupy the machine.
        "advice-compute": "20/hour",
        # Opening and sharing a link must not require thinking about it.
        "advice-read": "120/hour",
    },
    "UNAUTHENTICATED_USER": None,
}

# NUM_PROXIES is deliberately absent from this file. It decides what the rate
# limit counts, and its only correct value is a property of one deployment's
# proxy chain, so there is no shared default that is right. Left unset, DRF's
# ScopedRateThrottle keys on the whole client supplied X-Forwarded-For header:
# measured on 2026-08-21, forty requests with a rotating header produced zero
# 429s. Every settings module below therefore states a value: dev.py and
# test.py explicitly, prod.py from the environment with no fallback.

#: The table django.core.cache.backends.db.DatabaseCache reads and writes in
#: production. It is named here rather than in prod.py because the migration
#: that creates the table has to name the same string, and two literals that
#: must agree are one literal that eventually will not.
AMPEER_CACHE_TABLE = "ampeer_cache"

#: The NEDU standard profile file. There is no default and there is no
#: fallback shape: a consumption profile that nobody measured would be an
#: invented number at the centre of every answer. prod.py refuses to start
#: without it. See profiles.py.
AMPEER_NEDU_PROFILE_PATH: str | None = os.environ.get("AMPEER_NEDU_PROFILE_PATH")

#: The weather year and profile year every request is computed for. Both are
#: closed years, so an advice is reproducible from its stored inputs.
#:
#: The weather year is taken from the kernel rather than written again. It was
#: 2023 in three places on 2026-08-23, here and in ampeer_sim/simulate.py and
#: ampeer_sim/validate.py, and raising one of them would have left the product
#: computing one year while `python -m ampeer_sim.validate` checked another and
#: reported the difference as a model that had drifted from reality. A
#: deployment may still override this; doing so is now an edit that says so.
AMPEER_WEATHER_YEAR = DEFAULT_WEATHER_YEAR
AMPEER_PROFILE_YEAR = 2025

#: How long a stored advice stays retrievable.
AMPEER_ADVICE_TTL_DAYS = 90


#: Which origins the browser may read an answer from.
#:
#: This exists because the browser calls this API directly. That is deliberate:
#: the throttle is keyed on the caller, so a frontend fetching server-side would
#: put every visitor into one bucket, and the answers are personal data that
#: gain nothing from passing through one more process. The cost of that choice
#: is that the two halves are on different origins and the browser will not hand
#: over a response without being told to.
#:
#: It was missing entirely until 2026-08-21. Nothing caught it: Playwright stubs
#: every API route, DRF's APIClient sends no Origin and enforces no same-origin
#: policy, and the contract test reads a file. A visitor would have been the
#: first to know, and would have been told to check their own connection.
#:
#: Empty here, and required from the environment in production. A wildcard would
#: let any page on the internet read a household's figures out of this API.
CORS_ALLOWED_ORIGINS: list[str] = []

#: Only what the two POST bodies and the GET actually need. The default list is
#: wider, and every header on it is one more thing a preflight will agree to.
CORS_ALLOW_HEADERS = ["content-type"]
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]

#: No cookies cross the boundary. There is no session on this API, so there is
#: nothing to send; saying so out loud means a later view cannot start relying
#: on one by accident.
CORS_ALLOW_CREDENTIALS = False


# ---------------------------------------------------------------------------
# What a running process is allowed to write down.
#
# There was no LOGGING setting here at all until 2026-08-21, and the effect was
# not "the defaults". Django's own default routes django.request errors to
# mail_admins and gates its console handler on require_debug_true, so with
# DEBUG off an unhandled exception produced no output anywhere: measured, two
# 500s, zero lines. During an outage the entire evidence base was a status code
# in an access log.
#
# The obvious repair is the trap. Django's message for a 500 is
# `"Internal Server Error: %s" % request.path`, so adding a console handler
# writes /api/advice/<token>/ into the container log on the same day, into the
# same json-file driver that infra/nginx/nginx.conf and infra/entrypoint-api.sh
# both go out of their way to keep the token out of. The exception's own
# message is no safer: a psycopg IntegrityError quotes the offending key
# verbatim, which is how a throttle key and a stored token end up in a log
# without anybody formatting them.
#
# So the line is assembled from a whitelist rather than redacted afterwards. A
# scrubber has to guess what a secret looks like; a whitelist cannot be
# surprised by a shape nobody anticipated.
# ---------------------------------------------------------------------------


class RedactedFormatter(logging.Formatter):
    """A log line built only from things the code decided, never the request.

    What comes out: the time, the level, the logger, the response status when
    there is one, and for an exception its type and the frames it passed
    through. Every one of those is fixed by this repository.

    What never comes out: `record.getMessage()` is not called, so neither the
    format string nor `record.args` is rendered; the exception's own message is
    dropped; and the frames are file, line and function without their source
    text. A traceback's source lines hold no runtime value, but they are also
    the one part of this that a future edit could make carry one, and the
    frames alone already answer "where".
    """

    #: UTC, like every other timestamp this project stores. A container's local
    #: time is whatever the image decided and is not a thing to correlate on.
    #: staticmethod, because a bare function in a class body is a method: bound,
    #: it would be handed `self` as the timestamp.
    converter = staticmethod(time.gmtime)

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            self.formatTime(record, "%Y-%m-%dT%H:%M:%S") + "Z",
            record.levelname,
            record.name,
        ]
        # Set by django.request on every request it logs, and it is the whole
        # reason a 4xx line is worth keeping at all once the path is gone.
        status = getattr(record, "status_code", None)
        if isinstance(status, int):
            parts.append(f"status={status}")
        line = " ".join(parts)
        error = record.exc_info[1] if record.exc_info else None
        if error is not None:
            line = "\n".join([line, *_exception_lines(error)])
        return line


def _exception_lines(error: BaseException) -> list[str]:
    """An exception as its type and its frames, following the cause chain.

    The chain matters more here than usual: the interesting type is often the
    innermost one, and with the messages gone the type is most of what is left.
    """
    lines: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        lines.append(f"{type(current).__module__}.{type(current).__qualname__}")
        lines.extend(
            f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}'
            for frame in traceback.extract_tb(current.__traceback__)
        )
        current = current.__cause__ or current.__context__
    return lines


def logging_config() -> dict[str, Any]:
    """A fresh copy of the logging configuration.

    A factory and not a literal, because `logging.config.dictConfig` mutates
    the dictionary it is handed: it replaces each formatter and handler entry
    with the object it built and pops keys out of them as it goes. Django hands
    it `settings.LOGGING` directly, so after startup that setting no longer
    describes anything, and a second `dictConfig` over it fails. This way the
    setting is a snapshot and the configuration itself stays readable.
    """
    return {
        "version": 1,
        # The Django default has already been applied by the time this runs, so
        # the loggers below replace its handlers rather than adding to them.
        # Disabling existing loggers would silence every third-party logger
        # created before this point instead.
        "disable_existing_loggers": False,
        "formatters": {"redacted": {"()": RedactedFormatter}},
        "handlers": {
            # stderr, so nothing is written inside the container and the
            # retention is the log driver's, which infra/docker-compose.yml
            # bounds. One handler, because a second one with any other
            # formatter would write the unredacted line beside this one and
            # both would look like logs.
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "redacted",
                "level": "INFO",
            }
        },
        "root": {"handlers": ["stderr"], "level": "INFO"},
        "loggers": {
            # Replaces the default pair. `mail_admins` sends the request path
            # to whoever is in ADMINS, and the console handler it sits beside
            # is the one that does nothing when DEBUG is off.
            "django": {"handlers": ["stderr"], "level": "INFO", "propagate": False},
            # runserver's request log, whose message *is* the request line. It
            # is unused in production, where gunicorn serves and writes no
            # access log for the same reason, but a developer opening a stored
            # advice locally would otherwise put the token on their terminal
            # and in their scrollback.
            "django.server": {"handlers": ["stderr"], "level": "INFO", "propagate": False},
        },
    }


LOGGING = logging_config()
