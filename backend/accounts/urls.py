"""The account routes, mounted under /api/auth/ by the root URL configuration.

Which of them may skip the rate limit: none. tests/test_backend_settings.py
walks the resolver and fails on any view here without a scope that has a rate.
"""

from __future__ import annotations

from django.urls import URLPattern, path

from accounts.views import (
    ConsentView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RegisterView,
)

urlpatterns: list[URLPattern] = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("consent/", ConsentView.as_view(), name="auth-consent"),
]
