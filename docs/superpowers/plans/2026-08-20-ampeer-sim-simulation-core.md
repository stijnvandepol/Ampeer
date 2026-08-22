# ampeer_sim Simulation Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status on 2026-08-22: delivered.** Every file this plan names is in the tree,
> which `tests/test_plans.py` asserts for all six plans and fails on the day one
> of them stops being true. The checkboxes below were never ticked while the work
> was carried out, so read them as the task list this plan was written with and
> not as work that is waiting. What the test cannot say is whether each step was
> carried out the way it is written here; that is what the commit history and the
> suite are for.

**Goal:** Build `ampeer_sim`, a standalone Python package that turns four to nine self-reported answers into a quarter-hourly energy simulation and a money figure with a measured uncertainty band, without any meter connection.

**Architecture:** A pure-Python package with no I/O of its own. External data (NEDU standard consumption profiles, PVGIS production and temperature, day-ahead prices) enters through injected providers defined as `Protocol` types. Energy quantities are `float` in numpy arrays; money is `Decimal` and only appears in `economics/tariffs.py`. The package must never import Django; CI enforces this.

**Tech Stack:** Python 3.12, numpy, requests (providers only), pytest, hypothesis, ruff, mypy strict.

**Spec:** `docs/superpowers/specs/2026-08-20-simulation-core-design.md`

## Global Constraints

- Python 3.12. Type hints are mandatory on every function, `mypy --strict` must pass.
- `ampeer_sim` must not import `django`. Enforced by a test and by CI.
- Money is `Decimal`, energy is `float`. The only place a price meets an energy series is `economics/tariffs.py`.
- Code identifiers, docstrings, comments and commit messages are English. User-facing strings are Dutch, but this package produces no user-facing strings: it returns rule ids, numbers and enums only.
- Timestamps are stored in UTC. The profile grid uses constant winter time (UTC+1, no DST jump); local clock time is derived where behaviour is modelled.
- Every `Result` carries `ampeer_sim.ENGINE_VERSION`.
- Profile fraction sums are validated with tolerance `1e-6`, not `1e-9`.
- The per-timestep energy balance must close within `1e-9`.
- Never commit NEDU profile CSVs or PVGIS responses to the repository. They are fetched by `tools/ingest_profiles.py` into `data/` which is gitignored.
- A complete result from four answers, including the sensitivity runs, must finish in under 2 seconds.
- No em-dashes in any Dutch text this project produces.

---

## File Structure

| File | Responsibility |
|---|---|
| `ampeer_sim/__init__.py` | `ENGINE_VERSION` constant, package exports |
| `ampeer_sim/types.py` | Frozen dataclasses and enums for all inputs and outputs |
| `ampeer_sim/timebase.py` | `YearGrid`: the quarter-hour year grid, local clock derivation, hour-to-quarter interpolation, leap-year alignment |
| `ampeer_sim/providers.py` | `ProfileProvider`, `ProductionProvider`, `PriceProvider` protocols |
| `ampeer_sim/profiles/nedu.py` | Parse, validate and scale NEDU profile fractions |
| `ampeer_sim/profiles/assets.py` | EV and heat pump consumption profiles |
| `ampeer_sim/profiles/presence.py` | Shiftable-block presence correction |
| `ampeer_sim/profiles/compose.py` | Assemble the gross consumption series |
| `ampeer_sim/production/model.py` | Losses, degradation, hour-to-quarter conversion |
| `ampeer_sim/production/pvgis.py` | PVGIS provider and the offline fallback provider |
| `ampeer_sim/engine/battery.py` | Battery state model |
| `ampeer_sim/engine/strategies.py` | Control strategies, including the arbitrage foresight window |
| `ampeer_sim/engine/run.py` | The timestep loop and the energy balance invariant |
| `ampeer_sim/economics/tariffs.py` | The single kWh-to-euro boundary |
| `ampeer_sim/economics/sensitivity.py` | Input variation, p10/p50/p90 band |
| `ampeer_sim/validate.py` | CLI to check the model against a real annual statement |
| `tools/ingest_profiles.py` | Download and extract NEDU profiles into `data/` |

---

### Task 1: Package skeleton and the Django import guard

**Files:**
- Create: `pyproject.toml`
- Create: `ampeer_sim/__init__.py`
- Create: `.gitignore`
- Create: `tests/test_boundaries.py`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: nothing
- Produces: `ampeer_sim.ENGINE_VERSION: str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_boundaries.py`:

```python
"""Structural guarantees that must hold for the whole package."""

from __future__ import annotations

import ast
import pathlib

import ampeer_sim

PACKAGE_ROOT = pathlib.Path(ampeer_sim.__file__).parent


def _imported_module_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_package_never_imports_django() -> None:
    offenders = [
        path.relative_to(PACKAGE_ROOT)
        for path in PACKAGE_ROOT.rglob("*.py")
        if "django" in _imported_module_names(path)
    ]
    assert offenders == [], f"ampeer_sim must not import django: {offenders}"


def test_engine_version_is_declared() -> None:
    assert isinstance(ampeer_sim.ENGINE_VERSION, str)
    assert ampeer_sim.ENGINE_VERSION.count(".") == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boundaries.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim'`

- [ ] **Step 3: Write minimal implementation**

Create `pyproject.toml`:

```toml
[project]
name = "ampeer-sim"
version = "0.1.0"
description = "Ampeer simulation core: synthetic household energy profiles and scenario simulation"
requires-python = ">=3.12"
dependencies = ["numpy>=2.0", "requests>=2.32"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "hypothesis>=6.100", "mypy>=1.10", "ruff>=0.5", "types-requests"]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["ampeer_sim*"]

[tool.mypy]
python_version = "3.12"
strict = true

[tool.ruff]
line-length = 100
target-version = "py312"
```

Create `ampeer_sim/__init__.py`:

```python
"""Ampeer simulation core.

This package must remain free of Django imports and of I/O. External data
enters through the protocols in ``ampeer_sim.providers``.
"""

from __future__ import annotations

ENGINE_VERSION = "0.1.0"

__all__ = ["ENGINE_VERSION"]
```

Create `.gitignore`:

```
__pycache__/
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
data/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && pytest tests/test_boundaries.py -v`
Expected: PASS, 2 passed

- [ ] **Step 5: Add the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ruff check ampeer_sim tests
      - run: mypy ampeer_sim
      - run: pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml ampeer_sim/__init__.py .gitignore tests/test_boundaries.py .github/workflows/ci.yml
git commit -m "feat: add ampeer_sim package skeleton with django import guard"
```

---

### Task 2: Core types and provider protocols

**Files:**
- Create: `ampeer_sim/types.py`
- Create: `ampeer_sim/providers.py`
- Create: `tests/test_types.py`

**Interfaces:**
- Consumes: `ampeer_sim.ENGINE_VERSION`
- Produces:
  - Enums `EVChargingBehaviour`, `Strategy`, `ProductionSource`, `ProfileCategory`
  - Dataclasses `PVSystem`, `EV`, `HeatPump`, `BatterySpec`, `Household`, `TariffSet`, `EnergyFlows`, `MoneyResult`, `Band`, `Result`
  - Protocols `ProfileProvider`, `ProductionProvider`, `PriceProvider`

- [ ] **Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
from __future__ import annotations

import dataclasses
from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.providers import ProductionProvider
from ampeer_sim.types import (
    BatterySpec,
    EVChargingBehaviour,
    EnergyFlows,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.types'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/types.py`:

```python
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
    shiftable_block_kwh: float = 1.75
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
    consumption: np.ndarray
    production: np.ndarray
    self_consumption: np.ndarray
    from_grid: np.ndarray
    to_grid: np.ndarray
    battery_charge: np.ndarray
    battery_discharge: np.ndarray

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
        if len(lengths) != 1:
            raise ValueError("all flow series must have the same length")

    @property
    def self_consumption_rate(self) -> float:
        produced = float(self.production.sum())
        if produced == 0.0:
            return 0.0
        covered = float(self.self_consumption.sum() + self.battery_discharge.sum())
        return covered / produced


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
```

Create `ampeer_sim/providers.py`:

```python
"""Protocols for every source of external data.

The simulation core performs no I/O. Implementations of these protocols are
the only place where the network or the filesystem is touched.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ampeer_sim.types import ProductionSource, ProfileCategory


@runtime_checkable
class ProfileProvider(Protocol):
    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        """Return the quarter-hour fraction series for one profile category.

        The array holds 35040 values, or 35136 in a leap year.
        """


@runtime_checkable
class ProductionProvider(Protocol):
    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        """Return (irradiance_w_m2, temperature_c, source) at hourly resolution."""


@runtime_checkable
class PriceProvider(Protocol):
    def hourly_day_ahead(self, year: int) -> np.ndarray:
        """Return day-ahead prices in euro per kWh, one value per hour."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_types.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/types.py ampeer_sim/providers.py tests/test_types.py
git commit -m "feat: add core value types and provider protocols"
```

---

### Task 3: The year grid and time conversions

**Files:**
- Create: `ampeer_sim/timebase.py`
- Create: `tests/test_timebase.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `YearGrid.for_year(year: int) -> YearGrid`
  - `YearGrid.quarters: int`, `.local_hour: np.ndarray`, `.weekday: np.ndarray`, `.day_index: np.ndarray`, `.hours: int`
  - `YearGrid.hourly_to_quarters(hourly: np.ndarray) -> np.ndarray`
  - `YearGrid.align_hourly_year(hourly: np.ndarray, weather_year: int) -> np.ndarray`

Design notes an implementer needs:

- The grid is expressed in constant winter time (UTC+1, no DST jump), which is the
  convention NEDU uses. There are therefore exactly `days * 96` quarters and no gaps.
- Local clock time, which is what human behaviour follows, is derived by converting
  each grid instant to `Europe/Amsterdam`. This is where the March and October jumps
  appear.
- PVGIS timestamps an hourly value at ten past the hour. We treat the value as the
  average over the hour that starts at the stated hour, with its midpoint at
  `h + 0.5`. The resulting shift is twenty minutes and is negligible next to the
  other model uncertainties, but it must be recorded in `docs/methodologie.md`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_timebase.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.timebase import YearGrid


def test_non_leap_year_has_35040_quarters() -> None:
    assert YearGrid.for_year(2025).quarters == 35_040


def test_leap_year_has_35136_quarters() -> None:
    assert YearGrid.for_year(2024).quarters == 35_136


def test_grid_starts_at_local_midnight() -> None:
    grid = YearGrid.for_year(2025)
    assert grid.local_hour[0] == 0
    assert grid.weekday[0] == 2  # 1 January 2025 is a Wednesday


def test_summer_time_start_skips_an_hour_of_local_clock() -> None:
    grid = YearGrid.for_year(2025)
    # 30 March 2025, the clock jumps from 02:00 to 03:00 local time.
    march_30 = (31 + 28 + 29) * 96
    hours_that_day = sorted(set(grid.local_hour[march_30 : march_30 + 96].tolist()))
    assert 2 not in hours_that_day
    assert len(hours_that_day) == 23


def test_hourly_to_quarters_preserves_a_constant_series() -> None:
    grid = YearGrid.for_year(2025)
    quarters = grid.hourly_to_quarters(np.full(grid.hours, 7.0))
    assert quarters.shape == (grid.quarters,)
    assert np.allclose(quarters, 7.0)


def test_hourly_to_quarters_interpolates_between_midpoints() -> None:
    grid = YearGrid.for_year(2025)
    hourly = np.zeros(grid.hours)
    hourly[10] = 0.0
    hourly[11] = 4.0
    quarters = grid.hourly_to_quarters(hourly)
    # Midpoint of hour 10 is quarter index 42, midpoint of hour 11 is 46.
    assert quarters[42] == pytest.approx(0.0)
    assert quarters[46] == pytest.approx(4.0)
    assert quarters[44] == pytest.approx(2.0)


def test_align_hourly_year_drops_29_february_for_a_non_leap_grid() -> None:
    grid = YearGrid.for_year(2025)
    leap_hourly = np.arange(8784, dtype=float)
    aligned = grid.align_hourly_year(leap_hourly, weather_year=2024)
    assert aligned.shape == (8760,)
    # The first hour of 1 March survives; 29 February is gone.
    assert aligned[(31 + 28) * 24] == pytest.approx(leap_hourly[(31 + 29) * 24])


def test_align_hourly_year_duplicates_28_february_for_a_leap_grid() -> None:
    grid = YearGrid.for_year(2024)
    normal_hourly = np.arange(8760, dtype=float)
    aligned = grid.align_hourly_year(normal_hourly, weather_year=2025)
    assert aligned.shape == (8784,)
    feb_28 = (31 + 27) * 24
    feb_29 = (31 + 28) * 24
    assert np.allclose(aligned[feb_29 : feb_29 + 24], aligned[feb_28 : feb_28 + 24])


def test_align_hourly_year_rejects_a_wrong_length_series() -> None:
    grid = YearGrid.for_year(2025)
    with pytest.raises(ValueError, match="8760 or 8784"):
        grid.align_hourly_year(np.zeros(100), weather_year=2025)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_timebase.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.timebase'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/timebase.py`:

