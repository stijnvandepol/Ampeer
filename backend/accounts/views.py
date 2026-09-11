"""The account routes. Thirteen of them, and only `get` and `post` among them.

That is not a workaround for a test. docs/dpia.md chapter 7 describes an API
that reads and computes, and says that rectification adds a row rather than
changing one, so a PUT or a PATCH here would make the chapter wrong in the
direction that matters most. Withdrawing a consent is a new row, and deleting an
account needs a body, which is the other half of the reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from math import ceil
from typing import Any, NoReturn, cast
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils.formats import date_format
from rest_framework import status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError

from accounts import cookies, recovery, service, tokens
from accounts.authentication import CookieJWTAuthentication, enforce_csrf
from accounts.calibration import as_payload, propose_correction
from accounts.meter import MeterTokenAuthentication, store_readings
from accounts.models import Consent, MeterLink, User
from accounts.nl import CONSENT_TEXT_VERSION, NL
from accounts.serializers import (
    ConsentSerializer,
    LoginSerializer,
    ReadingBatchSerializer,
    RegisterSerializer,
    ResetConfirmSerializer,
    ResetRequestSerializer,
    TokenSerializer,
    password_error_messages,
)
from advice.models import AuditEvent, StoredAdvice
from advice.serializers import RefineInputSerializer
from advice.service import compute_and_store
from advice.views import _NoStoreAPIView

#: Where a household reads a moment, against the UTC every moment is stored
#: in. CLAUDE.md states both halves of that split; this is the second one.
AMSTERDAM = ZoneInfo("Europe/Amsterdam")


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

    def permission_denied(
        self, request: Request, message: str | None = None, code: str | None = None
    ) -> NoReturn:
        """Answer in this project's own Dutch, not DRF's default catalogue.

        DRF's own version:

            def permission_denied(self, request, message=None, code=None):
                if request.authenticators and not request.successful_authenticator:
                    raise exceptions.NotAuthenticated()
                raise exceptions.PermissionDenied(detail=message, code=code)

        `NotAuthenticated()` with no detail reads DRF's Dutch catalogue, which
        carries no translation, so under nl-nl the sentence a stranger reads on
        every one of the six signed-in routes is English: "Authentication
        credentials were not provided." Every stub in the frontend and every
        e2e mock already answers with NL["not_signed_in"]'s own sentence
        (`describeAuthError` shows a 401 literally), so each of them disagreed
        with the real server until this override existed.

        The PermissionDenied branch below is not reached by any route today:
        DeleteView raises its own PermissionDenied(NL["credentials_invalid"])
        rather than calling this method, and no other view withholds a
        permission once a caller is authenticated. It stays here anyway,
        because a permission that starts checking something in a later cycle
        should not silently reach DRF's English "You do not have permission to
        perform this action." on the way in.
        """
        if request.authenticators and not request.successful_authenticator:
            raise NotAuthenticated(NL["not_signed_in"])
        raise PermissionDenied(NL["forbidden"] if message is None else message, code=code)

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
        # One mail per new account, within the minute: an outbox row, no
        # network here. Spec 3.4.
        recovery.request_email_verification(user)
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
                "email_verified_at": (
                    None
                    if self.user.email_verified_at is None
                    else self.user.email_verified_at.isoformat()
                ),
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
        with transaction.atomic():
            Consent.record(self.user, kind, action)
            AuditEvent.record(
                AuditEvent.CONSENT_GRANTED
                if action == Consent.GRANTED
                else AuditEvent.CONSENT_WITHDRAWN,
                user_id=self.user.pk,
                kind=kind,
            )
            # Withdrawing METER_LINK has to be exactly as thorough as
            # pressing "ontkoppel": a consent taken back with the readings
            # left in place would make withdrawal a weaker promise than
            # revoking the link directly.
            if kind == Consent.METER_LINK and action == Consent.WITHDRAWN:
                service.unlink_meter(self.user)
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


class ResetRequestView(_AuthAPIView):
    """Ask for a reset link, and learn nothing from the answer.

    202 with an empty object for every well-formed address, known or not,
    active or not: a 202 and a 404 would be an address book that can be read
    at ten requests an hour. No mail leaves in this request and no token is
    minted; a known address costs one INSERT more than an unknown one, which
    is under the noise of a database round trip.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-reset"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = ResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recovery.request_password_reset(serializer.validated_data["email"])
        return Response({}, status=status.HTTP_202_ACCEPTED)


