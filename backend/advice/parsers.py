"""The JSON parser the public endpoints use.

DRF's JSONParser catches the errors json.load raises for malformed input and
turns them into a 400. It does not catch RecursionError, which json.load raises
for input that is well formed and too deeply nested, so `[` repeated two
hundred thousand times, a body of 200 kB, produced an instant 500 and an entry
in the error log for what is an ordinary bad request.

The depth is not configurable here on purpose. json.load recurses once per
level and the interpreter's own recursion limit is what stops it, so the limit
already exists; what was missing was the answer it produces.

No Dutch is written here. The sentence a caller reads lives in ``advice.nl``
under ``TOO_DEEPLY_NESTED``, which is the same table the serializers name and
for the same reason: this is a validation message rather than an advice, so
``ampeer_advice.nl`` cannot hold it. It sat in this file as a module constant
until 2026-08-27, and the scan that was meant to stop that read
advice/serializers.py by name, so a second module holding Dutch was never
looked at. tests/test_advice_serializers.py now reads every module in this
package.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser

from advice.nl import message_for


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
            raise ParseError(message_for("TOO_DEEPLY_NESTED")) from exc
