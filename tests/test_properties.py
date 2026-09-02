from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from ampeer_sim.engine.battery import Battery
from ampeer_sim.engine.run import assert_energy_balance, simulate
from ampeer_sim.profiles.presence import apply_presence
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import BatterySpec

SPEC = BatterySpec(
    capacity_kwh=5.0,
    max_charge_kw=2.5,
    max_discharge_kw=2.5,
    round_trip_efficiency=0.90,
    usable_dod=0.90,
)

series = st.lists(
    st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    min_size=96,
    max_size=96,
)


@settings(max_examples=50, deadline=None)
@given(consumption=series, production=series)
def test_energy_always_balances(consumption: list[float], production: list[float]) -> None:
    flows = simulate(np.array(consumption), np.array(production), battery_spec=SPEC)
    assert_energy_balance(flows)


@settings(max_examples=50, deadline=None)
@given(consumption=series, production=series)
def test_energy_always_balances_without_a_battery(
    consumption: list[float], production: list[float]
) -> None:
    assert_energy_balance(simulate(np.array(consumption), np.array(production)))


@settings(max_examples=50, deadline=None)
@given(
    consumption=series,
    production=series,
    extra=st.floats(min_value=0.01, max_value=1.0),
)
def test_more_production_never_raises_the_self_consumption_rate(
    consumption: list[float], production: list[float], extra: float
) -> None:
    base = np.array(production)
    if base.sum() == 0.0:
        return
    less = simulate(np.array(consumption), base)
    more = simulate(np.array(consumption), base * (1.0 + extra))
    assert more.self_consumption_rate <= less.self_consumption_rate + 1e-9


@settings(max_examples=50, deadline=None)
@given(consumption=series, production=series)
def test_a_battery_never_lowers_the_self_consumption_rate(
    consumption: list[float], production: list[float]
) -> None:
    if np.array(production).sum() == 0.0:
        return
    without = simulate(np.array(consumption), np.array(production))
    with_battery = simulate(np.array(consumption), np.array(production), battery_spec=SPEC)
    assert with_battery.self_consumption_rate >= without.self_consumption_rate - 1e-9


@settings(max_examples=50, deadline=None)
@given(consumption=series, production=series)
def test_the_self_consumption_rate_is_always_a_fraction(
    consumption: list[float], production: list[float]
) -> None:
    flows = simulate(np.array(consumption), np.array(production), battery_spec=SPEC)
    assert 0.0 <= flows.self_consumption_rate <= 1.0 + 1e-9


@settings(max_examples=100, deadline=None)
@given(
    offers=st.lists(st.floats(min_value=0.0, max_value=3.0), min_size=1, max_size=200),
    wants=st.lists(st.floats(min_value=0.0, max_value=3.0), min_size=1, max_size=200),
)
def test_the_state_of_charge_never_leaves_its_bounds(
    offers: list[float], wants: list[float]
) -> None:
    battery = Battery(SPEC)
    for quarter, (offered, wanted) in enumerate(zip(offers, wants, strict=False)):
        battery.charge(offered, quarter)
        battery.discharge(wanted, quarter)
        assert -1e-12 <= battery.soc_kwh <= SPEC.usable_capacity_kwh + 1e-12


@settings(max_examples=25, deadline=None)
@given(block=st.floats(min_value=0.0, max_value=3.0))
def test_presence_preserves_the_annual_total(block: float) -> None:
    grid = YearGrid.for_year(2025)
    flat = np.full(grid.quarters, 3_500.0 / grid.quarters)
    shifted = apply_presence(flat, grid, block_kwh=block, daytime_occupancy=True)
    assert abs(shifted.sum() - flat.sum()) < 1e-6


@settings(max_examples=25, deadline=None)
@given(block=st.floats(min_value=0.0, max_value=2.0))
def test_a_bigger_block_moves_at_least_as_much_energy(block: float) -> None:
    grid = YearGrid.for_year(2025)
    flat = np.full(grid.quarters, 3_500.0 / grid.quarters)
    midday = (grid.local_hour >= 11) & (grid.local_hour < 15)
    small = apply_presence(flat, grid, block_kwh=block, daytime_occupancy=True)
    large = apply_presence(flat, grid, block_kwh=block + 0.25, daytime_occupancy=True)
    assert large[midday].sum() >= small[midday].sum() - 1e-9


@settings(max_examples=25, deadline=None)
@given(block=st.floats(min_value=0.0, max_value=5.0))
def test_presence_never_produces_negative_consumption(block: float) -> None:
    grid = YearGrid.for_year(2025)
    flat = np.full(grid.quarters, 3_500.0 / grid.quarters)
    for occupancy in (True, False):
        shifted = apply_presence(flat, grid, block_kwh=block, daytime_occupancy=occupancy)
        assert shifted.min() >= 0.0
