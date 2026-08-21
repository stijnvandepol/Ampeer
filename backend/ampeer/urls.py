"""Root URL configuration."""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/advice/", include("advice.urls")),
]
