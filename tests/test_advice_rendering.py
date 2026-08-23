"""What a reader is finally shown.

Three properties are not negotiable and none of them is a matter of taste:
never a number without a band, the confidence label in plain sight, and the
free routes first. Each has its own test because each would fail silently.

The first of the three was the one this file could not actually check. It
walked the response looking for a ``p50`` without a ``p10`` beside it, which
finds a band that lost a member and finds nothing at all about a figure that
never had one. Five amounts were leaving here as lone numbers the whole time,
including the break even price the Dutch text tells the reader to hold a quote
against. The walk below asserts the rule instead of a symptom of it.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterator
from decimal import Decimal

import pytest

from advice.rendering import ROUTE_ORDER, money, render
from ampeer_advice.nl import SIZING_BASIS_TEXTS
from ampeer_advice.types import (
    Advice,
    BatteryAdvice,
    Confidence,
    FiredRule,
    Route,
    ScenarioBand,
)
from ampeer_sim.economics.sensitivity import band_from_differences
from ampeer_sim.types import Band, ProductionSource, Result

#: What the bands in this file say they moved and held. The real ones get these
#: from ampeer_advice.tariffs and ampeer_advice.advise.
VARIED = ("supply_price", "feed_in_price", "feed_in_cost_per_kwh")
PINNED = ("annual_consumption_kwh", "shiftable_block_kwh", "system_loss_fraction")


def _band_of(low: str, mid: str, high: str) -> ScenarioBand:
    return ScenarioBand.over(
        values=[Decimal(low), Decimal(mid), Decimal(high)],
        mid=Decimal(mid),
        varied=VARIED,
        pinned=PINNED,
    )


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
            estimated_saving_eur=_band_of("121.9012", "143.5612", "165.2212"),
        ),
    ),
    routes=(Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE),
    battery=None,
)

BATTERY = BatteryAdvice(
    sized_capacity_kwh=7.0,
    sized_at_largest_simulated_capacity=False,
    annual_saving_eur=_band_of("358.96", "422.31", "485.66"),
    payback_years=_band_of("7.74", "11.62", "20.16"),
    curve=(
        (3.0, _band_of("178.50", "210.00", "241.50")),
        (7.0, _band_of("358.96", "422.31", "485.66")),
    ),
    break_even_cost_per_kwh=_band_of("615.36", "696.82", "832.56"),
)

#: A key whose value is a figure about this household. Every one of them has to
#: arrive as a band or say in its own shape why it has none. The suffixes are
#: the units this product speaks in, so a new amount added to the response is
#: covered by this rule the moment it is named after what it measures.
FIGURE_SUFFIXES = ("_eur", "_years", "_kwh")

#: Named rather than suffixed, because it is the oldest key in the response.
FIGURE_KEYS = ("headline",)


def _is_percentile_band(node: object) -> bool:
    """The headline shape: percentiles of a stated number of runs."""
    return isinstance(node, dict) and set(node) == {"p10", "p50", "p90", "runs"}


#: Exact equality, not a subset, on purpose: a band that quietly gains a key is
#: a band whose shape changed without anybody deciding to. `varied_text` and
#: `pinned_text` joined on 2026-08-21, when the identifiers stopped reaching a
#: Dutch reader untranslated.
SCENARIO_BAND_KEYS = frozenset(
    {"low", "mid", "high", "varied", "pinned", "varied_text", "pinned_text", "combinations"}
)


def _is_scenario_band(node: object) -> bool:
    """A band measured at input levels, carrying what moved and what did not."""
    return (
        isinstance(node, dict)
        and set(node) == SCENARIO_BAND_KEYS
        and bool(node["varied"])
        # The Dutch names must be there and must line up one for one. A shorter
        # list would silently drop an assumption from what the reader is told
        # moved, which is worse than showing an identifier.
        and len(node["varied_text"]) == len(node["varied"])
        and len(node["pinned_text"]) == len(node["pinned"])
        # A translation, not a passthrough. An identifier carries an
        # underscore and a Dutch name does not, so this catches the one
        # failure mode that would look right in the payload: the label
        # table falling back to the key it could not find.
        and all("_" not in text for text in node["varied_text"] + node["pinned_text"])
    )


def _is_declared_bandless(node: object) -> bool:
    """A figure that legitimately has no band, and says why in the response."""
    return (
        isinstance(node, dict)
        and set(node) == {"value", "band", "basis", "basis_text"}
        and node["band"] is None
        and bool(node["basis_text"])
    )


def _figures(node: object, path: str = "") -> Iterator[tuple[str, object]]:
    """Every figure key in the response, with the path that leads to it."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if key in FIGURE_KEYS or key.endswith(FIGURE_SUFFIXES):
                yield here, value
            yield from _figures(value, here)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _figures(value, f"{path}[{index}]")


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


