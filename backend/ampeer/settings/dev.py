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
#
# http://localhost:3000 stood here until 2026-09-07 and could never hold a
# session, so allowing it only moved the failure somewhere harder to read. A
# cookie belongs to a SITE, and localhost and 127.0.0.1 are two different
# sites: a page served from localhost:3000 is not sent the SameSite=Strict
# session cookie that was set for 127.0.0.1, and the csrftoken cookie carries
# no Domain attribute, which makes it host-only and equally out of reach.
# Neither of those is a CORS question, so Access-Control-Allow-Credentials
# does not reach either one. A developer opens 127.0.0.1:3000.
CORS_ALLOWED_ORIGINS = ["http://127.0.0.1:3000", "http://127.0.0.1:4173"]

# Cookies are allowed to travel here because both origins above are a
# different PORT from the API on 8000, which makes every request from them
# cross-origin: without this the browser refuses the response to a request
# sent with credentials, so the session never gets used even though the
# cookie itself was willing to travel. A port is not part of a site, which is
# why staying on 127.0.0.1 is what makes that cookie willing. Only for the two
# origins above. prod.py does not set this, and base.py explains why it does
# not need to there.
CORS_ALLOW_CREDENTIALS = True
AMPEER_COOKIE_SECURE = False

# Two more things a cross-port developer setup needs and production does not,
# found on 2026-09-07 by the first person to register from a real browser at
# 127.0.0.1:3000 against 127.0.0.1:8000. The e2e specs answer their own
# preflights and the stack smoke sends a production shaped Origin, so neither
# had ever exercised this path. First: the account client sends X-CSRFToken on
# every unsafe request, and a preflight that does not name that header makes
# the browser drop the request before it leaves. base.py keeps the list to
# content-type because the advice API needs nothing else; the account API
# does, and only across ports. Second: Django's CSRF check compares the Origin
# header with the request's own host, so an Origin on port 3000 against a
# host on port 8000 is refused unless it is trusted here. Both
# lists are the same two origins on purpose: a third place to list them is
# a third place for one of them to be forgotten.
CORS_ALLOW_HEADERS = [*CORS_ALLOW_HEADERS, "x-csrftoken"]
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# A developer reads the mail as a file under data/mail/, which .gitignore
# already keeps out of the tree along with the rest of data/.
AMPEER_MAIL_TRANSPORT = "file"
