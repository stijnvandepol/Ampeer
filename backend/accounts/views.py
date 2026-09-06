"""The account routes. Nine of them, and only `get` and `post` among them.

That is not a workaround for a test. docs/dpia.md chapter 7 describes an API
that reads and computes, and says that rectification adds a row rather than
changing one, so a PUT or a PATCH here would make the chapter wrong in the
direction that matters most. Withdrawing a consent is a new row, and deleting an
account needs a body, which is the other half of the reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import ceil
from typing import Any, NoReturn

from django.conf import settings
from django.contrib.auth import authenticate
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
)
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError

from accounts import cookies, service, tokens
from accounts.authentication import CookieJWTAuthentication, enforce_csrf
from accounts.models import Consent, User
from accounts.nl import CONSENT_TEXT_VERSION, NL
from accounts.serializers import ConsentSerializer, LoginSerializer, RegisterSerializer
from advice.models import AuditEvent
from advice.views import _NoStoreAPIView


class _AuthAPIView(_NoStoreAPIView):
    """Every route under /api/auth/, with the two things they all share.

    `Cache-Control: private, no-store` comes from the base class, because each
    of these answers describes one household.

    The CSRF cookie is set in `finalize_response` and not in a view body, and
    that placement is load bearing. DRF answers an unauthenticated request to a
    view with `IsAuthenticated` before the handler runs, so a cookie set inside
    `me/` would never reach the one person who needs it, namely somebody about
    to log in. `finalize_response` also runs for the response `handle_exception`
    produces, so the cookie rides along on the 401 as well.
    """

    #: Tuples, not lists: a mutable list literal as a class attribute default
    #: is one instance away from two views sharing and mutating the same list,
    #: and `APIView` itself declares both as plain instance attributes rather
    #: than `ClassVar`, so annotating either as `ClassVar` here would be a real
    #: mypy error ("cannot override instance variable with class variable"),
    #: not a false positive to silence. Annotated with the same broad,
    #: `Sequence`-of-a-type shape `rest_framework-stubs` gives `APIView` itself,
    #: rather than left for mypy to infer: an inferred type narrows to the
    #: single tuple literal on this line, and a subclass assigning a
    #: differently shaped (but equally valid) tuple would then fail to
    #: override it.
    authentication_classes: Sequence[type[BaseAuthentication]] = (CookieJWTAuthentication,)
    permission_classes: Sequence[type[BasePermission]] = (IsAuthenticated,)

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        get_token(request)
        return super().finalize_response(request, response, *args, **kwargs)

    def throttled(self, request: Request, wait: float | None) -> NoReturn:
        # DRF's Dutch catalogue carries no translation for the throttle
        # message, so under nl-nl the default detail is English. The
        # sentence a refused visitor reads is ours, from nl.py, like
        # password_too_short. `wait` is what DRF computed; it is also what
        # sets Retry-After, so the number on screen and in the header agree.
        #
        # `Throttled.__init__` appends its own English "Expected available in
        # N seconds." to whatever `detail` it is given, whenever `wait` is
        # not `None`, regardless of whether that `detail` came from us. So
        # `wait` is never passed into the constructor: `seconds` is derived
        # here, the same way DRF derives it (`math.ceil`), and the exception
        # is built with only our sentence as `detail`.
        seconds = ceil(wait) if wait is not None else None
        detail = (
            NL["throttled"] % {"seconds": seconds}
            if seconds is not None
            else NL["throttled_unknown_wait"]
        )
        exc = Throttled(detail=detail)
        # `exception_handler` reads `exc.wait` back to build `Retry-After`;
        # the rest_framework-stubs omit the attribute even though the
        # runtime class sets it, so mypy does not know it exists here either.
        exc.wait = seconds  # type: ignore[attr-defined]
        raise exc

    def get_authenticate_header(self, request: Request) -> str:
        """The `WWW-Authenticate` header DRF asks for before answering a
        401, independent of `authentication_classes`.

        `APIView.get_authenticate_header` reads this off the first configured
        authenticator and returns `None` when that list is empty, and
        `handle_exception` downgrades every `AuthenticationFailed` and
        `NotAuthenticated` to a 403 whenever this method answers `None`.
        `RegisterView`, `LoginView` and `RefreshView` all set
        `authentication_classes = ()` on purpose, so without this override
        `test_a_wrong_password_says_the_same_thing_as_an_unknown_address` and
        `test_refreshing_without_a_refresh_cookie_is_refused` would both read
        403, "you are not allowed", for a caller who is doing exactly what
        this route is for and simply getting it wrong.
        """
        return CookieJWTAuthentication().authenticate_header(request)

    @property
    def user(self) -> User:
        """`self.request.user`, narrowed to what it actually is here.

        drf-stubs types `Request.user` as `AbstractBaseUser | AnonymousUser`,
        which is the right type for a view an anonymous caller may reach and
        the wrong one for everything under this base class: `IsAuthenticated`
        has already refused the request by the time a handler runs, so
        `CookieJWTAuthentication.authenticate` returned this project's own
        `User`. Reading `.email`, `.pk` or `.check_password` straight off
        `request.user` is an `attr-defined` error under `mypy --strict`; this
        property is the one place that narrowing happens, instead of at every
        call site.

        A `NotAuthenticated` raise here, not a bare `assert`: `python -O`
        strips `assert` statements, and with `REST_FRAMEWORK["UNAUTHENTICATED_USER"]
        = None`, the stripped version would return `None` typed as `User`
        rather than fail loudly. `LogoutView` is on `IsAuthenticated` so this
        branch is unreachable there today, but `_AuthAPIView` is the base
        every later authenticated view inherits, and three of this task's own
        subclasses (`RegisterView`, `LoginView`, `RefreshView`) are `AllowAny`
        with `self.user` still available to a handler that reaches for it by
        mistake.
        """
        if not isinstance(self.request.user, User):
            raise NotAuthenticated(NL["not_signed_in"])
        return self.request.user


class RegisterView(_AuthAPIView):
    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-register"

    def post(self, request: Request) -> Response:
        # Explicitly, because there is no cookie yet and the authentication class
        # that would have done it does not run. Login CSRF is the attack: it puts
        # a visitor into an account somebody else controls.
        enforce_csrf(request)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.create_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        AuditEvent.record(AuditEvent.ACCOUNT_CREATED, user_id=user.pk)
        for kind in serializer.granted_kinds:
            Consent.record(user, kind, Consent.GRANTED)
            AuditEvent.record(AuditEvent.CONSENT_GRANTED, user_id=user.pk, kind=kind)
        access, refresh = tokens.issue(user)
        AuditEvent.record(AuditEvent.LOGIN_SUCCEEDED, user_id=user.pk)
        response = Response(status=status.HTTP_201_CREATED)
        cookies.set_tokens(response, access, refresh)
        return response


class LoginView(_AuthAPIView):
    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-login"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        # `authenticate` runs AxesStandaloneBackend first, so a locked out
        # attempt never reaches ModelBackend and never checks a password.
        #
        # `request._request` and not `request`: axes forwards this straight to
        # `AXES_CLIENT_IP_CALLABLE`, which is `accounts.lockout.client_ip`, and
        # that wraps its argument in a fresh `rest_framework.request.Request`.
        # `Request.__init__` asserts its argument is a `django.http.HttpRequest`
        # and raises on being handed a `Request` a second time, which is exactly
        # what DRF's own `request` here is. The unwrap belongs at this call site
        # and not inside `lockout.py`: that module is shared with the Django
        # admin login form, which never has a DRF `Request` to unwrap in the
        # first place.
        user = authenticate(
            request._request,
            username=email,
            password=serializer.validated_data["password"],
        )
        if user is None:
            # The audit line carries the user id when the account exists and
            # nothing identifying when it does not. Never the address that was
            # tried: that would be the address of somebody who may not even be a
            # customer, in a table with no retention.
            existing = User.objects.filter(email=email).values_list("pk", flat=True).first()
            AuditEvent.record(AuditEvent.LOGIN_FAILED, user_id=existing)
            # One answer for a wrong password and for an unknown address.
            raise AuthenticationFailed(NL["credentials_invalid"])
        AuditEvent.record(AuditEvent.LOGIN_SUCCEEDED, user_id=user.pk)
        access, refresh = tokens.issue(user)
        response = Response(status=status.HTTP_200_OK)
        cookies.set_tokens(response, access, refresh)
        return response


class RefreshView(_AuthAPIView):
    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-refresh"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        raw = request.COOKIES.get(settings.AMPEER_REFRESH_COOKIE)
        if not raw:
            raise AuthenticationFailed(NL["not_signed_in"])
        try:
            access, refresh = tokens.rotate(raw)
        except (tokens.TokenReuse, TokenError) as error:
            # Every failure here ends the session rather than leaving a half
            # usable one behind, and the cookies go with it. `rotate` has already
            # revoked the whole chain when the cause is reuse; this only reports
            # it. Two exception types and not a bare `except`, so a bug inside
            # `rotate` surfaces as a 500 instead of being answered as if the
            # visitor's token were the problem.
            AuditEvent.record(AuditEvent.LOGIN_FAILED, reused=isinstance(error, tokens.TokenReuse))
            response = Response(
                {"detail": NL["session_expired"]}, status=status.HTTP_401_UNAUTHORIZED
            )
            cookies.clear_tokens(response)
            return response
        response = Response(status=status.HTTP_200_OK)
        cookies.set_tokens(response, access, refresh)
        return response


class ConsentTextsView(_AuthAPIView):
    """The sentences a household agrees to, and the version they are agreed under.

    Public, because the registration form may not be shown until it has them:
    a `true` sent for a sentence nobody read is not consent. On `auth-read`
    rather than a scope of its own, for the same reason `me/` is: this is a
    call at the start of a page load, and 120 an hour is the measure for that.
    A seventh `auth` rate for an answer that touches no database and is the
    same for everybody would be a number nobody derived from anything.

    The view composes nothing and formats nothing. The keys are
    `sorted(Consent.KINDS)` under both `texts` and `labels`, and the values
    are `NL["CONSENT_" + kind]` and `NL["CONSENT_LABEL_" + kind]`, literally,
    which is what makes the sentence on the screen and the sentence behind
    the recorded version the same string.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-read"

    def get(self, request: Request) -> Response:
        return Response(
            {
                "text_version": CONSENT_TEXT_VERSION,
                "texts": {kind: NL[f"CONSENT_{kind}"] for kind in sorted(Consent.KINDS)},
                "labels": {kind: NL[f"CONSENT_LABEL_{kind}"] for kind in sorted(Consent.KINDS)},
            }
        )


