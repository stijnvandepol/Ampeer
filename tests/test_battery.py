from __future__ import annotations

import math

import pytest

from ampeer_sim.engine.battery import Battery
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
    accepted = battery.charge(offered_kwh=5.0)
    assert accepted == pytest.approx(4.0 / 4)


def test_charging_stores_less_than_it_takes() -> None:
    battery = Battery(SPEC)
    accepted = battery.charge(offered_kwh=1.0)
    assert battery.soc_kwh == pytest.approx(accepted * math.sqrt(0.90))


def test_charging_is_limited_by_usable_capacity() -> None:
    battery = Battery(SPEC)
    for _ in range(200):
        battery.charge(offered_kwh=1.0)
    assert battery.soc_kwh == pytest.approx(SPEC.usable_capacity_kwh)


def test_discharging_an_empty_battery_delivers_nothing() -> None:
    assert Battery(SPEC).discharge(wanted_kwh=1.0) == pytest.approx(0.0)


def test_discharging_is_limited_by_power() -> None:
    battery = Battery(SPEC)
    for _ in range(200):
        battery.charge(offered_kwh=1.0)
    assert battery.discharge(wanted_kwh=5.0) == pytest.approx(4.0 / 4)


def test_a_full_cycle_loses_exactly_the_round_trip_efficiency() -> None:
    spec = BatterySpec(
        capacity_kwh=10.0,
        max_charge_kw=40.0,
        max_discharge_kw=40.0,
        round_trip_efficiency=0.90,
        usable_dod=1.0,
    )
    battery = Battery(spec)
    taken = battery.charge(offered_kwh=10.0)
    delivered = battery.discharge(wanted_kwh=10.0)
    assert delivered / taken == pytest.approx(0.90)


def test_state_of_charge_never_leaves_its_bounds() -> None:
    battery = Battery(SPEC)
    for step in range(500):
        battery.charge(offered_kwh=2.0 if step % 3 else 0.0)
        battery.discharge(wanted_kwh=1.5)
        assert 0.0 <= battery.soc_kwh <= SPEC.usable_capacity_kwh + 1e-12


def test_throughput_accumulates_delivered_energy() -> None:
    battery = Battery(SPEC)
    battery.charge(offered_kwh=1.0)
    delivered = battery.discharge(wanted_kwh=1.0)
    assert battery.throughput_kwh == pytest.approx(delivered)


def test_negative_offers_are_ignored() -> None:
    battery = Battery(SPEC)
    assert battery.charge(offered_kwh=-1.0) == pytest.approx(0.0)
    assert battery.discharge(wanted_kwh=-1.0) == pytest.approx(0.0)
    assert battery.soc_kwh == pytest.approx(0.0)
