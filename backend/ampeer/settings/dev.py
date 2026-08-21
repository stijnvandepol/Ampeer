"""Developer machine. The only file in which DEBUG may be true."""

from __future__ import annotations

import os

from ampeer.settings.base import *

DEBUG = True
# nosec B105: this is a developer key and not a secret. prod.py has no default
# for SECRET_KEY at all and refuses to start without one from the environment,
# so nothing that serves the public can ever reach this value. Written in full
# rather than read from the environment so a developer machine needs no setup.
SECRET_KEY = "dev-only-not-a-secret"  # nosec B105
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "ampeer"),
        "USER": os.environ.get("POSTGRES_USER", "ampeer"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "ampeer"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
