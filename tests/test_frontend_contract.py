"""The frontend's fixture must stay a true description of the API's answer.

Two codebases sharing a JSON shape with no shared check is the classic way a
frontend ends up quietly showing something the backend did not mean. The
frontend builds against a committed fixture; this asserts the fixture is still
what the real renderer produces, structurally.

Values are deliberately not compared. They move whenever the model is
corrected, and pinning them here would make an honest model change look like a
frontend failure. What must not move without somebody noticing is the shape.

This runs inside the existing Python `test` job. It needs no server, no browser
and no Node, and it fails on the side where the response is produced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "advice-response.json"
TYPES = REPO_ROOT / "frontend" / "src" / "lib" / "types.ts"


def _shape(node: Any) -> Any:
    """The structure of a value with every leaf replaced by its type name."""
    if isinstance(node, dict):
        return {key: _shape(value) for key, value in sorted(node.items())}
    if isinstance(node, list):
        return [_shape(node[0])] if node else []
    return type(node).__name__


def _payload() -> Any:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_the_fixture_matches_what_the_renderer_produces() -> None:
    """Regenerate the fixture when this fails; do not edit it by hand.

    `uv run --no-sync python tests/helpers/advice_fixture.py` rewrites it
    through the same function this test calls.
    """
    from helpers.advice_fixture import build_reference_payload

    live = _shape(build_reference_payload())
    committed = _shape(_payload())
    assert live == committed, "the API response shape changed; regenerate the fixture"


def test_every_amount_crosses_the_wire_as_a_string() -> None:
    """JSON has floats and no decimals, so an amount that goes through a JSON
    number is rounded by whichever parser touches it last."""
    payload = _payload()
    offenders: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"p10", "p50", "p90", "low", "mid", "high"} and not isinstance(
                    value, str
                ):
                    offenders.append(f"{path}.{key} is {type(value).__name__}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload, "")
    assert not offenders, offenders


def test_the_typescript_types_name_every_key_the_response_has() -> None:
    """A field the API adds and the types do not know about is a field the
    frontend will never show, silently.

    Every key at every depth, not only the top level. A field added inside the
    battery block is exactly as invisible as one added beside `token`, and a
    check that only reads the outermost object would let it through.
    """
    declared = TYPES.read_text(encoding="utf-8")
    missing: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if f"readonly {key}:" not in declared:
                    missing.append(f"{path}.{key}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(_payload(), "")
    assert not missing, f"types.ts does not declare: {sorted(set(missing))}"


def test_the_fixture_token_is_a_token_the_api_could_have_issued() -> None:
    """The fixture is what the frontend builds and tests against.

    A token of the wrong length is the quietest possible defect here: the shape
    check above compares types, and a string is a string whatever its length,
    so the fixture and the API agreed on everything except the one value the
    router matches on. The end-to-end tests would then reject their own fixture
    before reaching the page they were written to check, and the failure would
    read as a frontend bug rather than as a fixture that was never valid.

    Found on 2026-08-21 by the lane that wrote the API client, which validates
    the token shape before making a request and could not use its own fixture.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    from advice.urls import TOKEN_LENGTH

    token = json.loads(FIXTURE.read_text(encoding="utf-8"))["token"]
    assert len(token) == TOKEN_LENGTH, (
        f"the fixture token is {len(token)} characters and the API issues {TOKEN_LENGTH}"
    )
    assert re.fullmatch(r"[A-Za-z0-9_-]+", token), token
