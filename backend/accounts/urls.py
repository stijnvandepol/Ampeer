"""The account routes, mounted under /api/auth/ by the root URL configuration.

Which of them may skip the rate limit: none. tests/test_backend_settings.py
walks the resolver and fails on any view here without a scope that has a rate.
"""

from __future__ import annotations

from django.urls import URLPattern, path

from accounts.views import (
    ConsentTextsView,
    ConsentView,
    DeleteView,
    ExportView,
    LoginView,
    LogoutView,
    MeterLinkView,
    MeterStatusView,
    MeterUnlinkView,
    MeView,
    RefreshView,
    RegisterView,
    ResetConfirmView,
    ResetRequestView,
    VerifyConfirmView,
    VerifyRequestView,
)

urlpatterns: list[URLPattern] = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("consent/", ConsentView.as_view(), name="auth-consent"),
    path("consent-texts/", ConsentTextsView.as_view(), name="auth-consent-texts"),
    path("export/", ExportView.as_view(), name="auth-export"),
    path("delete/", DeleteView.as_view(), name="auth-delete"),
    path("reset/request/", ResetRequestView.as_view(), name="auth-reset-request"),
    path("reset/confirm/", ResetConfirmView.as_view(), name="auth-reset-confirm"),
    path("verify/request/", VerifyRequestView.as_view(), name="auth-verify-request"),
    path("verify/confirm/", VerifyConfirmView.as_view(), name="auth-verify-confirm"),
    path("meter/", MeterStatusView.as_view(), name="auth-meter"),
    path("meter/link/", MeterLinkView.as_view(), name="auth-meter-link"),
    path("meter/unlink/", MeterUnlinkView.as_view(), name="auth-meter-unlink"),
]
