"""Developer machine. The only file in which DEBUG may be true."""

from __future__ import annotations

import os

from ampeer.settings.base import *

DEBUG = True
# A developer key and not a secret. prod.py has no default for SECRET_KEY at
# all and refuses to start without one from the environment, so nothing that
# serves the public can ever reach this value. Written in full rather than read
# from the environment so a developer machine needs no setup.
#
# The explanation is on its own line and the suppression below carries nothing
# but the test id. Bandit reads every word after that marker as a further test
# id, so a prose sentence written beside it was parsed as a list of them: the
# sast job printed "Test in comment: ... is not a test name or id" once per
# word. Which is also why no line in this file writes that marker out inside a
# sentence; doing so during the fix started it again.
SECRET_KEY = "dev-only-not-a-secret"  # nosec B105
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# No proxy sits in front of runserver or the test client, so REMOTE_ADDR is the
# client and X-Forwarded-For must be ignored entirely. Stated rather than left
# unset: unset is not "no proxies", it is "trust the header", which is how the
# rate limit stopped counting. See the note in base.py.
REST_FRAMEWORK = REST_FRAMEWORK | {"NUM_PROXIES": 0}

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


# Where `pnpm dev` and the built site under `serve` listen. Named rather than
# left open, so a developer meets the same shape of failure locally that a
# misconfigured production would produce, instead of discovering CORS exists on
# the day of the deploy.
CORS_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://127.0.0.1:4173"]

# Cookies are allowed to travel here, because without that a developer cannot
# log in at all: localhost:3000 to 127.0.0.1:8000 is cross-site, and the
# browser drops a SameSite=Strict cookie there. Only for the three origins
# above. prod.py does not set this, and base.py explains why it does not need
# to there.
CORS_ALLOW_CREDENTIALS = True
AMPEER_COOKIE_SECURE = False
