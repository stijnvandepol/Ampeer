"""The published methodology must describe the model that actually ships.

``docs/methodologie.md`` is the document Ampeer is judged on. Somebody who
disagrees with a number will read it, and if it describes a version of the model
that no longer exists, the honesty this whole project rests on is gone.

It went stale within a day of being written: four corrections landed in the code
and none of them reached the document. Nothing noticed, because a document
cannot fail a build. These tests are how it fails one.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ampeer_advice import tariffs
from ampeer_advice.battery import MAX_ACCEPTABLE_PAYBACK_YEARS
from ampeer_sim.economics.sensitivity import VARIATIONS
from ampeer_sim.production.model import (
    DEGRADATION_PER_YEAR,
    MAX_DEGRADATION,
    degradation_factor,
)
from ampeer_sim.types import Household, PVSystem

METHODOLOGY = Path(__file__).resolve().parent.parent / "docs" / "methodologie.md"
TEXT = METHODOLOGY.read_text(encoding="utf-8")

GOLDEN: dict[str, dict[str, Any]] = json.loads(
    (Path(__file__).resolve().parent / "golden" / "advice_households.json").read_text(
        encoding="utf-8"
    )
)


def _dutch(value: Decimal) -> str:
    """Render a figure the way the document writes it, with a comma."""
    return str(value).replace(".", ",")


#: The label each band carries in the table in section 10. Reading the row
#: rather than searching the whole document matters: an earlier version of this
#: test only checked that the figure appeared somewhere, and the anchored middle
#: also appears in the paragraph that explains it, so the table could quietly
#: drift back to the arithmetic midpoint while the test stayed green.
TABLE_ROWS = {
    "SUPPLY_PRICE": "Stroomprijs per kWh, alles inbegrepen",
    "FEED_IN_GROSS_FIXED": "Bruto terugleververgoeding, vast contract",
    "FEED_IN_COST": "Terugleverkosten per teruggeleverde kWh",
    "FEED_IN_NET_DYNAMIC": "Netto terugleververgoeding, dynamisch contract",
    "BATTERY_COST_PER_KWH": "Thuisbatterij per kWh capaciteit, geplaatst",
}


def _table_values(label: str) -> tuple[str, str, str]:
    """The three figures on one row of the tariff table, as written."""
    match = re.search(rf"^\| {re.escape(label)} \|(.+)\|$", TEXT, re.MULTILINE)
    assert match, f"no table row for {label!r}"
    cells = [cell.strip() for cell in match.group(1).split("|") if cell.strip()]
    assert len(cells) == 3, f"{label!r} does not have three figures: {cells}"
    return cells[0], cells[1], cells[2]


@pytest.mark.parametrize("band_name", sorted(TABLE_ROWS))
def test_the_published_tariff_table_matches_the_code(band_name: str) -> None:
    """Every tariff the document prints must be the one the model uses.

    The middle of FEED_IN_COST is the one that moved: it is anchored so the net
    figure matches what suppliers publish rather than being the midpoint of its
    own range. This reads the row, so putting the arithmetic midpoint back in
    the table fails even though the anchored figure still appears in the prose.
    """
    band = getattr(tariffs, band_name)
    printed = _table_values(TABLE_ROWS[band_name])
    expected = (_dutch(band.low), _dutch(band.mid), _dutch(band.high))
    assert printed == expected, f"{band_name}: document says {printed}, code says {expected}"


def test_the_document_states_the_right_number_of_sensitivity_runs() -> None:
    """The band is the product's central honesty claim, so its size is a fact.

    The document said 81 while the code ran 243, because a fifth assumption was
    added without the text following. A reader checking the claim would have
    found a different number than the one they were told.
    """
    runs = 3 ** len(VARIATIONS)
    assert f"{runs} doorrekeningen" in TEXT, f"the document does not mention {runs} runs"
    assert "81 doorrekeningen" not in TEXT, "a stale run count survived in the document"


def test_the_document_states_the_right_number_of_varied_assumptions() -> None:
    spelled = {4: "vier", 5: "vijf", 6: "zes", 7: "zeven"}[len(VARIATIONS)]
    assert f"{spelled} aannames" in TEXT


def test_the_document_states_the_payback_limit_the_code_applies() -> None:
    assert MAX_ACCEPTABLE_PAYBACK_YEARS == Decimal("12")
    assert "twaalf jaar" in TEXT


def test_the_document_carries_no_em_dashes() -> None:
    """Project convention for every user-facing Dutch text."""
    assert "—" not in TEXT


def test_the_document_still_names_its_own_limitations() -> None:
    """The section a reader looks for when they distrust the answer.

    Losing it would be the single most damaging edit anyone could make to this
    file, and the easiest to make by accident while tidying.

    The heading is matched without its number on purpose. Inserting a chapter
    ahead of it renumbers it, and pinning the number would turn a correct edit
    into a failure while a deletion and a renumber would look the same. What
    has to hold is that the chapter is there and that it still names what it
    is for.
    """
    assert re.search(r"^## \d+\. Wat wij niet weten$", TEXT, re.MULTILINE)
    for limitation in ("schaduw", "gemiddelde", "aangenomen"):
        assert limitation in TEXT, f"the limitations section no longer mentions {limitation}"


def test_the_document_states_what_is_assumed_when_it_does_not_ask() -> None:
    """Round one asks four questions and fills in the rest.

    Nothing in this document said so. It described what happens to an answer
    the reader gives, which reads as though the reader gives all of them, and
    the confidence label says INDICATIVE without naming a single thing that
    made it indicative. A reader cannot check an assumption that is not
    written down.

    The five names below are the ones a household would recognise as questions
    it was not asked. They are not the whole set and this test is not the one
    that guards the whole set: it cannot notice a sixth, which is how the panel
    age stayed missing. `test_the_list_of_filled_in_inputs_is_the_one_the_code_produces`
    derives that set from assembly.py instead.
    """
    assert re.search(r"^## \d+\. Wat wij aannemen als wij het niet vragen$", TEXT, re.MULTILINE)
    chapter = TEXT.split("Wat wij aannemen als wij het niet vragen", 1)[1]
    for assumption in (
        "Overdag iemand thuis",
        "Elektrische auto",
        "Warmtepomp",
        "Thuisbatterij",
        "Contract",
    ):
        assert assumption in chapter, f"the assumptions chapter does not name {assumption}"


def test_the_document_says_which_way_those_assumptions_push() -> None:
    """A default that maximises the shock is not a conservative default.

    It is the direction that makes the product's case, and the word for it is
    not "voorzichtig" without a sentence saying so. The chapter has to state
    the direction, not only the list, because a list of assumptions with no
    direction reads as neutral.
    """
    chapter = TEXT.split("Wat wij aannemen als wij het niet vragen", 1)[1]
    assert "Voorzichtig in de richting die ons goed uitkomt is niet voorzichtig" in chapter
    assert "conservatief" in chapter, "the chapter no longer says what word was wrong"
    assert "634 euro" in chapter, "the chapter no longer quotes what it measured"


def test_the_document_does_not_claim_the_payback_band_moves_the_price_alone() -> None:
    """The claim that went stale the moment the band was widened.

    The old sentence said the margin on the payback comes from the price of the
    battery only. That was true of the old code and is not true of this one, and
    a document that describes the previous model is the failure this file exists
    to prevent.
    """
    assert "alleen uit de prijs van de batterij" not in TEXT
    chapter = TEXT.split("## 12.", 1)[1].split("## 13.", 1)[0]
    assert "p10" in chapter, "chapter 12 no longer explains which band is a percentile"
    assert "laag, midden en hoog" in chapter


def test_the_document_quotes_the_payback_band_the_model_produces() -> None:
    """Chapter 12 names three figures for the reference household.

    They are there to show a reader what widening the band did, which is only
    worth anything if they are still the figures the model produces. Same
    reason as the break even price below: a number in prose that nothing
    compares against is a number that goes stale silently.
    """
    rob = GOLDEN["rob_fixed_contract"]
    chapter = TEXT.split("## 12.", 1)[1].split("## 13.", 1)[0]
    for key in (
        "battery_payback_low_years",
        "battery_payback_mid_years",
        "battery_payback_high_years",
    ):
        printed = f"{round(float(rob[key]), 1)}".replace(".", ",")
        assert printed in chapter, f"chapter 12 does not quote {printed} for {key}"


def test_the_document_quotes_break_even_prices_the_model_still_produces() -> None:
    """The check that would have caught the 833 euro that sat here for a day.

    That figure was a real output of an earlier model and stayed in the text
    after the model moved, because the only place it was written down besides
    the document was a golden file that no test read. A document is judged on
    figures like this one: it is the number a reader is invited to hold a quote
    against.
    """
    mids = [
        float(case["battery_break_even_mid_cost_per_kwh"])
        for case in GOLDEN.values()
        if case.get("battery_break_even_mid_cost_per_kwh") is not None
    ]
    lows = [
        float(case["battery_break_even_low_cost_per_kwh"])
        for case in GOLDEN.values()
        if case.get("battery_break_even_low_cost_per_kwh") is not None
    ]
    assert mids and lows
    assert f"{round(max(mids))} euro" in TEXT, f"the document does not quote {round(max(mids))}"
    assert f"{round(max(lows))} euro" in TEXT, f"the document does not quote {round(max(lows))}"
    assert "833" not in TEXT.split("Hier stond eerder", 1)[0]


def test_every_section_is_numbered_consecutively() -> None:
    """A renumbering that skips or repeats is a merge accident, not a choice."""
    numbers = [int(match) for match in re.findall(r"^## (\d+)\.", TEXT, re.MULTILINE)]
    assert numbers == list(range(1, len(numbers) + 1)), numbers


#: The module that turns a validated request into the dataclasses the engine
#: reads. Everything it does not pass is a default, and a default is an
#: assumption whether or not anybody wrote it down.
ASSEMBLY = METHODOLOGY.parent.parent / "backend" / "advice" / "assembly.py"

#: Every model input the API fills in rather than asks for, and the words this
#: document has to use about it.
#:
#: The list is written out, and the test below recomputes the same set from
#: assembly.py and fails when the two disagree. That pairing is the point.
#: Until 2026-08-21 the only check here compared a hand written list of five
#: names against a hand written table of six rows, and two lists that are both
#: written by hand do not check each other: `install_year` was missing from the
#: document, from the table and from the test at the same time, and chapter 6
#: described the ageing correction as something the model applies while nothing
#: ever supplied the year it needs.
FILLED_IN_BY_US = {
    "profile_category": "huizen zonder zonnepanelen",
    "shiftable_block_kwh": "Verplaatsbaar verbruik per dag",
    "install_year": "Hoe oud je panelen zijn",
    "system_loss_fraction": "systeemverlies",
}

#: The Dutch for each figure the document spells out in words rather than
#: digits, which is why a search for the digits finds nothing. Written as a map
#: from the value so that changing a constant fails here instead of silently
#: leaving the document describing the previous model.
NUMBER_WORDS = {
    0.005: "een half procent per jaar",
    0.05: "vijf procent minder opwek",
    0.10: "tien procent minder",
    0.20: "maximaal twintig procent",
}


def _fields_the_api_supplies(model: str, builder: str) -> set[str]:
    """The keyword arguments assembly.py actually passes to a model.

    Read from the source rather than by calling the function, because calling
    it needs a validated payload and the question is about the call site.
    """
    tree = ast.parse(ASSEMBLY.read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == builder
    )
    call = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == model
    )
    return {keyword.arg for keyword in call.keywords if keyword.arg}


def _filled_in_by_us() -> set[str]:
    filled: set[str] = set()
    for model, builder in ((Household, "build_household"), (PVSystem, "build_pv_system")):
        supplied = _fields_the_api_supplies(model.__name__, builder)
        filled |= {field.name for field in dataclasses.fields(model)} - supplied
    return filled


def test_the_list_of_filled_in_inputs_is_the_one_the_code_produces() -> None:
    """The check that would have caught the panel age.

    A field the API never passes takes its dataclass default, and that default
    is an answer the household never gave. Deriving the set here means a new
    default cannot arrive without either appearing in the document or failing
    this.
    """
    assert _filled_in_by_us() == set(FILLED_IN_BY_US), (
        "the inputs the API fills in itself are not the ones listed here:\n"
        f"  code:     {sorted(_filled_in_by_us())}\n"
        f"  this list: {sorted(FILLED_IN_BY_US)}"
    )


@pytest.mark.parametrize(("field", "phrase"), sorted(FILLED_IN_BY_US.items()))
def test_the_document_names_every_input_the_api_fills_in_itself(field: str, phrase: str) -> None:
    """A reader cannot check an assumption that is not written down."""
    assert phrase in TEXT, f"the document never names {field}, which the API fills in as a default"


def test_the_document_says_the_ageing_correction_is_not_applied() -> None:
    """Chapter 6 used to describe a correction the product never performs.

    The panels' year is the only input the ageing factor needs, nothing
    supplies it, so `degradation_factor` returns 1.0 for every household that
    has ever used this. The chapter said the model applies the factor, which
    made it a description of a model that does not ship.

    This test is conditional on purpose. The day the API starts asking for the
    year, `install_year` leaves the set above and this stops applying; until
    then the sentence has to stay.
    """
    if "install_year" not in _filled_in_by_us():
        pytest.skip("the API now supplies the install year, so the caveat no longer applies")
    assert degradation_factor(None, 2025) == 1.0, "an unknown install year no longer means new"
    chapter = TEXT.split("## 6.", 1)[1].split("## 7.", 1)[0]
    assert "gebruiken wij nu nooit" in chapter, (
        "chapter 6 no longer says the ageing correction is never applied"
    )


@pytest.mark.parametrize(("value", "words"), sorted(NUMBER_WORDS.items()))
def test_the_document_spells_out_the_degradation_the_code_applies(value: float, words: str) -> None:
    """These four figures appear as words, not digits, which is how they hid.

    A grep for "0,5" or "20" finds nothing in this document, so the only thing
    that ties the sentence to the constant is this map. Changing a constant
    without changing the words fails here rather than leaving the document
    describing the previous model.
    """
    known = {
        DEGRADATION_PER_YEAR,
        MAX_DEGRADATION,
        round(10 * DEGRADATION_PER_YEAR, 10),
        round(20 * DEGRADATION_PER_YEAR, 10),
    }
    assert value in known, f"{value} is no longer a figure the ageing model produces: {known}"
    assert words in TEXT, f"the document no longer spells out {value} as {words!r}"
