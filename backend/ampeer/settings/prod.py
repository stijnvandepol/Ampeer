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


DEBUG = False
SECRET_KEY = _required("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [host for host in _required("DJANGO_ALLOWED_HOSTS").split(",") if host]
AMPEER_NEDU_PROFILE_PATH = _required("AMPEER_NEDU_PROFILE_PATH")

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
