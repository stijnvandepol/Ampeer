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

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

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

    def is_named(key: str) -> bool:
        """Whether `types.ts` names this key, required or optional.

        A field the API may leave out is declared `readonly year?: ...`, and
        that names the key just as surely as the required form. Both spellings
        keep the colon in the pattern, so `year` is not satisfied by a
        neighbouring `yearly`.
        """
        return any(f"readonly {key}{mark}:" in declared for mark in ("", "?"))

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if not is_named(key):
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


def test_every_bound_the_form_applies_is_one_the_serializer_also_applies() -> None:
    """The direction neither of the two above walks.

    One asserts every Python bound has a copy in the form. The other compares
    the values of the fields both of them know about, and skipped a field the
    serializer does not bound: `if field in authoritative` reads as caution and
    is a hole. A BOUNDS entry with nothing behind it means the form refuses
    something the API would have accepted, and the visitor is stopped by our
    own message rather than by a rule.

    That is the quieter half of the two failures validation.ts describes in its
    own opening. Too loose produces a 400 the visitor can at least see; too
    tight produces a form that will not go on, for a reason that exists nowhere
    but here.
    """
    authoritative = _serializer_bounds()
    invented = sorted(set(_frontend_bounds()) - set(authoritative))
    assert not invented, (
        f"BOUNDS refuses values for {invented} and serializers.py bounds none of them, "
        "so the form is stricter than the API and the difference lives only in the "
        "frontend"
    )


