"""The JSON parser the public endpoints use.

DRF's JSONParser catches the errors json.load raises for malformed input and
turns them into a 400. It does not catch RecursionError, which json.load raises
for input that is well formed and too deeply nested, so `[` repeated two
hundred thousand times, a body of 200 kB, produced an instant 500 and an entry
in the error log for what is an ordinary bad request.

The depth is not configurable here on purpose. json.load recurses once per
level and the interpreter's own recursion limit is what stops it, so the limit
already exists; what was missing was the answer it produces.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

#: Dutch, because this reaches a caller. Advice sentences live in
#: ampeer_advice.nl keyed by rule id; this is a validation message, the same
#: category as the strings in serializers.py.
TOO_DEEPLY_NESTED = "de JSON is te diep genest"


class BoundedJSONParser(JSONParser):
    """JSONParser, with a body too deep to parse answered as a bad request."""

    def parse(
        self,
        stream: Any,
        media_type: str | None = None,
        parser_context: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError as exc:
            # Deliberately not chained into the response: ParseError renders its
            # own message and the traceback of a two hundred thousand frame
            # recursion is not something to put in a log line.
            raise ParseError(TOO_DEEPLY_NESTED) from exc
