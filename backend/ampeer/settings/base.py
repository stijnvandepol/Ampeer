"""Settings shared by every environment.

Nothing here reads an environment variable that decides a security property.
Those live in prod.py, where a missing value stops the process instead of
falling back to something permissive.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "advice.apps.AdviceConfig",
]

# No auth, no sessions, no admin. There is nothing to log in to in this phase,
# and an installed app is an attack surface whether or not a URL points at it.

MIDDLEWARE = [
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
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
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
AMPEER_WEATHER_YEAR = 2023
AMPEER_PROFILE_YEAR = 2025

#: How long a stored advice stays retrievable.
AMPEER_ADVICE_TTL_DAYS = 90
