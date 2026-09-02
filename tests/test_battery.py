from __future__ import annotations

import math

import pytest

from ampeer_sim.engine.battery import Battery
from ampeer_sim.timebase import QUARTERS_PER_HOUR
from ampeer_sim.types import BatterySpec

SPEC = BatterySpec(
    capacity_kwh=10.0,
    max_charge_kw=4.0,
    max_discharge_kw=4.0,
    round_trip_efficiency=0.90,
    usable_dod=0.90,
)


def test_a_new_battery_is_empty() -> None:
    assert Battery(SPEC).soc_kwh == 0.0


def test_charging_is_limited_by_power() -> None:
    battery = Battery(SPEC)
    accepted = battery.charge(offered_kwh=5.0, quarter=0)
    assert accepted == pytest.approx(4.0 / 4)


def test_charging_stores_less_than_it_takes() -> None:
    battery = Battery(SPEC)
    accepted = battery.charge(offered_kwh=1.0, quarter=0)
    assert battery.soc_kwh == pytest.approx(accepted * math.sqrt(0.90))


def test_charging_is_limited_by_usable_capacity() -> None:
    battery = Battery(SPEC)
    for quarter in range(200):
        battery.charge(offered_kwh=1.0, quarter=quarter)
    assert battery.soc_kwh == pytest.approx(SPEC.usable_capacity_kwh)


def test_discharging_an_empty_battery_delivers_nothing() -> None:
    assert Battery(SPEC).discharge(wanted_kwh=1.0, quarter=0) == pytest.approx(0.0)


def test_discharging_is_limited_by_power() -> None:
    battery = Battery(SPEC)
    for quarter in range(200):
        battery.charge(offered_kwh=1.0, quarter=quarter)
    assert battery.discharge(wanted_kwh=5.0, quarter=200) == pytest.approx(4.0 / 4)


def test_a_full_cycle_loses_exactly_the_round_trip_efficiency() -> None:
    spec = BatterySpec(
        capacity_kwh=10.0,
        max_charge_kw=40.0,
        max_discharge_kw=40.0,
        round_trip_efficiency=0.90,
        usable_dod=1.0,
    )
    battery = Battery(spec)
    taken = battery.charge(offered_kwh=10.0, quarter=0)
    delivered = battery.discharge(wanted_kwh=10.0, quarter=0)
    assert delivered / taken == pytest.approx(0.90)


def test_state_of_charge_never_leaves_its_bounds() -> None:
    battery = Battery(SPEC)
    for step in range(500):
        battery.charge(offered_kwh=2.0 if step % 3 else 0.0, quarter=step)
        battery.discharge(wanted_kwh=1.5, quarter=step)
        assert 0.0 <= battery.soc_kwh <= SPEC.usable_capacity_kwh + 1e-12


def test_throughput_accumulates_delivered_energy() -> None:
    battery = Battery(SPEC)
    battery.charge(offered_kwh=1.0, quarter=0)
    delivered = battery.discharge(wanted_kwh=1.0, quarter=0)
    assert battery.throughput_kwh == pytest.approx(delivered)


def test_negative_offers_are_ignored() -> None:
    battery = Battery(SPEC)
    assert battery.charge(offered_kwh=-1.0, quarter=0) == pytest.approx(0.0)
    assert battery.discharge(wanted_kwh=-1.0, quarter=0) == pytest.approx(0.0)
    assert battery.soc_kwh == pytest.approx(0.0)


def test_the_power_limit_belongs_to_the_quarter_and_not_to_the_call() -> None:
    """A battery cannot exceed its rating by being asked twice.

    ampeer_sim/engine/run.py asks twice in the same quarter: once for the
    household's own surplus and once for a price-driven plan. Until 2026-08-23
    each call carried the full limit, so a battery rated at 2 kW moved 4 kW
    whenever both fired. That is the mistake the module docstring of
    engine/battery.py warns about in so many words, making a battery look
    better than it is, and it was in the module doing the warning.

    Dormant rather than harmless. Nothing in the shipped path sets
    allow_grid_charging, and without it the strategy returns empty plans, so
    the second call never fires and no household's advice moved. The golden
    set proves that from the other side: it is asserted to the cent and did
    not shift when this was fixed.
    """
    limit = SPEC.max_charge_kw / QUARTERS_PER_HOUR
    battery = Battery(SPEC)
    first = battery.charge(offered_kwh=5.0, quarter=0)
    second = battery.charge(offered_kwh=5.0, quarter=0)
    assert first + second == pytest.approx(limit), (
        "the two calls of one quarter took more than the battery can take in one"
    )
    assert battery.charge(offered_kwh=5.0, quarter=1) == pytest.approx(limit), (
        "the next quarter did not open a fresh allowance"
    )


def test_the_discharge_limit_belongs_to_the_quarter_too() -> None:
    """The same, in the direction that sells rather than buys."""
    limit = SPEC.max_discharge_kw / QUARTERS_PER_HOUR
    battery = Battery(SPEC)
    for quarter in range(200):
        battery.charge(offered_kwh=1.0, quarter=quarter)
    first = battery.discharge(wanted_kwh=5.0, quarter=500)
    second = battery.discharge(wanted_kwh=5.0, quarter=500)
    assert first + second == pytest.approx(limit)
    assert battery.discharge(wanted_kwh=5.0, quarter=501) == pytest.approx(limit)
