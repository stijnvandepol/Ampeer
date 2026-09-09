"""Root URL configuration."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, include, path

from accounts.views import MeterReadingsView

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/advice/", include("advice.urls")),
    path("api/auth/", include("accounts.urls")),
    # Outside /api/auth/ on purpose: no session comes with this call, a
    # household's own device does. tests/test_frontend_contract.py finds the
    # /api/auth/ prefix by the first `include("accounts.urls")` above, so this
    # route is named directly here rather than through a second include of
    # that same module.
    path("api/meter/readings/", MeterReadingsView.as_view(), name="meter-readings"),
]
