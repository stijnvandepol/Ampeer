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
REPO_ROOT = Path(__file__).resolve().parent.parent
SERIALIZERS = REPO_ROOT / "backend" / "advice" / "serializers.py"
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


#: Every model dataclass the API builds, and the function in assembly.py that
#: builds it. EV and HeatPump are constructed inside build_household, which is
#: why two of them name the same builder.
BUILT_MODELS = (
    ("Household", "build_household"),
    ("PVSystem", "build_pv_system"),
    ("EV", "build_household"),
    ("HeatPump", "build_household"),
    ("BatterySpec", "build_battery_spec"),
)

#: Every field on those five that the API leaves at its default, the value it
#: leaves it at, and the words this document uses about it.
#:
#: The value is written down beside the phrase on purpose. Keying only on the
#: field name would let somebody change 12.000 kilometres to 20.000 while the
#: document still said twelve and this test still passed, which is the failure
#: the whole file exists for.
#:
#: Until 2026-08-21 this test looked at Household and PVSystem alone, so the
#: nine defaults on the three nested models were invisible to it. Six of them
#: were in no chapter of the document at all, including the size of the car:
#: 12.000 km at 18 kWh per 100 km is 2160 kWh a year, against the 3500 kWh the
#: reference household uses in total. A visitor who answered "yes, and it
#: charges on my surplus" was given a car nobody described.
ASSUMED_DEFAULTS = {
    ("Household", "profile_category"): ("E1A", "huizen zonder zonnepanelen"),
    ("Household", "shiftable_block_kwh"): (1.0, "Verplaatsbaar verbruik per dag"),
    ("PVSystem", "install_year"): (None, "Hoe oud je panelen zijn"),
    ("PVSystem", "system_loss_fraction"): (0.14, "systeemverlies"),
    ("EV", "annual_km"): (12_000, "12.000 kilometer"),
    ("EV", "kwh_per_100km"): (18.0, "18 kWh per 100"),
    ("EV", "charge_power_kw"): (3.7, "3,7 kilowatt"),
    ("HeatPump", "base_temperature_c"): (15.0, "15 graden"),
    ("HeatPump", "cop_at_7c"): (3.5, "3,5 bij 7 graden"),
    ("HeatPump", "cop_slope_per_c"): (0.06, "0,06 daalt"),
    ("BatterySpec", "round_trip_efficiency"): (0.90, "rendement van 90 procent"),
    ("BatterySpec", "usable_dod"): (0.90, "diepte stellen wij op 90 procent"),
    ("BatterySpec", "allow_grid_charging"): (False, "laadt nooit stroom van het net"),
}


def _model(name: str) -> type:
    import ampeer_sim.types as types_module

    model = getattr(types_module, name, None)
    assert model is not None, f"ampeer_sim.types no longer defines {name}"
    return model


def _defaults_the_api_leaves(name: str, builder: str) -> dict[str, object]:
    """Field name to default, for every field assembly.py does not pass."""
    supplied = _fields_the_api_supplies(name, builder)
    return {
        field.name: field.default
        for field in dataclasses.fields(_model(name))
        if field.name not in supplied
    }


def test_the_list_of_assumed_defaults_is_the_one_the_code_produces() -> None:
    """Two directions, because one of them is how this went wrong.

    A default arriving on any of the five must appear here, and an entry here
    must still be a default the API leaves. Without the second half a field the
    API starts asking for keeps a line vouching for an assumption that is no
    longer made.
    """
    found = {
        (name, field)
        for name, builder in BUILT_MODELS
        for field in _defaults_the_api_leaves(name, builder)
    }
    assert found == set(ASSUMED_DEFAULTS), (
        "the defaults the API leaves are not the ones listed here:\n"
        f"  code only: {sorted(found - set(ASSUMED_DEFAULTS))}\n"
        f"  list only: {sorted(set(ASSUMED_DEFAULTS) - found)}"
    )


@pytest.mark.parametrize(("key", "expected"), sorted(ASSUMED_DEFAULTS.items()))
def test_every_assumed_default_is_still_the_value_the_document_describes(
    key: tuple[str, str], expected: tuple[object, str]
) -> None:
    """The value and the sentence move together or this fails."""
    name, field = key
    value, phrase = expected
    actual = _defaults_the_api_leaves(name, dict(BUILT_MODELS)[name])[field]
    # An enum default is compared by its value, so the expected column reads as
    # the profile name a person would recognise rather than as a repr.
    actual = getattr(actual, "value", actual)
    assert actual == value, (
        f"{name}.{field} is now {actual!r} and the document still describes {value!r}"
    )
    assert phrase in TEXT, f"the document no longer says {phrase!r} about {name}.{field}"


