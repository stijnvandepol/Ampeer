"""Tests for the advice rule table and the confidence level.

The rule table is data, so these tests read like a truth table: for a context
that satisfies a condition the rule id must appear, and for one that does not it
must be absent. Nothing here asserts on a sentence, because a rule that returns a
sentence is a defect this layering exists to make impossible.
"""

from __future__ import annotations

import itertools
from decimal import Decimal
from typing import Any

from ampeer_advice.confidence import confidence_for
from ampeer_advice.rules import RULE_IDS, RULES, evaluate
from ampeer_advice.types import AdviceContext, Confidence, Route
from ampeer_sim.types import Band

_NEUTRAL: dict[str, Any] = {
    "self_consumption_rate": 0.5,
    "annual_production_kwh": 3_500.0,
    "annual_export_kwh": 1_000.0,
    "annual_import_kwh": 2_000.0,
    "mean_evening_night_consumption_kwh": 5.0,
    "midday_surplus_kwh": 800.0,
    "export_after_free_routes_kwh": 1_000.0,
    "daytime_occupancy": False,
    "has_ev": False,
    "ev_charges_on_solar": False,
    "has_battery": False,
    "battery_capacity_kwh": None,
    "dynamic_contract": False,
    "headline": Band(Decimal("500"), Decimal("600"), Decimal("700"), runs=81),
    "confidence": Confidence.INDICATIVE,
}


def _context(**overrides: Any) -> AdviceContext:
    """A context that fires nothing, so every test states its own trigger."""
    fields = dict(_NEUTRAL)
    fields.update(overrides)
    return AdviceContext(**fields)


def _fired_ids(context: AdviceContext) -> list[str]:
    return [fired.rule_id for fired in evaluate(context)]


def _saving(context: AdviceContext, rule_id: str) -> Decimal | None:
    (fired,) = [f for f in evaluate(context) if f.rule_id == rule_id]
    return fired.estimated_saving_eur


def _every_context() -> list[AdviceContext]:
    """A small exhaustive sweep over the fields the conditions actually read."""
    contexts = []
    for (
        self_consumption_rate,
        export,
        evening,
        surplus,
        daytime_occupancy,
        has_ev,
        ev_charges_on_solar,
        has_battery,
        dynamic_contract,
    ) in itertools.product(
        (0.20, 0.50),
        (0.0, 2_000.0),
        (1.0, 5.0),
        (100.0, 800.0),
        (False, True),
        (False, True),
        (False, True),
        (False, True),
        (False, True),
    ):
        contexts.append(
            _context(
                self_consumption_rate=self_consumption_rate,
                annual_export_kwh=export,
                mean_evening_night_consumption_kwh=evening,
                midday_surplus_kwh=surplus,
                daytime_occupancy=daytime_occupancy,
                has_ev=has_ev,
                ev_charges_on_solar=ev_charges_on_solar,
                has_battery=has_battery,
                battery_capacity_kwh=10.0 if has_battery else None,
                dynamic_contract=dynamic_contract,
            )
        )
    return contexts


def test_every_rule_id_is_unique() -> None:
    ids = [rule.rule_id for rule in RULES]
    assert len(ids) == len(set(ids))
    assert RULE_IDS == frozenset(ids)


def test_rules_are_in_priority_order() -> None:
    priorities = [rule.priority for rule in RULES]
    assert priorities == sorted(priorities)
    assert len(set(priorities)) == len(priorities)


def test_shift_flexible_load_fires_on_low_self_consumption_and_nobody_home() -> None:
    context = _context(self_consumption_rate=0.30, daytime_occupancy=False)
    assert "SHIFT_FLEXIBLE_LOAD" in _fired_ids(context)
    # No euro figure here on purpose. What this intervention is worth is measured
    # by simulating it, in advise.py, because three rules estimating from the
    # same context priced the same kilowatt hours three times over.
    assert _saving(context, "SHIFT_FLEXIBLE_LOAD") is None


def test_shift_flexible_load_does_not_fire_when_somebody_is_home() -> None:
    context = _context(self_consumption_rate=0.30, daytime_occupancy=True)
    assert "SHIFT_FLEXIBLE_LOAD" not in _fired_ids(context)
    # Nor on a household that already uses most of its own production.
    assert "SHIFT_FLEXIBLE_LOAD" not in _fired_ids(_context(self_consumption_rate=0.35))


def test_charge_ev_on_surplus_needs_an_ev_that_is_not_already_solar_charging() -> None:
    charging_at_night = _context(has_ev=True, ev_charges_on_solar=False, midday_surplus_kwh=800.0)
    assert "CHARGE_EV_ON_SURPLUS" in _fired_ids(charging_at_night)
    assert _saving(charging_at_night, "CHARGE_EV_ON_SURPLUS") is None

    already_solar = _context(has_ev=True, ev_charges_on_solar=True, midday_surplus_kwh=800.0)
    assert "CHARGE_EV_ON_SURPLUS" not in _fired_ids(already_solar)
    assert "CHARGE_EV_ON_SURPLUS" not in _fired_ids(
        _context(has_ev=False, midday_surplus_kwh=800.0)
    )
    assert "CHARGE_EV_ON_SURPLUS" not in _fired_ids(_context(has_ev=True, midday_surplus_kwh=500.0))