def test_the_headline_is_rounded_by_a_rule_money_does_not_own() -> None:
    """The exception to "rounded here and nowhere else", asserted out loud.

    The headline band is rounded to cents inside ampeer_sim by Python's round,
    which breaks a tie to the nearest even digit, while money breaks it away
    from zero. So two amounts of equal value can leave this file a cent apart,
    and money cannot undo it: by the time the band arrives the third decimal is
    gone. This package may not edit the simulation core, so the convention is
    pinned where it can be seen instead of being described as something it is
    not. If ampeer_sim ever rounds the other way, or stops rounding, this fails
    and the module docstring has to be rewritten rather than quietly become
    false.
    """
    band = band_from_differences([Decimal("700.125"), Decimal("700.125"), Decimal("700.125")])
    assert band.p50_eur == Decimal("700.12"), "the core no longer rounds half to even"
    assert money(Decimal("700.125")) == "700.13"
    assert money(band.p50_eur) == "700.12"


def test_the_headline_is_a_band_and_never_a_single_number() -> None:
    payload = render(ADVICE, RESULT, token="abc123")
    assert set(payload["headline"]) == {"p10", "p50", "p90", "runs"}
    assert payload["headline"]["p50"] == "700.08"
    assert payload["headline"]["runs"] == 243


def test_no_figure_anywhere_in_the_response_arrives_without_a_band() -> None:
    """The house rule, walked over the whole document.

    Every key that names an amount, a payback time or a capacity has to hold a
    band, or a shape that states in the response itself that it has none and
    why. The previous version of this test only looked for a p50 that had lost
    its neighbours, so five figures that never had a band at all passed it
    without a murmur.
    """
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    found = list(_figures(payload))
    assert len(found) >= 6, f"the walk found almost nothing, so it proves nothing: {found}"
    for path, value in found:
        if value is None:
            continue  # nothing was measured, which three rules do on purpose
        assert (
            _is_percentile_band(value) or _is_scenario_band(value) or _is_declared_bandless(value)
        ), f"{path} is a bare figure: {value!r}"


def test_a_band_measured_at_input_levels_never_borrows_the_percentile_names() -> None:
    """Two different kinds of claim may not look identical in one document.

    p10 and p90 on the headline are percentiles of 243 factorial runs. The
    battery band is the extremes of nine priced combinations with three
    uncertain inputs held still, and it used to be published under the same
    three key names with no runs count beside it, so nothing in the response
    distinguished a sampled distribution from a sweep of chosen levels.
    """
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    for path, value in _figures(payload):
        if path == ".headline":
            assert _is_percentile_band(value)
        elif isinstance(value, dict):
            assert "p50" not in value, f"{path} claims a percentile it did not measure"


def test_every_band_says_what_it_was_measured_over_and_what_it_left_out() -> None:
    """A band that does not say what it covers is read as covering everything.

    Three of the five assumptions the headline varies are held at their central
    value behind these figures, so the true spread is wider than what is shown.
    That is only honest if the response carries the list.
    """
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    bands = [value for _, value in _figures(payload) if _is_scenario_band(value)]
    assert bands
    for band in bands:
        assert isinstance(band, dict)
        assert band["varied"], "a band over nothing is three copies of one number"
        assert band["pinned"] == list(PINNED)
        assert band["combinations"] >= 3


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
    assert rule["saving_eur"]["mid"] == "143.56"
    assert len(rule["text"]) > 20


def test_what_a_free_route_is_worth_is_a_band_and_not_one_amount() -> None:
    """This is the figure that decides whether somebody rearranges their week.

    It left here as a single number while the document beside it promised there
    would never be one. It is measured at the three levels of the tariff band,
    which costs no extra simulation, so there was never a reason for it to be
    alone other than nobody noticing.
    """
    payload = render(ADVICE, RESULT, token="abc123")
    saving = payload["routes"][0]["rules"][0]["saving_eur"]
    assert saving["low"] == "121.90"
    assert saving["mid"] == "143.56"
    assert saving["high"] == "165.22"
    assert saving["varied"] == list(VARIED)


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
    figure in the advice the reader can go and check against a quote, and that
    is exactly why it may not be a single mid-scenario number. It was one until
    2026-08-21: a threshold to act on, published as a certainty."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    battery = payload["battery"]
    assert battery["sized_capacity_kwh"]["value"] == 7.0
    assert battery["break_even_cost_per_kwh"]["mid"] == "696.82"
    assert battery["break_even_cost_per_kwh"]["low"] == "615.36"
    assert battery["break_even_cost_per_kwh"]["high"] == "832.56"
    assert battery["annual_saving_eur"]["mid"] == "422.31"


