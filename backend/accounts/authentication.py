"""Reading the identity out of a cookie, and only out of a cookie.

Not out of an `Authorization` header, in either direction. A second accepted
place for a credential is a second place it can leak from, and a header reaches
a proxy log more easily than a cookie does. That is the same argument
docs/dpia.md chapter 8 makes about the advice token sitting in the path.
"""

from __future__ import annotations

from typing import Any, NoReturn

from django.conf import settings
from django.http import HttpRequest
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.nl import NL

#: The methods that change nothing, so they need no CSRF token. Same set Django
#: and DRF use, written out here so this file does not depend on which of the
#: two happens to be imported.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _never_called_get_response(_request: HttpRequest) -> NoReturn:
    """`CSRFCheck` never actually calls this during `process_request` or
    `process_view`; it exists only because `CsrfViewMiddleware.__init__`
    requires a `get_response` callable. `NoReturn` is the honest annotation
    for a function that only ever raises. Module level, not a closure inside
    `enforce_csrf`, specifically so a test can call it directly and assert
    that it does raise, rather than leaving that claim unverified."""
    raise AssertionError("_never_called_get_response is never called")


def _never_called_callback(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Likewise never invoked: `process_view` only inspects the request, it
    does not call the view callback it is handed."""
    raise AssertionError("_never_called_callback is never called")


def enforce_csrf(request: HttpRequest | Request) -> None:
    """Django's own CSRF machinery, on a view DRF has already exempted.

    DRF wraps every `APIView` in `csrf_exempt`, so nothing here is protected
    unless it asks. This is DRF's own `SessionAuthentication.enforce_csrf` with
    one change: the message a visitor reads is Dutch and comes from nl.py.

    SameSite=Strict is the first defence and in this deployment very nearly the
    whole one. This is the second, and it costs one function.
    """
    check = CSRFCheck(_never_called_get_response)
    check.process_request(request)
    reason = check.process_view(request, _never_called_callback, (), {})
    if reason:
        raise PermissionDenied(NL["csrf_failed"])


class CookieJWTAuthentication(JWTAuthentication):
    """The access token, from the cookie, with a CSRF check on anything unsafe."""

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        raw = request.COOKIES.get(settings.AMPEER_ACCESS_COOKIE)
        if not raw:
            return None
        validated = self.get_validated_token(raw.encode())
        user = self.get_user(validated)
        if request.method not in SAFE_METHODS:
            enforce_csrf(request)
        return user, validated

    def authenticate_header(self, request: Request) -> str:
        """Present so DRF answers 401 and not 403 to somebody who is not logged
        in. Without a header DRF cannot tell "you did not authenticate" from
        "you may not do this", and the frontend needs the difference to know
        whether to show a login form."""
        return 'Cookie realm="api"'
