"""The test environment.

Postgres, because the schema under test must be the schema that ships. An
in-memory SQLite would hide a whole class of fault, and this project exists to
have no invisible failure modes.
"""

from __future__ import annotations

from ampeer.settings.dev import *

DEBUG = False

# Throttling is live in tests. A separate local cache keeps one test's requests
# out of another's counter; tests/conftest.py clears it before each test.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ampeer-tests",
    }
}
