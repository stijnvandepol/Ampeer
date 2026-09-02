"""The four routes, mounted under /api/advice/ by the root URL configuration.

Three answer a visitor and one answers the container runtime. Which of them
is allowed to skip the rate limit is pinned in tests/test_backend_settings.py.
"""

from __future__ import annotations

import math

from django.urls import URLPattern, path, re_path

from advice.models import TOKEN_BYTES
from advice.views import EstimateView, HealthView, RefineView, StoredAdviceView

#: secrets.token_urlsafe(n) emits base64url with the padding stripped, so
#: ceil(n * 8 / 6) characters: 22 for 16 bytes. Derived from the constant the
#: token is actually made with rather than written down again, because a
#: literal here that drifted from it would turn every stored link into a 404
#: while every test that makes its own token kept passing.
TOKEN_LENGTH = math.ceil(TOKEN_BYTES * 8 / 6)

urlpatterns: list[URLPattern] = [
    # Above the token route on purpose. `re_path` matches 22 url-safe
    # characters and `health` is eight, so this is not actually shadowed today,
    # but the ordering is the property being kept: a token pattern that ever
    # widens would otherwise swallow the readiness endpoint and the deploy
    # would go unhealthy for a reason nobody would look for here.
    path("health/", HealthView.as_view(), name="advice-health"),
    path("estimate/", EstimateView.as_view(), name="advice-estimate"),
    path("refine/", RefineView.as_view(), name="advice-refine"),
    # Matched narrowly rather than with <str:token>, so a malformed token is a
    # 404 from the router and never reaches the database at all.
    re_path(
        rf"^(?P<token>[A-Za-z0-9_-]{{{TOKEN_LENGTH}}})/$",
        StoredAdviceView.as_view(),
        name="advice-detail",
    ),
]
