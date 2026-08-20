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