def test_the_document_says_the_battery_never_charges_from_the_grid() -> None:
    """The engine can. The product does not, and the difference is the claim.

    `allow_grid_charging` defaults to False, no caller outside the tests sets
    it, and nothing outside the tests selects ARBITRAGE or HYBRID or supplies
    prices per quarter. So a battery in an answer only ever stores surplus.
    Chapter 8 used to open with what the engine does when it trades, which
    invites a reader to assume the answer contains that, and a battery that
    trades is the version a seller quotes.
    """
    import ampeer_sim.simulate as simulate_module

    source = Path(simulate_module.__file__).read_text(encoding="utf-8")
    assert "strategy: Strategy = Strategy.SELF_CONSUMPTION" in source, (
        "the default strategy moved; chapter 8 says a battery only stores surplus"
    )
    chapter = TEXT.split("## 8.", 1)[1].split("## 9.", 1)[0]
    assert "laadt nooit stroom van het net" in chapter
    assert "handelt niet op de stroombeurs" in chapter


def _class_attribute(source: Path, class_name: str, attribute: str) -> object:
    """A ClassVar assigned a literal, read without importing Django."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        item
        for item in ast.walk(tree)
        if isinstance(item, ast.ClassDef) and item.name == class_name
    )
    for statement in node.body:
        target = None
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            target = statement.target.id
        elif isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name):
            target = statement.targets[0].id
        if target == attribute:
            value = statement.value
            assert isinstance(value, ast.Constant), f"{class_name}.{attribute} is not a literal"
            return value.value
    raise AssertionError(f"{class_name} no longer sets {attribute}")


def test_the_document_says_where_a_battery_gets_its_power() -> None:
    """The fourth of the four things chapter 8 says it models.

    Depth and efficiency had values, power did not, and power is derived rather
    than asked: every battery on the capacity curve is modelled at half its
    capacity in kilowatts. The constant carries a measurement saying the answer
    does not move between 0.3 and 1.0, and that measurement is more useful to a
    reader than the number, so the chapter carries both.
    """
    from ampeer_advice.advise import BATTERY_C_RATE

    assert BATTERY_C_RATE == 0.5, (
        f"a battery is now modelled at {BATTERY_C_RATE} C and chapter 8 says half"
    )
    chapter = TEXT.split("## 8.", 1)[1].split("## 9.", 1)[0]
    assert "de helft ervan in kilowatt" in chapter
    assert "5 kW bij een batterij van 10 kWh" in chapter
    assert "0,3 en 1,0" in chapter, "the chapter no longer quotes the range that was measured"


def test_the_document_explains_all_three_confidence_levels() -> None:
    """A label on every answer, explained in one word until 2026-08-21.

    The document named INDICATIVE in passing and said nothing about the other
    two, so a household reading "indicatief" had no way to learn what the scale
    was or how to move up it. The answer is short and worth printing: round one
    or round two.
    """
    from ampeer_advice.confidence import GOOD_FIELD_COUNT

    chapter = TEXT.split("## 17.", 1)[1].split("## 18.", 1)[0]
    for word in ("Indicatief", "Goed", "Precies"):
        assert word in chapter, f"chapter 17 no longer names {word}"
    assert GOOD_FIELD_COUNT == 5, (
        f"the threshold is now {GOOD_FIELD_COUNT} and the chapter says five"
    )
    assert "de grens ligt bij vijf" in chapter

    estimate = _class_attribute(SERIALIZERS, "EstimateInputSerializer", "QUESTION_COUNT")
    refine = _class_attribute(SERIALIZERS, "RefineInputSerializer", "QUESTION_COUNT")
    assert (estimate, refine) == (4, 9), (
        f"the two forms now count {estimate} and {refine}; chapter 17 says four and nine"
    )
    assert "vier vragen van ronde 1" in chapter
    assert "negen in totaal" in chapter


def test_the_document_says_precise_cannot_be_reached_yet() -> None:
    """The third level, and the third dead path found in this document.

    `confidence_for` returns PRECISE only for has_meter_data, and nothing
    outside ampeer_advice ever passes it, so no answer this version produces can
    carry that word. Leaving the level in the scale is fine; leaving a reader to
    discover it is unreachable is not.

    Conditional, like the one about the ageing correction: the day the API
    supplies meter data this stops applying and the sentence has to go.
    """
    supplied = any(
        isinstance(node, ast.Call)
        and any(keyword.arg == "has_meter_data" for keyword in node.keywords)
        for path in (REPO_ROOT / "backend").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    )
    if supplied:
        pytest.skip("the API now supplies meter data, so PRECISE is reachable")
    chapter = TEXT.split("## 17.", 1)[1].split("## 18.", 1)[0]
    assert "kun je vandaag niet krijgen" in chapter, (
        "nothing supplies meter data, so no answer can say PRECISE, and chapter 17 "
        "has to keep saying so"
    )


def test_the_document_describes_the_table_used_when_pvgis_is_unreachable() -> None:
    """A path a real visitor lands on, and the chapter did not say it existed.

    backend/advice/production.py wraps PvgisProvider in a
    ResilientProductionProvider with FallbackProvider behind it, so a network
    failure produces an answer computed from a table rather than an error. The
    answer itself says so through nl.py. Chapter 6 said only that we ask PVGIS,
    which is the sentence somebody would quote back at us.

    The annual total is recomputed from the table rather than read from its
    docstring, so a rebuilt table cannot leave the document quoting the old one.
    """
    import calendar

    from ampeer_sim.production.fallback_yield import MONTHLY_MEAN_PRODUCTION_W_PER_KWP

    days = [calendar.monthrange(2023, month)[1] for month in range(1, 13)]
    assert len(MONTHLY_MEAN_PRODUCTION_W_PER_KWP) == len(days)
    annual = sum(
        watts * count * 24 / 1000.0
        for watts, count in zip(MONTHLY_MEAN_PRODUCTION_W_PER_KWP, days, strict=True)
    )
    chapter = TEXT.split("## 6.", 1)[1].split("## 7.", 1)[0]
    assert f"{round(annual)} kWh per" in chapter, (
        f"the fallback table totals {annual:.1f} kWh per kWp and chapter 6 quotes something else"
    )

    production = (REPO_ROOT / "backend" / "advice" / "production.py").read_text(encoding="utf-8")
    assert "ResilientProductionProvider" in production, (
        "nothing falls back any more, so chapter 6 describes a path that is gone"
    )
    assert "PVGIS niet bereikbaar" in TEXT or "PVGIS niet bereikbaar is" in chapter
    assert "halve sinus" in chapter, "the chapter no longer states the weakness of the table"


def test_the_document_says_which_of_the_three_household_profiles_is_used() -> None:
    """Three exist in the enum, one is ever used, and the API cannot choose.

    `Household.profile_category` defaults to E1A and assembly.py does not pass
    it, so a household on a double tariff is modelled on a single tariff shape.
    The figures in chapter 2 are the measured consequence rather than a worry:
    the share of the year falling in the solar window differs by about one
    point between the three, which is less than the tariff names suggest.
    """
    from ampeer_sim.types import ProfileCategory

    assert [category.value for category in ProfileCategory] == ["E1A", "E1B", "E1C"], (
        "the profile categories changed; chapter 2 says there are three"
    )
    chapter = TEXT.split("## 2.", 1)[1].split("## 3.", 1)[0]
    assert "drie van deze profielen" in chapter
    assert "enkel tarief" in chapter
    for share in ("27,05", "26,63", "27,95"):
        assert share in chapter, f"chapter 2 no longer quotes the measured share {share}"


def test_the_measured_shares_in_chapter_two_are_the_ones_the_profiles_have() -> None:
    """The one measurement in this document taken from the data file itself.

    data/ is git-ignored, so this can only run where the NEDU file is present.
    Skipping where it is absent is honest; asserting nothing would let the three
    figures drift with the next profile year and say so nowhere.
    """
    import numpy as np

    from ampeer_sim.profiles.nedu import NeduFileProvider
    from ampeer_sim.types import ProfileCategory

    profiles = REPO_ROOT / "data" / "nedu-profiles-2025.csv"
    if not profiles.is_file():
        pytest.skip("the NEDU profile file is not committed; see infra/README.md")

    provider = NeduFileProvider(profiles)
    chapter = TEXT.split("## 2.", 1)[1].split("## 3.", 1)[0]
    for category in ProfileCategory:
        fractions = provider.fractions(2025, category)
        quarter_of_day = np.arange(len(fractions)) % 96
        # 10:00 to 16:00, the window the sun and the argument are both about.
        window = (quarter_of_day >= 40) & (quarter_of_day < 64)
        share = fractions[window].sum() / fractions.sum() * 100
        printed = f"{share:.2f}".replace(".", ",")
        assert printed in chapter, (
            f"{category.value} puts {printed} percent in the solar window and chapter 2 "
            "quotes something else"
        )
