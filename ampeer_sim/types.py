"""Value types for the simulation core.

Energy quantities are floats in kWh. Money is Decimal in euro. The two never
mix outside ``ampeer_sim.economics.tariffs``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto

import numpy as np


class EVChargingBehaviour(Enum):
    """How the household charges its electric vehicle at home."""

    NIGHT = auto()
    ARRIVAL = auto()
    SOLAR = auto()


class Strategy(Enum):
    """Battery control strategy."""

    SELF_CONSUMPTION = auto()
    ARBITRAGE = auto()
    HYBRID = auto()


class ProductionSource(Enum):
    """Where the production series came from."""

    PVGIS = auto()
    FALLBACK = auto()


class ProfileCategory(Enum):
    """NEDU standard profile category.

    E1A has no tariff registers and its fractions sum to 1. E1B and E1C carry
    two registers and sum to 2.
    """

    E1A = "E1A"
    E1B = "E1B"
    E1C = "E1C"


@dataclass(frozen=True)
class PVSystem:
    peak_power_wp: int
    azimuth_deg: float
    tilt_deg: float
    install_year: int | None = None
    system_loss_fraction: float = 0.14

    def __post_init__(self) -> None:
        if not 0 < self.peak_power_wp <= 50_000:
            raise ValueError("peak_power_wp must be between 1 and 50000")
        if not -180.0 <= self.azimuth_deg <= 180.0:
            raise ValueError("azimuth_deg must be between -180 and 180")
        if not 0.0 <= self.tilt_deg <= 90.0:
            raise ValueError("tilt_deg must be between 0 and 90")
        if not 0.0 <= self.system_loss_fraction < 1.0:
            raise ValueError("system_loss_fraction must be in [0, 1)")


@dataclass(frozen=True)
class EV:
    behaviour: EVChargingBehaviour
    annual_km: int = 12_000
    kwh_per_100km: float = 18.0
    charge_power_kw: float = 3.7

    @property
    def annual_kwh(self) -> float:
        return self.annual_km / 100.0 * self.kwh_per_100km


@dataclass(frozen=True)
class HeatPump:
    heat_demand_kwh: float
    base_temperature_c: float = 15.0
    cop_at_7c: float = 3.5
    cop_slope_per_c: float = 0.06


@dataclass(frozen=True)
class BatterySpec:
    capacity_kwh: float
    max_charge_kw: float
    max_discharge_kw: float
    round_trip_efficiency: float = 0.90
    usable_dod: float = 0.90
    allow_grid_charging: bool = False

    def __post_init__(self) -> None:
        if self.capacity_kwh <= 0:
            raise ValueError("capacity_kwh must be positive")
        if not 0.0 < self.round_trip_efficiency <= 1.0:
            raise ValueError("round_trip_efficiency must be in (0, 1]")
        if not 0.0 < self.usable_dod <= 1.0:
            raise ValueError("usable_dod must be in (0, 1]")

    @property
    def usable_capacity_kwh(self) -> float:
        return self.capacity_kwh * self.usable_dod


@dataclass(frozen=True)
class Household:
    postcode4: str
    annual_consumption_kwh: float
    daytime_occupancy: bool = False
    #: Calibrated on 2026-08-20 so that daytime occupancy moves self consumption
    #: by 13.7 percentage points, matching the 10 to 15 the domain document
    #: reports. At 1.75 kWh the model produced 22 points, which is too much.
    shiftable_block_kwh: float = 1.0
    profile_category: ProfileCategory = ProfileCategory.E1A
    ev: EV | None = None
    heat_pump: HeatPump | None = None

    def __post_init__(self) -> None:
        if len(self.postcode4) != 4 or not self.postcode4.isdigit():
            raise ValueError("postcode4 must be exactly four digits")
        if self.annual_consumption_kwh <= 0:
            raise ValueError("annual_consumption_kwh must be positive")


@dataclass(frozen=True)
class TariffSet:
    """All prices are euro per kWh unless stated otherwise."""

    supply_price: Decimal
    feed_in_price: Decimal
    feed_in_fixed_cost_year: Decimal = Decimal("0")
    standing_charge_year: Decimal = Decimal("0")
    net_metering: bool = False
    dynamic: bool = False


@dataclass(frozen=True)
class EnergyFlows:
    """Quarter-hour energy flows in kWh.

    ``from_grid`` and ``to_grid`` are the household's own offtake and feed-in.
    Energy the battery moves for price reasons is kept apart in ``grid_charge``
    and ``grid_discharge``, so the per-step energy balance stays two plain
    equations with no correction terms. Anything that bills the meter should use
    ``total_import`` and ``total_export``.
    """

    consumption: np.ndarray
    production: np.ndarray
    self_consumption: np.ndarray
    from_grid: np.ndarray
    to_grid: np.ndarray
    battery_charge: np.ndarray
    battery_discharge: np.ndarray
    grid_charge: np.ndarray | None = None
    grid_discharge: np.ndarray | None = None

    def __post_init__(self) -> None:
        lengths = {
            len(self.consumption),
            len(self.production),
            len(self.self_consumption),
            len(self.from_grid),
            len(self.to_grid),
            len(self.battery_charge),
            len(self.battery_discharge),
        }
        if self.grid_charge is not None:
            lengths.add(len(self.grid_charge))
        if self.grid_discharge is not None:
            lengths.add(len(self.grid_discharge))
        if len(lengths) != 1:
            raise ValueError("all flow series must have the same length")

    @property
    def total_import(self) -> np.ndarray:
        """Everything the meter counts as offtake."""
        if self.grid_charge is None:
            return self.from_grid
        imported: np.ndarray = self.from_grid + self.grid_charge
        return imported

    @property
    def total_export(self) -> np.ndarray:
        """Everything the meter counts as feed-in."""
        if self.grid_discharge is None:
            return self.to_grid
        exported: np.ndarray = self.to_grid + self.grid_discharge
        return exported

    @property
    def self_consumption_rate(self) -> float:
        """Share of production that stayed on the property.

        Production either serves the household directly, charges the battery or
        leaves through the meter. Counting the first two is exact. Counting
        discharge instead would be wrong twice over: it has already lost the
        round trip efficiency, and with grid charging it contains energy that
        never came off the roof.
        """
        produced = float(self.production.sum())
        if produced == 0.0:
            return 0.0
        kept = float(self.self_consumption.sum() + self.battery_charge.sum())
        return kept / produced


@dataclass(frozen=True)
class MoneyResult:
    baseline_eur: Decimal
    scenario_eur: Decimal

    @property
    def difference_eur(self) -> Decimal:
        return self.scenario_eur - self.baseline_eur


@dataclass(frozen=True)
class Band:
    """A measured uncertainty band. Never a hard-coded percentage."""

    p10_eur: Decimal
    p50_eur: Decimal
    p90_eur: Decimal
    runs: int


@dataclass(frozen=True)
class Result:
    engine_version: str
    band: Band
    self_consumption_rate: float
    production_source: ProductionSource
    profile_year: int
    weather_year: int
    scenarios: dict[str, MoneyResult] = field(default_factory=dict)