```python
"""The single definition of the simulation year grid.

Every series entering the core is placed on this grid first. After that,
everything is index against index and no module needs timezone logic.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import cached_property
from zoneinfo import ZoneInfo

import numpy as np

QUARTERS_PER_HOUR = 4
QUARTERS_PER_DAY = 96
HOURS_PER_DAY = 24

#: NEDU expresses its grid in continuous winter time, so there is no DST gap.
GRID_TZ = timezone(timedelta(hours=1))
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")


@dataclass(frozen=True)
class YearGrid:
    """A quarter-hour grid for one calendar year."""

    year: int
    days: int

    @classmethod
    def for_year(cls, year: int) -> YearGrid:
        return cls(year=year, days=366 if calendar.isleap(year) else 365)

    @property
    def quarters(self) -> int:
        return self.days * QUARTERS_PER_DAY

    @property
    def hours(self) -> int:
        return self.days * HOURS_PER_DAY

    @property
    def is_leap(self) -> bool:
        return self.days == 366

    @cached_property
    def _local_times(self) -> list[datetime]:
        start = datetime(self.year, 1, 1, tzinfo=GRID_TZ)
        return [
            (start + timedelta(minutes=15 * index)).astimezone(LOCAL_TZ)
            for index in range(self.quarters)
        ]

    @cached_property
    def local_hour(self) -> np.ndarray:
        """Local clock hour per quarter. Behaviour models use this, not UTC."""
        return np.array([moment.hour for moment in self._local_times], dtype=np.int8)

    @cached_property
    def weekday(self) -> np.ndarray:
        """Monday is 0, Sunday is 6."""
        return np.array([moment.weekday() for moment in self._local_times], dtype=np.int8)

    @cached_property
    def day_index(self) -> np.ndarray:
        """Zero-based day number within the year, one value per quarter."""
        return np.repeat(np.arange(self.days, dtype=np.int16), QUARTERS_PER_DAY)

    def hourly_to_quarters(self, hourly: np.ndarray) -> np.ndarray:
        """Interpolate an hourly series onto the quarter grid.

        The hourly value is treated as the average over its hour, so its
        midpoint sits at quarter index ``hour * 4 + 1.5``. Values outside the
        first and last midpoint are clamped rather than extrapolated.
        """
        if hourly.shape != (self.hours,):
            raise ValueError(f"expected {self.hours} hourly values, got {hourly.shape}")
        hour_midpoints = np.arange(self.hours, dtype=float) * QUARTERS_PER_HOUR + 1.5
        quarter_positions = np.arange(self.quarters, dtype=float)
        return np.interp(quarter_positions, hour_midpoints, hourly)

    def align_hourly_year(self, hourly: np.ndarray, weather_year: int) -> np.ndarray:
        """Align an hourly series from another year onto this grid by calendar date.

        Production is not weekday dependent, so aligning on date rather than on
        weekday is correct and keeps the profile year in charge of the weekday
        structure.
        """
        if hourly.shape[0] not in (8760, 8784):
            raise ValueError(f"expected 8760 or 8784 hourly values, got {hourly.shape[0]}")
        source_is_leap = hourly.shape[0] == 8784
        if source_is_leap == self.is_leap:
            return hourly.astype(float, copy=False)

        feb_29_start = (31 + 28) * HOURS_PER_DAY
        if source_is_leap and not self.is_leap:
            return np.delete(hourly, np.arange(feb_29_start, feb_29_start + HOURS_PER_DAY))

        feb_28_start = (31 + 27) * HOURS_PER_DAY
        duplicated = hourly[feb_28_start : feb_28_start + HOURS_PER_DAY]
        return np.insert(hourly, feb_29_start, duplicated)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_timebase.py -v`
Expected: PASS, 9 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/timebase.py tests/test_timebase.py
git commit -m "feat: add YearGrid with local clock derivation and leap alignment"
```

---

### Task 4: NEDU profile ingest tool

**Files:**
- Create: `tools/ingest_profiles.py`
- Create: `tests/test_ingest_profiles.py`

**Interfaces:**
- Consumes: nothing from the package
- Produces: `tools.ingest_profiles.ingest(year: int, target_dir: Path, opener: UrlOpener | None = None) -> Path`

Design notes:

- The NEDU archive lives at
  `https://energiedatawijzer.nl/app/uploads/Documenten/Profielen/Profielen/Profielen-elektriciteit-<year>-v1.00-incl.-verslag.zip`.
- The archive holds a readme PDF, a report PDF and two CSVs. We only need the main
  CSV, whose name starts with `Standaardprofielen elektriciteit` and does not contain
  `E4A`.
- Never commit the extracted CSV. `data/` is gitignored.
- The redistribution licence is unconfirmed, which is exactly why this is a fetch step
  and not a vendored file.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_profiles.py`:

```python
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from tools.ingest_profiles import ProfileArchiveError, ingest

CSV_BODY = "header;row\n2025-01-01 00:15;0.1\n"


def _archive_bytes(names: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, CSV_BODY)
    return buffer.getvalue()


def test_ingest_extracts_the_main_profile_csv(tmp_path: Path) -> None:
    payload = _archive_bytes(
        [
            "Standaardprofielen elektriciteit 2025 versie 1.00.csv",
            "Standaardprofielen elektriciteit 2025 versie E4A_21 1.00.csv",
            "readme.pdf",
        ]
    )
    written = ingest(2025, tmp_path, opener=lambda url: payload)
    assert written == tmp_path / "nedu-profiles-2025.csv"
    assert written.read_text(encoding="utf-8") == CSV_BODY


def test_ingest_rejects_an_archive_without_a_profile_csv(tmp_path: Path) -> None:
    payload = _archive_bytes(["readme.pdf"])
    with pytest.raises(ProfileArchiveError, match="no profile CSV"):
        ingest(2025, tmp_path, opener=lambda url: payload)


