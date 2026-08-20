from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.economics.tariffs import annual_cost, compare
from ampeer_sim.types import EnergyFlows, TariffSet

FIXED_2026 = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.27"),
    standing_charge_year=Decimal("120.00"),
    net_metering=True,
)
FIXED_2027 = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.05"),
    feed_in_fixed_cost_year=Decimal("90.00"),
    standing_charge_year=Decimal("120.00"),
    net_metering=False,
)


def _flows(from_grid: float, to_grid: float, steps: int = 4) -> EnergyFlows:
    zeros = np.zeros(steps)
    return EnergyFlows(
        consumption=np.full(steps, from_grid / steps),
        production=np.full(steps, to_grid / steps),
        self_consumption=zeros,
        from_grid=np.full(steps, from_grid / steps),
        to_grid=np.full(steps, to_grid / steps),
        battery_charge=zeros,
        battery_discharge=zeros,
    )


def test_cost_is_a_decimal() -> None:
    assert isinstance(annual_cost(_flows(1_000.0, 0.0), FIXED_2027), Decimal)


def test_pure_offtake_costs_price_times_volume_plus_standing_charge() -> None:
    cost = annual_cost(_flows(1_000.0, 0.0), FIXED_2027)
    assert cost == Decimal("390.000")


def test_a_household_that_never_feeds_in_is_not_billed_for_feeding_in() -> None:
    with_feed_in = annual_cost(_flows(1_000.0, 1.0), FIXED_2027)
    without_feed_in = annual_cost(_flows(1_000.0, 0.0), FIXED_2027)
    assert with_feed_in - without_feed_in == pytest.approx(
        Decimal("90.00") - Decimal("0.05"), abs=Decimal("0.001")
    )


def test_net_metering_cancels_feed_in_against_offtake() -> None:
    cost = annual_cost(_flows(2_000.0, 800.0), FIXED_2026)
    # 1200 kWh net offtake at 0.27 plus the standing charge.
    assert cost == Decimal("444.000")


def test_net_metering_never_pays_more_than_the_offtake_is_worth() -> None:
    cost = annual_cost(_flows(500.0, 2_000.0), FIXED_2026)
    surplus = Decimal("1500") * Decimal("0.27")
    assert cost == Decimal("120.000") - surplus


def test_without_net_metering_feed_in_earns_the_feed_in_price() -> None:
    cost = annual_cost(_flows(2_000.0, 800.0), FIXED_2027)
    expected = (
        Decimal("2000") * Decimal("0.27")
        - Decimal("800") * Decimal("0.05")
        + Decimal("90.00")
        + Decimal("120.00")
    )
    assert cost == expected


def test_a_dynamic_contract_prices_each_quarter_separately() -> None:
    tariffs = TariffSet(supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True)
    prices = np.array([0.10, 0.20, 0.30, 0.40])
    cost = annual_cost(_flows(400.0, 0.0), tariffs, prices_per_quarter=prices)
    assert cost == Decimal("100.000")


def test_a_dynamic_contract_requires_prices() -> None:
    tariffs = TariffSet(supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True)
    with pytest.raises(ValueError, match="dynamic"):
        annual_cost(_flows(400.0, 0.0), tariffs)


def test_a_dynamic_contract_rejects_a_mismatched_price_series() -> None:
    tariffs = TariffSet(supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True)
    with pytest.raises(ValueError, match="same length"):
        annual_cost(_flows(400.0, 0.0), tariffs, prices_per_quarter=np.zeros(3))


def test_arbitrage_flows_reach_the_meter() -> None:
    steps = 4
    zeros = np.zeros(steps)
    flows = EnergyFlows(
        consumption=zeros,
        production=zeros,
        self_consumption=zeros,
        from_grid=zeros,
        to_grid=zeros,
        battery_charge=zeros,
        battery_discharge=zeros,
        grid_charge=np.full(steps, 250.0),
        grid_discharge=zeros,
    )
    # 1000 kWh bought for the battery is still 1000 kWh off the meter.
    assert annual_cost(flows, FIXED_2027) == Decimal("390.000")


def test_compare_returns_the_difference_between_two_tariff_sets() -> None:
    result = compare(_flows(2_000.0, 800.0), baseline=FIXED_2026, scenario=FIXED_2027)
    assert result.difference_eur == result.scenario_eur - result.baseline_eur
    assert result.difference_eur > 0