class ResetConfirmView(_AuthAPIView):
    """Set a new password with a link, and do not sign in.

    Token first, then the password: a bad token is one sentence under
    `token` for expired, spent, superseded and unknown alike, and a rejected
    password is the same list of sentences registration gives. 204 without
    cookies on purpose: `login/` stays the only place a session starts and
    `LOGIN_SUCCEEDED` is written, so the DPIA's sentence that every sign-in
    is a line stays true. Axes plays no part here, since nothing goes
    through `authenticate()`; the token's 256 bits and `auth-reset` do.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-reset"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = ResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recovery.confirm_password_reset(
                serializer.validated_data["token"], serializer.validated_data["password"]
            )
        except recovery.TokenInvalid as error:
            raise ValidationError({"token": [NL["token_invalid"]]}) from error
        except recovery.PasswordRejected as rejected:
            raise ValidationError(
                {"password": password_error_messages(rejected.error)}
            ) from rejected
        return Response(status=status.HTTP_204_NO_CONTENT)


class VerifyRequestView(_AuthAPIView):
    """Send the confirmation mail again. The one recovery route that needs a
    session, and therefore the one that needs no body. 202 whether or not a
    mail is written: an address already confirmed answers the same, because
    `me/` already says so and a 400 would be a second way to read it."""

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        recovery.request_email_verification(self.user)
        return Response({}, status=status.HTTP_202_ACCEPTED)


class VerifyConfirmView(_AuthAPIView):
    """Confirm an address with a link. Public, because the link is opened on
    whatever device the mail was read on, and a 401 would send a household
    to a sign-in form to prove what the link already proves."""

    authentication_classes: Sequence[type[BaseAuthentication]] = ()
    permission_classes: Sequence[type[BasePermission]] = (AllowAny,)
    throttle_scope = "auth-reset"

    def post(self, request: Request) -> Response:
        enforce_csrf(request)
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            recovery.confirm_email_verification(serializer.validated_data["token"])
        except recovery.TokenInvalid as error:
            raise ValidationError({"token": [NL["token_invalid"]]}) from error
        return Response(status=status.HTTP_204_NO_CONTENT)


def _amsterdam_label(moment: datetime) -> str:
    """One stored UTC moment, as the words a household in this country reads.

    CLAUDE.md: store in UTC, show in Europe/Amsterdam. `TIME_ZONE` is `UTC`
    because that is what storage needs, so the conversion is explicit here
    rather than inherited. `date_format` with `DATETIME_FORMAT` takes its
    month names from Django's own `nl` locale data under `LANGUAGE_CODE`,
    which keeps the Dutch out of this module: nothing here is a sentence
    this project wrote, so nothing here belongs in `nl.py`.
    """
    return date_format(moment.astimezone(AMSTERDAM), "DATETIME_FORMAT")


class MeterStatusView(_AuthAPIView):
    """Whether a household may link a meter, and what its link looks like today.

    A route of its own rather than a field on `me/`: adding one there would
    change the shape `frontend/src/lib/accounts.ts` already validates for
    that call, and this project would rather add a call than reshape one
    that already works.

    `last_seen_label` travels beside `last_seen_at` because the page may not
    build it. `.semgrep/frontend.yml`'s ampeer-no-reading-the-clock forbids
    `new Date(...)` in the frontend, and its own message says why and what to
    do instead: a date the visitor should see comes from the API, which
    computed it, and not from the machine the page happens to be rendered
    on. The rule reads as being about scarcity, a countdown subtracted from
    the clock, and this is only a formatted timestamp, but the remedy it
    names is the right one anyway: the browser's locale data decides nothing
    here, so two households do not read the same moment differently, and the
    ISO stays in the answer for anything that needs the value rather than
    the words.
    """

    throttle_scope = "auth-read"

    def get(self, request: Request) -> Response:
        link = MeterLink.active_for(self.user)
        seen = None if link is None else link.last_seen_at
        return Response(
            {
                "may_link": service.may_link_meter(self.user),
                "linked": link is not None,
                "created_at": None if link is None else link.created_at.isoformat(),
                "last_seen_at": None if seen is None else seen.isoformat(),
                "last_seen_label": None if seen is None else _amsterdam_label(seen),
            }
        )


class MeterLinkView(_AuthAPIView):
    """Mint a fresh key and hand it back exactly once.

    Nothing here composes the address the device pushes to: `push_path` is a
    fixed string and not a URL. This backend does not know the public origin
    it is deployed behind, and guessing would risk putting a wrong address in
    a device nobody revisits; the frontend already knows its own API base and
    builds the full address from that.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        if not service.may_link_meter(self.user):
            raise PermissionDenied(NL["meter_not_allowed"])
        link, raw = service.link_meter(self.user)
        return Response(
            {
                "token": raw,
                "push_path": "/api/meter/readings/",
                "created_at": link.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class MeterUnlinkView(_AuthAPIView):
    """Revoke the key and erase what it collected. 204 either way.

    Whether there was a link to revoke changes nothing about the answer: the
    result a caller sees, no meter linked, is the same either way, and a
    different status code here would only tell a caller something they did
    not ask.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        service.unlink_meter(self.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeterReadingsView(_NoStoreAPIView):
    """Where a household's own device pushes what its meter measured.

    `_NoStoreAPIView` and not `_AuthAPIView`: the cookie machinery that base
    class carries, the CSRF cookie set in `finalize_response`, is for a
    browser, and the caller here has none. `Cache-Control: private, no-store`
    is the one property of the base class this route still needs, since one
    answer here still describes one household.

    A missing or unresolvable key never reaches `post`: `IsAuthenticated` is
    what turns that into a 401, on `request.auth` as
    `MeterTokenAuthentication.authenticate` left it, so this handler is only
    ever entered with a real `MeterLink` to write into.
    """

    authentication_classes: Sequence[type[BaseAuthentication]] = (MeterTokenAuthentication,)
    permission_classes: Sequence[type[BasePermission]] = (IsAuthenticated,)
    throttle_scope = "meter-ingest"

    def post(self, request: Request) -> Response:
        # IsAuthenticated has already refused any request whose
        # authenticator did not return a link, so this cast states what is
        # already true rather than skipping a check that runs elsewhere.
        link = cast(MeterLink, request.auth)
        serializer = ReadingBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        stored, skipped = store_readings(link, serializer.validated_data["readings"])
        return Response({"stored": stored, "skipped": skipped}, status=status.HTTP_202_ACCEPTED)


class AccountAdviceView(_AuthAPIView):
    """An advice asked for through a session, which is what makes it theirs.

    The anonymous calculator is untouched and stays the ordinary way in. This
    route exists because two things need an account behind them: an advice that
    can carry an owner, and a correction that can only be proposed by reading
    this household's own meter.

    The body is the refine form's, unchanged. A household with an account
    answers the same nine questions as anybody else; what the account adds is
    who the answer belongs to and whether a meter has anything to say about it.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request) -> Response:
        serializer = RefineInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        payload = compute_and_store(data, RefineInputSerializer.QUESTION_COUNT, owner=self.user)

        # Asked after the advice, and not stored with it. The advice runs on
        # the figure the household typed; the proposal describes what their
        # meter says about that figure right now, which is a different
        # statement with a different lifetime.
        fit = propose_correction(self.user, data)
        payload["consumption_check"] = (
            None if fit is None else as_payload(fit, float(data["annual_consumption_kwh"]))
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class AccountAdviceAcceptView(_AuthAPIView):
    """Recompute one advice on the figure its owner accepted.

    The fit is run again here rather than read back from the proposal. Storing
    it would mean this route trusted a number written down earlier, and
    recomputing costs one fit on a route nobody takes twice while buying two
    things: the accepted figure is the current one, and a meter that has since
    stopped disagreeing says so instead of being overruled by its own older
    opinion.

    The lookup filters on the owner. `StoredAdvice.get_live` deliberately does
    not, because the shareable token has to keep opening an advice for whoever
    holds it, and that is exactly why it is not what this route uses.
    """

    throttle_scope = "auth-write"

    def post(self, request: Request, token: str) -> Response:
        stored = StoredAdvice.objects.filter(owner=self.user, token=token).first()
        if stored is None:
            raise NotFound(NL["advice_not_found"])

        data = dict(stored.inputs)
        fit = propose_correction(self.user, data)
        if fit is None:
            raise ValidationError(NL["consumption_correction_gone"])

        data["annual_consumption_kwh"] = fit.p50_kwh
        payload = compute_and_store(
            data,
            RefineInputSerializer.QUESTION_COUNT,
            owner=self.user,
            consumption_measured=True,
        )
        return Response(payload, status=status.HTTP_201_CREATED)
