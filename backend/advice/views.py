"""Three endpoints, anonymous, no cookie, no session.

There is nothing to log in to, so there is nothing to steal from a session and
nothing for a cross-site request to abuse: both POSTs are anonymous and change
nothing that belongs to anyone.
"""

from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from advice.models import StoredAdvice
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
