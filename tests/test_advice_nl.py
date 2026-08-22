from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ampeer_advice.nl import CONFIDENCE_LABELS, ROUTE_TITLES, RULE_TEXTS, text_for
from ampeer_advice.rules import RULE_IDS
from ampeer_advice.types import Confidence, Route

NL = Path(__file__).resolve().parent.parent / "ampeer_advice" / "nl.py"
METHODOLOGY = Path(__file__).resolve().parent.parent / "docs" / "methodologie.md"


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
    from ampeer_advice.advise import PINNED_INPUTS
    from ampeer_advice.battery import BATTERY_PRICE_INPUT
    from ampeer_advice.nl import INPUT_LABELS
    from ampeer_advice.tariffs import scenario_2027_levels
    from ampeer_sim.economics.sensitivity import VARIATIONS

    # Every place a name can enter a band, read from that place rather than
    # copied. Until 2026-08-22 this was the variations plus two names typed out
    # here, which covered the real set only because three of the four sources
    # happen to overlap with the variations. A name pinned in advise.py or
    # listed in tariffs.py that was not also a variation would have passed this
    # test and raised in `label_for` for every visitor, which is a 500 rather
    # than a red build. Measured that day: the two sets were identical, so this
    # fixes a derivation and not a defect.
    nameable = (
        {variation.name for variation in VARIATIONS}
        | set(PINNED_INPUTS)
        | set(scenario_2027_levels(dynamic=False).inputs)
        | set(scenario_2027_levels(dynamic=True).inputs)
        | {BATTERY_PRICE_INPUT}
    )
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
#: reader.
#:
#: It covers docs/methodologie.md too, since 2026-08-22. That document was on
#: "je" while this package was on "u", and the two are not separate surfaces:
#: frontend/src/lib/methodology.ts reads the file at build time and serves it
#: as a page of the same site, so a visitor met both registers by following a
#: link. Moving it was 165 edits; keeping it moved is the test below.
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


def test_the_methodology_page_uses_the_same_form_of_address() -> None:
    """The methodology is a page of this site, not a document beside it.

    frontend/src/lib/methodology.ts reads docs/methodologie.md at build time and
    renders it, deliberately, so that the published page and the file the Python
    tests guard can never disagree. The consequence nobody had drawn is that the
    register has to match too: until 2026-08-22 a visitor read an answer written
    in "u", followed the link under it, and was addressed as "je" for six
    hundred lines.

    That is the same defect the test above was written for, one page further
    along. It went unnoticed for the same reason: both are Dutch, so the
    language rule in this project had nothing to say about it, and no test asked
    the question across a file boundary.

    Moving the document took 165 edits and most of them were not substitutions.
    Dutch drops the -t from a verb in inversion after "je" and keeps it after
    "u", so "kun je" becomes "kunt u" and "Beantwoord je meer vragen" becomes
    "Beantwoordt u meer vragen", while a possessive "je dak" becomes "uw dak"
    and a subject "je ziet" becomes "u ziet". This test is what keeps that work
    from being undone a sentence at a time.
    """
    other = "je" if ADVICE_REGISTER == "u" else "u"
    text = METHODOLOGY.read_text(encoding="utf-8")
    offenders = [line.strip() for line in text.splitlines() if _SECOND_PERSON[other].search(line)]
    assert not offenders, (
        f"docs/methodologie.md addresses the reader as {other!r} on these lines, and the "
        f"advice they arrived from is written in {ADVICE_REGISTER!r}:\n  "
        + "\n  ".join(line[:90] for line in offenders[:12])
    )


def test_the_methodology_addresses_the_reader_at_all() -> None:
    """The other half, for the same reason the nl.py pair has one.

    A document with no second person in it satisfies the test above completely,
    and so would a file that had been emptied or moved. The count is a floor
    against the 165 places the register was changed in, not the number itself.
    """
    text = METHODOLOGY.read_text(encoding="utf-8")
    used = len(_SECOND_PERSON[ADVICE_REGISTER].findall(text))
    assert used >= 120, (
        f"docs/methodologie.md addresses the reader as {ADVICE_REGISTER!r} {used} times, "
        "which is far fewer than the document it should be, so this pair is reading "
        "something other than the published methodology"
    )
