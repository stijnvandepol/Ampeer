from __future__ import annotations

import pytest

from ampeer_advice.nl import CONFIDENCE_LABELS, ROUTE_TITLES, RULE_TEXTS, text_for
from ampeer_advice.rules import RULE_IDS
from ampeer_advice.types import Confidence, Route


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
