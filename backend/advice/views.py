"""Three endpoints, anonymous, no cookie, no session.

There is nothing to log in to, so there is nothing to steal from a session and
nothing for a cross-site request to abuse: both POSTs are anonymous and change
nothing that belongs to anyone.

A cookie identity does exist since phase 1, in `accounts/views.py`, and these
three routes stay outside its reach on purpose: the calculator is anonymous
whether or not the caller happens to be signed in.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from advice.models import DailyCounter, StoredAdvice
from advice.profiles import profile_provider
from advice.serializers import EstimateInputSerializer, RefineInputSerializer
from advice.service import compute_and_store

#: Every response here describes one household: its consumption, its roof and
#: what its energy costs. A shared proxy that kept a copy would hand the next
#: caller on that address somebody else's figures, and `private` alone still
#: permits a browser cache on a shared machine. `no-store` is the only value
#: that says keep nothing. Set on error responses too, because a 400 echoes the
#: rejected answers back.
CACHE_CONTROL = "private, no-store"


class _NoStoreAPIView(APIView):
    """An APIView whose responses are never written down anywhere in between."""

    def finalize_response(
        self, request: Request, response: Response, *args: Any, **kwargs: Any
    ) -> Response:
        finalized: Response = super().finalize_response(request, response, *args, **kwargs)
        finalized["Cache-Control"] = CACHE_CONTROL
        return finalized


class _ComputeView(_NoStoreAPIView):
    """Shared body of the two POST endpoints."""

    throttle_scope = "advice-compute"
    serializer_class: ClassVar[type[EstimateInputSerializer]] = EstimateInputSerializer

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload: dict[str, Any] = compute_and_store(
            dict(serializer.validated_data), self.serializer_class.QUESTION_COUNT
        )
        return Response(payload, status=status.HTTP_201_CREATED)


class EstimateView(_ComputeView):
    serializer_class: ClassVar[type[EstimateInputSerializer]] = EstimateInputSerializer


class RefineView(_ComputeView):
    serializer_class: ClassVar[type[EstimateInputSerializer]] = RefineInputSerializer


class StoredAdviceView(_NoStoreAPIView):
    throttle_scope = "advice-read"

    def get(self, request: Request, token: str) -> Response:
        stored = StoredAdvice.get_live(token)
        if stored is None:
            # An unknown token and an expired one answer identically. Telling a
            # caller that a token used to exist tells them something.
            return Response(status=status.HTTP_404_NOT_FOUND)
        advice: dict[str, Any] = stored.advice
        return Response(advice)


class HealthView(APIView):
    """Is this container able to answer, not merely alive.

    It opens the consumption profile, because that is the one thing a wrong
    mount breaks and the one thing nothing else notices: the settings require
    the path to be set, not the file to exist, and the provider is only called
    when an advice is computed. Without this a misconfigured deploy reports
    healthy and fails every visitor.

    It does no arithmetic and issues no query. A check that runs every thirty
    seconds and does real work is a load generator with a nice name, and the
    throttle is switched off here for the same reason: in production its
    counter lives in Postgres, so leaving it on would turn this check into the
    database query it exists to avoid.
    """

    throttle_classes: Sequence[type[BaseThrottle]] = ()

    def get(self, request: Request) -> Response:
        try:
            profile_provider()
        except RuntimeError:
            # Deliberately without the reason. This endpoint is unauthenticated
            # and reachable wherever the service is; a path on disk is not
            # something to hand out.
            return Response({"status": "unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "ok"})


class CountView(_NoStoreAPIView):
    """One increment of one named counter, and no answer worth reading.

    Deliberately the smallest public write in this repository. It takes a name
    out of a fixed list, adds one to today's row, and returns 204 with no body.
    It stores no address, no session, no identifier and nothing derived from
    one, so there is no record here that belongs to anybody.

    The name is checked against `DailyCounter.CLIENT_NAMES` rather than against
    a pattern, so a caller cannot open a new column of behaviour by inventing a
    string, and a typo in the frontend fails loudly instead of quietly counting
    into a name nobody reads. The outcome counters are not in that set on
    purpose: they are written by the server from what it decided, so the one
    distribution this product would be tempted to flatter cannot be moved from
    outside.

    Refusing an unknown name with 400 rather than ignoring it is the choice
    that makes the frontend's own tests able to fail.
    """

    throttle_scope = "advice-count"

    def post(self, request: Request) -> Response:
        name = request.data.get("name") if isinstance(request.data, dict) else None
        if not isinstance(name, str) or name not in DailyCounter.CLIENT_NAMES:
            # English, and that is not an oversight. Nothing renders this: the
            # browser silences every failure of this call on purpose, because a
            # counter that can break the form it measures is worse than no
            # counter. So the only reader is a developer holding a response,
            # and the language rule sends Dutch a visitor reads to nl.py and
            # leaves English an operator reads where it is.
            return Response({"detail": "unknown counter name"}, status=status.HTTP_400_BAD_REQUEST)
        DailyCounter.bump(name)
        return Response(status=status.HTTP_204_NO_CONTENT)