def test_every_bound_in_the_form_is_the_bound_the_serializer_enforces() -> None:
    """The values themselves, for every field the form bounds.

    No longer skipping a field the serializer does not know: the test above
    makes that case impossible, and a comparison that steps over its own
    unknowns reports agreement it never checked. Reported here rather than
    raising a KeyError, so the two failures read the same way.
    """
    authoritative = _serializer_bounds()
    disagreements = [
        f"{field}: the form says {bound}, serializers.py says {authoritative.get(field, 'nothing')}"
        for field, bound in _frontend_bounds().items()
        if authoritative.get(field) != bound
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


# ---------------------------------------------------------------------------
# The address, not just the shape
# ---------------------------------------------------------------------------

ROOT_URLS = REPO_ROOT / "backend" / "ampeer" / "urls.py"
ADVICE_URLS = REPO_ROOT / "backend" / "advice" / "urls.py"
ACCOUNTS_URLS = REPO_ROOT / "backend" / "accounts" / "urls.py"
NGINX = REPO_ROOT / "infra" / "nginx" / "nginx.conf"
API_TS = REPO_ROOT / "frontend" / "src" / "lib" / "api.ts"
ACCOUNTS_TS = REPO_ROOT / "frontend" / "src" / "lib" / "accounts.ts"

#: A path this frontend asks the API for, quoted or in a template literal.
_CALLED_PATH = re.compile(r"""["'`](/api/[^"'`]*)["'`]""")

#: What a template literal interpolates, flattened so a token and a postcode
#: read the same. What matters is the shape of the address, not the value.
_INTERPOLATION = re.compile(r"\$\{[^}]*\}")

#: A Django path converter, `<str:token>` and friends. Reduced to the same
#: `<dynamic>` the frontend's `${...}` becomes, so the two notations for one
#: variable segment can be compared at all.
_CONVERTER = re.compile(r"<[^>]+>")


def _api_prefix(module: str) -> str:
    """Where Django mounts one of the two APIs, from the root URL configuration.

    Django is the only place that decides this. nginx forwards it and the
    frontend asks for it, and both of those are copies.
    """
    tree = ast.parse(ROOT_URLS.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "path"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[0], ast.Constant):
            continue
        included = node.args[1]
        if (
            isinstance(included, ast.Call)
            and getattr(included.func, "id", "") == "include"
            and included.args
            and isinstance(included.args[0], ast.Constant)
            and included.args[0].value == module
        ):
            return "/" + str(node.args[0].value)
    raise AssertionError(f"{ROOT_URLS.name} no longer mounts {module} anywhere")


def _api_routes(urls: Path) -> set[str]:
    """Every fixed route under that prefix, from one app's URL configuration."""
    tree = ast.parse(urls.read_text(encoding="utf-8"))
    return {
        str(node.args[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "path"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }


@pytest.mark.parametrize(
    ("module", "urls", "client"),
    [
        ("advice.urls", ADVICE_URLS, API_TS),
        ("accounts.urls", ACCOUNTS_URLS, ACCOUNTS_TS),
    ],
    ids=["advice", "accounts"],
)
def test_every_path_the_frontend_calls_is_one_the_backend_serves(
    module: str, urls: Path, client: Path
) -> None:
    """The shape was checked and the address was not.

    This file already argues that two codebases sharing a JSON shape with no
    shared check is how a frontend ends up showing something the backend did
    not mean. The address is the same argument one step earlier: the fixture
    can be perfect and every call can still land on a 404.

    `/api/advice/` is written out in fifteen places across this repository, and
    each of them asserted its own half. Change the mount in
    backend/ampeer/urls.py and the Python tests keep passing, because they use
    reverse(); the frontend tests keep passing, because they mock; the nginx
    test keeps passing, because it checks that its own block exists. Only a
    visitor finds out.

    Django decides, so Django is read. Everything else here is a copy.

    Parametrised since the second client arrived. accounts.ts calls nine paths
    under /api/auth/ and not one of them is reachable by reverse(), by a Vitest
    mock or by a page.route fixture: all three answer whatever they are asked.
    Only this reads the URL configuration Django actually serves.
    """
    prefix = _api_prefix(module)
    routes = _api_routes(urls)
    assert routes, f"{urls.name} declares no routes at all"

    called = {
        _INTERPOLATION.sub("<dynamic>", path)
        for path in _CALLED_PATH.findall(client.read_text(encoding="utf-8"))
    }
    assert called, f"{client.name} asks the API for nothing; this test read nothing"

    # A Django converter and a template literal describe the same segment in
    # two notations, so both are reduced to the same word before they are
    # compared. Without this, `advice/<str:token>/accept/` and the frontend's
    # `advice/${token}/accept/` are a mismatch on spelling alone, and the only
    # way to pass would be to stop parametrising the route.
    comparable = {_CONVERTER.sub("<dynamic>", route) for route in routes}

    wrong = []
    for path in sorted(called):
        if not path.startswith(prefix):
            wrong.append(f"{path} is not under {prefix}")
            continue
        rest = path[len(prefix) :]
        if rest == "<dynamic>/" or rest in comparable:
            continue
        wrong.append(f"{path} asks for {rest!r}, which is not one of {sorted(routes)}")
    assert not wrong, "the frontend calls addresses the backend does not serve:\n  " + "\n  ".join(
        wrong
    )


def test_nginx_forwards_the_prefix_django_answers_on() -> None:
    """The third copy, and the one that fails in production rather than in a test.

    nginx has its own location for this prefix, with a log format that keeps a
    token out of the access log. If Django moves and nginx does not, the block
    stops matching, requests fall through to the general /api/ location, and
    the promise about tokens in logs quietly stops applying to the one path it
    was written for.
    """
    prefix = _api_prefix("advice.urls")
    text = NGINX.read_text(encoding="utf-8")
    assert re.search(rf"location\s+{re.escape(prefix)}\s*\{{", text), (
        f"nginx.conf has no location block for {prefix}, which is where Django now "
        "answers. Requests would fall through to the generic /api/ block and lose the "
        "log format that keeps tokens out of the access log."
    )


def test_the_counter_names_the_browser_sends_are_the_ones_the_api_accepts() -> None:
    """Two lists in two languages, and a drift between them is a missing number.

    `frontend/src/lib/count.ts` names the events it may send and
    `DailyCounter.CLIENT_NAMES` names the ones the API will accept. The API
    refuses anything else with a 400 rather than counting it into a name nobody
    reads, which is the right refusal and also means a typo here does not
    announce itself as an error anywhere a person looks: the form keeps working,
    the request keeps failing silently by design, and one number quietly stops
    being collected.

    Read out of both files rather than restated, so this cannot pass by agreeing
    with a copy of itself.
    """
    typescript = (REPO_ROOT / "frontend" / "src" / "lib" / "count.ts").read_text(encoding="utf-8")
    declared = set(re.findall(r'^\s*\|\s*"([a-z0-9_]+)";?$', typescript, re.MULTILINE))
    assert declared, "no CountName union found in frontend/src/lib/count.ts"

    models = (REPO_ROOT / "backend" / "advice" / "models.py").read_text(encoding="utf-8")
    block = re.search(r"CLIENT_NAMES:.*?frozenset\(\s*\{(.*?)\}\s*\)", models, re.DOTALL)
    assert block, "no CLIENT_NAMES frozenset found in backend/advice/models.py"
    constants = {name.strip().rstrip(",") for name in block.group(1).split() if name.strip(",")}
    accepted = {
        match.group(1)
        for constant in constants
        if (
            match := re.search(
                rf'^\s*{re.escape(constant)} = "([a-z0-9_]+)"$', models, re.MULTILINE
            )
        )
    }
    assert accepted, f"could not resolve CLIENT_NAMES constants to strings: {sorted(constants)}"

    assert declared == accepted, (
        "the browser and the API disagree about the counter names; "
        f"only in count.ts: {sorted(declared - accepted)}, "
        f"only in models.py: {sorted(accepted - declared)}"
    )


# --------------------------------------------------------------------------
# The consent texts, the one auth response that touches no database.
# --------------------------------------------------------------------------

CONSENT_TEXTS_FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "consent-texts.json"
FRONTEND_SOURCE = REPO_ROOT / "frontend" / "src"


def test_the_consent_texts_fixture_is_byte_for_byte_what_the_generator_writes() -> None:
    """The same claim advice-response.json carries, for the sentences a
    household agrees to.

    A hand-edited word here would be a fixture describing a consent nobody
    ever gave, and every frontend test that renders it would then agree with
    a sentence the API does not send.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from helpers.consent_texts_fixture import build_consent_texts_payload

    written = json.dumps(build_consent_texts_payload(), indent=2, ensure_ascii=False) + "\n"
    committed = CONSENT_TEXTS_FIXTURE.read_text(encoding="utf-8")
    assert committed == written, (
        "frontend/tests/fixtures/consent-texts.json is not what "
        "tests/helpers/consent_texts_fixture.py produces. Regenerate it with\n"
        "    uv run --no-sync python tests/helpers/consent_texts_fixture.py\n"
        "rather than editing it, and do not run a formatter over it."
    )


def test_the_fixture_keys_are_the_consent_kinds() -> None:
    """Two copies of one list: the model, and the fixture the browser builds
    against. A third kind of consent has to fall over on the side where it was
    added, not in a browser where the row simply never appears."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.models import Consent

    payload = json.loads(CONSENT_TEXTS_FIXTURE.read_text(encoding="utf-8"))
    assert sorted(payload["texts"]) == sorted(Consent.KINDS)
    for kind, sentence in payload["texts"].items():
        assert sentence.strip(), f"{kind} carries an empty sentence"
    assert sorted(payload["labels"]) == sorted(Consent.KINDS)
    for kind, label in payload["labels"].items():
        assert label.strip(), f"{kind} carries an empty label"


def test_no_consent_text_lives_in_the_frontend() -> None:
    """Chapter 5, checked rather than promised.

    If the frontend carried its own copy of either sentence, the text_version
    column would prove nothing: there would be two texts, the row would point
    at one and the screen would have shown the other, and nothing could see
    the difference. Read out of nl.py rather than restated, so this cannot
    pass by agreeing with a copy of itself.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.nl import NL

    sentences = {key: NL[key] for key in ("CONSENT_METER_LINK", "CONSENT_LEAD_GENERATION")}
    offenders: list[str] = []
    for path in sorted(FRONTEND_SOURCE.rglob("*.ts*")):
        text = path.read_text(encoding="utf-8")
        for key, sentence in sentences.items():
            # The first clause of each sentence, so a copy a formatter reflowed
            # over two lines is still found. A whole-sentence search would be
            # defeated by the one edit somebody would actually make.
            if sentence.split(".")[0] in text:
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()} carries {key}")
    assert not offenders, (
        "the consent text lives in the frontend as well as in nl.py:\n  " + "\n  ".join(offenders)
    )


def test_the_frontend_knows_exactly_the_two_kinds_the_api_has() -> None:
    """`CONSENT_KINDS` in accounts.ts is what every shape check and both consent
    rows iterate, so a kind missing there is a consent the API records and the
    browser never shows, and a kind too many is a row that renders `undefined`.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.models import Consent

    declared = _quoted(ACCOUNTS_TS.read_text(encoding="utf-8"), "export const CONSENT_KINDS =")
    assert declared == sorted(Consent.KINDS), (
        f"accounts.ts declares {declared} and Consent.KINDS is {sorted(Consent.KINDS)}"
    )


def test_no_consent_label_lives_in_the_frontend() -> None:
    """Decision 38 closed: the labels travel with the texts, so a copy in the
    frontend would be the drift `text_version` cannot see."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.nl import NL

    labels = {key: NL[key] for key in ("CONSENT_LABEL_METER_LINK", "CONSENT_LABEL_LEAD_GENERATION")}
    offenders = [
        f"{path.relative_to(REPO_ROOT).as_posix()} carries {key}"
        for path in sorted(FRONTEND_SOURCE.rglob("*.ts*"))
        for key, label in labels.items()
        if label in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "a consent label lives in the frontend as well as in nl.py:\n  " + "\n  ".join(offenders)
    )


def test_the_fragment_accepts_exactly_the_token_length_the_backend_mints() -> None:
    """43 in fragment.ts and TOKEN_BYTES in recovery.py are one number written
    on two sides of a language boundary. Held together here."""
    import secrets
    import sys

    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from accounts.recovery import TOKEN_BYTES

    fragment = (FRONTEND_SOURCE / "app" / "_account" / "fragment.ts").read_text(encoding="utf-8")
    # `PATTERN` builds itself from `TOKEN_LENGTH` through `new RegExp(` + a
    # template literal, not a `/.../ ` regex literal with the digits written
    # out, so the number this test pins is read off the exported constant
    # rather than off the character class it parameterises.
    declared = re.search(r"export const TOKEN_LENGTH = (\d+);", fragment)
    assert declared, "fragment.ts no longer pins a token length"
    assert int(declared.group(1)) == len(secrets.token_urlsafe(TOKEN_BYTES))


def test_the_icon_is_well_formed_xml() -> None:
    """A browser stops reading icon.svg at the first XML error.

    On 2026-09-18 that was line 19: the comment inside the file named four
    CSS custom properties, and XML forbids "--" anywhere inside a comment.
    The build copied the file unchanged, every gate was green, and the tab
    icon was a parse error. Nothing here parses SVG; the one thing that
    does is the browser, so this test parses it the way the browser does.
    """
    from xml.dom import minidom

    icon = REPO_ROOT / "frontend" / "src" / "app" / "icon.svg"
    document = minidom.parse(str(icon))
    assert document.documentElement.tagName == "svg"
