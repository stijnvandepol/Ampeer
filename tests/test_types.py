from __future__ import annotations

import dataclasses
from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.providers import ProductionProvider
from ampeer_sim.types import (
    BatterySpec,
    EnergyFlows,
    EVChargingBehaviour,
    Household,
    ProductionSource,
    PVSystem,
)


def test_household_is_frozen() -> None:
    household = Household(postcode4="5401", annual_consumption_kwh=3500.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        household.annual_consumption_kwh = 4000.0  # type: ignore[misc]


def test_pv_system_rejects_impossible_orientation() -> None:
    with pytest.raises(ValueError, match="tilt"):
        PVSystem(peak_power_wp=3500, azimuth_deg=0, tilt_deg=95)


def test_battery_spec_rejects_efficiency_above_one() -> None:
    with pytest.raises(ValueError, match="round_trip_efficiency"):
        BatterySpec(
            capacity_kwh=5.0,
            max_charge_kw=2.5,
            max_discharge_kw=2.5,
            round_trip_efficiency=1.2,
            usable_dod=0.9,
            allow_grid_charging=False,
        )


def test_energy_flows_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        EnergyFlows(
            consumption=np.zeros(4),
            production=np.zeros(4),
            self_consumption=np.zeros(4),
            from_grid=np.zeros(3),
            to_grid=np.zeros(4),
            battery_charge=np.zeros(4),
            battery_discharge=np.zeros(4),
        )


def test_ev_charging_behaviour_members() -> None:
    assert {behaviour.name for behaviour in EVChargingBehaviour} == {
        "NIGHT",
        "ARRIVAL",
        "SOLAR",
    }


def test_fake_provider_satisfies_production_protocol() -> None:
    class FakeProduction:
        def hourly_series(
            self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
        ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
            return np.zeros(8760), np.zeros(8760), ProductionSource.FALLBACK

    assert isinstance(FakeProduction(), ProductionProvider)


def test_money_values_are_decimal() -> None:
    from ampeer_sim.types import MoneyResult

    result = MoneyResult(
        baseline_eur=Decimal("1200.00"),
        scenario_eur=Decimal("1840.00"),
    )
    assert result.difference_eur == Decimal("640.00")
