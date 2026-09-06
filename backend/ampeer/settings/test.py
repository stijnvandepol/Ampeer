"""The test environment.

Postgres, because the schema under test must be the schema that ships. An
in-memory SQLite would hide a whole class of fault, and this project exists to
have no invisible failure modes.
"""

from __future__ import annotations

from ampeer.settings.dev import *

DEBUG = False

# NUM_PROXIES = 0 arrives from dev.py above and is stated there, not restated
# here: two literals that must agree are one that eventually will not. Zero is
# what makes the spoofing test in tests/test_advice_api.py meaningful, because
# the test client sends a fixed REMOTE_ADDR and the rotating X-Forwarded-For it
# adds must count for nothing. tests/test_backend_settings.py asserts the value
# that actually arrives here, so the inheritance is checked rather than assumed.

# Throttling is live in tests. A separate local cache keeps one test's requests
# out of another's counter; tests/conftest.py clears it before each test.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ampeer-tests",
    }
}

# Pinned back to False for the same reason DEBUG and CACHES are pinned above:
# the schema and settings under test have to be the ones that ship. dev.py
# turns this on so a developer's browser can carry the accounts cookies across
# localhost:3000 to 127.0.0.1:8000, which is cross-site; inheriting that
# convenience here would make tests/test_advice_api.py's assertion that no
# advice response carries Access-Control-Allow-Credentials untrue, since
# django-cors-headers applies this setting to every response, not only the
# accounts ones. tests/test_backend_settings.py asserts that dev.py's own
# line still says True, so deleting it here cannot silently break developer
# login under a fully green suite.
CORS_ALLOW_CREDENTIALS = False
