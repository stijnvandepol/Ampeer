"""What a reader is finally shown.

Three properties are not negotiable and none of them is a matter of taste:
never a number without a band, the confidence label in plain sight, and the
free routes first. Each has its own test because each would fail silently.
"""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest

from advice.rendering import money, render
from ampeer_advice.types import (
    Advice,
    BatteryAdvice,
    Confidence,
    FiredRule,
    Route,
)
from ampeer_sim.types import Band, ProductionSource, Result

BAND = Band(
    p10_eur=Decimal("561.11"), p50_eur=Decimal("700.08"), p90_eur=Decimal("846.90"), runs=243
)

RESULT = Result(
    engine_version="0.1.0",
    band=BAND,
    self_consumption_rate=0.31,
    production_source=ProductionSource.PVGIS,
    profile_year=2025,
    weather_year=2023,
)

ADVICE = Advice(
    engine_version="0.1.0",
    advice_version="0.1.0",
    confidence=Confidence.INDICATIVE,
    headline=BAND,
    fired=(
        FiredRule(
            rule_id="SHIFT_FLEXIBLE_LOAD",
            route=Route.SHIFT_BEHAVIOUR,
            estimated_saving_eur=Decimal("143.5612"),
        ),
    ),
    routes=(Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE),
    battery=None,
)

BATTERY = BatteryAdvice(
    sized_capacity_kwh=7.0,
    annual_saving_eur=Decimal("422.31"),
    payback_years_p10=Decimal("7.74"),
    payback_years_p50=Decimal("11.62"),
    payback_years_p90=Decimal("15.49"),
    curve=((3.0, Decimal("210.00")), (7.0, Decimal("422.31"))),
    break_even_cost_per_kwh=Decimal("696.82"),
)


def _advice_with_battery(verdict_rule_ids: tuple[str, ...]) -> Advice:
    """An advice whose storage slot holds the rules named, and a battery.

    advise.py fills that slot with exactly one rule whenever it computed a
    battery, by substituting the verdict in place of CONSIDER_BATTERY. The
    argument is a tuple so a test can also build the shapes it promises never
    to produce.
    """
    return dataclasses.replace(
        ADVICE,
        confidence=Confidence.GOOD,
        fired=tuple(
            FiredRule(rule_id=rule_id, route=Route.STORAGE, estimated_saving_eur=None)
            for rule_id in verdict_rule_ids
        ),
        battery=BATTERY,
    )


def test_money_is_a_string_with_two_decimals() -> None:
    """JSON has floats and no decimals. A euro amount that goes through a JSON
    float parser is exactly the rounding error this project avoids everywhere
    else, so amounts cross the wire as text."""
    assert money(Decimal("143.5612")) == "143.56"
    assert money(Decimal("700")) == "700.00"
    assert money(Decimal("0")) == "0.00"


def test_money_rounds_half_away_from_zero_everywhere() -> None:
    """One rounding convention, in one function. Two conventions in one
    response is how a total stops matching its own parts."""
    assert money(Decimal("0.125")) == "0.13"
    assert money(Decimal("-0.125")) == "-0.13"


def test_the_headline_is_a_band_and_never_a_single_number() -> None:
    payload = render(ADVICE, RESULT, token="abc123")
    assert set(payload["headline"]) == {"p10", "p50", "p90", "runs"}
    assert payload["headline"]["p50"] == "700.08"
    assert payload["headline"]["runs"] == 243


def test_no_key_anywhere_in_the_response_holds_a_lone_middle_value() -> None:
    """Walks the whole document. A p50 without its neighbours anywhere in here
    is a number presented as certain, which is the one thing this product
    promises not to do."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "p50" in node:
                assert {"p10", "p90"} <= set(node), f"lone p50 in {sorted(node)}"
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)


def test_the_confidence_label_sits_at_the_top_level() -> None:
    """A footnote is where a caveat goes to be ignored."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert payload["confidence"] == "INDICATIVE"


def test_the_confidence_carries_the_word_a_reader_sees_next_to_it() -> None:
    """The routes already cross this boundary carrying Dutch titles, and this
    label is subject to the same rule: Dutch lives in nl.py and is not written
    down a second time in whatever renders the page."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert payload["confidence_label"] == "Indicatief"


def test_all_three_routes_are_always_present_and_always_in_order() -> None:
    """Two rules at once. The free routes come first even when they are worth
    nothing, and an empty route is sent rather than dropped, so the frontend
    never has to know the order to restore it."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert [route["route"] for route in payload["routes"]] == [
        "SHIFT_BEHAVIOUR",
        "SMART_CONTROL",
        "STORAGE",
    ]
    assert payload["routes"][1]["rules"] == []


def test_every_route_carries_the_dutch_title_that_says_what_it_costs() -> None:
    payload = render(ADVICE, RESULT, token="abc123")
    assert payload["routes"][0]["title"].startswith("Gratis")
    assert payload["routes"][2]["title"].startswith("Investeren")