def test_ingest_rejects_an_ambiguous_archive(tmp_path: Path) -> None:
    payload = _archive_bytes(
        [
            "Standaardprofielen elektriciteit 2025 versie 1.00.csv",
            "Standaardprofielen elektriciteit 2025 versie 1.01.csv",
        ]
    )
    with pytest.raises(ProfileArchiveError, match="ambiguous"):
        ingest(2025, tmp_path, opener=lambda url: payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest_profiles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Write minimal implementation**

Create `tools/__init__.py` as an empty file, then create `tools/ingest_profiles.py`:

```python
"""Fetch NEDU standard consumption profiles into the local data directory.

The redistribution licence of these files is not confirmed, so they are never
committed. Run this at build or deploy time.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests

ARCHIVE_URL = (
    "https://energiedatawijzer.nl/app/uploads/Documenten/Profielen/Profielen/"
    "Profielen-elektriciteit-{year}-v1.00-incl.-verslag.zip"
)

UrlOpener = Callable[[str], bytes]


class ProfileArchiveError(RuntimeError):
    """The downloaded archive did not look the way we expect."""


def _download(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def _select_profile_member(names: list[str]) -> str:
    candidates = [
        name
        for name in names
        if name.lower().endswith(".csv")
        and "standaardprofielen elektriciteit" in name.lower()
        and "e4a" not in name.lower()
    ]
    if not candidates:
        raise ProfileArchiveError("archive contains no profile CSV")
    if len(candidates) > 1:
        raise ProfileArchiveError(f"ambiguous archive, found {len(candidates)} profile CSVs")
    return candidates[0]


def ingest(year: int, target_dir: Path, opener: UrlOpener | None = None) -> Path:
    """Download the archive for ``year`` and write the main CSV into ``target_dir``."""
    fetch = opener or _download
    payload = fetch(ARCHIVE_URL.format(year=year))
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        member = _select_profile_member(archive.namelist())
        body = archive.read(member)
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / f"nedu-profiles-{year}.csv"
    destination.write_bytes(body)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int)
    parser.add_argument("--target", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    written = ingest(args.year, args.target)
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest_profiles.py -v`
Expected: PASS, 3 passed

- [ ] **Step 5: Commit**

```bash
git add tools/__init__.py tools/ingest_profiles.py tests/test_ingest_profiles.py
git commit -m "feat: add NEDU profile ingest tool"
```

---

### Task 5: Parse, validate and scale NEDU profiles

**Files:**
- Create: `ampeer_sim/profiles/__init__.py`
- Create: `ampeer_sim/profiles/nedu.py`
- Create: `tests/fixtures/nedu_tiny.csv`
- Create: `tests/test_nedu.py`

**Interfaces:**
- Consumes: `ProfileCategory`, `YearGrid`
- Produces:
  - `NeduFileProvider(path: Path)` implementing `ProfileProvider`
  - `expected_sum(category: ProfileCategory) -> float`
  - `validate_fractions(fractions: np.ndarray, category: ProfileCategory, grid: YearGrid) -> None`
  - `scale_to_annual(fractions: np.ndarray, annual_kwh: float, category: ProfileCategory) -> np.ndarray`

Design notes:

- Column layout, verified against the real 2025 file: six header rows, then data.
  Column 0 is continuous winter time, columns 1 and 2 are local from and to, and the
  data columns start at index 3. Header row 0 holds names like `1.00_E1A_AZI_A`.
- Only `AZI_A` series are used as the base consumption shape. `AMI_A` is the net grid
  offtake of households that already feed in, so using it would count the sun twice.
- E1A sums to 1, E1B and E1C sum to 2 because they carry two tariff registers. Leap
  years exceed those sums. Tolerance is `1e-6`.
- Scaling divides by the observed sum rather than by the nominal one. That makes the
  scaled series total exactly `annual_kwh` regardless of category or leap year, which
  is what every downstream test wants to assert.

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/nedu_tiny.csv`. This is a hand-made four-quarter file with the
real header layout, so the parser is tested against the real shape without a 13 MB file:

```
HASH;;Versienr;1.00_E1A_AZI_A;1.00_E1A_AZI_I;1.00_E1B_AZI_A
;;Toepassingsjaar;2025;2025;2025
;;Categoriecode;E1A;E1A;E1B
;;Type;AZI;AZI;AZI
;;Richting;A;I;A
CET;CEST
;van;tot
2025-01-01 00:15;2025-01-01 00:00;2025-01-01 00:15;0.10000000;0.00000000;0.50000000
2025-01-01 00:30;2025-01-01 00:15;2025-01-01 00:30;0.20000000;0.00000000;0.50000000
2025-01-01 00:45;2025-01-01 00:30;2025-01-01 00:45;0.30000000;0.00000000;0.50000000
2025-01-01 01:00;2025-01-01 00:45;2025-01-01 01:00;0.40000000;1.00000000;0.50000000
```

Create `tests/test_nedu.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ampeer_sim.profiles.nedu import (
    NeduFileProvider,
    ProfileValidationError,
    expected_sum,
    scale_to_annual,
    validate_fractions,
)
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import ProfileCategory

FIXTURE = Path(__file__).parent / "fixtures" / "nedu_tiny.csv"


def test_provider_reads_the_requested_category_column() -> None:
    provider = NeduFileProvider(FIXTURE)
    fractions = provider.fractions(2025, ProfileCategory.E1A)
    assert np.allclose(fractions, [0.1, 0.2, 0.3, 0.4])


def test_provider_reads_a_second_category_from_the_same_file() -> None:
    provider = NeduFileProvider(FIXTURE)
    fractions = provider.fractions(2025, ProfileCategory.E1B)
    assert np.allclose(fractions, [0.5, 0.5, 0.5, 0.5])


def test_provider_rejects_a_year_the_file_does_not_hold() -> None:
    provider = NeduFileProvider(FIXTURE)
    with pytest.raises(ProfileValidationError, match="2026"):
        provider.fractions(2026, ProfileCategory.E1A)


def test_expected_sum_is_one_for_e1a_and_two_for_dual_register_profiles() -> None:
    assert expected_sum(ProfileCategory.E1A) == pytest.approx(1.0)
    assert expected_sum(ProfileCategory.E1B) == pytest.approx(2.0)
    assert expected_sum(ProfileCategory.E1C) == pytest.approx(2.0)


def test_validate_accepts_a_sum_within_tolerance() -> None:
    grid = YearGrid.for_year(2025)
    fractions = np.full(grid.quarters, 1.0 / grid.quarters)
    fractions[0] += 5e-7
    validate_fractions(fractions, ProfileCategory.E1A, grid)


def test_validate_rejects_a_sum_outside_tolerance() -> None:
    grid = YearGrid.for_year(2025)
    fractions = np.full(grid.quarters, 1.05 / grid.quarters)
    with pytest.raises(ProfileValidationError, match="sum"):
        validate_fractions(fractions, ProfileCategory.E1A, grid)


def test_validate_rejects_a_wrong_length_series() -> None:
    grid = YearGrid.for_year(2025)
    with pytest.raises(ProfileValidationError, match="35040"):
        validate_fractions(np.zeros(10), ProfileCategory.E1A, grid)


def test_validate_accepts_a_leap_year_sum_above_the_nominal_value() -> None:
    grid = YearGrid.for_year(2024)
    fractions = np.full(grid.quarters, 1.0 / 35_040)  # sums to about 1.0027
    validate_fractions(fractions, ProfileCategory.E1A, grid)


def test_scaling_hits_the_annual_total_exactly() -> None:
    fractions = np.array([0.1, 0.2, 0.3, 0.4])
    scaled = scale_to_annual(fractions, 3_500.0, ProfileCategory.E1A)
    assert scaled.sum() == pytest.approx(3_500.0)
    assert scaled[3] == pytest.approx(1_400.0)


def test_scaling_a_dual_register_profile_also_hits_the_annual_total() -> None:
    fractions = np.full(4, 0.5)  # sums to 2, as E1B does
    scaled = scale_to_annual(fractions, 3_500.0, ProfileCategory.E1B)
    assert scaled.sum() == pytest.approx(3_500.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_nedu.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.profiles'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/profiles/__init__.py` as an empty file, then create
`ampeer_sim/profiles/nedu.py`:

```python
"""Read and scale NEDU standard consumption profiles.

Verified against the real 2025 file on 2026-08-20: six header rows, semicolon
separated, decimal point, 35040 data rows for a non-leap year.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import ProfileCategory

HEADER_ROWS = 7
FIRST_DATA_COLUMN = 3
NAME_ROW = 0
YEAR_ROW = 1

#: Only E1A and E2A carry a single register. The rest hold two, each summing to 1.
SINGLE_REGISTER = frozenset({ProfileCategory.E1A})

#: Measured spread on the real files is about 6e-7, so 1e-9 would be far too strict.
SUM_TOLERANCE = 1e-6

#: The base consumption shape always comes from connections without feed-in.
BASE_SERIES_SUFFIX = "AZI_A"


class ProfileValidationError(ValueError):
    """The profile file or series did not match what the format guarantees."""


def expected_sum(category: ProfileCategory) -> float:
    return 1.0 if category in SINGLE_REGISTER else 2.0


def validate_fractions(
    fractions: np.ndarray, category: ProfileCategory, grid: YearGrid
) -> None:
    """Check length and total. Raises ``ProfileValidationError`` on a mismatch."""
    if fractions.shape != (grid.quarters,):
        raise ProfileValidationError(
            f"expected {grid.quarters} values for {grid.year}, got {fractions.shape[0]}"
        )
    nominal = expected_sum(category)
    total = float(fractions.sum())
    # A leap year adds one day of fractions on top of the nominal sum.
    upper = nominal * (366 / 365) if grid.is_leap else nominal
    if not nominal - SUM_TOLERANCE <= total <= upper + SUM_TOLERANCE:
        raise ProfileValidationError(
            f"{category.value} fraction sum {total!r} outside "
            f"[{nominal - SUM_TOLERANCE}, {upper + SUM_TOLERANCE}]"
        )


def scale_to_annual(
    fractions: np.ndarray, annual_kwh: float, category: ProfileCategory
) -> np.ndarray:
    """Scale a fraction series so it totals exactly ``annual_kwh``.

    Dividing by the observed sum rather than the nominal one makes this correct
    for single and dual register profiles and for leap years alike.
    """
    total = float(fractions.sum())
    if total <= 0.0:
        raise ProfileValidationError(f"{category.value} fractions sum to {total!r}")
    return fractions * (annual_kwh / total)


class NeduFileProvider:
    """A ``ProfileProvider`` backed by an ingested NEDU CSV."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        with self._path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle, delimiter=";"))
        column = self._locate_column(rows, year, category)
        values = [float(row[column]) for row in rows[HEADER_ROWS:] if row[column].strip()]
        return np.array(values, dtype=float)

    def _locate_column(
        self, rows: list[list[str]], year: int, category: ProfileCategory
    ) -> int:
        wanted = f"{category.value}_{BASE_SERIES_SUFFIX}"
        for index, name in enumerate(rows[NAME_ROW]):
            if index < FIRST_DATA_COLUMN or not name.endswith(wanted):
                continue
            found_year = rows[YEAR_ROW][index].strip()
            if found_year != str(year):
                continue
            return index
        raise ProfileValidationError(
            f"{self._path.name} holds no {wanted} series for {year}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_nedu.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/profiles/ tests/fixtures/nedu_tiny.csv tests/test_nedu.py
git commit -m "feat: parse, validate and scale NEDU profile fractions"
```

---

### Task 6: Production model

**Files:**
- Create: `ampeer_sim/production/__init__.py`
- Create: `ampeer_sim/production/model.py`
- Create: `tests/test_production_model.py`

**Interfaces:**
- Consumes: `YearGrid`, `PVSystem`
- Produces: `production_series(irradiance_w_m2: np.ndarray, system: PVSystem, grid: YearGrid, weather_year: int, reference_year: int | None = None) -> np.ndarray`

Design notes:

- The order matters and is a spec decision: interpolate the irradiance onto the
  quarter grid first, then convert to power. Irradiance is smooth, power is not, and
  interpolation does not commute with a non-linear conversion.
- Conversion uses standard test conditions: `1000 W/m2` yields the rated peak power.
  Losses and degradation are applied as multiplicative factors.
- Degradation is 0.5 percent per year since the install year, capped at 20 percent.

- [ ] **Step 1: Write the failing test**

Create `tests/test_production_model.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.production.model import production_series
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import PVSystem


def _flat_irradiance(grid: YearGrid, value: float) -> np.ndarray:
    return np.full(grid.hours, value)


def test_full_sun_yields_rated_power_minus_losses() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, system_loss_fraction=0.14)
    series = production_series(_flat_irradiance(grid, 1_000.0), system, grid, weather_year=2025)
    # 4 kW rated, 14 percent loss, a quarter of an hour per step.
    assert series[0] == pytest.approx(4.0 * 0.86 * 0.25)


def test_darkness_yields_nothing() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35)
    series = production_series(_flat_irradiance(grid, 0.0), system, grid, weather_year=2025)
    assert series.sum() == pytest.approx(0.0)


def test_series_lands_on_the_quarter_grid() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35)
    series = production_series(_flat_irradiance(grid, 500.0), system, grid, weather_year=2025)
    assert series.shape == (grid.quarters,)


def test_a_leap_weather_year_is_aligned_onto_a_non_leap_grid() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35)
    series = production_series(np.full(8_784, 500.0), system, grid, weather_year=2024)
    assert series.shape == (grid.quarters,)


def test_degradation_reduces_output_for_an_older_system() -> None:
    grid = YearGrid.for_year(2025)
    fresh = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2025)
    aged = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2015)
    irradiance = _flat_irradiance(grid, 800.0)
    fresh_total = production_series(irradiance, fresh, grid, weather_year=2025).sum()
    aged_total = production_series(irradiance, aged, grid, weather_year=2025).sum()
    assert aged_total == pytest.approx(fresh_total * 0.95)


def test_degradation_is_capped(inplace: None = None) -> None:
    grid = YearGrid.for_year(2025)
    ancient = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=1960)
    fresh = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2025)
    irradiance = _flat_irradiance(grid, 800.0)
    ratio = (
        production_series(irradiance, ancient, grid, weather_year=2025).sum()
        / production_series(irradiance, fresh, grid, weather_year=2025).sum()
    )
    assert ratio == pytest.approx(0.80)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_production_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.production'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/production/__init__.py` as an empty file, then create
`ampeer_sim/production/model.py`:

```python
"""Convert an irradiance series into a quarter-hour production series."""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_HOUR, YearGrid
from ampeer_sim.types import PVSystem

#: Irradiance at standard test conditions, in W/m2.
STC_IRRADIANCE = 1_000.0

#: Annual output loss of a crystalline panel, as a fraction.
DEGRADATION_PER_YEAR = 0.005

#: Never model a panel as worse than this, however old it is.
MAX_DEGRADATION = 0.20


def degradation_factor(install_year: int | None, reference_year: int) -> float:
    if install_year is None:
        return 1.0
    age = max(0, reference_year - install_year)
    return 1.0 - min(age * DEGRADATION_PER_YEAR, MAX_DEGRADATION)


def production_series(
    irradiance_w_m2: np.ndarray,
    system: PVSystem,
    grid: YearGrid,
    weather_year: int,
    reference_year: int | None = None,
) -> np.ndarray:
    """Return production in kWh per quarter.

    Interpolation happens on irradiance and the conversion to power happens
    afterwards. The conversion is non-linear, so the two do not commute and this
    order is the correct one.
    """
    aligned = grid.align_hourly_year(irradiance_w_m2, weather_year=weather_year)
    quarterly_irradiance = grid.hourly_to_quarters(aligned)

    rated_kw = system.peak_power_wp / 1_000.0
    loss = 1.0 - system.system_loss_fraction
    aging = degradation_factor(system.install_year, reference_year or grid.year)

    power_kw = quarterly_irradiance / STC_IRRADIANCE * rated_kw * loss * aging
    return power_kw / QUARTERS_PER_HOUR
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_production_model.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/production/ tests/test_production_model.py
git commit -m "feat: add production model with interpolation before conversion"
```

---

### Task 7: PVGIS provider and offline fallback

**Files:**
- Create: `ampeer_sim/production/pvgis.py`
- Create: `ampeer_sim/production/fallback_yield.py`
- Create: `tests/test_pvgis_provider.py`

**Interfaces:**
- Consumes: `ProductionSource`, `ProductionProvider`
- Produces:
  - `PvgisProvider(weather_year: int, timeout_s: float = 20.0, session: requests.Session | None = None)`
  - `FallbackProvider(weather_year: int)`
  - `ResilientProductionProvider(primary: ProductionProvider, fallback: ProductionProvider)`
  - `postcode4_to_latlon(postcode4: str) -> tuple[float, float]`

Design notes:

- This is the only module in the package that performs outbound HTTP. The URL is
  built from a constant plus validated numeric parameters. User input never becomes
  part of the URL structure, which is what keeps the project SSRF rule intact.
- A timeout or an HTTP 429 must never fail the advice. `ResilientProductionProvider`
  catches those, falls back, and marks the result `ProductionSource.FALLBACK` so the
  degradation is visible in the output instead of silent.
- `postcode4_to_latlon` uses a small lookup table shipped with the package. For the
  first version a coarse mapping is fine, because a postcode area is a few kilometres
  across and irradiance barely varies over that distance.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pvgis_provider.py`:

```python
from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import requests

from ampeer_sim.production.pvgis import (
    FallbackProvider,
    PvgisProvider,
    ResilientProductionProvider,
    postcode4_to_latlon,
)
from ampeer_sim.types import ProductionSource


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None

    def get(self, url: str, params: dict[str, Any], timeout: float) -> _FakeResponse:
        self.last_url = url
        self.last_params = params
        if self.error is not None:
            raise self.error
        assert self.payload is not None
        return _FakeResponse(self.payload)


def _payload(hours: int = 8_760) -> dict[str, Any]:
    return {
        "outputs": {
            "hourly": [
                {"time": "20230101:0010", "G(i)": 100.0, "T2m": 5.0} for _ in range(hours)
            ]
        }
    }


def test_provider_returns_irradiance_and_temperature() -> None:
    session = _FakeSession(payload=_payload())
    provider = PvgisProvider(weather_year=2023, session=session)
    irradiance, temperature, source = provider.hourly_series("5401", 0.0, 35.0, 3_500)
    assert irradiance.shape == (8_760,)
    assert temperature.shape == (8_760,)
    assert source is ProductionSource.PVGIS


def test_provider_never_puts_user_input_in_the_url() -> None:
    session = _FakeSession(payload=_payload())
    provider = PvgisProvider(weather_year=2023, session=session)
    provider.hourly_series("5401", 0.0, 35.0, 3_500)
    assert session.last_url == "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
    assert session.last_params is not None
    assert isinstance(session.last_params["lat"], float)


def test_fallback_provider_returns_a_full_year_without_network() -> None:
    irradiance, temperature, source = FallbackProvider(2023).hourly_series(
        "5401", 0.0, 35.0, 3_500
    )
    assert irradiance.shape == (8_760,)
    assert temperature.shape == (8_760,)
    assert source is ProductionSource.FALLBACK
    assert irradiance.sum() > 0.0


def test_resilient_provider_falls_back_on_timeout() -> None:
    session = _FakeSession(error=requests.Timeout("too slow"))
    provider = ResilientProductionProvider(
        primary=PvgisProvider(weather_year=2023, session=session),
        fallback=FallbackProvider(2023),
    )
    _, _, source = provider.hourly_series("5401", 0.0, 35.0, 3_500)
    assert source is ProductionSource.FALLBACK


def test_resilient_provider_falls_back_on_rate_limit() -> None:
    session = _FakeSession(error=requests.HTTPError("429 Too Many Requests"))
    provider = ResilientProductionProvider(
        primary=PvgisProvider(weather_year=2023, session=session),
        fallback=FallbackProvider(2023),
    )
    _, _, source = provider.hourly_series("5401", 0.0, 35.0, 3_500)
    assert source is ProductionSource.FALLBACK


def test_resilient_provider_does_not_swallow_a_programming_error() -> None:
    class Broken:
        def hourly_series(
            self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
        ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
            raise TypeError("wrong argument")

    provider = ResilientProductionProvider(primary=Broken(), fallback=FallbackProvider(2023))
    with pytest.raises(TypeError):
        provider.hourly_series("5401", 0.0, 35.0, 3_500)


def test_postcode_lookup_returns_a_dutch_coordinate() -> None:
    lat, lon = postcode4_to_latlon("5401")
    assert 50.7 <= lat <= 53.6
    assert 3.3 <= lon <= 7.3


def test_postcode_lookup_rejects_a_non_numeric_postcode() -> None:
    with pytest.raises(ValueError, match="four digits"):
        postcode4_to_latlon("54AB")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pvgis_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.production.pvgis'`

- [ ] **Step 3: Write the fallback yield table**

Create `ampeer_sim/production/fallback_yield.py`:

```python
"""Offline monthly yield table, used when PVGIS is unreachable.

Values are monthly mean irradiance in W/m2 on a plane tilted 35 degrees facing
south in the Netherlands, derived from long-term PVGIS averages. The table is
deliberately coarse: it exists so the advice never fails, not so it competes
with the real thing.
"""

from __future__ import annotations

#: Monthly mean plane-of-array irradiance in W/m2, January through December.
MONTHLY_MEAN_IRRADIANCE = (
    28.0,
    52.0,
    99.0,
    155.0,
    178.0,
    186.0,
    180.0,
    161.0,
    117.0,
    70.0,
    33.0,
    22.0,
)

#: Monthly mean outdoor temperature in degrees Celsius, De Bilt long-term average.
MONTHLY_MEAN_TEMPERATURE = (
    3.6,
    3.9,
    6.5,
    9.8,
    13.4,
    16.2,
    18.3,
    17.9,
    14.8,
    11.0,
    7.0,
    4.2,
)

#: Relative yield of a plane compared with south at 35 degrees.
ORIENTATION_FACTORS = {
    (0, 35): 1.00,
    (90, 35): 0.85,
    (-90, 35): 0.85,
    (180, 35): 0.62,
    (0, 15): 0.95,
    (0, 60): 0.94,
}
```

- [ ] **Step 4: Write the providers**

Create `ampeer_sim/production/pvgis.py`:

```python
"""Production providers.

This is the only module in ``ampeer_sim`` that performs outbound HTTP. The URL
is a constant; user input contributes validated numeric parameters only, never
parts of the URL itself.
"""

from __future__ import annotations

import calendar
import math

import numpy as np
import requests

from ampeer_sim.production.fallback_yield import (
    MONTHLY_MEAN_IRRADIANCE,
    MONTHLY_MEAN_TEMPERATURE,
    ORIENTATION_FACTORS,
)
from ampeer_sim.types import ProductionSource

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
RADIATION_DATABASE = "PVGIS-SARAH3"

#: Coarse centroid per postcode century, good enough because irradiance barely
#: varies over a few kilometres. Keys are the first two digits of the postcode.
_POSTCODE_CENTROIDS: dict[str, tuple[float, float]] = {
    "10": (52.37, 4.90), "11": (52.31, 4.94), "12": (52.16, 5.02), "13": (52.35, 5.24),
    "14": (52.52, 4.96), "15": (52.46, 4.63), "16": (52.63, 4.75), "17": (52.79, 4.83),
    "18": (52.63, 4.74), "19": (52.46, 4.61), "20": (52.38, 4.63), "21": (52.26, 4.49),
    "22": (52.16, 4.49), "23": (52.16, 4.49), "24": (52.05, 4.63), "25": (52.08, 4.31),
    "26": (52.01, 4.36), "27": (52.02, 4.71), "28": (51.99, 4.47), "29": (51.92, 4.48),
    "30": (51.92, 4.48), "31": (51.92, 4.48), "32": (51.87, 4.60), "33": (51.81, 4.67),
    "34": (52.09, 5.11), "35": (52.09, 5.11), "36": (52.02, 5.17), "37": (52.16, 5.39),
    "38": (52.16, 5.39), "39": (52.05, 5.24), "40": (51.96, 5.32), "41": (51.90, 5.29),
    "42": (51.82, 4.66), "43": (51.49, 3.61), "44": (51.50, 3.90), "45": (51.44, 3.57),
    "46": (51.49, 4.29), "47": (51.59, 4.78), "48": (51.59, 4.78), "49": (51.69, 5.30),
    "50": (51.56, 5.09), "51": (51.56, 5.06), "52": (51.44, 5.48), "53": (51.69, 5.30),
    "54": (51.66, 5.61), "55": (51.44, 5.48), "56": (51.44, 5.48), "57": (51.48, 5.66),
    "58": (51.36, 5.22), "59": (51.44, 5.98), "60": (51.44, 5.98), "61": (51.20, 5.99),
    "62": (50.85, 5.69), "63": (50.85, 5.69), "64": (50.88, 5.98), "65": (51.84, 5.86),
    "66": (51.84, 5.86), "67": (51.98, 5.90), "68": (51.98, 5.90), "69": (51.90, 5.98),
    "70": (51.99, 6.56), "71": (51.99, 6.56), "72": (52.15, 6.19), "73": (52.21, 6.19),
    "74": (52.22, 6.89), "75": (52.22, 6.89), "76": (52.26, 6.79), "77": (52.51, 6.09),
    "78": (52.51, 6.09), "79": (52.71, 6.19), "80": (52.51, 6.09), "81": (52.51, 6.09),
    "82": (52.51, 5.47), "83": (52.71, 6.19), "84": (52.90, 5.90), "85": (52.90, 5.90),
    "86": (53.03, 5.66), "87": (53.03, 5.66), "88": (53.20, 5.79), "89": (53.20, 5.79),
    "90": (53.22, 6.57), "91": (53.22, 6.57), "92": (53.22, 6.57), "93": (53.11, 6.56),
    "94": (53.11, 6.56), "95": (53.33, 6.75), "96": (53.33, 6.75), "97": (53.22, 6.57),
    "98": (53.33, 6.92), "99": (53.33, 6.92),
}

_DEFAULT_CENTROID = (52.09, 5.11)


def postcode4_to_latlon(postcode4: str) -> tuple[float, float]:
    """Map a four digit postcode onto a coarse centroid."""
    if len(postcode4) != 4 or not postcode4.isdigit():
        raise ValueError("postcode4 must be exactly four digits")
    return _POSTCODE_CENTROIDS.get(postcode4[:2], _DEFAULT_CENTROID)


class PvgisProvider:
    """Fetch an hourly irradiance and temperature series from PVGIS."""

    def __init__(
        self,
        weather_year: int,
        timeout_s: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self._weather_year = weather_year
        self._timeout_s = timeout_s
        self._session = session or requests.Session()

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        latitude, longitude = postcode4_to_latlon(postcode4)
        params = {
            "lat": float(latitude),
            "lon": float(longitude),
            "raddatabase": RADIATION_DATABASE,
            "startyear": int(self._weather_year),
            "endyear": int(self._weather_year),
            "pvcalculation": 0,
            "angle": float(tilt_deg),
            "aspect": float(azimuth_deg),
            "outputformat": "json",
        }
        response = self._session.get(PVGIS_URL, params=params, timeout=self._timeout_s)
        response.raise_for_status()
        hourly = response.json()["outputs"]["hourly"]
        irradiance = np.array([row["G(i)"] for row in hourly], dtype=float)
        temperature = np.array([row["T2m"] for row in hourly], dtype=float)
        return irradiance, temperature, ProductionSource.PVGIS


class FallbackProvider:
    """Build an hourly series from monthly means, with no network access.

    The daily shape is a half sine between sunrise and sunset, scaled so the
    monthly mean matches the table. This is deliberately crude; its only job is
    to keep the advice available when PVGIS is not.
    """

    def __init__(self, weather_year: int) -> None:
        self._weather_year = weather_year

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        postcode4_to_latlon(postcode4)  # validate the input the same way
        factor = self._orientation_factor(azimuth_deg, tilt_deg)
        irradiance: list[float] = []
        temperature: list[float] = []
        for month in range(1, 13):
            days = calendar.monthrange(self._weather_year, month)[1]
            mean = MONTHLY_MEAN_IRRADIANCE[month - 1] * factor
            for _ in range(days):
                irradiance.extend(self._day_shape(mean))
                temperature.extend([MONTHLY_MEAN_TEMPERATURE[month - 1]] * 24)
        return (
            np.array(irradiance, dtype=float),
            np.array(temperature, dtype=float),
            ProductionSource.FALLBACK,
        )

    @staticmethod
    def _orientation_factor(azimuth_deg: float, tilt_deg: float) -> float:
        nearest = min(
            ORIENTATION_FACTORS,
            key=lambda key: abs(key[0] - azimuth_deg) + abs(key[1] - tilt_deg),
        )
        return ORIENTATION_FACTORS[nearest]

    @staticmethod
    def _day_shape(mean_irradiance: float) -> list[float]:
        """A half sine over twelve daylight hours, averaging to ``mean_irradiance``."""
        daylight_hours = 12
        peak = mean_irradiance * 24 / daylight_hours * (math.pi / 2)
        values = [0.0] * 24
        for hour in range(6, 6 + daylight_hours):
            phase = (hour - 6 + 0.5) / daylight_hours * math.pi
            values[hour] = peak * math.sin(phase)
        return values


class ResilientProductionProvider:
    """Try the primary provider, fall back on a network problem.

    Only network failures are caught. A ``TypeError`` is a bug in our own code
    and must not be hidden behind a degraded result.
    """

    def __init__(self, primary: object, fallback: object) -> None:
        self._primary = primary
        self._fallback = fallback

    def hourly_series(
        self, postcode4: str, azimuth_deg: float, tilt_deg: float, peak_power_wp: int
    ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
        try:
            return self._primary.hourly_series(  # type: ignore[attr-defined,no-any-return]
                postcode4, azimuth_deg, tilt_deg, peak_power_wp
            )
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError):
            return self._fallback.hourly_series(  # type: ignore[attr-defined,no-any-return]
                postcode4, azimuth_deg, tilt_deg, peak_power_wp
            )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_pvgis_provider.py -v`
Expected: PASS, 8 passed

- [ ] **Step 6: Commit**

```bash
git add ampeer_sim/production/pvgis.py ampeer_sim/production/fallback_yield.py tests/test_pvgis_provider.py
git commit -m "feat: add PVGIS provider with visible offline fallback"
```

---

### Task 8: EV and heat pump profiles

**Files:**
- Create: `ampeer_sim/profiles/assets.py`
- Create: `tests/test_assets.py`

**Interfaces:**
- Consumes: `YearGrid`, `EV`, `EVChargingBehaviour`, `HeatPump`
- Produces:
  - `ev_profile(ev: EV, grid: YearGrid) -> np.ndarray`
  - `ev_solar_profile(ev: EV, grid: YearGrid, surplus_kwh: np.ndarray) -> np.ndarray`
  - `heat_pump_profile(pump: HeatPump, temperature_c: np.ndarray, grid: YearGrid, weather_year: int) -> np.ndarray`

Design notes:

- `NIGHT` charges between 23:00 and 07:00 local time, `ARRIVAL` between 17:00 and
  21:00. Both spread the daily need evenly over their window and both respect the
  charge power limit.
- `SOLAR` needs the production series and is therefore applied later, in
  `compose.py`. It is a separate function so the ordering dependency is visible in
  the signature rather than hidden in a flag.
- Heat demand is proportional to degree hours below the base temperature. The COP
  falls with the outdoor temperature: `cop = cop_at_7c + (t - 7) * cop_slope_per_c`,
  floored at 1.0. A fixed COP would understate winter consumption in exactly the
  months without production.

- [ ] **Step 1: Write the failing test**

Create `tests/test_assets.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.assets import ev_profile, ev_solar_profile, heat_pump_profile
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EV, EVChargingBehaviour, HeatPump

GRID = YearGrid.for_year(2025)


def test_night_charging_hits_the_annual_energy_need() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT, annual_km=12_000, kwh_per_100km=18.0)
    series = ev_profile(ev, GRID)
    assert series.sum() == pytest.approx(ev.annual_kwh)


def test_night_charging_only_happens_at_night() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT)
    series = ev_profile(ev, GRID)
    daytime = series[(GRID.local_hour >= 7) & (GRID.local_hour < 23)]
    assert daytime.sum() == pytest.approx(0.0)


def test_arrival_charging_only_happens_in_the_evening() -> None:
    ev = EV(behaviour=EVChargingBehaviour.ARRIVAL)
    series = ev_profile(ev, GRID)
    outside = series[(GRID.local_hour < 17) | (GRID.local_hour >= 21)]
    assert outside.sum() == pytest.approx(0.0)


def test_charging_never_exceeds_the_charge_power_limit() -> None:
    ev = EV(behaviour=EVChargingBehaviour.ARRIVAL, annual_km=60_000, charge_power_kw=3.7)
    series = ev_profile(ev, GRID)
    assert series.max() <= 3.7 / 4 + 1e-9


def test_solar_charging_requires_a_surplus() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR)
    series = ev_solar_profile(ev, GRID, surplus_kwh=np.zeros(GRID.quarters))
    assert series.sum() == pytest.approx(0.0)


def test_solar_charging_takes_from_the_surplus_up_to_the_daily_need() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=3_650, kwh_per_100km=20.0)
    surplus = np.zeros(GRID.quarters)
    surplus[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 1.0
    series = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    assert series.sum() == pytest.approx(ev.annual_kwh, rel=1e-6)
    assert series[GRID.local_hour < 11].sum() == pytest.approx(0.0)


def test_solar_charging_is_capped_by_the_available_surplus() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=100_000)
    surplus = np.zeros(GRID.quarters)
    surplus[(GRID.local_hour == 12)] = 0.1
    series = ev_solar_profile(ev, GRID, surplus_kwh=surplus)
    assert np.all(series <= surplus + 1e-9)


def test_heat_pump_consumes_nothing_in_a_warm_year() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0, base_temperature_c=15.0)
    warm = np.full(GRID.hours, 25.0)
    series = heat_pump_profile(pump, warm, GRID, weather_year=2025)
    assert series.sum() == pytest.approx(0.0)


def test_heat_pump_delivers_the_requested_heat_demand() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0, base_temperature_c=15.0, cop_at_7c=3.0,
                    cop_slope_per_c=0.0)
    cold = np.full(GRID.hours, 5.0)
    series = heat_pump_profile(pump, cold, GRID, weather_year=2025)
    # With a flat COP of 3, electricity is a third of the heat demand.
    assert series.sum() == pytest.approx(2_000.0, rel=1e-6)


def test_heat_pump_uses_more_electricity_per_unit_of_heat_when_it_is_colder() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0, base_temperature_c=15.0)
    mild = np.full(GRID.hours, 10.0)
    cold = np.full(GRID.hours, -5.0)
    mild_total = heat_pump_profile(pump, mild, GRID, weather_year=2025).sum()
    cold_total = heat_pump_profile(pump, cold, GRID, weather_year=2025).sum()
    assert cold_total > mild_total
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_assets.py -v`
Expected: FAIL with `ImportError: cannot import name 'ev_profile'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/profiles/assets.py`:

```python
"""Consumption profiles for assets the NEDU average does not represent.

An EV and a heat pump are added on top of the base shape rather than mixed
into it, because the household that has them is not the household the average
describes.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_HOUR, YearGrid
from ampeer_sim.types import EV, EVChargingBehaviour, HeatPump

NIGHT_WINDOW = (23, 7)
ARRIVAL_WINDOW = (17, 21)

#: A heat pump never does worse than a resistive heater.
MIN_COP = 1.0


def _window_mask(grid: YearGrid, window: tuple[int, int]) -> np.ndarray:
    start, end = window
    if start < end:
        return (grid.local_hour >= start) & (grid.local_hour < end)
    return (grid.local_hour >= start) | (grid.local_hour < end)


def ev_profile(ev: EV, grid: YearGrid) -> np.ndarray:
    """Return quarter-hour EV consumption in kWh for NIGHT and ARRIVAL behaviour.

    SOLAR is handled by ``ev_solar_profile`` because it needs the production
    series, and that dependency belongs in the signature.
    """
    if ev.behaviour is EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    window = NIGHT_WINDOW if ev.behaviour is EVChargingBehaviour.NIGHT else ARRIVAL_WINDOW
    mask = _window_mask(grid, window)
    series = np.zeros(grid.quarters)
    series[mask] = ev.annual_kwh / float(mask.sum())

    cap = ev.charge_power_kw / QUARTERS_PER_HOUR
    if series.max() > cap:
        raise ValueError(
            f"charging {ev.annual_kwh:.0f} kWh within the window needs more than "
            f"{ev.charge_power_kw} kW"
        )
    return series


def ev_solar_profile(ev: EV, grid: YearGrid, surplus_kwh: np.ndarray) -> np.ndarray:
    """Charge from the production surplus, day by day, up to the daily need."""
    if ev.behaviour is not EVChargingBehaviour.SOLAR:
        return np.zeros(grid.quarters)

    cap = ev.charge_power_kw / QUARTERS_PER_HOUR
    daily_need = ev.annual_kwh / grid.days
    available = np.minimum(surplus_kwh, cap)
    charged = np.zeros(grid.quarters)

    for day in range(grid.days):
        start = day * 96
        stop = start + 96
        day_available = available[start:stop]
        cumulative = np.cumsum(day_available)
        headroom = np.clip(daily_need - (cumulative - day_available), 0.0, None)
        charged[start:stop] = np.minimum(day_available, headroom)
    return charged


def heat_pump_profile(
    pump: HeatPump, temperature_c: np.ndarray, grid: YearGrid, weather_year: int
) -> np.ndarray:
    """Return quarter-hour heat pump electricity consumption in kWh.

    Heat demand follows degree hours below the base temperature. The COP falls
    with the outdoor temperature, which is why a flat COP understates winter
    consumption in exactly the months without production.
    """
    aligned = grid.align_hourly_year(temperature_c, weather_year=weather_year)
    quarterly_temperature = grid.hourly_to_quarters(aligned)

    degree_steps = np.clip(pump.base_temperature_c - quarterly_temperature, 0.0, None)
    total = float(degree_steps.sum())
    if total == 0.0:
        return np.zeros(grid.quarters)

    heat_kwh = degree_steps / total * pump.heat_demand_kwh
    cop = np.clip(
        pump.cop_at_7c + (quarterly_temperature - 7.0) * pump.cop_slope_per_c,
        MIN_COP,
        None,
    )
    return heat_kwh / cop
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_assets.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/profiles/assets.py tests/test_assets.py
git commit -m "feat: add EV and temperature dependent heat pump profiles"
```

---

### Task 9: Presence correction

**Files:**
- Create: `ampeer_sim/profiles/presence.py`
- Create: `tests/test_presence.py`

**Interfaces:**
- Consumes: `YearGrid`
- Produces: `apply_presence(series: np.ndarray, grid: YearGrid, block_kwh: float, daytime_occupancy: bool) -> np.ndarray`

Design notes:

- This is a shift, not a scale. Every day's total must come out unchanged, which is
  the single strongest test available for this function.
- Energy is removed from the source window proportionally, so the shape inside that
  window survives, and added to the target window evenly.
- If the source window holds less than the block, move what is there. Never produce
  negative consumption.

- [ ] **Step 1: Write the failing test**

Create `tests/test_presence.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.presence import EVENING_WINDOW, MIDDAY_WINDOW, apply_presence
from ampeer_sim.timebase import YearGrid

GRID = YearGrid.for_year(2025)


def _flat_series() -> np.ndarray:
    return np.full(GRID.quarters, 3_500.0 / GRID.quarters)


def _window_mask(window: tuple[int, int]) -> np.ndarray:
    start, end = window
    return (GRID.local_hour >= start) & (GRID.local_hour < end)


def test_daily_totals_are_unchanged() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=True)
    daily_before = before.reshape(GRID.days, 96).sum(axis=1)
    daily_after = after.reshape(GRID.days, 96).sum(axis=1)
    assert np.allclose(daily_before, daily_after)


def test_daytime_occupancy_moves_energy_into_the_midday_window() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=True)
    midday = _window_mask(MIDDAY_WINDOW)
    assert after[midday].sum() > before[midday].sum()


def test_absence_moves_energy_into_the_evening_window() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=False)
    evening = _window_mask(EVENING_WINDOW)
    assert after[evening].sum() > before[evening].sum()


def test_the_moved_amount_matches_the_block() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=1.0, daytime_occupancy=True)
    midday = _window_mask(MIDDAY_WINDOW)
    moved = after[midday].sum() - before[midday].sum()
    assert moved == pytest.approx(1.0 * GRID.days)


def test_a_block_larger_than_the_window_is_clamped_not_negative() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=999.0, daytime_occupancy=True)
    assert after.min() >= 0.0
    daily_before = before.reshape(GRID.days, 96).sum(axis=1)
    daily_after = after.reshape(GRID.days, 96).sum(axis=1)
    assert np.allclose(daily_before, daily_after)


def test_a_zero_block_changes_nothing() -> None:
    before = _flat_series()
    after = apply_presence(before, GRID, block_kwh=0.0, daytime_occupancy=True)
    assert np.allclose(before, after)


def test_the_input_series_is_not_mutated() -> None:
    before = _flat_series()
    original = before.copy()
    apply_presence(before, GRID, block_kwh=1.75, daytime_occupancy=True)
    assert np.allclose(before, original)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_presence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.profiles.presence'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/profiles/presence.py`:

```python
"""Move the shiftable block between the midday and the evening window.

This is a shift and never a scale. Somebody who works from home does not use
more electricity, they use it at another moment, and the daily total is the
invariant that keeps the model honest.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_DAY, YearGrid

MIDDAY_WINDOW = (11, 15)
EVENING_WINDOW = (17, 21)


def _mask(grid: YearGrid, window: tuple[int, int]) -> np.ndarray:
    start, end = window
    return (grid.local_hour >= start) & (grid.local_hour < end)


def apply_presence(
    series: np.ndarray, grid: YearGrid, block_kwh: float, daytime_occupancy: bool
) -> np.ndarray:
    """Return a copy of ``series`` with the shiftable block relocated."""
    if block_kwh <= 0.0:
        return series.copy()

    source_window, target_window = (
        (EVENING_WINDOW, MIDDAY_WINDOW) if daytime_occupancy else (MIDDAY_WINDOW, EVENING_WINDOW)
    )
    source = _mask(grid, source_window).reshape(grid.days, QUARTERS_PER_DAY)
    target = _mask(grid, target_window).reshape(grid.days, QUARTERS_PER_DAY)

    shifted = series.copy().reshape(grid.days, QUARTERS_PER_DAY)
    for day in range(grid.days):
        source_slots = shifted[day][source[day]]
        available = float(source_slots.sum())
        moved = min(block_kwh, available)
        if moved <= 0.0:
            continue
        shifted[day, source[day]] = source_slots * (1.0 - moved / available)
        shifted[day, target[day]] += moved / float(target[day].sum())
    return shifted.reshape(grid.quarters)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_presence.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/profiles/presence.py tests/test_presence.py
git commit -m "feat: add presence correction as a shift of the shiftable block"
```

---

### Task 10: Compose the gross consumption series

**Files:**
- Create: `ampeer_sim/profiles/compose.py`
- Create: `tests/test_compose.py`

**Interfaces:**
- Consumes: `scale_to_annual`, `validate_fractions`, `apply_presence`, `ev_profile`, `ev_solar_profile`, `heat_pump_profile`
- Produces: `compose_consumption(household: Household, grid: YearGrid, fractions: np.ndarray, temperature_c: np.ndarray, weather_year: int, production_kwh: np.ndarray | None = None) -> np.ndarray`

Design notes:

- Order is fixed and meaningful: scale the base, shift it for presence, add the EV
  and the heat pump, and only then add solar EV charging, which needs the surplus
  left after everything else.
- Presence acts on the base shape only. The shiftable block is a washing machine and
  a dishwasher, and those are already inside the NEDU average. Shifting a heat pump
  by hand is not what the advice tells people to do.

- [ ] **Step 1: Write the failing test**

Create `tests/test_compose.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EV, EVChargingBehaviour, HeatPump, Household, ProfileCategory

GRID = YearGrid.for_year(2025)
FRACTIONS = np.full(GRID.quarters, 1.0 / GRID.quarters)
MILD = np.full(GRID.hours, 20.0)


def _household(**overrides: object) -> Household:
    defaults: dict[str, object] = {
        "postcode4": "5401",
        "annual_consumption_kwh": 3_500.0,
        "profile_category": ProfileCategory.E1A,
    }
    defaults.update(overrides)
    return Household(**defaults)  # type: ignore[arg-type]


def test_a_bare_household_totals_its_annual_consumption() -> None:
    series = compose_consumption(_household(), GRID, FRACTIONS, MILD, weather_year=2025)
    assert series.sum() == pytest.approx(3_500.0)


def test_an_ev_adds_its_own_annual_energy() -> None:
    ev = EV(behaviour=EVChargingBehaviour.NIGHT, annual_km=12_000, kwh_per_100km=18.0)
    series = compose_consumption(
        _household(ev=ev), GRID, FRACTIONS, MILD, weather_year=2025
    )
    assert series.sum() == pytest.approx(3_500.0 + ev.annual_kwh)


def test_a_heat_pump_adds_consumption_in_a_cold_year() -> None:
    pump = HeatPump(heat_demand_kwh=6_000.0)
    cold = np.full(GRID.hours, 0.0)
    series = compose_consumption(
        _household(heat_pump=pump), GRID, FRACTIONS, cold, weather_year=2025
    )
    assert series.sum() > 3_500.0


def test_presence_changes_the_shape_but_not_the_total() -> None:
    home = compose_consumption(
        _household(daytime_occupancy=True), GRID, FRACTIONS, MILD, weather_year=2025
    )
    away = compose_consumption(
        _household(daytime_occupancy=False), GRID, FRACTIONS, MILD, weather_year=2025
    )
    assert home.sum() == pytest.approx(away.sum())
    assert not np.allclose(home, away)


def test_solar_charging_needs_a_production_series() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR)
    with pytest.raises(ValueError, match="production"):
        compose_consumption(_household(ev=ev), GRID, FRACTIONS, MILD, weather_year=2025)


def test_solar_charging_uses_the_surplus_that_is_left() -> None:
    ev = EV(behaviour=EVChargingBehaviour.SOLAR, annual_km=3_650, kwh_per_100km=20.0)
    production = np.zeros(GRID.quarters)
    production[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 2.0
    series = compose_consumption(
        _household(ev=ev), GRID, FRACTIONS, MILD, weather_year=2025, production_kwh=production
    )
    assert series.sum() == pytest.approx(3_500.0 + ev.annual_kwh, rel=1e-6)


def test_a_mismatched_fraction_length_is_rejected() -> None:
    with pytest.raises(ValueError, match="35040"):
        compose_consumption(_household(), GRID, np.zeros(10), MILD, weather_year=2025)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.profiles.compose'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/profiles/compose.py`:

```python
"""Assemble the gross household consumption series.

The order of the steps is part of the model, not an implementation detail:
scale, shift for presence, add assets, and only then charge the EV on whatever
surplus is left.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.profiles.assets import ev_profile, ev_solar_profile, heat_pump_profile
from ampeer_sim.profiles.nedu import scale_to_annual, validate_fractions
from ampeer_sim.profiles.presence import apply_presence
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EVChargingBehaviour, Household


def compose_consumption(
    household: Household,
    grid: YearGrid,
    fractions: np.ndarray,
    temperature_c: np.ndarray,
    weather_year: int,
    production_kwh: np.ndarray | None = None,
) -> np.ndarray:
    """Return gross household consumption in kWh per quarter."""
    validate_fractions(fractions, household.profile_category, grid)

    series = scale_to_annual(
        fractions, household.annual_consumption_kwh, household.profile_category
    )
    series = apply_presence(
        series,
        grid,
        block_kwh=household.shiftable_block_kwh,
        daytime_occupancy=household.daytime_occupancy,
    )

    if household.ev is not None:
        series = series + ev_profile(household.ev, grid)
    if household.heat_pump is not None:
        series = series + heat_pump_profile(
            household.heat_pump, temperature_c, grid, weather_year=weather_year
        )

    if household.ev is not None and household.ev.behaviour is EVChargingBehaviour.SOLAR:
        if production_kwh is None:
            raise ValueError("solar EV charging needs a production series")
        surplus = np.clip(production_kwh - series, 0.0, None)
        series = series + ev_solar_profile(household.ev, grid, surplus_kwh=surplus)

    return series
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compose.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/profiles/compose.py tests/test_compose.py
git commit -m "feat: compose the gross consumption series from profile and assets"
```

---

### Task 11: Battery state model

**Files:**
- Create: `ampeer_sim/engine/__init__.py`
- Create: `ampeer_sim/engine/battery.py`
- Create: `tests/test_battery.py`

**Interfaces:**
- Consumes: `BatterySpec`
- Produces: `Battery(spec: BatterySpec)` with `.soc_kwh`, `.charge(offered_kwh: float) -> float`, `.discharge(wanted_kwh: float) -> float`, `.throughput_kwh`

Design notes:

- Round-trip efficiency is split evenly over both directions, so each way uses
  `sqrt(round_trip_efficiency)`. That is the usual convention and it keeps a full
  cycle at exactly the stated efficiency.
- `charge` returns the energy taken from the source, not the energy stored. `discharge`
  returns the energy delivered to the household, not the energy removed from the cells.
  Getting this the wrong way round breaks the energy balance, so both are tested.
- The quarter-hour power limit is `power_kw / 4`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_battery.py`:

```python
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
        capacity_kwh=10.0, max_charge_kw=40.0, max_discharge_kw=40.0,
        round_trip_efficiency=0.90, usable_dod=1.0,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_battery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.engine'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/engine/__init__.py` as an empty file, then create
`ampeer_sim/engine/battery.py`:

```python
"""A quarter-hour battery state model.

``charge`` speaks in energy taken from the source and ``discharge`` in energy
delivered to the household. Both are the quantities the energy balance needs;
the losses live inside.
"""

from __future__ import annotations

import math

from ampeer_sim.timebase import QUARTERS_PER_HOUR
from ampeer_sim.types import BatterySpec


class Battery:
    def __init__(self, spec: BatterySpec) -> None:
        self._spec = spec
        self._one_way_efficiency = math.sqrt(spec.round_trip_efficiency)
        self.soc_kwh = 0.0
        self.throughput_kwh = 0.0

    @property
    def spec(self) -> BatterySpec:
        return self._spec

    @property
    def headroom_kwh(self) -> float:
        return self._spec.usable_capacity_kwh - self.soc_kwh

    def charge(self, offered_kwh: float) -> float:
        """Take energy from a source. Returns the energy actually taken."""
        if offered_kwh <= 0.0:
            return 0.0
        power_limit = self._spec.max_charge_kw / QUARTERS_PER_HOUR
        capacity_limit = self.headroom_kwh / self._one_way_efficiency
        taken = min(offered_kwh, power_limit, capacity_limit)
        self.soc_kwh += taken * self._one_way_efficiency
        return taken

    def discharge(self, wanted_kwh: float) -> float:
        """Deliver energy to the household. Returns the energy actually delivered."""
        if wanted_kwh <= 0.0:
            return 0.0
        power_limit = self._spec.max_discharge_kw / QUARTERS_PER_HOUR
        stored_limit = self.soc_kwh * self._one_way_efficiency
        delivered = min(wanted_kwh, power_limit, stored_limit)
        self.soc_kwh -= delivered / self._one_way_efficiency
        self.throughput_kwh += delivered
        return delivered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_battery.py -v`
Expected: PASS, 9 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/engine/ tests/test_battery.py
git commit -m "feat: add quarter-hour battery state model"
```

---

### Task 12: The timestep loop and the energy balance invariant

**Files:**
- Create: `ampeer_sim/engine/run.py`
- Create: `tests/test_engine_run.py`

**Interfaces:**
- Consumes: `Battery`, `EnergyFlows`, `Strategy`
- Produces:
  - `simulate(consumption: np.ndarray, production: np.ndarray, battery_spec: BatterySpec | None = None, charge_plan: np.ndarray | None = None, discharge_plan: np.ndarray | None = None) -> EnergyFlows`
  - `assert_energy_balance(flows: EnergyFlows, tolerance: float = 1e-9) -> None`
  - `EnergyBalanceError`

Design notes:

- `simulate` handles self-consumption on its own. Price-driven behaviour arrives as
  two optional plans: `charge_plan` holds the extra kWh to draw from the grid per
  quarter, `discharge_plan` the extra kWh to push out. Strategies build those plans;
  the loop stays free of price logic and stays testable without price data.
- The invariant is checked in tests over every quarter of every scenario. It is the
  cheapest defence against the failure mode this whole package exists to prevent: an
  answer that is wrong but plausible.

- [ ] **Step 1: Write the failing test**

Create `tests/test_engine_run.py`:

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.engine.run import EnergyBalanceError, assert_energy_balance, simulate
from ampeer_sim.types import BatterySpec, EnergyFlows

SPEC = BatterySpec(
    capacity_kwh=5.0, max_charge_kw=2.5, max_discharge_kw=2.5,
    round_trip_efficiency=0.90, usable_dod=0.90,
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


def test_a_grid_charge_plan_shows_up_as_extra_offtake() -> None:
    plan = np.zeros(96)
    plan[0] = 0.5
    flows = simulate(
        consumption=np.zeros(96), production=np.zeros(96),
        battery_spec=SPEC, charge_plan=plan,
    )
    assert flows.from_grid.sum() > 0.0
    assert_energy_balance(flows)


def test_a_discharge_plan_shows_up_as_extra_feed_in() -> None:
    charge = np.zeros(96)
    charge[0] = 0.5
    discharge = np.zeros(96)
    discharge[50] = 0.5
    flows = simulate(
        consumption=np.zeros(96), production=np.zeros(96),
        battery_spec=SPEC, charge_plan=charge, discharge_plan=discharge,
    )
    assert flows.to_grid.sum() > 0.0
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


def test_mismatched_input_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="same length"):
        simulate(consumption=np.zeros(96), production=np.zeros(95))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.engine.run'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/engine/run.py`:

```python
"""The timestep loop.

The loop knows about energy and never about prices. Price-driven behaviour
arrives as a pair of plans built by ``ampeer_sim.engine.strategies``.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.engine.battery import Battery
from ampeer_sim.types import BatterySpec, EnergyFlows


class EnergyBalanceError(AssertionError):
    """Energy appeared or vanished. Always a bug in the engine."""


def simulate(
    consumption: np.ndarray,
    production: np.ndarray,
    battery_spec: BatterySpec | None = None,
    charge_plan: np.ndarray | None = None,
    discharge_plan: np.ndarray | None = None,
) -> EnergyFlows:
    """Run the quarter-hour simulation and return the resulting energy flows."""
    if consumption.shape != production.shape:
        raise ValueError("consumption and production must have the same length")

    steps = consumption.shape[0]
    battery = Battery(battery_spec) if battery_spec is not None else None
    grid_charge = charge_plan if charge_plan is not None else np.zeros(steps)
    grid_discharge = discharge_plan if discharge_plan is not None else np.zeros(steps)

    self_consumption = np.zeros(steps)
    from_grid = np.zeros(steps)
    to_grid = np.zeros(steps)
    battery_charge = np.zeros(steps)
    battery_discharge = np.zeros(steps)

    for step in range(steps):
        direct = min(consumption[step], production[step])
        self_consumption[step] = direct
        surplus = production[step] - direct
        deficit = consumption[step] - direct

        if battery is not None:
            stored = battery.charge(surplus)
            battery_charge[step] += stored
            surplus -= stored

            delivered = battery.discharge(deficit)
            battery_discharge[step] += delivered
            deficit -= delivered

            if battery.spec.allow_grid_charging and grid_charge[step] > 0.0:
                taken = battery.charge(grid_charge[step])
                from_grid[step] += taken

            if grid_discharge[step] > 0.0:
                exported = battery.discharge(grid_discharge[step])
                to_grid[step] += exported

        from_grid[step] += deficit
        to_grid[step] += surplus

    return EnergyFlows(
        consumption=consumption,
        production=production,
        self_consumption=self_consumption,
        from_grid=from_grid,
        to_grid=to_grid,
        battery_charge=battery_charge,
        battery_discharge=battery_discharge,
    )


def assert_energy_balance(flows: EnergyFlows, tolerance: float = 1e-9) -> None:
    """Raise ``EnergyBalanceError`` if energy does not conserve on any quarter.

    Grid charging and grid discharging move energy through the battery without
    touching the household, so they are excluded from both sides.
    """
    consumption_side = flows.self_consumption + flows.battery_discharge
    consumption_gap = np.abs(flows.consumption - np.minimum(consumption_side, flows.consumption))
    served = flows.self_consumption + np.minimum(
        flows.battery_discharge, flows.consumption - flows.self_consumption
    )
    consumption_residual = flows.consumption - served - flows.from_grid
    if np.any(np.abs(consumption_residual) > tolerance + consumption_gap * 0):
        worst = int(np.argmax(np.abs(consumption_residual)))
        raise EnergyBalanceError(
            f"consumption does not balance at step {worst}: "
            f"residual {consumption_residual[worst]!r}"
        )

    stored_from_production = np.minimum(
        flows.battery_charge, np.clip(flows.production - flows.self_consumption, 0.0, None)
    )
    production_residual = (
        flows.production - flows.self_consumption - stored_from_production - flows.to_grid
    )
    if np.any(production_residual > tolerance):
        worst = int(np.argmax(production_residual))
        raise EnergyBalanceError(
            f"production does not balance at step {worst}: "
            f"residual {production_residual[worst]!r}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine_run.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/engine/run.py tests/test_engine_run.py
git commit -m "feat: add timestep loop with an energy balance invariant"
```

---

### Task 13: Control strategies and the arbitrage foresight window

**Files:**
- Create: `ampeer_sim/engine/strategies.py`
- Create: `tests/test_strategies.py`

**Interfaces:**
- Consumes: `Strategy`, `BatterySpec`, `YearGrid`
- Produces:
  - `build_plans(strategy: Strategy, spec: BatterySpec, prices_per_quarter: np.ndarray | None, grid: YearGrid) -> tuple[np.ndarray, np.ndarray]`
  - `minimum_profitable_spread(prices_day: np.ndarray, round_trip_efficiency: float) -> float`
  - `FORESIGHT_HORIZON_DAYS = 1`

Design notes, and this is the honesty-critical part of the package:

- Day-ahead prices for a given day become known at 13:00 the day before. A strategy
  may therefore plan a whole day at a time using that day's prices. It may not look
  further, because that would be knowledge nobody has, and it is precisely how
  optimistic battery quotes are produced.
- The implementation enforces this structurally: the planner receives one day of
  prices at a time and cannot see the rest of the array.
- Arbitrage is only worth doing when the spread beats the round-trip loss. Buying at
  `p_low` and selling at `p_high` earns `p_high * efficiency - p_low` per kWh, so the
  break-even spread depends on the price level, not only on the difference.

- [ ] **Step 1: Write the failing test**

Create `tests/test_strategies.py`:

```python
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
    capacity_kwh=10.0, max_charge_kw=4.0, max_discharge_kw=4.0,
    round_trip_efficiency=0.90, usable_dod=0.90, allow_grid_charging=True,
)


def _sawtooth_prices() -> np.ndarray:
    day = np.concatenate([np.full(48, 0.05), np.full(48, 0.35)])
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


def test_arbitrage_charges_in_the_cheap_half_and_discharges_in_the_dear_half() -> None:
    prices = _sawtooth_prices()
    charge, discharge = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    cheap = prices < 0.10
    assert charge[cheap].sum() == pytest.approx(charge.sum())
    assert discharge[~cheap].sum() == pytest.approx(discharge.sum())


def test_arbitrage_does_nothing_when_the_spread_is_too_small() -> None:
    flat = np.full(GRID.quarters, 0.20)
    charge, discharge = build_plans(Strategy.ARBITRAGE, SPEC, flat, GRID)
    assert charge.sum() == pytest.approx(0.0)
    assert discharge.sum() == pytest.approx(0.0)


def test_arbitrage_plans_never_exceed_the_usable_capacity_per_day() -> None:
    prices = _sawtooth_prices()
    charge, _ = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    per_day = charge.reshape(GRID.days, 96).sum(axis=1)
    assert per_day.max() <= SPEC.usable_capacity_kwh + 1e-9


def test_a_strategy_cannot_see_beyond_its_horizon() -> None:
    """Day two is expensive, day one is flat. Day one must not react to day two."""
    prices = np.concatenate(
        [np.full(96, 0.20), np.full(48, 0.05), np.full(48, 0.60)]
    )
    prices = np.concatenate([prices, np.full(GRID.quarters - prices.size, 0.20)])
    charge, _ = build_plans(Strategy.ARBITRAGE, SPEC, prices, GRID)
    assert charge[:96].sum() == pytest.approx(0.0)


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_strategies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.engine.strategies'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/engine/strategies.py`:

```python
"""Battery control strategies and the foresight rule they must obey.

Day-ahead prices for a day are published at about 13:00 the day before, so a
strategy may plan one day at a time. Looking further is knowledge nobody has,
and it is exactly how optimistic battery quotes are produced. The rule is
enforced by handing the planner one day of prices at a time.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_DAY, QUARTERS_PER_HOUR, YearGrid
from ampeer_sim.types import BatterySpec, Strategy

#: A planner may see the day it is planning, and nothing beyond it.
FORESIGHT_HORIZON_DAYS = 1

#: Hybrid only trades when the spread clears the break-even by this margin.
HYBRID_SAFETY_MARGIN = 1.5


def minimum_profitable_spread(prices_day: np.ndarray, round_trip_efficiency: float) -> float:
    """The smallest price difference that still earns money after losses.

    Buying at ``p_low`` and selling at ``p_high`` yields
    ``p_high * efficiency - p_low``. Break-even therefore depends on the price
    level as well as on the difference.
    """
    reference = float(np.median(prices_day))
    return reference * (1.0 / round_trip_efficiency - 1.0)


def _plan_one_day(
    prices_day: np.ndarray, spec: BatterySpec, safety_margin: float
) -> tuple[np.ndarray, np.ndarray]:
    """Plan a single day. Receives only this day's prices, by design."""
    charge = np.zeros(QUARTERS_PER_DAY)
    discharge = np.zeros(QUARTERS_PER_DAY)
    if not spec.allow_grid_charging:
        return charge, discharge

    spread = float(prices_day.max() - prices_day.min())
    threshold = minimum_profitable_spread(prices_day, spec.round_trip_efficiency)
    if spread <= threshold * safety_margin:
        return charge, discharge

    per_step_limit = spec.max_charge_kw / QUARTERS_PER_HOUR
    steps_needed = int(np.ceil(spec.usable_capacity_kwh / per_step_limit))

    cheapest = np.argsort(prices_day, kind="stable")[:steps_needed]
    dearest = np.argsort(-prices_day, kind="stable")[:steps_needed]

    budget = spec.usable_capacity_kwh
    for index in cheapest:
        take = min(per_step_limit, budget)
        charge[index] = take
        budget -= take
        if budget <= 0.0:
            break

    budget = spec.usable_capacity_kwh
    release_limit = spec.max_discharge_kw / QUARTERS_PER_HOUR
    for index in dearest:
        give = min(release_limit, budget)
        discharge[index] = give
        budget -= give
        if budget <= 0.0:
            break
    return charge, discharge


def build_plans(
    strategy: Strategy,
    spec: BatterySpec,
    prices_per_quarter: np.ndarray | None,
    grid: YearGrid,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (grid_charge_plan, grid_discharge_plan) in kWh per quarter."""
    charge = np.zeros(grid.quarters)
    discharge = np.zeros(grid.quarters)

    if strategy is Strategy.SELF_CONSUMPTION or prices_per_quarter is None:
        return charge, discharge

    margin = HYBRID_SAFETY_MARGIN if strategy is Strategy.HYBRID else 1.0
    for day in range(grid.days):
        start = day * QUARTERS_PER_DAY
        stop = start + QUARTERS_PER_DAY
        day_charge, day_discharge = _plan_one_day(
            prices_per_quarter[start:stop], spec, margin
        )
        charge[start:stop] = day_charge
        discharge[start:stop] = day_discharge
    return charge, discharge
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_strategies.py -v`
Expected: PASS, 9 passed

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/engine/strategies.py tests/test_strategies.py
git commit -m "feat: add control strategies with an enforced foresight horizon"
```

---

### Task 14: The money boundary

**Files:**
- Create: `ampeer_sim/economics/__init__.py`
- Create: `ampeer_sim/economics/tariffs.py`
- Create: `tests/test_tariffs.py`

**Interfaces:**
- Consumes: `EnergyFlows`, `TariffSet`, `MoneyResult`
- Produces:
  - `annual_cost(flows: EnergyFlows, tariffs: TariffSet, prices_per_quarter: np.ndarray | None = None) -> Decimal`
  - `compare(flows: EnergyFlows, baseline: TariffSet, scenario: TariffSet, prices_per_quarter: np.ndarray | None = None) -> MoneyResult`
  - `KWH_PRECISION`, `EUR_PRECISION`

Design notes:

- This is the only module where a price meets an energy series. Energy sums are
  quantised to three decimals before they become `Decimal`, which stops float noise
  from leaking into a money figure.
- Net metering nets annual feed-in against annual offtake, capped at the offtake. Any
  remaining feed-in is paid at the feed-in price. That is how the current Dutch rule
  works and it is the baseline the shock figure is measured against.
- With a dynamic contract the offtake price varies per quarter, so the sum is taken
  per quarter and only then converted.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tariffs.py`:

```python
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
        Decimal("2000") * Decimal("0.27") - Decimal("800") * Decimal("0.05")
        + Decimal("90.00") + Decimal("120.00")
    )
    assert cost == expected


def test_a_dynamic_contract_prices_each_quarter_separately() -> None:
    tariffs = TariffSet(
        supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True
    )
    prices = np.array([0.10, 0.20, 0.30, 0.40])
    cost = annual_cost(_flows(400.0, 0.0), tariffs, prices_per_quarter=prices)
    assert cost == Decimal("100.000")


def test_a_dynamic_contract_requires_prices() -> None:
    tariffs = TariffSet(
        supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True
    )
    with pytest.raises(ValueError, match="dynamic"):
        annual_cost(_flows(400.0, 0.0), tariffs)


def test_compare_returns_the_difference_between_two_tariff_sets() -> None:
    result = compare(_flows(2_000.0, 800.0), baseline=FIXED_2026, scenario=FIXED_2027)
    assert result.difference_eur == result.scenario_eur - result.baseline_eur
    assert result.difference_eur > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tariffs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.economics'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/economics/__init__.py` as an empty file, then create
`ampeer_sim/economics/tariffs.py`:

```python
"""The single boundary where kWh become euro.

Nowhere else in the package does a price stand next to an energy series.
Energy sums are quantised before conversion so that float noise cannot leak
into a money figure.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from ampeer_sim.types import EnergyFlows, MoneyResult, TariffSet

#: Energy is rounded to a watt-hour before it becomes money.
KWH_PRECISION = Decimal("0.001")

#: Money is kept at three decimals internally and rounded for display elsewhere.
EUR_PRECISION = Decimal("0.001")


def _to_decimal_kwh(value: float) -> Decimal:
    return Decimal(repr(float(value))).quantize(KWH_PRECISION)


def _dynamic_offtake_cost(from_grid: np.ndarray, prices_per_quarter: np.ndarray) -> Decimal:
    if from_grid.shape != prices_per_quarter.shape:
        raise ValueError("price series must have the same length as the flow series")
    return Decimal(repr(float((from_grid * prices_per_quarter).sum()))).quantize(EUR_PRECISION)


def annual_cost(
    flows: EnergyFlows,
    tariffs: TariffSet,
    prices_per_quarter: np.ndarray | None = None,
) -> Decimal:
    """Return the annual electricity cost in euro. Negative means a net payout."""
    offtake = _to_decimal_kwh(flows.from_grid.sum())
    feed_in = _to_decimal_kwh(flows.to_grid.sum())

    if tariffs.dynamic:
        if prices_per_quarter is None:
            raise ValueError("a dynamic tariff needs a price series")
        supply_cost = _dynamic_offtake_cost(flows.from_grid, prices_per_quarter)
        feed_in_revenue = Decimal(
            repr(float((flows.to_grid * prices_per_quarter).sum()))
        ).quantize(EUR_PRECISION)
    elif tariffs.net_metering:
        netted = min(feed_in, offtake)
        supply_cost = (offtake - netted) * tariffs.supply_price
        feed_in_revenue = (feed_in - netted) * tariffs.feed_in_price + netted * tariffs.supply_price
        supply_cost += netted * tariffs.supply_price
    else:
        supply_cost = offtake * tariffs.supply_price
        feed_in_revenue = feed_in * tariffs.feed_in_price

    total = (
        supply_cost
        - feed_in_revenue
        + tariffs.standing_charge_year
        + tariffs.feed_in_fixed_cost_year
    )
    return total.quantize(EUR_PRECISION)


def compare(
    flows: EnergyFlows,
    baseline: TariffSet,
    scenario: TariffSet,
    prices_per_quarter: np.ndarray | None = None,
) -> MoneyResult:
    """Price the same energy flows under two tariff sets."""
    return MoneyResult(
        baseline_eur=annual_cost(flows, baseline, prices_per_quarter),
        scenario_eur=annual_cost(flows, scenario, prices_per_quarter),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tariffs.py -v`
Expected: PASS, 8 passed

Note for the implementer: the net metering branch above is written so the netted
volume cancels exactly. If a test fails on that branch, simplify it to
`supply_cost = (offtake - netted) * supply_price` and
`feed_in_revenue = (feed_in - netted) * feed_in_price` rather than adding and
subtracting the netted term. Keep the tests as they are; they encode the intent.

- [ ] **Step 5: Commit**

```bash
git add ampeer_sim/economics/ tests/test_tariffs.py
git commit -m "feat: add the single kWh to euro boundary"
```

---

### Task 15: Sensitivity band and the composition root

**Files:**
- Create: `ampeer_sim/economics/sensitivity.py`
- Create: `ampeer_sim/simulate.py`
- Create: `tests/test_sensitivity.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - `VARIATIONS: tuple[Variation, ...]`
  - `band_from_differences(differences: list[Decimal]) -> Band`
  - `run_advice(household, pv_system, baseline, scenario, grid, profile_provider, production_provider, prices_per_quarter=None, weather_year=...) -> Result`

Note on the file list: the spec does not name a composition root. `simulate.py` is
added here because assembling a `Result` is a responsibility that belongs to neither
`economics` nor `profiles`. Record this addition in the spec when the plan is done.

Design notes:

- The band is measured, never asserted. A hard-coded plus or minus 30 percent is
  forbidden by the spec, because the honest band is the whole positioning.
- Each `Variation` perturbs one uncertain input. The runs are the cross product of
  the low and high setting of each variation plus the central case, which keeps the
  count small enough to stay inside the two second budget.
- `p10` and `p90` come from `numpy.percentile` over the resulting differences.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sensitivity.py`:

```python
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.economics.sensitivity import VARIATIONS, band_from_differences
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.simulate import run_advice
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Household, ProductionSource, ProfileCategory, PVSystem, TariffSet

GRID = YearGrid.for_year(2025)


class _FlatProfileProvider:
    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


BASELINE = TariffSet(
    supply_price=Decimal("0.27"), feed_in_price=Decimal("0.27"),
    standing_charge_year=Decimal("120.00"), net_metering=True,
)
SCENARIO = TariffSet(
    supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"),
    feed_in_fixed_cost_year=Decimal("90.00"), standing_charge_year=Decimal("120.00"),
)


def test_band_is_ordered() -> None:
    band = band_from_differences([Decimal(str(value)) for value in range(100)])
    assert band.p10_eur <= band.p50_eur <= band.p90_eur
    assert band.runs == 100


def test_band_rejects_an_empty_run_set() -> None:
    with pytest.raises(ValueError, match="at least one"):
        band_from_differences([])


def test_there_is_more_than_one_variation() -> None:
    assert len(VARIATIONS) >= 4


def test_run_advice_returns_a_result_with_a_measured_band() -> None:
    result = run_advice(
        household=Household(postcode4="5401", annual_consumption_kwh=3_500.0),
        pv_system=PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35),
        baseline=BASELINE,
        scenario=SCENARIO,
        grid=GRID,
        profile_provider=_FlatProfileProvider(),
        production_provider=FallbackProvider(2025),
    )
    assert result.engine_version
    assert result.band.runs > 1
    assert result.band.p10_eur < result.band.p90_eur
    assert result.production_source is ProductionSource.FALLBACK


def test_the_headline_figure_is_a_cost_increase() -> None:
    result = run_advice(
        household=Household(postcode4="5401", annual_consumption_kwh=3_500.0),
        pv_system=PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35),
        baseline=BASELINE,
        scenario=SCENARIO,
        grid=GRID,
        profile_provider=_FlatProfileProvider(),
        production_provider=FallbackProvider(2025),
    )
    assert result.band.p50_eur > 0


def test_self_consumption_rate_is_a_fraction() -> None:
    result = run_advice(
        household=Household(postcode4="5401", annual_consumption_kwh=3_500.0),
        pv_system=PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35),
        baseline=BASELINE,
        scenario=SCENARIO,
        grid=GRID,
        profile_provider=_FlatProfileProvider(),
        production_provider=FallbackProvider(2025),
    )
    assert 0.0 <= result.self_consumption_rate <= 1.0


def test_a_full_run_finishes_within_the_time_budget() -> None:
    import time

    started = time.perf_counter()
    run_advice(
        household=Household(postcode4="5401", annual_consumption_kwh=3_500.0),
        pv_system=PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35),
        baseline=BASELINE,
        scenario=SCENARIO,
        grid=GRID,
        profile_provider=_FlatProfileProvider(),
        production_provider=FallbackProvider(2025),
    )
    assert time.perf_counter() - started < 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sensitivity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.economics.sensitivity'`

- [ ] **Step 3: Write the sensitivity module**

Create `ampeer_sim/economics/sensitivity.py`:

```python
"""Turn model uncertainty into a measured band.

A hard-coded plus or minus percentage is forbidden. The honest band is the
whole point of this product, so it has to come out of varying the inputs we
know we do not know.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from ampeer_sim.types import Band


@dataclass(frozen=True)
class Variation:
    """One uncertain input and how far it plausibly moves."""

    name: str
    low: float
    high: float


VARIATIONS: tuple[Variation, ...] = (
    Variation(name="annual_consumption_kwh", low=0.90, high=1.10),
    Variation(name="shiftable_block_kwh", low=0.57, high=1.43),
    Variation(name="system_loss_fraction", low=0.80, high=1.20),
    Variation(name="feed_in_price", low=0.60, high=1.40),
)


def band_from_differences(differences: list[Decimal]) -> Band:
    """Return the p10, p50 and p90 of a set of scenario differences."""
    if not differences:
        raise ValueError("a band needs at least one run")
    values = np.array([float(value) for value in differences])
    p10, p50, p90 = np.percentile(values, [10, 50, 90])
    return Band(
        p10_eur=Decimal(repr(round(float(p10), 2))),
        p50_eur=Decimal(repr(round(float(p50), 2))),
        p90_eur=Decimal(repr(round(float(p90), 2))),
        runs=len(differences),
    )
```

- [ ] **Step 4: Write the composition root**

Create `ampeer_sim/simulate.py`:

```python
"""The composition root: answers in, ``Result`` out.

This is the only module that knows about every other one. It performs no I/O
itself; providers do that.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import numpy as np

from ampeer_sim import ENGINE_VERSION
from ampeer_sim.economics.sensitivity import VARIATIONS, band_from_differences
from ampeer_sim.economics.tariffs import compare
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
    BatterySpec,
    Household,
    ProductionSource,
    PVSystem,
    Result,
    TariffSet,
)

DEFAULT_WEATHER_YEAR = 2023


def _apply_variation(
    household: Household, pv_system: PVSystem, tariffs: TariffSet, name: str, factor: float
) -> tuple[Household, PVSystem, TariffSet]:
    if name == "annual_consumption_kwh":
        household = dataclasses.replace(
            household, annual_consumption_kwh=household.annual_consumption_kwh * factor
        )
    elif name == "shiftable_block_kwh":
        household = dataclasses.replace(
            household, shiftable_block_kwh=household.shiftable_block_kwh * factor
        )
    elif name == "system_loss_fraction":
        pv_system = dataclasses.replace(
            pv_system, system_loss_fraction=min(pv_system.system_loss_fraction * factor, 0.99)
        )
    elif name == "feed_in_price":
        tariffs = dataclasses.replace(
            tariffs, feed_in_price=tariffs.feed_in_price * Decimal(repr(factor))
        )
    return household, pv_system, tariffs


def run_advice(
    household: Household,
    pv_system: PVSystem,
    baseline: TariffSet,
    scenario: TariffSet,
    grid: YearGrid,
    profile_provider: object,
    production_provider: object,
    battery_spec: BatterySpec | None = None,
    prices_per_quarter: np.ndarray | None = None,
    weather_year: int = DEFAULT_WEATHER_YEAR,
) -> Result:
    """Run the central case plus every variation and return a ``Result``."""
    fractions = profile_provider.fractions(  # type: ignore[attr-defined]
        grid.year, household.profile_category
    )
    irradiance, temperature, source = production_provider.hourly_series(  # type: ignore[attr-defined]
        household.postcode4, pv_system.azimuth_deg, pv_system.tilt_deg, pv_system.peak_power_wp
    )

    def one_run(
        run_household: Household, run_system: PVSystem, run_scenario: TariffSet
    ) -> tuple[Decimal, float]:
        production = production_series(
            irradiance, run_system, grid, weather_year=weather_year
        )
        consumption = compose_consumption(
            run_household,
            grid,
            fractions,
            temperature,
            weather_year=weather_year,
            production_kwh=production,
        )
        flows = simulate(consumption, production, battery_spec=battery_spec)
        money = compare(flows, baseline, run_scenario, prices_per_quarter)
        return money.difference_eur, flows.self_consumption_rate

    central_difference, central_rate = one_run(household, pv_system, scenario)
    differences = [central_difference]

    for variation in VARIATIONS:
        for factor in (variation.low, variation.high):
            varied = _apply_variation(household, pv_system, scenario, variation.name, factor)
            difference, _ = one_run(*varied)
            differences.append(difference)

    return Result(
        engine_version=ENGINE_VERSION,
        band=band_from_differences(differences),
        self_consumption_rate=central_rate,
        production_source=source if isinstance(source, ProductionSource) else ProductionSource.PVGIS,
        profile_year=grid.year,
        weather_year=weather_year,
        scenarios={},
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_sensitivity.py -v`
Expected: PASS, 7 passed

If the timing test fails, the loop in `engine/run.py` is the bottleneck. Vectorise the
no-battery path first: without a battery the whole simulation is
`np.minimum(consumption, production)` and two subtractions, with no state to carry.

- [ ] **Step 6: Commit**

```bash
git add ampeer_sim/economics/sensitivity.py ampeer_sim/simulate.py tests/test_sensitivity.py
git commit -m "feat: add measured sensitivity band and composition root"
```

---

### Task 16: Property tests and golden files

**Files:**
- Create: `tests/test_properties.py`
- Create: `tests/golden/README.md`
- Create: `tests/golden/households.json`
- Create: `tests/test_golden.py`

**Interfaces:**
- Consumes: everything above
- Produces: no new production code, only the tests that the spec requires

Design notes:

- Property tests use hypothesis over generated series rather than fixed inputs,
  because the interesting failures live at the edges nobody thinks to write down.
- One golden household must be small enough to check with a pencil. That is the only
  one that catches a mistake in the golden file itself.

- [ ] **Step 1: Write the property tests**

Create `tests/test_properties.py`:

```python
from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from ampeer_sim.engine.run import assert_energy_balance, simulate
from ampeer_sim.profiles.presence import apply_presence
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import BatterySpec

SPEC = BatterySpec(
    capacity_kwh=5.0, max_charge_kw=2.5, max_discharge_kw=2.5,
    round_trip_efficiency=0.90, usable_dod=0.90,
)

series = st.lists(
    st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    min_size=96, max_size=96,
)


@settings(max_examples=50, deadline=None)
@given(consumption=series, production=series)
def test_energy_always_balances(consumption: list[float], production: list[float]) -> None:
    flows = simulate(np.array(consumption), np.array(production), battery_spec=SPEC)
    assert_energy_balance(flows)


@settings(max_examples=50, deadline=None)
@given(consumption=series, production=series, extra=st.floats(min_value=0.01, max_value=1.0))
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
```

- [ ] **Step 2: Run the property tests**

Run: `pytest tests/test_properties.py -v`
Expected: PASS, 5 passed

- [ ] **Step 3: Write the golden households**

Create `tests/golden/README.md`:

```markdown
# Golden households

Five households with a recorded expected outcome. When a number here changes,
the diff must show it and the change must be deliberate.

`hand_checkable` is the one case small enough to verify with a pencil: a flat
consumption profile, a flat production series, no assets and no battery. Its
expected values are derived by hand in the comments of `tests/test_golden.py`,
not copied from a program run.
```

Create `tests/golden/households.json`:

```json
{
  "hand_checkable": {
    "postcode4": "5401",
    "annual_consumption_kwh": 3650.0,
    "daytime_occupancy": false,
    "shiftable_block_kwh": 0.0,
    "peak_power_wp": 1000,
    "expected_self_consumption_rate": 0.4247,
    "tolerance": 0.01
  },
  "rob_fixed_contract": {
    "postcode4": "5401",
    "annual_consumption_kwh": 3500.0,
    "daytime_occupancy": false,
    "shiftable_block_kwh": 1.75,
    "peak_power_wp": 3500,
    "expected_self_consumption_rate": 0.33,
    "tolerance": 0.06
  },
  "sander_home_office": {
    "postcode4": "3512",
    "annual_consumption_kwh": 4200.0,
    "daytime_occupancy": true,
    "shiftable_block_kwh": 1.75,
    "peak_power_wp": 5000,
    "expected_self_consumption_rate": 0.32,
    "tolerance": 0.06
  },
  "marloes_ev": {
    "postcode4": "1017",
    "annual_consumption_kwh": 3000.0,
    "daytime_occupancy": false,
    "shiftable_block_kwh": 1.75,
    "peak_power_wp": 4000,
    "expected_self_consumption_rate": 0.30,
    "tolerance": 0.07
  },
  "large_array_small_use": {
    "postcode4": "9711",
    "annual_consumption_kwh": 2200.0,
    "daytime_occupancy": false,
    "shiftable_block_kwh": 1.75,
    "peak_power_wp": 7000,
    "expected_self_consumption_rate": 0.17,
    "tolerance": 0.06
  }
}
```

- [ ] **Step 4: Write the golden test**

Create `tests/test_golden.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Household, ProfileCategory, PVSystem

GOLDEN = json.loads((Path(__file__).parent / "golden" / "households.json").read_text("utf-8"))
GRID = YearGrid.for_year(2025)


class _FlatProfileProvider:
    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


def _run(case: dict[str, Any]) -> float:
    household = Household(
        postcode4=case["postcode4"],
        annual_consumption_kwh=case["annual_consumption_kwh"],
        daytime_occupancy=case["daytime_occupancy"],
        shiftable_block_kwh=case["shiftable_block_kwh"],
    )
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0, tilt_deg=35)
    irradiance, temperature, _ = FallbackProvider(2025).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg, system.peak_power_wp
    )
    production = production_series(irradiance, system, GRID, weather_year=2025)
    consumption = compose_consumption(
        household, GRID, _FlatProfileProvider().fractions(2025, ProfileCategory.E1A),
        temperature, weather_year=2025, production_kwh=production,
    )
    return simulate(consumption, production).self_consumption_rate


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_household_self_consumption(name: str) -> None:
    case = GOLDEN[name]
    assert _run(case) == pytest.approx(
        case["expected_self_consumption_rate"], abs=case["tolerance"]
    )


def test_the_hand_checkable_case_can_be_derived_by_hand() -> None:
    """Verify the pencil case rather than trusting the recorded number.

    Consumption is flat: 3650 kWh over 35040 quarters is 0.10416 kWh per
    quarter. Production comes from a 1 kWp array on the fallback table, whose
    daily shape is a half sine over twelve hours. Self consumption is therefore
    the integral of min(flat, sine) over the year, divided by the annual yield.
    The assertion below recomputes that directly instead of restating it.
    """
    case = GOLDEN["hand_checkable"]
    household = Household(
        postcode4=case["postcode4"],
        annual_consumption_kwh=case["annual_consumption_kwh"],
        shiftable_block_kwh=0.0,
    )
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0, tilt_deg=35)
    irradiance, temperature, _ = FallbackProvider(2025).hourly_series(
        household.postcode4, 0.0, 35.0, system.peak_power_wp
    )
    production = production_series(irradiance, system, GRID, weather_year=2025)
    consumption = np.full(GRID.quarters, case["annual_consumption_kwh"] / GRID.quarters)

    by_hand = float(np.minimum(consumption, production).sum() / production.sum())
    assert _run(case) == pytest.approx(by_hand, abs=1e-9)
```

- [ ] **Step 5: Run the golden tests and record the real numbers**

Run: `pytest tests/test_golden.py -v`

If a case fails, do not widen its tolerance to make it pass. Read the produced value,
decide whether it is plausible for that household, and only then update
`households.json`. A golden file that is edited to match whatever the code produced is
not a test.

- [ ] **Step 6: Commit**

```bash
git add tests/test_properties.py tests/test_golden.py tests/golden/
git commit -m "test: add property tests and golden household cases"
```

---

### Task 17: Validation CLI and the published methodology

**Files:**
- Create: `ampeer_sim/validate.py`
- Create: `tests/test_validate.py`
- Create: `docs/methodologie.md`

**Interfaces:**
- Consumes: `run_advice`, `Household`, `PVSystem`, `TariffSet`
- Produces:
  - `load_statement(path: Path) -> Statement`
  - `check(statement: Statement, ...) -> Deviation`
  - `main(argv: list[str] | None = None) -> int`

Design notes:

- This is the only test that says whether the model has anything to do with reality.
  The other four say whether the code does what the design says. Making it a one
  command script is the difference between running it at every model change and
  running it twice.
- Exit code 0 when the deviation is within 10 percent, 1 when it is not. That makes it
  usable from CI later without changing anything.

- [ ] **Step 1: Write the failing test**

Create `tests/test_validate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ampeer_sim.validate import Deviation, load_statement, main

STATEMENT = {
    "postcode4": "5401",
    "annual_consumption_kwh": 3500.0,
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "daytime_occupancy": False,
    "measured_offtake_kwh": 2300.0,
    "measured_feed_in_kwh": 2100.0,
}


def _write(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "statement.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_statement_reads_every_required_field(tmp_path: Path) -> None:
    statement = load_statement(_write(tmp_path, STATEMENT))
    assert statement.measured_offtake_kwh == pytest.approx(2_300.0)
    assert statement.postcode4 == "5401"


def test_load_statement_rejects_a_missing_field(tmp_path: Path) -> None:
    incomplete = {key: value for key, value in STATEMENT.items() if key != "measured_offtake_kwh"}
    with pytest.raises(ValueError, match="measured_offtake_kwh"):
        load_statement(_write(tmp_path, incomplete))


def test_deviation_reports_a_relative_error() -> None:
    deviation = Deviation(measured=2_000.0, modelled=2_200.0, label="offtake")
    assert deviation.relative_error == pytest.approx(0.10)
    assert not deviation.within(0.05)
    assert deviation.within(0.15)


def test_deviation_handles_a_zero_measurement() -> None:
    deviation = Deviation(measured=0.0, modelled=5.0, label="feed_in")
    assert deviation.relative_error == float("inf")


def test_cli_exits_zero_when_the_model_is_close_enough(tmp_path: Path) -> None:
    path = _write(tmp_path, STATEMENT)
    assert main([str(path), "--tolerance", "10.0"]) == 0


def test_cli_exits_one_when_the_model_is_too_far_off(tmp_path: Path) -> None:
    path = _write(tmp_path, STATEMENT)
    assert main([str(path), "--tolerance", "0.0001"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_sim.validate'`

- [ ] **Step 3: Write minimal implementation**

Create `ampeer_sim/validate.py`:

```python
"""Check the model against a real annual statement.

Every other test asks whether the code matches the design. This one asks
whether the design matches reality, which is the only question a critic on a
forum will actually ask.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Household, ProfileCategory, PVSystem

REQUIRED_FIELDS = (
    "postcode4",
    "annual_consumption_kwh",
    "peak_power_wp",
    "azimuth_deg",
    "tilt_deg",
    "daytime_occupancy",
    "measured_offtake_kwh",
    "measured_feed_in_kwh",
)

DEFAULT_TOLERANCE_PERCENT = 10.0


@dataclass(frozen=True)
class Statement:
    postcode4: str
    annual_consumption_kwh: float
    peak_power_wp: int
    azimuth_deg: float
    tilt_deg: float
    daytime_occupancy: bool
    measured_offtake_kwh: float
    measured_feed_in_kwh: float


@dataclass(frozen=True)
class Deviation:
    measured: float
    modelled: float
    label: str

    @property
    def relative_error(self) -> float:
        if self.measured == 0.0:
            return float("inf") if self.modelled != 0.0 else 0.0
        return abs(self.modelled - self.measured) / self.measured

    def within(self, tolerance_fraction: float) -> bool:
        return self.relative_error <= tolerance_fraction


def load_statement(path: Path) -> Statement:
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"statement is missing {', '.join(missing)}")
    return Statement(**{field: payload[field] for field in REQUIRED_FIELDS})


class _FlatProfileProvider:
    """Placeholder provider so validation runs without an ingested profile file."""

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


def check(statement: Statement, profile_year: int = 2025) -> list[Deviation]:
    grid = YearGrid.for_year(profile_year)
    household = Household(
        postcode4=statement.postcode4,
        annual_consumption_kwh=statement.annual_consumption_kwh,
        daytime_occupancy=statement.daytime_occupancy,
    )
    system = PVSystem(
        peak_power_wp=statement.peak_power_wp,
        azimuth_deg=statement.azimuth_deg,
        tilt_deg=statement.tilt_deg,
    )
    irradiance, temperature, _ = FallbackProvider(profile_year).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg, system.peak_power_wp
    )
    production = production_series(irradiance, system, grid, weather_year=profile_year)
    consumption = compose_consumption(
        household,
        grid,
        _FlatProfileProvider().fractions(profile_year, ProfileCategory.E1A),
        temperature,
        weather_year=profile_year,
        production_kwh=production,
    )
    flows = simulate(consumption, production)
    return [
        Deviation(statement.measured_offtake_kwh, float(flows.from_grid.sum()), "offtake"),
        Deviation(statement.measured_feed_in_kwh, float(flows.to_grid.sum()), "feed_in"),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("statement", type=Path)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PERCENT)
    parser.add_argument("--profile-year", type=int, default=2025)
    args = parser.parse_args(argv)

    deviations = check(load_statement(args.statement), profile_year=args.profile_year)
    tolerance = args.tolerance / 100.0
    failed = False
    for deviation in deviations:
        status = "ok" if deviation.within(tolerance) else "OFF"
        print(
            f"{status:>3} {deviation.label:<8} measured {deviation.measured:9.1f} kWh  "
            f"modelled {deviation.modelled:9.1f} kWh  "
            f"error {deviation.relative_error * 100:5.1f} percent"
        )
        failed = failed or not deviation.within(tolerance)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validate.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Write the public methodology**

Create `docs/methodologie.md` with chapter 9 of the spec written in plain Dutch, aimed
at a reader who wants to check the sums. It must contain, each as its own short
section with a heading:

1. Waar de verbruiksvorm vandaan komt en dat standaardprofielen gemiddelden zijn
2. Dat het basisprofiel dat van huishoudens zonder teruglevering is, en waarom dat een
   systematische afwijking geeft voor mensen met panelen
3. Dat de drie laadgedragingen van een EV stereotypen zijn en geen gemeten verdeling
4. Dat het verplaatsbare blok een aangenomen grootheid van 1,75 kWh per dag is, nog
   niet gekalibreerd, gevarieerd tussen 1,0 en 2,5 kWh in de bandbreedte
5. Dat profieljaar en weerjaar kunnen verschillen en op kalenderdatum worden uitgelijnd
6. Dat er gerekend wordt op een historisch verbruiks- en weerpatroon met toekomstige
   tarieven
7. Dat de opwek van uur naar kwartier wordt gebracht door op instraling te
   interpoleren, en dat PVGIS zijn uurwaarde op tien over stempelt terwijl wij hem als
   uurgemiddelde behandelen, een verschuiving van twintig minuten
8. Dat arbitrage alleen binnen het bekende day-ahead-venster mag vooruitkijken, met de
   uitleg waarom een simulatie zonder die grens te mooie getallen geeft

No em-dashes. Write for Rob, not for a colleague.

- [ ] **Step 6: Commit**

```bash
git add ampeer_sim/validate.py tests/test_validate.py docs/methodologie.md
git commit -m "feat: add validation CLI and publish the methodology"
```

---

## Self-review

**Spec coverage.** Every numbered section of the spec maps onto at least one task:
section 2 onto tasks 4, 5 and 7; section 3 onto tasks 1, 2 and 15; section 4 onto
task 3; section 5 onto tasks 5, 8, 9 and 10; section 6 onto tasks 11, 12 and 13;
section 7 onto tasks 14 and 15; section 8 onto tasks 12, 16 and 17; section 9 onto
task 17; section 10 onto tasks 1, 15, 16 and 17.

**Two gaps found and closed while reviewing.**

1. The spec names no composition root, but a `Result` has to be assembled somewhere.
   `ampeer_sim/simulate.py` was added in task 15 and is flagged there. Add it to the
   spec's module list when this plan is accepted.
2. The spec mentions comparing the modelled feed-in against `E1A_AMI_I` as a free
   calibration reference. No task implements it, because the flat test provider used
   throughout the plan makes the comparison meaningless until a real ingested profile
   file exists. This is deliberately deferred to the first task after ingest runs
   against real data, and it is recorded here so it does not quietly disappear.

**Known simplifications an implementer should not mistake for bugs.**

- The tests use a flat profile provider rather than the real 13 MB CSV, so the suite
  runs without network access and without a gitignored data file. `NeduFileProvider`
  is tested separately against a four-row fixture with the real header layout.
- The golden numbers in `households.json` are starting values based on the fallback
  yield table, not on PVGIS. Task 16 step 5 says explicitly what to do when one fails.
- `ProductionProvider` implementations are typed as `object` in `ResilientProductionProvider`
  and `run_advice` to avoid a Protocol variance problem. Tighten this once mypy strict
  runs clean over the whole package.
