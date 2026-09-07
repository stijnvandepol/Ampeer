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
# turns this on so a developer's browser accepts the answers to the accounts
# calls it makes from 127.0.0.1:3000 to 127.0.0.1:8000, which is a different
# origin because the port differs; inheriting that
# convenience here would make tests/test_advice_api.py's assertion that no
# advice response carries Access-Control-Allow-Credentials untrue, since
# django-cors-headers applies this setting to every response, not only the
# accounts ones. tests/test_backend_settings.py asserts that dev.py's own
# line still says True, so deleting it here cannot silently break developer
# login under a fully green suite.
CORS_ALLOW_CREDENTIALS = False

# Pinned back to memory for the reason DEBUG, CACHES and CORS_ALLOW_CREDENTIALS
# are pinned above: this file inherits dev.py, and dev.py chooses the file
# transport so a developer can open a mail from data/mail/. Inherited here
# that would fill data/mail/ on every run and leave mailer.MEMORY.sent empty,
# so every command test would read nothing and say so. The suite never
# reaches the network, and tests/test_accounts_mail.py asserts the value that
# actually arrives here rather than the one dev.py sets.
AMPEER_MAIL_TRANSPORT = "memory"