def test_consider_dynamic_contract_needs_a_fixed_contract_and_heavy_export() -> None:
    heavy = _context(annual_production_kwh=3_500.0, annual_export_kwh=2_000.0)
    assert "CONSIDER_DYNAMIC_CONTRACT" in _fired_ids(heavy)
    assert _saving(heavy, "CONSIDER_DYNAMIC_CONTRACT") is None

    assert "CONSIDER_DYNAMIC_CONTRACT" not in _fired_ids(
        _context(annual_production_kwh=3_500.0, annual_export_kwh=2_000.0, dynamic_contract=True)
    )
    assert "CONSIDER_DYNAMIC_CONTRACT" not in _fired_ids(
        _context(annual_production_kwh=3_500.0, annual_export_kwh=1_400.0)
    )
    # A household without production must not divide by zero.
    assert "CONSIDER_DYNAMIC_CONTRACT" not in _fired_ids(
        _context(annual_production_kwh=0.0, annual_export_kwh=0.0)
    )


def test_consider_battery_judges_the_export_left_after_the_free_routes() -> None:
    """Storage is judged on the residual, which is what the Dutch copy claims.

    The rule used to read annual_export_kwh, the export the household has
    before doing anything, while the spec and the text both said "after routes
    1 and 2". A household could therefore be told to buy a battery sized on
    kilowatt hours it would no longer be exporting once it had done the free
    things it was told to do first.
    """
    context = _context(export_after_free_routes_kwh=2_000.0)
    assert "CONSIDER_BATTERY" in _fired_ids(context)
    # Its value is the advice itself, so it carries no invented figure.
    assert _saving(context, "CONSIDER_BATTERY") is None

    assert "CONSIDER_BATTERY" not in _fired_ids(_context(export_after_free_routes_kwh=1_500.0))
    # A battery that is full at sunset and still full at sunrise saves nothing.
    assert "CONSIDER_BATTERY" not in _fired_ids(
        _context(export_after_free_routes_kwh=2_000.0, mean_evening_night_consumption_kwh=3.0)
    )


def test_a_large_export_today_does_not_justify_storage_if_the_free_routes_absorb_it() -> None:
    """The case that made this change necessary.

    Marloes exports plenty as she lives now, and none of it survives charging
    her car on her own surplus. Before this, she was told to buy a battery for
    kilowatt hours the previous line of the same advice had just told her how
    to use.
    """
    absorbed = _context(
        annual_export_kwh=4_000.0,
        export_after_free_routes_kwh=900.0,
        mean_evening_night_consumption_kwh=8.0,
    )
    assert "CONSIDER_BATTERY" not in _fired_ids(absorbed)


def test_consider_battery_does_not_fire_when_a_battery_is_present() -> None:
    context = _context(
        annual_export_kwh=2_000.0,
        mean_evening_night_consumption_kwh=5.0,
        has_battery=True,
        battery_capacity_kwh=10.0,
    )
    fired = _fired_ids(context)
    assert "CONSIDER_BATTERY" not in fired
    assert "REVIEW_EXISTING_BATTERY" in fired


def test_review_existing_battery_fires_only_with_a_battery() -> None:
    assert "REVIEW_EXISTING_BATTERY" in _fired_ids(
        _context(has_battery=True, battery_capacity_kwh=5.0)
    )
    assert "REVIEW_EXISTING_BATTERY" not in _fired_ids(_context(has_battery=False))


def test_battery_does_not_pay_back_never_fires_from_the_table_alone() -> None:
    """It needs a payback figure AdviceContext does not carry, so advise.py sets it.

    Its condition in the table is deliberately always false. This test is what
    keeps that deliberate choice from being read as a bug and repaired.
    """
    assert "BATTERY_DOES_NOT_PAY_BACK" in RULE_IDS
    for context in _every_context():
        assert "BATTERY_DOES_NOT_PAY_BACK" not in _fired_ids(context)


def test_free_routes_are_always_ordered_before_storage() -> None:
    for context in _every_context():
        routes = [fired.route.value for fired in evaluate(context)]
        assert routes == sorted(routes), context


def test_the_rule_table_never_estimates_a_saving() -> None:
    """A rule decides whether, never how much.

    The table can only see AdviceContext, so any euro figure it produced was an
    analytic guess. Three of them drew on the same kilowatt hours independently,
    which meant the numbers could not be added together, and one valued a
    shifted kWh at 0.27 euro where the engine measures a different figure
    entirely. advise.py measures each intervention by simulating it.
    """
    for context in _every_context():
        for fired in evaluate(context):
            assert fired.estimated_saving_eur is None, fired


def test_no_rule_returns_dutch_text() -> None:
    """A FiredRule carries an id, a route and a number, never a sentence."""
    for context in _every_context():
        for fired in evaluate(context):
            assert isinstance(fired.rule_id, str)
            assert " " not in fired.rule_id
            assert fired.rule_id == fired.rule_id.upper()
            assert isinstance(fired.route, Route)


def test_confidence_rises_with_the_number_of_filled_fields() -> None:
    assert confidence_for(0, has_meter_data=False) is Confidence.INDICATIVE
    assert confidence_for(4, has_meter_data=False) is Confidence.INDICATIVE
    assert confidence_for(5, has_meter_data=False) is Confidence.GOOD
    assert confidence_for(9, has_meter_data=False) is Confidence.GOOD
    assert confidence_for(20, has_meter_data=False) is Confidence.GOOD
    levels = [confidence_for(n, has_meter_data=False).value for n in range(21)]
    assert levels == sorted(levels)


def test_meter_data_always_means_precise() -> None:
    for filled in range(21):
        assert confidence_for(filled, has_meter_data=True) is Confidence.PRECISE
