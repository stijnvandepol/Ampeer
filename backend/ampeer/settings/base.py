"""Settings shared by every environment.

Nothing here reads an environment variable that decides a security property.
Those live in prod.py, where a missing value stops the process instead of
falling back to something permissive.
"""

from __future__ import annotations

import os
from pathlib import Path

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

REST_FRAMEWORK = {
    # Anonymous by design. There is no account to authenticate.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
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
