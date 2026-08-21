"""Production. Every value that decides a security property comes from the
environment and has no default.

A missing secret must stop the process. The alternative, a fallback, is how a
service ends up running in the open with a key that is in a public repository,
and it fails silently by construction: everything works.
"""

from __future__ import annotations

import os

from ampeer.settings.base import *


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set; refusing to start")
    return value


def _required_count(name: str) -> int:
    """A required setting that must be a whole number of proxies, zero included.

    ``_required`` refuses an empty string, which is what a shell exports for an
    unset variable, and this refuses anything that is not a count. A misspelled
    value must stop the process for the same reason a missing one does: the
    setting it feeds decides whether the rate limit counts anything.
    """
    value = _required(name)
    if not value.isdigit():
        raise RuntimeError(f"{name} must be a whole number of proxies, got {value!r}")
    return int(value)


DEBUG = False
SECRET_KEY = _required("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [host for host in _required("DJANGO_ALLOWED_HOSTS").split(",") if host]
AMPEER_NEDU_PROFILE_PATH = _required("AMPEER_NEDU_PROFILE_PATH")

# No default and no wildcard. An origin list that falls back to something
# permissive is an API any page on the internet can read a household's figures
# out of, and the failure is silent from this side: the request succeeds and
# somebody else's page gets the answer.
CORS_ALLOWED_ORIGINS = [
    origin for origin in _required("DJANGO_CORS_ALLOWED_ORIGINS").split(",") if origin
]

# Required from the environment exactly like SECRET_KEY, and for the same kind
# of reason. Unset, DRF keys its rate limit on the entire client supplied
# X-Forwarded-For header, so one rotating header per request makes every
# request look like a new client: measured on 2026-08-21, forty requests that
# way produced zero 429s. A rate limit that is silently switched off is worse
# than a process that refuses to start, because the crash is visible on the
# first deploy and the missing limit is visible only afterwards. The value is
# how many proxies of this deployment's own chain append to that header, so it
# belongs to the deployment and not to this file.
REST_FRAMEWORK = REST_FRAMEWORK | {"NUM_PROXIES": _required_count("DJANGO_NUM_PROXIES")}

# The throttle counter lives in Postgres, which this deployment already
# requires. Without this block Django's default LocMemCache applies, and a
# throttle counter in a per-process dict is three separate faults: the limit is
# per worker rather than per service, it resets on every deploy, and the dict
# holds 300 entries, so 400 distinct client keys cull a third of the history at
# random, including the history of whoever produced them. Redis stays out of
# the request path, which is the same decision section 4 of the design makes
# for the PVGIS cache: one fewer thing that can be down while somebody is on
# the site. The table is created by a migration in the advice app, so a deploy
# cannot forget a manual createcachetable.
#: MAX_ENTRIES is not a capacity estimate and must not be read as one. Django's
#: default is 300 for every backend, DatabaseCache included, so simply moving
#: the counter into Postgres would have carried the culling defect along with
#: it: past 300 rows, a write deletes a third of the table ordered by key,
#: which is to say at random with respect to who is being throttled. This
#: number is a ceiling chosen so that culling is never the mechanism that
#: removes an entry; expiry is, because every throttle entry is written with
#: the one hour window as its timeout. Two scopes means at most two rows per
#: client address per hour, so this covers fifty thousand distinct addresses in
#: an hour, about fourteen new ones a second sustained. That is far past the
#: point at which section 3 of the design says the computation moves to a
#: worker, so it will be revisited for a different reason first.
CACHE_MAX_ENTRIES = 100_000

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": AMPEER_CACHE_TABLE,
        "OPTIONS": {"MAX_ENTRIES": CACHE_MAX_ENTRIES},
    }
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _required("POSTGRES_DB"),
        "USER": _required("POSTGRES_USER"),
        "PASSWORD": _required("POSTGRES_PASSWORD"),
        "HOST": _required("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
