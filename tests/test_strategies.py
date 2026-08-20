from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.engine.strategies import (
    FORESIGHT_HORIZON_DAYS,
    build_plans,
    minimum_profitable_spread,
)
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import BatterySpec, Strategy

GRID = YearGrid.for_year(2025)
SPEC = BatterySpec(
    capacity_kwh=10.0,
    max_charge_kw=4.0,
    max_discharge_kw=4.0,
    round_trip_efficiency=0.90,
    usable_dod=0.90,
    allow_grid_charging=True,
)


def _sawtooth_prices(low: float = 0.05, high: float = 0.35) -> np.ndarray:
    day = np.concatenate([np.full(48, low), np.full(48, high)])
    return np.tile(day, GRID.days)


def test_the_foresight_horizon_is_one_day() -> None:
    assert FORESIGHT_HORIZON_DAYS == 1


def test_self_consumption_produces_no_price_driven_plans() -> None:
    charge, discharge = build_plans(Strategy.SELF_CONSUMPTION, SPEC, _sawtooth_prices(), GRID)
    assert charge.sum() == pytest.approx(0.0)
    assert discharge.sum() == pytest.approx(0.0)


def test_arbitrage_without_prices_produces_no_plans() -> None:
    charge, discharge = build_plans(Strategy.ARBITRAGE, SPEC, None, GRID)
    assert charge.sum() == pytest.approx(0.0)
    assert discharge.sum() == pytest.approx(0.0)


def test_a_battery_that_may_not_grid_charge_produces_no_plans() -> None:
    no_trading = BatterySpec(
        capacity_kwh=10.0, max_charge_kw=4.0, max_discharge_kw=4.0, allow_grid_charging=False
    )
    charge, discharge = build_plans(Strategy.ARBITRAGE, no_trading, _sawtooth_prices(), GRID)
    assert charge.sum() == pytest.approx(0.0)
    assert discharge.sum() == pytest.approx(0.0)


def test_arbitrage_charges_in_the_cheap_half_and_discharges_in_the_dear_half() -> None:
    prices = _sawtooth_prices()
    charge, discharge = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    cheap = prices < 0.10
    assert charge[cheap].sum() == pytest.approx(charge.sum())
    assert discharge[~cheap].sum() == pytest.approx(discharge.sum())
    assert charge.sum() > 0.0


def test_arbitrage_does_nothing_when_the_spread_is_too_small() -> None:
    flat = np.full(GRID.quarters, 0.20)
    charge, discharge = build_plans(Strategy.ARBITRAGE, SPEC, flat, GRID)
    assert charge.sum() == pytest.approx(0.0)
    assert discharge.sum() == pytest.approx(0.0)


def test_arbitrage_plans_never_exceed_the_usable_capacity_per_day() -> None:
    charge, _ = build_plans(Strategy.ARBITRAGE, SPEC, _sawtooth_prices(), GRID)
    per_day = charge.reshape(GRID.days, 96).sum(axis=1)
    assert per_day.max() <= SPEC.usable_capacity_kwh + 1e-9


def test_a_strategy_cannot_see_beyond_its_horizon() -> None:
    """Day two is worth trading, day one is flat. Day one must not react."""
    prices = np.concatenate([np.full(96, 0.20), np.full(48, 0.05), np.full(48, 0.60)])
    prices = np.concatenate([prices, np.full(GRID.quarters - prices.size, 0.20)])
    charge, _ = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    assert charge[:96].sum() == pytest.approx(0.0)
    assert charge[96:192].sum() > 0.0


def test_hybrid_holds_back_where_plain_arbitrage_would_trade() -> None:
    """A spread that clears break-even but not the hybrid safety margin."""
    prices = _sawtooth_prices(low=0.1875, high=0.2125)
    arbitrage_charge, _ = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    hybrid_charge, _ = build_plans(Strategy.HYBRID, SPEC, prices, GRID)
    assert arbitrage_charge.sum() > 0.0
    assert hybrid_charge.sum() == pytest.approx(0.0)


def test_hybrid_plans_are_never_larger_than_pure_arbitrage_plans() -> None:
    prices = _sawtooth_prices()
    hybrid_charge, _ = build_plans(Strategy.HYBRID, SPEC, prices, GRID)
    arbitrage_charge, _ = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    assert hybrid_charge.sum() <= arbitrage_charge.sum() + 1e-9


def test_minimum_profitable_spread_grows_with_the_price_level() -> None:
    cheap_day = np.full(96, 0.05)
    dear_day = np.full(96, 0.50)
    assert minimum_profitable_spread(dear_day, 0.90) > minimum_profitable_spread(cheap_day, 0.90)


def test_a_perfect_battery_needs_no_spread() -> None:
    assert minimum_profitable_spread(np.full(96, 0.20), 1.0) == pytest.approx(0.0)
