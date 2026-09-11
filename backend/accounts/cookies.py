"""The two cookies, set and cleared in exactly one place.

One place, because a cookie whose name, path or SameSite is written out at both
the setting view and the clearing view is a cookie that will eventually differ
between the two, and the symptom of that is a logout that leaves the visitor
logged in.
"""

from __future__ import annotations

from typing import Literal

from django.conf import settings
from rest_framework.response import Response
from rest_framework_simplejwt.settings import api_settings

#: Typed as a Literal, not left as `str`: `Response.set_cookie`'s `samesite`
#: parameter only accepts one of a fixed set of literals, and a bare `str`
#: does not narrow to that even when the value is this exact constant.
SAMESITE: Literal["Strict"] = "Strict"


def set_tokens(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        settings.AMPEER_ACCESS_COOKIE,
        access,
        # `settings.SIMPLE_JWT[...]` types as `object` to mypy, because the
        # dict mixes `timedelta`, `bool`, `tuple` and `str` values, so this
        # reads the same two lifetimes back through simplejwt's own already
        # `timedelta`-typed `api_settings` instead of casting.
        max_age=int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.AMPEER_COOKIE_SECURE,
        samesite=SAMESITE,
        path=settings.AMPEER_ACCESS_COOKIE_PATH,
    )
    response.set_cookie(
        settings.AMPEER_REFRESH_COOKIE,
        refresh,
        max_age=int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.AMPEER_COOKIE_SECURE,
        samesite=SAMESITE,
        path=settings.AMPEER_REFRESH_COOKIE_PATH,
    )


def clear_tokens(response: Response) -> None:
    """Deleting a cookie only works when the path matches the one it was set
    with, which is the quiet way a logout leaves a working session behind."""
    response.delete_cookie(
        settings.AMPEER_ACCESS_COOKIE,
        path=settings.AMPEER_ACCESS_COOKIE_PATH,
        samesite=SAMESITE,
    )
    response.delete_cookie(
        settings.AMPEER_REFRESH_COOKIE,
        path=settings.AMPEER_REFRESH_COOKIE_PATH,
        samesite=SAMESITE,
    )
