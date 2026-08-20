from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ampeer_advice import tariffs


def test_every_band_is_ordered() -> None:
    for name in (
        "SUPPLY_PRICE",
        "FEED_IN_GROSS_FIXED",
        "FEED_IN_COST",
        "FEED_IN_NET_DYNAMIC",
        "BATTERY_COST_PER_KWH",
    ):
        band = getattr(tariffs, name)
        assert band.low <= band.mid <= band.high, name


def test_the_values_carry_the_date_they_were_read() -> None:
    assert tariffs.SOURCED_ON == date(2026, 8, 20)


def test_net_feed_in_on_a_fixed_contract_can_be_negative() -> None:
    """The published 2027 tariffs run from -7.43 to +1.19 cent net.

    The project plan assumed 3 to 8 cent, which is the gross figure. If this
    test ever passes only for positive values, the model has drifted back to
    the assumption the spec corrected.
    """
    worst = tariffs.FEED_IN_GROSS_FIXED.low - tariffs.FEED_IN_COST.high
    best = tariffs.FEED_IN_GROSS_FIXED.high - tariffs.FEED_IN_COST.low
    assert worst < Decimal("0")
    assert best > Decimal("0")


def test_the_baseline_nets_feed_in_against_offtake() -> None:
    baseline = tariffs.baseline_tariffs()
    assert baseline.net_metering is True
    assert baseline.feed_in_price == tariffs.SUPPLY_PRICE.mid


def test_the_2027_scenario_stops_netting_and_charges_per_kwh() -> None:
    scenario = tariffs.scenario_2027_tariffs()
    assert scenario.net_metering is False
    assert scenario.feed_in_cost_per_kwh == tariffs.FEED_IN_COST.mid


def test_a_dynamic_contract_pays_more_for_exports_than_a_fixed_one() -> None:
    fixed = tariffs.scenario_2027_tariffs(dynamic=False)
    dynamic = tariffs.scenario_2027_tariffs(dynamic=True)
    fixed_net = fixed.feed_in_price - fixed.feed_in_cost_per_kwh
    dynamic_net = dynamic.feed_in_price - dynamic.feed_in_cost_per_kwh
    assert dynamic_net > fixed_net


def test_standing_charges_are_zero_on_both_sides() -> None:
    """The headline figure is a difference, so anything identical cancels."""
    for tariff_set in (tariffs.baseline_tariffs(), tariffs.scenario_2027_tariffs()):
        assert tariff_set.standing_charge_year == Decimal("0")
        assert tariff_set.feed_in_fixed_cost_year == Decimal("0")


@pytest.mark.parametrize("level", ["low", "mid", "high"])
def test_every_level_produces_a_usable_tariff_set(level: str) -> None:
    assert tariffs.scenario_2027_tariffs(level=level).supply_price > Decimal("0")


def test_an_unknown_level_is_rejected() -> None:
    with pytest.raises(ValueError, match="level"):
        tariffs.scenario_2027_tariffs(level="medium")


def test_a_changed_value_forces_a_changed_source_date() -> None:
    """Spec section 9, point 4: values and their date move together.

    A tariff table that goes stale gives no error message, only a confident
    wrong number. This snapshot is the error message.

    Keyed on both the source date and the revision, because they answer
    different questions. ``SOURCED_ON`` says when the sources were last read.
    ``VALUES_REVISION`` says when the numbers last moved, which also happens
    when a value is corrected without re-reading anything. Keying on the date
    alone forced a methodological correction to be dated as a re-read, which
    would quietly destroy the one thing this test exists to protect.

    When a value is genuinely re-read: update the value, its comment,
    ``SOURCED_ON``, ``VALUES_REVISION`` and this snapshot in one commit. When a
    value is corrected without re-reading: everything except ``SOURCED_ON``.
    """
    snapshot = {
        (date(2026, 8, 20), 2): {
            "SUPPLY_PRICE": (Decimal("0.22"), Decimal("0.26"), Decimal("0.30")),
            "FEED_IN_GROSS_FIXED": (Decimal("0.050"), Decimal("0.065"), Decimal("0.077")),
            "FEED_IN_COST": (Decimal("0.0446"), Decimal("0.0625"), Decimal("0.115")),
            "FEED_IN_NET_DYNAMIC": (Decimal("0.05"), Decimal("0.06"), Decimal("0.07")),
            "BATTERY_COST_PER_KWH": (Decimal("450"), Decimal("675"), Decimal("900")),
        }
    }
    key = (tariffs.SOURCED_ON, tariffs.VALUES_REVISION)
    assert key in snapshot, "a value moved, so SOURCED_ON or VALUES_REVISION must move too"
    for name, expected in snapshot[key].items():
        band = getattr(tariffs, name)
        assert (band.low, band.mid, band.high) == expected, name


def test_the_central_net_feed_in_matches_what_suppliers_actually_publish() -> None:
    """The central case must be a figure somebody offers.

    Pairing the midpoint of the gross compensation with the midpoint of the
    charge, each chosen independently, produced -0.010 per kWh. The published
    net tariffs cluster at +0.0025, so the derived middle was more pessimistic
    than the market by more than a cent on every exported kWh. That error made
    the shock this product reports larger, which is the direction an error is
    least likely to be questioned and therefore the one to pin down.
    """
    assert tariffs.net_feed_in_fixed("mid") == tariffs.PUBLISHED_NET_FEED_IN_MODE


def test_the_charge_middle_stays_inside_its_observed_range() -> None:
    """Anchoring the middle must not push it outside what was measured."""
    assert tariffs.FEED_IN_COST.low < tariffs.FEED_IN_COST.mid < tariffs.FEED_IN_COST.high
