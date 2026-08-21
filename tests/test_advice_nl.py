from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ampeer_advice.nl import CONFIDENCE_LABELS, ROUTE_TITLES, RULE_TEXTS, text_for
from ampeer_advice.rules import RULE_IDS
from ampeer_advice.types import Confidence, Route

NL = Path(__file__).resolve().parent.parent / "ampeer_advice" / "nl.py"


def test_every_rule_has_dutch_text() -> None:
    assert RULE_IDS <= set(RULE_TEXTS)


def test_no_text_belongs_to_a_rule_that_does_not_exist() -> None:
    assert set(RULE_TEXTS) <= RULE_IDS


def test_every_route_and_every_confidence_level_has_a_label() -> None:
    assert set(ROUTE_TITLES) == set(Route)
    assert set(CONFIDENCE_LABELS) == set(Confidence)


def test_no_em_dashes_anywhere() -> None:
    """Project convention: no em-dashes in user-facing Dutch text."""
    for text in list(RULE_TEXTS.values()) + list(ROUTE_TITLES.values()):
        assert "\u2014" not in text, text


def test_text_for_rejects_an_unknown_rule() -> None:
    with pytest.raises(KeyError):
        text_for("NO_SUCH_RULE")


def test_every_model_input_a_band_can_name_has_a_dutch_name() -> None:
    """An identifier that reaches a reader is a language boundary that leaked.

    A scenario band sends `varied` and `pinned` so it can admit it is narrower
    than the headline. Those come from the simulation core as English names,
    and the frontend must not translate them: a Dutch copy of the model's
    vocabulary living there is a second copy, and it drifts the first time an
    assumption is added.

    So the names live here, and this pairs the table with every source that can
    put a name into a band: the sensitivity variations, plus the battery price,
    which the payback band varies on its own.
    """
    from ampeer_advice.nl import INPUT_LABELS
    from ampeer_sim.economics.sensitivity import VARIATIONS

    nameable = {variation.name for variation in VARIATIONS} | {
        "supply_price",
        "battery_cost_per_kwh",
    }
    missing = nameable - set(INPUT_LABELS)
    assert not missing, f"model inputs with no Dutch name: {sorted(missing)}"

    unused = set(INPUT_LABELS) - nameable
    assert not unused, f"Dutch names for inputs no band can emit: {sorted(unused)}"


def test_a_model_input_without_a_name_refuses_rather_than_falling_back() -> None:
    """A fallback to the identifier would put English in front of a reader and
    nothing would say so."""
    import pytest

    from ampeer_advice.nl import label_for

    with pytest.raises(KeyError, match="no Dutch name"):
        label_for("a_variation_nobody_named")


def test_every_production_source_has_a_dutch_sentence() -> None:
    """The response names where the sun figures came from, and a reader who is
    told "FALLBACK" learns nothing from it.

    nl.py keys this table by the enum's name rather than by the member, because
    this file promises to import nothing from the simulation core. That promise
    is what makes this pairing test necessary: without it the table and the enum
    can diverge silently, and the first sign would be a KeyError in front of a
    visitor.
    """
    from ampeer_advice.nl import PRODUCTION_SOURCE_TEXTS
    from ampeer_sim.types import ProductionSource

    assert set(PRODUCTION_SOURCE_TEXTS) == {member.name for member in ProductionSource}


def test_an_unknown_production_source_refuses_rather_than_falling_back() -> None:
    import pytest

    from ampeer_advice.nl import production_source_text

    with pytest.raises(KeyError, match="no Dutch text"):
        production_source_text("SOME_SOURCE_NOBODY_NAMED")


# ---------------------------------------------------------------------------
# The second person
# ---------------------------------------------------------------------------

#: Which form of address the advice layer uses. Dutch has two and this package
#: has to pick one, because a household reads every string in this file inside a
#: single answer.
#:
#: It is written here rather than assumed anywhere, so switching the product to
#: "je" is a change to this line plus the strings, and the test below then names
#: every string still on the old form instead of leaving them to be found by a
#: reader. `docs/methodologie.md` is on "je" today and the app on "u"; that gap
#: is a decision for the owner and is not what this test is about.
ADVICE_REGISTER = "u"

_SECOND_PERSON = {
    "u": re.compile(r"(?<![A-Za-zÀ-ÿ])(u|uw|uzelf)(?![A-Za-zÀ-ÿ])"),
    "je": re.compile(r"(?<![A-Za-zÀ-ÿ])(je|jij|jouw|jezelf)(?![A-Za-zÀ-ÿ])"),
}


def _dutch_strings() -> list[str]:
    """Every string literal in nl.py, which is the whole of its output.

    Read with ast rather than by importing and walking the dictionaries,
    because a string added to a new dictionary tomorrow is still a string a
    household will read.
    """
    tree = ast.parse(NL.read_text(encoding="utf-8"))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_the_advice_layer_uses_one_form_of_address() -> None:
    """Both forms reached the same answer until 2026-08-21.

    Measured on the committed fixture that the frontend renders: sixteen "u" or
    "uw" beside thirty-two "je" or "jouw". A visitor read "U levert een groot
    deel van uw opwek terug" and "het verlies in je installatie" on one page.
    Five strings were out of line with the other thirty-odd: three input labels
    and the two sentences about where the production figures came from.

    Nothing enforced it because nothing could: the language rule in this project
    is about which language, and both of these are Dutch.
    """
    other = "je" if ADVICE_REGISTER == "u" else "u"
    offenders = [
        text
        for text in _dutch_strings()
        if _SECOND_PERSON[other].search(text) and not text.startswith("#")
    ]
    assert not offenders, (
        f"ampeer_advice/nl.py addresses the household as {ADVICE_REGISTER!r} everywhere "
        f"except here, and one answer carries all of it:\n  "
        + "\n  ".join(repr(text[:80]) for text in offenders)
    )


def test_the_declared_form_of_address_is_the_one_actually_used() -> None:
    """The constant above must describe the file rather than an intention.

    Without this, flipping ADVICE_REGISTER to "je" and changing nothing else
    would pass: every string would be free of "je", which is exactly what the
    test above asks for and exactly the wrong reading.
    """
    used = sum(1 for text in _dutch_strings() if _SECOND_PERSON[ADVICE_REGISTER].search(text))
    assert used > 0, (
        f"nothing in nl.py addresses the household as {ADVICE_REGISTER!r}, so that "
        "constant describes an intention rather than the file"
    )
