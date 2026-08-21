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
    """The structure of a value with every leaf replaced by its type name.

    Every element of every list, not element zero. The first version of this
    returned ``[_shape(node[0])]``, so `routes[1]` and `routes[2]` were never
    compared at all: the whole STORAGE block, the four battery bands under it
    and the shape of every route after the first were outside the check. It
    also made a list's length invisible, so cutting `routes` from three to one
    and `curve` from five to one both left this test green while the frontend
    lost a third of the page. Lengths move when the model is corrected, and the
    instruction when that happens is the one in the test below: regenerate the
    fixture, do not edit it.
    """
    if isinstance(node, dict):
        return {key: _shape(value) for key, value in sorted(node.items())}
    if isinstance(node, list):
        return [_shape(item) for item in node]
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


def test_the_committed_fixture_is_byte_for_byte_what_the_generator_writes() -> None:
    """The fixture claims to be generated. This is what makes that true.

    The shape comparison above catches a response whose keys changed. It does
    not catch an edit to a value, because a hand-changed euro amount is still
    the same shape, and the frontend builds every one of its own tests against
    this file. A fixture somebody adjusted by hand to make a test pass is a
    description of a response that never existed, which is the whole reason
    tests/helpers/advice_fixture.py calls the real renderer.

    Bytes rather than parsed content, because the file is also in
    frontend/.prettierignore on the grounds that the generator is its author.
    That claim and this assertion are the same statement seen from two sides:
    if a formatter or an editor rewrites it, the generator is no longer its
    author and this fails.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from helpers.advice_fixture import build_reference_payload

    written = json.dumps(build_reference_payload(), indent=2, ensure_ascii=False) + "\n"
    committed = FIXTURE.read_text(encoding="utf-8")
    assert committed == written, (
        "frontend/tests/fixtures/advice-response.json is not what "
        "tests/helpers/advice_fixture.py produces. Regenerate it with\n"
        "    uv run python tests/helpers/advice_fixture.py\n"
        "rather than editing it, and do not run a formatter over it."
    )


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


# --------------------------------------------------------------------------
# The enums, paired.
#
# Nothing anywhere paired the Python enums with the TypeScript unions until
# 2026-08-21. `_shape` above maps every leaf to `type(node).__name__`, so
# `confidence`, `route`, `basis` and `verdict` all compare as `"str"`: adding a
# fourth Confidence member, renaming a route and adding a third sizing basis
# each kept every test in this repository green. A fourth confidence level also
# passes the pairing test in ampeer_advice, which only forces a Dutch label, and
# then in the browser `CONFIDENCE_TONE[confidence]` is undefined and the band
# loses the tone that encodes how sure the answer is.
#
# This is the same shape as the token length gap found earlier the same day,
# and larger: that one broke a fixture, this one breaks the page.
# --------------------------------------------------------------------------

TOKENS = REPO_ROOT / "frontend" / "src" / "design" / "tokens.ts"


def _declaration(source: str, anchor: str) -> str:
    """The text between an anchor and the semicolon that ends its declaration."""
    start = source.index(anchor) + len(anchor)
    end = source.index(";", start)
    return source[start:end]


def _quoted(source: str, anchor: str) -> list[str]:
    """Every double quoted literal in one declaration, in source order."""
    return re.findall(r'"([^"]*)"', _declaration(source, anchor))


def test_the_confidence_union_is_the_confidence_enum() -> None:
    from ampeer_advice.types import Confidence

    declared = _quoted(TYPES.read_text(encoding="utf-8"), "readonly confidence:")
    expected = [member.name for member in Confidence]
    assert declared == expected, f"types.ts declares {declared} and Confidence has {expected}"


def test_every_confidence_level_has_a_tone_in_the_frontend() -> None:
    """The consequence, checked where it lands rather than one step short.

    `CONFIDENCE_TONE` is an object literal in tokens.ts and the component reads
    it with the level off the API response. A level with no entry is
    `undefined`, which reaches CSS as `var(undefined)` and silently drops the
    tint that says how sure the answer is. tokens.ts says of itself that the
    map is exhaustive on purpose; this is what makes that true.
    """
    from ampeer_advice.types import Confidence

    body = _declaration(TOKENS.read_text(encoding="utf-8"), "export const CONFIDENCE_TONE =")
    toned = re.findall(r"^\s*([A-Z_]+):", body, re.MULTILINE)
    expected = [member.name for member in Confidence]
    assert toned == expected, f"CONFIDENCE_TONE covers {toned}, Confidence has {expected}"


def test_the_route_union_and_the_route_order_are_the_route_enum() -> None:
    """Both of them, because they are two copies of the same list.

    `ROUTE_ORDER` in types.ts is what e2e/rules.spec.ts checks the page against,
    so a route dropped from it takes the end to end proof of spec rule 3 with
    it: the page would render two routes and the test would expect two.
    """
    from ampeer_advice.types import Route

    source = TYPES.read_text(encoding="utf-8")
    expected = [member.name for member in Route]
    assert _quoted(source, "readonly route:") == expected
    assert _quoted(source, "export const ROUTE_ORDER =") == expected


def test_the_sizing_basis_union_is_every_basis_the_renderer_can_send() -> None:
    """The keys of SIZING_BASIS_TEXTS are the ids the renderer substitutes.

    A third basis would arrive with a Dutch sentence the reader never sees,
    because `BandlessFigure.basis` would not admit it exists.
    """
    from ampeer_advice.nl import SIZING_BASIS_TEXTS

    declared = _quoted(TYPES.read_text(encoding="utf-8"), "export type SizingBasis =")
    assert sorted(declared) == sorted(SIZING_BASIS_TEXTS), (
        f"types.ts declares {sorted(declared)} and nl.py has {sorted(SIZING_BASIS_TEXTS)}"
    )


def test_the_verdict_is_a_storage_rule_id() -> None:
    """`verdict` is deliberately a `string` in types.ts and not a union: it is a
    rule id, the frontend never renders it, and pinning the set here would make
    a new storage rule a frontend change.

    What can still be wrong is the fixture carrying a verdict that is not a
    storage rule at all, which would make every end to end test build its idea
    of the battery block on an id the API cannot produce.
    """
    from ampeer_advice.rules import RULES
    from ampeer_advice.types import Route

    storage = {rule.rule_id for rule in RULES if rule.route is Route.STORAGE}
    battery = _payload()["battery"]
    assert battery is not None, "the fixture no longer exercises the battery block"
    verdict = battery["verdict"]
    assert verdict in storage, f"{verdict} is not one of {sorted(storage)}"


def test_the_production_source_is_a_source_the_language_layer_knows() -> None:
    from ampeer_advice.nl import PRODUCTION_SOURCE_TEXTS

    source = _payload()["production_source"]
    assert source in PRODUCTION_SOURCE_TEXTS, f"{source} has no Dutch sentence in nl.py"


# --------------------------------------------------------------------------
# Structure the spec promises, asserted as structure rather than as a value.
# --------------------------------------------------------------------------


def test_the_fixture_carries_all_three_routes_in_the_order_the_api_sends() -> None:
    """Spec rule 3, on the side where the order is decided.

    e2e/rules.spec.ts checks that the page renders three routes, but it checks
    them against `ROUTE_ORDER` in the frontend and serves a fixture that would
    not have been regenerated if the API stopped sending one. Both copies could
    therefore agree on two routes while the API sent three.
    """
    from advice.rendering import ROUTE_ORDER

    sent = [route["route"] for route in _payload()["routes"]]
    assert sent == [route.name for route in ROUTE_ORDER]


def test_the_battery_curve_is_still_a_curve() -> None:
    """One point is not a curve, and the page draws a list of them.

    `_shape` compares the length now, so a curve that shrank fails there too;
    this says out loud what the minimum is, because the fixture is allowed to
    be regenerated and a regenerated one point curve would pass that check.
    """
    curve = _payload()["battery"]["curve"]
    assert len(curve) > 1, f"the curve has {len(curve)} point(s)"
    for capacity, band in curve:
        assert isinstance(capacity, (int, float))
        assert set(band) >= {"low", "mid", "high"}


def test_every_scenario_band_says_what_it_varied_and_what_it_pinned() -> None:
    """A band that does not say what it is a band over reads as though it
    covered everything, and the two lists are what stops that.

    Both are checked non empty, and each translated list is checked to be the
    same length as the identifier list it translates: `varied_text` shorter than
    `varied` is a model input with no Dutch name, dropped silently.
    """
    offenders: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "varied" in node and "pinned" in node:
                if not node["varied"]:
                    offenders.append(f"{path}.varied is empty")
                for name in ("varied", "pinned"):
                    names = len(node[f"{name}_text"])
                    ids = len(node[name])
                    if names != ids:
                        offenders.append(f"{path}: {names} names for {ids} {name} inputs")
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(_payload(), "")
    assert not offenders, offenders


# --------------------------------------------------------------------------
# The wire format of an amount.
#
# `money` emits `str(Decimal)`, and the shape check above sees only `"str"`.
# Reformatting it to Dutch display notation, "1.684,85", is the plausible next
# request on a Dutch product and would pass every other test here. The frontend
# then calls `Number.parseFloat` on it in components/band/position.ts, gets
# 1.684, which is finite, so the guard that returns 50 never fires and the
# marker lands on the 8 percent clamp regardless of where the model put the
# middle. The three amounts print correctly beside it and the picture is a lie.
#
# What is pinned here is the wire format and not the display format. Turning
# "1684.85" into "1.684,85" for a reader is a frontend decision and this says
# nothing about it; what may not happen is an amount crossing the boundary in a
# form no parser can read back.
# --------------------------------------------------------------------------

#: An optional sign, digits, a dot, exactly two digits. No thousands separator,
#: no currency symbol, no comma. This is what `Number.parseFloat` on one side
#: and `Decimal` on the other both read back without losing a digit.
WIRE_AMOUNT = re.compile(r"-?\d+\.\d{2}")

#: The keys whose values are amounts, plus the payback time that travels beside
#: them under the same three names. Both are quantized to two decimals and both
#: are read by `middlePercentage`.
AMOUNT_KEYS = frozenset({"p10", "p50", "p90", "low", "mid", "high"})


def test_every_amount_on_the_wire_is_machine_parseable() -> None:
    offenders: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in AMOUNT_KEYS and not WIRE_AMOUNT.fullmatch(str(value)):
                    offenders.append(f"{path}.{key} is {value!r}")
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(_payload(), "")
    assert not offenders, f"amounts a parser cannot read back: {offenders}"


def test_money_writes_a_four_figure_amount_without_a_thousands_separator() -> None:
    """Four figures on purpose: every smaller amount is identical under both
    conventions, so a test on 12.34 would not notice the change."""
    from decimal import Decimal

    from advice.rendering import money

    written = money(Decimal("1684.845"))
    assert WIRE_AMOUNT.fullmatch(written), f"money wrote {written!r}"
    assert float(written) == 1684.85, written


# --------------------------------------------------------------------------
# The input bounds, all the way round.
#
# backend/advice/serializers.py is the authority. frontend/src/lib/validation.ts
# is a declared copy of it and frontend/tests/lib/validation.test.ts compares
# the two. Two things that check did not cover, both found on 2026-08-21.
#
# One: it only walked the entries validation.ts already has, so a new bounded
# field in the serializer with no BOUNDS entry failed nothing. The form would
# then let a value through that the API refuses, and the visitor learns about
# it from a 400 naming a field they cannot see.
#
# Two: there is a third copy. berekenen/page.tsx carries a comment saying that
# writing `?? 1000` beside a lookup there would create "the copy nobody would
# think to check", and that copy exists one file over, in _flow/answers.ts,
# where `postcodeText` hardcodes 1000 and 9999. Nothing read it. Lower
# MIN_POSTCODE4 and the form accepts the value, `stepComplete` reports the
# question answered, `toEstimateInput` then returns null because `postcodeText`
# refuses it, and the visitor is told to answer a question they answered. A
# dead end form, produced by changing one number in a Python file.
#
# This lives on the Python side rather than in validation.test.ts because the
# authority is here, and because a check that fails on the side where the
# change was made is the one somebody reads.
# --------------------------------------------------------------------------

SERIALIZERS = REPO_ROOT / "backend" / "advice" / "serializers.py"
VALIDATION = REPO_ROOT / "frontend" / "src" / "lib" / "validation.ts"
ANSWERS = REPO_ROOT / "frontend" / "src" / "app" / "_flow" / "answers.ts"

#: A module level `NAME = number` in the serializer, underscores allowed.
_PYTHON_CONSTANT = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(-?[\d_]+(?:\.\d+)?)$", re.MULTILINE)

#: One entry of the BOUNDS table in validation.ts.
_TS_BOUND = re.compile(
    r"(\w+):\s*\{\s*min:\s*(-?[\d_]+(?:\.\d+)?)\s*,\s*max:\s*(-?[\d_]+(?:\.\d+)?)\s*\}"
)


def _number(literal: str) -> float:
    return float(literal.replace("_", ""))


def _serializer_bounds() -> dict[str, tuple[float, float]]:
    """Every field the serializer bounds on both sides, keyed by field name.

    Read from the tree rather than listed, which is the whole point: a bound
    added to serializers.py appears here the moment it is written, so the
    frontend copy is checked against it without anybody remembering to.
    """
    constants = {
        name: _number(literal)
        for name, literal in _PYTHON_CONSTANT.findall(SERIALIZERS.read_text(encoding="utf-8"))
    }
    return {
        name.removeprefix("MIN_").lower(): (value, constants[f"MAX_{name.removeprefix('MIN_')}"])
        for name, value in constants.items()
        if name.startswith("MIN_") and f"MAX_{name.removeprefix('MIN_')}" in constants
    }


def _frontend_bounds() -> dict[str, tuple[float, float]]:
    source = VALIDATION.read_text(encoding="utf-8")
    table = source[source.index("export const BOUNDS") :]
    return {field: (_number(low), _number(high)) for field, low, high in _TS_BOUND.findall(table)}


def test_every_bound_the_serializer_enforces_has_a_copy_in_the_form() -> None:
    """The direction validation.test.ts does not walk.

    It iterates its own MIRRORS table, so a bound that exists only in Python is
    invisible to it. Adding a bounded field to the serializer and forgetting the
    form is not a hypothetical: every field on this form arrived that way.
    """
    authoritative = _serializer_bounds()
    assert len(authoritative) >= 7, f"only {len(authoritative)} bounds parsed; the regex is stale"
    copied = _frontend_bounds()
    missing = sorted(set(authoritative) - set(copied))
    assert not missing, f"serializers.py bounds these and BOUNDS does not mention them: {missing}"


def test_every_bound_in_the_form_is_the_bound_the_serializer_enforces() -> None:
    authoritative = _serializer_bounds()
    disagreements = [
        f"{field}: the form says {bound}, serializers.py says {authoritative[field]}"
        for field, bound in _frontend_bounds().items()
        if field in authoritative and bound != authoritative[field]
    ]
    assert not disagreements, f"the API wins; fix validation.ts: {disagreements}"


def _postcode_text_body() -> str:
    """The body of `postcodeText` in _flow/answers.ts.

    Located by name rather than by line number so the file may move around it.
    A rename fails here with this message, which is the correct outcome: the
    third copy would have moved and this test would no longer be reading it.
    """
    source = ANSWERS.read_text(encoding="utf-8")
    anchor = "export function postcodeText"
    assert anchor in source, (
        f"{ANSWERS.name} no longer declares postcodeText; find where the postcode "
        "range moved to and point this test at it"
    )
    start = source.index(anchor)
    end = source.index("\n}", start)
    return source[start:end]


def test_the_third_copy_of_the_postcode_range_agrees_with_the_first() -> None:
    """`postcodeText` refuses anything outside the range and returns null.

    `toEstimateInput` turns that null into "no input", and the flow turns that
    into "Beantwoord deze vraag om verder te gaan" on a question the visitor
    already answered. So this copy decides whether the form has an exit, and
    until now nothing compared it with anything.

    Two ways to pass, on purpose. Either the function names no numbers at all,
    because it reads the range from `BOUNDS` like the rest of the form does,
    which is the fix; or the numbers it does name are the two the serializer
    enforces. What fails is a third number that agrees with nothing.
    """
    low, high = _serializer_bounds()["postcode4"]
    body = _postcode_text_body()
    literals = {_number(literal) for literal in re.findall(r"\b\d[\d_]*(?:\.\d+)?\b", body)}
    if not literals:
        assert "BOUNDS" in body, (
            "postcodeText names no bound and no numbers; it no longer checks the range"
        )
        return
    unexplained = sorted(literals - {low, high})
    assert not unexplained, (
        f"postcodeText in answers.ts names {unexplained}, and serializers.py bounds "
        f"postcode4 at {low} to {high}. This is the third copy of that range and it "
        "is the one nothing else reads."
    )
    assert literals == {low, high}, (
        f"postcodeText names {sorted(literals)} and the range is {low} to {high}"
    )