def test_every_fired_rule_carries_its_id_and_its_dutch_text() -> None:
    """The id is what makes an advice explainable and reproducible; the text is
    what a person reads. Sending only the text would make the advice
    unauditable, sending only the id would make it unreadable."""
    payload = render(ADVICE, RESULT, token="abc123")
    rule = payload["routes"][0]["rules"][0]
    assert rule["rule_id"] == "SHIFT_FLEXIBLE_LOAD"
    assert rule["saving_eur"] == "143.56"
    assert len(rule["text"]) > 20


def test_a_rule_that_measured_no_saving_says_so_rather_than_showing_a_zero() -> None:
    """Three of the rules estimate nothing at all, on purpose. A 0.00 next to
    "have your existing battery checked" would read as a measured result, and
    the measurement was never made."""
    advice = dataclasses.replace(
        ADVICE,
        fired=(
            FiredRule(
                rule_id="REVIEW_EXISTING_BATTERY",
                route=Route.STORAGE,
                estimated_saving_eur=None,
            ),
        ),
    )
    payload = render(advice, RESULT, token="abc123")
    assert payload["routes"][2]["rules"][0]["saving_eur"] is None


def test_a_household_with_no_battery_advice_still_gets_the_key() -> None:
    """An absent key and a null mean different things to a frontend, and only
    one of them is "we looked and the answer is no"."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert "battery" in payload
    assert payload["battery"] is None


def test_a_battery_advice_reports_a_payback_band_and_a_break_even_price() -> None:
    """A refusal to buy is a valid and required outcome, and it needs a
    defensible reason attached. The break-even price is that reason: it is the
    one figure in the advice the reader can go and check against a quote."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    battery = payload["battery"]
    assert battery["sized_capacity_kwh"] == 7.0
    assert battery["break_even_cost_per_kwh"] == "696.82"
    assert battery["annual_saving_eur"] == "422.31"
    assert battery["curve"] == [[3.0, "210.00"], [7.0, "422.31"]]


def test_the_payback_time_is_a_band_and_never_a_single_figure() -> None:
    """The most consequential sentence in the product hangs on this number, and
    the installed price it is computed from spans a factor two. One figure here
    would be a decision to buy or not to buy presented as a fact."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    assert payload["battery"]["payback_years"] == {"p10": "7.74", "p50": "11.62", "p90": "15.49"}


def test_the_battery_block_names_the_verdict_the_rules_reached() -> None:
    """Read back from the fired rules rather than recomputed. advise.py owns
    the payback thresholds, and a second copy of that decision here is a copy
    that can contradict the text the reader is shown two lines further up."""
    payload = render(_advice_with_battery(("BATTERY_DOES_NOT_PAY_BACK",)), RESULT, token="abc123")
    assert payload["battery"]["verdict"] == "BATTERY_DOES_NOT_PAY_BACK"


def test_every_field_of_a_battery_advice_reaches_the_reader() -> None:
    """A field added to BatteryAdvice and not rendered is a figure the engine
    computed and nobody sees. The three payback fields arrive as one band, so
    they are checked under that name."""
    payload = render(_advice_with_battery(("CONSIDER_BATTERY",)), RESULT, token="abc123")
    rendered = set(payload["battery"])
    for field in dataclasses.fields(BatteryAdvice):
        expected = "payback_years" if field.name.startswith("payback_years") else field.name
        assert expected in rendered, f"{field.name} never reaches the reader"


@pytest.mark.parametrize("storage_rules", [(), ("CONSIDER_BATTERY", "REVIEW_EXISTING_BATTERY")])
def test_a_battery_without_exactly_one_verdict_is_refused_rather_than_shown(
    storage_rules: tuple[str, ...],
) -> None:
    """There is one storage slot and advise.py substitutes the verdict into it,
    so a battery block with no verdict, or with two, is a composition fault. It
    fails here instead of rendering a recommendation with no stated conclusion,
    which is the shape a reader cannot tell apart from a sales pitch."""
    with pytest.raises(ValueError, match="verdict"):
        render(_advice_with_battery(storage_rules), RESULT, token="abc123")


def test_the_response_names_the_versions_and_years_it_was_computed_with() -> None:
    """Every calculation logs its engine version. An advice that cannot say
    which model produced it cannot be defended when somebody disagrees."""
    payload = render(ADVICE, RESULT, token="abc123")
    assert payload["engine_version"] == "0.1.0"
    assert payload["advice_version"] == "0.1.0"
    assert payload["production_source"] == "PVGIS"
    assert payload["profile_year"] == 2025
    assert payload["weather_year"] == 2023


def test_the_token_is_carried_back_so_the_link_is_shareable() -> None:
    assert render(ADVICE, RESULT, token="abc123")["token"] == "abc123"


def test_the_whole_response_survives_json_serialisation() -> None:
    """A Decimal that reached the payload would raise here rather than in
    production."""
    payload = render(_advice_with_battery(("CONSIDER_BATTERY",)), RESULT, token="abc123")
    assert json.loads(json.dumps(payload)) == payload