def test_every_point_on_the_capacity_curve_carries_its_own_band() -> None:
    """The curve is the plot behind the recommendation, so it obeys the rule
    the recommendation obeys. Each point is a capacity, which is a coordinate,
    and a saving, which is a measurement and therefore a band."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    curve = payload["battery"]["curve"]
    assert [capacity for capacity, _ in curve] == [3.0, 7.0]
    for _, saving in curve:
        assert _is_scenario_band(saving), saving
    assert curve[0][1]["mid"] == "210.00"


def test_the_recommended_capacity_states_why_it_carries_no_band() -> None:
    """A capacity is a choice out of five simulated sizes, not an estimate.

    So it gets no band, and the response says that in its own shape rather than
    leaving a reader to wonder whether one went missing. The reason is a Dutch
    sentence from nl.py, keyed by an English id, like every other word here.
    """
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    capacity = payload["battery"]["sized_capacity_kwh"]
    assert capacity["value"] == 7.0
    assert capacity["band"] is None
    assert capacity["basis"] == "CHOSEN_FROM_SIMULATED_CAPACITIES"
    assert capacity["basis_text"] == SIZING_BASIS_TEXTS["CHOSEN_FROM_SIMULATED_CAPACITIES"]


def test_a_capacity_that_hit_the_top_of_the_range_is_labelled_differently() -> None:
    """15 kWh can mean the knee is at 15, or that the search ran out of curve.

    Those are different answers and the number cannot tell them apart. In the
    second case the recommendation is a floor, and a reader deciding what to buy
    needs to know which of the two they are looking at.
    """
    advice = dataclasses.replace(
        _advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)),
        battery=dataclasses.replace(
            BATTERY, sized_capacity_kwh=15.0, sized_at_largest_simulated_capacity=True
        ),
    )
    capacity = render(advice, RESULT, token="abc123")["battery"]["sized_capacity_kwh"]
    assert capacity["basis"] == "LIMITED_BY_LARGEST_SIMULATED_CAPACITY"
    assert "ondergrens" in capacity["basis_text"]


def test_no_em_dash_reaches_a_reader_through_this_response() -> None:
    """Project convention for every user-facing Dutch text, checked on the
    payload rather than on one dictionary, because the payload is what ships."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    assert "—" not in json.dumps(payload, ensure_ascii=False)


def test_the_payback_time_is_a_band_and_never_a_single_figure() -> None:
    """The most consequential sentence in the product hangs on this number, and
    the installed price it is computed from spans a factor two. One figure here
    would be a decision to buy or not to buy presented as a fact."""
    payload = render(_advice_with_battery(("BATTERY_DEPENDS_ON_PRICE",)), RESULT, token="abc123")
    payback = payload["battery"]["payback_years"]
    assert payback["low"] == "7.74"
    assert payback["mid"] == "11.62"
    assert payback["high"] == "20.16"
    assert payback["pinned"] == list(PINNED)


def test_the_battery_block_names_the_verdict_the_rules_reached() -> None:
    """Read back from the fired rules rather than recomputed. advise.py owns
    the payback thresholds, and a second copy of that decision here is a copy
    that can contradict the text the reader is shown two lines further up."""
    payload = render(_advice_with_battery(("BATTERY_DOES_NOT_PAY_BACK",)), RESULT, token="abc123")
    assert payload["battery"]["verdict"] == "BATTERY_DOES_NOT_PAY_BACK"


def test_every_field_of_a_battery_advice_reaches_the_reader() -> None:
    """A field added to BatteryAdvice and not rendered is a figure the engine
    computed and nobody sees. The flag that says whether the capacity hit the
    top of the simulated range reaches the reader inside the capacity block, as
    the reason it carries no band, so it is checked under that name."""
    payload = render(_advice_with_battery(("CONSIDER_BATTERY",)), RESULT, token="abc123")
    rendered = set(payload["battery"])
    for field in dataclasses.fields(BatteryAdvice):
        expected = (
            "sized_capacity_kwh"
            if field.name == "sized_at_largest_simulated_capacity"
            else field.name
        )
        assert expected in rendered, f"{field.name} never reaches the reader"
    assert payload["battery"]["sized_capacity_kwh"]["basis"]


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


def test_the_order_the_rules_fire_in_is_the_order_the_reader_is_shown() -> None:
    """Two notions of route order, and nothing tied them together.

    `evaluate` sorts the fired rules on `Route.value`. `_routes` builds the
    blocks a reader sees by walking `ROUTE_ORDER`, a tuple written out by hand
    in this module. They agree today because the enum happens to carry 1, 2 and
    3 in the same sequence that tuple lists.

    Nothing said they had to. Changing `Route.STORAGE` to 0 leaves the rendered
    blocks in their old order while the fired list, and therefore
    `recommended_route`, puts storage first. The reader would then be shown the
    free routes at the top of the page and told a battery is the first thing to
    do.

    Derived from both sides rather than written out a third time. The literal
    order already has a test above; this one is about the two agreeing.
    """
    from ampeer_advice.rules import RULES
    from ampeer_advice.types import Route

    by_value = sorted(Route, key=lambda route: route.value)
    assert by_value == list(ROUTE_ORDER), (
        f"evaluate would present {[route.name for route in by_value]} and this module "
        f"renders {[route.name for route in ROUTE_ORDER]}"
    )
    assert {rule.route for rule in RULES} <= set(ROUTE_ORDER), (
        "a rule now names a route the renderer never walks, so its advice reaches nobody"
    )
