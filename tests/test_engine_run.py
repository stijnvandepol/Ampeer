from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.engine.run import EnergyBalanceError, assert_energy_balance, simulate
from ampeer_sim.types import BatterySpec, EnergyFlows

SPEC = BatterySpec(
    capacity_kwh=5.0,
    max_charge_kw=2.5,
    max_discharge_kw=2.5,
    round_trip_efficiency=0.90,
    usable_dod=0.90,
)
TRADING_SPEC = BatterySpec(
    capacity_kwh=5.0,
    max_charge_kw=2.5,
    max_discharge_kw=2.5,
    round_trip_efficiency=0.90,
    usable_dod=0.90,
    allow_grid_charging=True,
)


def test_without_production_everything_comes_from_the_grid() -> None:
    flows = simulate(consumption=np.full(96, 0.1), production=np.zeros(96))
    assert flows.from_grid.sum() == pytest.approx(9.6)
    assert flows.self_consumption.sum() == pytest.approx(0.0)


def test_simultaneous_production_is_consumed_directly() -> None:
    flows = simulate(consumption=np.full(96, 0.1), production=np.full(96, 0.1))
    assert flows.self_consumption.sum() == pytest.approx(9.6)
    assert flows.from_grid.sum() == pytest.approx(0.0)
    assert flows.to_grid.sum() == pytest.approx(0.0)


def test_surplus_without_a_battery_goes_to_the_grid() -> None:
    flows = simulate(consumption=np.zeros(96), production=np.full(96, 0.1))
    assert flows.to_grid.sum() == pytest.approx(9.6)


def test_a_battery_stores_surplus_and_returns_it_later() -> None:
    consumption = np.concatenate([np.zeros(48), np.full(48, 0.05)])
    production = np.concatenate([np.full(48, 0.05), np.zeros(48)])
    flows = simulate(consumption, production, battery_spec=SPEC)
    assert flows.battery_charge.sum() > 0.0
    assert flows.battery_discharge.sum() > 0.0
    assert flows.to_grid.sum() < production.sum()


def test_a_battery_never_lowers_self_consumption() -> None:
    consumption = np.concatenate([np.zeros(48), np.full(48, 0.05)])
    production = np.concatenate([np.full(48, 0.05), np.zeros(48)])
    without = simulate(consumption, production)
    with_battery = simulate(consumption, production, battery_spec=SPEC)
    assert with_battery.self_consumption_rate >= without.self_consumption_rate


def test_the_energy_balance_closes_on_every_quarter() -> None:
    rng = np.random.default_rng(seed=7)
    consumption = rng.uniform(0.0, 0.3, size=2_000)
    production = rng.uniform(0.0, 0.4, size=2_000)
    assert_energy_balance(simulate(consumption, production, battery_spec=SPEC))


def test_the_energy_balance_closes_without_a_battery_too() -> None:
    rng = np.random.default_rng(seed=11)
    assert_energy_balance(
        simulate(rng.uniform(0.0, 0.3, size=2_000), rng.uniform(0.0, 0.4, size=2_000))
    )


def test_a_grid_charge_plan_shows_up_as_extra_offtake() -> None:
    plan = np.zeros(96)
    plan[0] = 0.5
    flows = simulate(
        consumption=np.zeros(96),
        production=np.zeros(96),
        battery_spec=TRADING_SPEC,
        charge_plan=plan,
    )
    assert flows.grid_charge is not None, "a trading battery reported no grid charging"
    assert flows.grid_charge.sum() > 0.0
    assert flows.from_grid.sum() == pytest.approx(0.0)
    assert flows.total_import.sum() > 0.0
    assert_energy_balance(flows)


def test_a_battery_that_may_not_grid_charge_ignores_the_plan() -> None:
    plan = np.zeros(96)
    plan[0] = 0.5
    flows = simulate(
        consumption=np.zeros(96), production=np.zeros(96), battery_spec=SPEC, charge_plan=plan
    )
    assert flows.grid_charge is not None, "a battery with a plan reported no grid charging"
    assert flows.grid_charge.sum() == pytest.approx(0.0)


def test_a_discharge_plan_shows_up_as_extra_feed_in() -> None:
    charge = np.zeros(96)
    charge[0] = 0.5
    discharge = np.zeros(96)
    discharge[50] = 0.5
    flows = simulate(
        consumption=np.zeros(96),
        production=np.zeros(96),
        battery_spec=TRADING_SPEC,
        charge_plan=charge,
        discharge_plan=discharge,
    )
    assert flows.grid_discharge is not None, "a trading battery reported no grid discharge"
    assert flows.grid_discharge.sum() > 0.0
    assert flows.total_export.sum() > 0.0
    assert_energy_balance(flows)


def test_a_broken_balance_is_detected() -> None:
    broken = EnergyFlows(
        consumption=np.array([1.0]),
        production=np.array([0.0]),
        self_consumption=np.array([0.0]),
        from_grid=np.array([0.5]),
        to_grid=np.array([0.0]),
        battery_charge=np.array([0.0]),
        battery_discharge=np.array([0.0]),
    )
    with pytest.raises(EnergyBalanceError, match="consumption"):
        assert_energy_balance(broken)


def test_a_broken_production_balance_is_detected() -> None:
    broken = EnergyFlows(
        consumption=np.array([0.0]),
        production=np.array([1.0]),
        self_consumption=np.array([0.0]),
        from_grid=np.array([0.0]),
        to_grid=np.array([0.2]),
        battery_charge=np.array([0.0]),
        battery_discharge=np.array([0.0]),
    )
    with pytest.raises(EnergyBalanceError, match="production"):
        assert_energy_balance(broken)


def test_mismatched_input_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="same length"):
        simulate(consumption=np.zeros(96), production=np.zeros(95))