class MeView(_AuthAPIView):
    """Who is logged in, and what they have said yes to.

    The one route a frontend with httpOnly cookies has to call to know whether
    anybody is logged in at all, which is why it is also where the CSRF cookie
    is picked up on the way to the login form.
    """

    throttle_scope = "auth-read"

    def get(self, request: Request) -> Response:
        return Response(
            {
                "email": self.user.email,
                "consents": {
                    kind: Consent.current(self.user, kind) for kind in sorted(Consent.KINDS)
                },
            }
        )


class ConsentView(_AuthAPIView):
    """Give or withdraw one consent. A POST, because a withdrawal adds a row.

    A PATCH would be the shape that changes one, and docs/dpia.md chapter 7 says
    this API does not do that. It is also the wrong shape for the thing itself:
    the history of a consent is what makes it demonstrable.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        serializer = ConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        action = serializer.validated_data["action"]
        Consent.record(self.user, kind, action)
        AuditEvent.record(
            AuditEvent.CONSENT_GRANTED
            if action == Consent.GRANTED
            else AuditEvent.CONSENT_WITHDRAWN,
            user_id=self.user.pk,
            kind=kind,
        )
        return Response({"kind": kind, "granted": Consent.current(self.user, kind)})


class LogoutView(_AuthAPIView):
    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        raw = request.COOKIES.get(settings.AMPEER_REFRESH_COOKIE)
        if raw:
            try:
                tokens.revoke(raw)
            except TokenError:
                pass
        AuditEvent.record(AuditEvent.LOGOUT, user_id=self.user.pk)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        cookies.clear_tokens(response)
        return response


class ExportView(_AuthAPIView):
    """A POST and not a GET, for two reasons that both outweigh the convention.

    It writes a DATA_EXPORTED line, and a GET with a side effect is a GET a
    browser or a proxy may repeat. And the answer describes one household in
    full, so it has to fall under `Cache-Control: private, no-store`, which the
    base class already applies.
    """

    throttle_scope = "auth-export"

    def post(self, request: Request) -> Response:
        payload = service.export_account(self.user)
        AuditEvent.record(AuditEvent.DATA_EXPORTED, user_id=self.user.pk)
        return Response(payload)


class DeleteView(_AuthAPIView):
    """Remove the account, on a POST rather than a DELETE.

    Two reasons. This is the one genuinely destructive act in the whole API,
    and docs/dpia.md chapter 7 commits to an API where rectification adds a
    row rather than changing one, so keeping DELETE, PUT and PATCH absent
    everywhere else stays exact only if the one exception rides on a verb the
    document already allows. And this route needs a body, the password, to
    prove the caller still is who the session says: a DELETE with a body is
    something proxies and clients disagree about.

    `CookieJWTAuthentication` already calls `enforce_csrf()` on every unsafe
    method, so this does not call it a second time.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        password = request.data.get("password") if isinstance(request.data, dict) else None
        if not isinstance(password, str) or not self.user.check_password(password):
            raise PermissionDenied(NL["credentials_invalid"])
        service.delete_account(self.user)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        cookies.clear_tokens(response)
        return response
