# ampeer_advice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a simulation result into an explainable advice: which of three routes applies, which rules fired, what it is worth, and how sure we are.

**Architecture:** A second pure-Python package beside `ampeer_sim`, with the same boundary and the same reason. Rules are data in an ordered table, they judge derived facts rather than numpy arrays, and they return rule ids rather than sentences. Dutch text lives in one file keyed by those ids, so a copy change and a behaviour change cannot break the same test.

**Tech Stack:** Python 3.12, numpy (facts only), Decimal for money, pytest, hypothesis, uv.

**Spec:** `docs/superpowers/specs/2026-08-20-advice-rules-design.md`

## Global Constraints

- `ampeer_advice` must not import Django, and must not import `django` transitively. The existing `tests/test_boundaries.py` check is extended to cover it.
- No Dutch text anywhere outside `ampeer_advice/nl.py`. Enforced by a test.
- Money is `Decimal`, energy is `float`. Rules never see a numpy array; they see the fields of `AdviceContext`.
- Rules return `rule_id` strings. A rule that returns a sentence is a defect.
- Every tariff value carries a source and the date it was read, in a comment beside it.
- Free routes (1 and 2) are always emitted before route 3, regardless of input.
- `BATTERY_DOES_NOT_PAY_BACK` and `CONSIDER_BATTERY` are mutually exclusive.
- Coverage floor stays at 98 or higher. `precision = 2` stays.
- Type hints mandatory, `mypy --strict` must pass over `ampeer_advice`.
- Work on `feat/advice-layer`. Never commit directly to `main`.

---

## The multi-agent working model

Same four rules as the delivery pipeline plan, and they are what make concurrency safe:

1. **A lane owns paths exclusively.** No two lanes write the same file.
2. **Implementation agents never run git.** The integration gate commits.
3. **Every lane runs its own verification command** and reports the output.
4. **Gates run after lanes.** Integration first, audit second.

A fifth rule was learned while running the previous plan and applies here too:
**a lane may not run a tool that writes outside the files it owns.** Formatters,
code generators and `pre-commit run --all-files` belong in the barrier, never in a
lane. Lanes verify with `uv run --no-sync <tool>` against their own paths only.

### File ownership map

| Lane | Owns exclusively |
|---|---|
| **0. Foundation** | `ampeer_sim/types.py`, `ampeer_sim/economics/tariffs.py`, `ampeer_advice/__init__.py`, `ampeer_advice/types.py`, `tests/test_tariffs.py`, `tests/test_boundaries.py` |
| **A. Facts** | `ampeer_advice/facts.py`, `tests/test_advice_facts.py` |
| **B. Tariffs** | `ampeer_advice/tariffs.py`, `tests/test_advice_tariffs.py` |
| **C. Rules** | `ampeer_advice/rules.py`, `ampeer_advice/confidence.py`, `tests/test_advice_rules.py` |
| **D. Text and battery** | `ampeer_advice/nl.py`, `ampeer_advice/battery.py`, `tests/test_advice_nl.py`, `tests/test_advice_battery.py` |
| **Integration** | `ampeer_advice/advise.py`, `tests/test_advise.py`, `tests/golden/advice_households.json`, `docs/methodologie.md` |

---

## Phase 0: foundation

### Task 1: Feed-in charges per kWh, and the shared advice types

**Files:**
- Modify: `ampeer_sim/types.py` (the `TariffSet` dataclass)
- Modify: `ampeer_sim/economics/tariffs.py` (the `annual_cost` function)
- Modify: `tests/test_tariffs.py`
- Modify: `tests/test_boundaries.py`
- Create: `ampeer_advice/__init__.py`
- Create: `ampeer_advice/types.py`

**Interfaces:**
- Produces: `TariffSet.feed_in_cost_per_kwh: Decimal = Decimal("0")`
- Produces: every type in the block below. Lanes A through D are written against
  these names and nothing else.

- [ ] **Step 1: Write the failing test for the per-kWh feed-in charge**

Append to `tests/test_tariffs.py`:

```python
def test_feed_in_charges_scale_with_exported_volume() -> None:
    """Suppliers price feed-in charges per kWh, not as a flat annual fee.

    That is not only a different number but different behaviour: a per kWh
    charge falls hardest on the household with the largest array, which is
    exactly the audience this product is for.
    """
    tariffs = TariffSet(
        supply_price=Decimal("0.26"),
        feed_in_price=Decimal("0.065"),
        feed_in_cost_per_kwh=Decimal("0.075"),
    )
    small = annual_cost(_flows(0.0, 1_000.0), tariffs)
    large = annual_cost(_flows(0.0, 2_000.0), tariffs)
    # Net feed-in is 0.065 - 0.075 = -0.010 per kWh, so exporting costs money
    # and twice the export costs twice as much.
    assert small == Decimal("10.000")
    assert large == Decimal("20.000")


def test_a_household_that_never_exports_pays_no_per_kwh_feed_in_charge() -> None:
    tariffs = TariffSet(
        supply_price=Decimal("0.26"),
        feed_in_price=Decimal("0.065"),
        feed_in_cost_per_kwh=Decimal("0.075"),
    )
    assert annual_cost(_flows(1_000.0, 0.0), tariffs) == Decimal("260.000")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --no-sync pytest tests/test_tariffs.py -q -k feed_in_charges`
Expected: FAIL with `TypeError: TariffSet.__init__() got an unexpected keyword argument 'feed_in_cost_per_kwh'`

- [ ] **Step 3: Add the field and use it**

In `ampeer_sim/types.py`, inside `TariffSet`, after `feed_in_price`:

```python
    #: Suppliers price feed-in charges per exported kWh, typically 4.46 to 11.50
    #: cent in the 2027 tariffs published by August 2026. Modelling this as a
    #: flat annual fee spreads the cost evenly and therefore understates what a
    #: large array costs its owner.
    feed_in_cost_per_kwh: Decimal = Decimal("0")
```

In `ampeer_sim/economics/tariffs.py`, inside `annual_cost`, change the feed-in
revenue calculation so the per-kWh charge is subtracted from the revenue in every
branch. Replace the whole `if tariffs.dynamic: ... else: ...` block's trailing
lines with:

```python
    # The per kWh charge applies to every exported kWh regardless of contract
    # type, so it is subtracted once here rather than in each branch.
    feed_in_revenue -= feed_in * tariffs.feed_in_cost_per_kwh
```

placed immediately after the branch that sets `feed_in_revenue`, and before the
`feed_in_fixed` line.

- [ ] **Step 4: Run the whole tariff suite**

Run: `uv run --no-sync pytest tests/test_tariffs.py -q`
Expected: PASS, every existing test still green. The existing tests all leave
`feed_in_cost_per_kwh` at its default of zero, so none of them change.

- [ ] **Step 5: Extend the Django boundary check to the new package**

In `tests/test_boundaries.py`, replace the module-level constant and the test so
both packages are covered:

```python
import ampeer_advice
import ampeer_sim

PACKAGE_ROOTS = (
    pathlib.Path(ampeer_sim.__file__).parent,
    pathlib.Path(ampeer_advice.__file__).parent,
)


def test_packages_never_import_django() -> None:
    offenders = [
        str(path)
        for root in PACKAGE_ROOTS
        for path in root.rglob("*.py")
        if "django" in _imported_module_names(path)
    ]
    assert offenders == [], f"pure packages must not import django: {offenders}"
```

Keep `test_engine_version_is_declared` unchanged.

- [ ] **Step 6: Write the shared types**

Create `ampeer_advice/__init__.py`:

```python
"""Ampeer advice layer.

Turns a simulation result into an explainable recommendation. Like
``ampeer_sim`` this package imports no Django and performs no I/O, for the same
reason: a wrong advice produces no error message, only a confident sentence.
"""

from __future__ import annotations

ADVICE_VERSION = "0.1.0"

__all__ = ["ADVICE_VERSION"]
```

Create `ampeer_advice/types.py`:

```python
"""Value types for the advice layer.

``AdviceContext`` is the only thing a rule may read. It holds derived facts and
no numpy arrays, so a rule condition stays readable to someone who does not know
what a simulation is. That is the requirement: when somebody asks on a forum why
they got this advice, you must be able to point at the rule.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto

from ampeer_sim.types import Band


class Route(Enum):
    """The three routes, always presented in this order.

    The free ones come first even when they yield nothing. That ordering is a
    property of the output, not a sorting choice the frontend may revisit.
    """

    SHIFT_BEHAVIOUR = 1
    SMART_CONTROL = 2
    STORAGE = 3


class Confidence(Enum):
    """How complete the input was. Says nothing about the width of the band."""

    INDICATIVE = auto()
    GOOD = auto()
    PRECISE = auto()


@dataclass(frozen=True)
class AdviceContext:
    """Everything a rule may look at, and nothing else."""

    self_consumption_rate: float
    annual_production_kwh: float
    annual_export_kwh: float
    annual_import_kwh: float
    #: Mean daily consumption between 17:00 and 07:00 local time.
    mean_evening_night_consumption_kwh: float
    #: Annual production that exceeded consumption between 11:00 and 15:00.
    midday_surplus_kwh: float
    daytime_occupancy: bool
    has_ev: bool
    ev_charges_on_solar: bool
    has_battery: bool
    battery_capacity_kwh: float | None
    dynamic_contract: bool
    headline: Band
    confidence: Confidence


@dataclass(frozen=True)
class FiredRule:
    """A rule that matched. Carries an id, never a sentence."""

    rule_id: str
    route: Route
    estimated_saving_eur: Decimal | None


@dataclass(frozen=True)
class Rule:
    rule_id: str
    route: Route
    priority: int
    condition: Callable[[AdviceContext], bool]
    saving: Callable[[AdviceContext], Decimal | None]


@dataclass(frozen=True)
class BatteryAdvice:
    recommended_capacity_kwh: float
    annual_saving_eur: Decimal
    payback_years_p10: Decimal
    payback_years_p50: Decimal
    payback_years_p90: Decimal
    #: (capacity_kwh, annual_saving_eur) for every capacity that was simulated.
    curve: tuple[tuple[float, Decimal], ...]


@dataclass(frozen=True)
class Advice:
    engine_version: str
    advice_version: str
    confidence: Confidence
    headline: Band
    fired: tuple[FiredRule, ...]
    routes: tuple[Route, ...]
    battery: BatteryAdvice | None
```

- [ ] **Step 7: Verify**

Run:

```bash
uv run --no-sync pytest tests/test_tariffs.py tests/test_boundaries.py -q
uv run --no-sync mypy ampeer_sim ampeer_advice tools
uv run --no-sync ruff check ampeer_sim ampeer_advice tests tools
```

Expected: all green. Do not commit; the integration gate commits.

---

## Phase 1: four concurrent lanes

### Task 2 (Lane A): derive the facts rules judge on

**Files:**
- Create: `ampeer_advice/facts.py`
- Create: `tests/test_advice_facts.py`

**Interfaces:**
- Consumes: `AdviceContext`, `Confidence` from `ampeer_advice.types`;
  `EnergyFlows`, `Household`, `Result` from `ampeer_sim.types`;
  `YearGrid` from `ampeer_sim.timebase`
- Produces:
  `build_context(flows: EnergyFlows, household: Household, grid: YearGrid, result: Result, confidence: Confidence, dynamic_contract: bool) -> AdviceContext`

Window definitions, fixed here so no other module invents its own:

- Evening and night is 17:00 up to 07:00 local time, using `grid.local_hour`.
- Midday is 11:00 up to 15:00 local time, matching
  `ampeer_sim.profiles.presence.MIDDAY_WINDOW`.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import numpy as np
import pytest

from ampeer_advice.facts import build_context
from ampeer_advice.types import Confidence
from ampeer_sim.engine.run import simulate
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Band, Household, ProductionSource, Result
from decimal import Decimal

GRID = YearGrid.for_year(2025)


def _result() -> Result:
    return Result(
        engine_version="0.1.0",
        band=Band(Decimal("500"), Decimal("600"), Decimal("700"), runs=81),
        self_consumption_rate=0.3,
        production_source=ProductionSource.FALLBACK,
        profile_year=2025,
        weather_year=2025,
    )


def _context(consumption: np.ndarray, production: np.ndarray, **household_kwargs: object):
    household = Household(postcode4="5401", annual_consumption_kwh=3_500.0, **household_kwargs)  # type: ignore[arg-type]
    flows = simulate(consumption, production)
    return build_context(
        flows=flows,
        household=household,
        grid=GRID,
        result=_result(),
        confidence=Confidence.INDICATIVE,
        dynamic_contract=False,
    )


def test_annual_totals_come_straight_from_the_flows() -> None:
    consumption = np.full(GRID.quarters, 0.1)
    production = np.full(GRID.quarters, 0.2)
    context = _context(consumption, production)
    assert context.annual_production_kwh == pytest.approx(production.sum())
    assert context.annual_export_kwh == pytest.approx(
        float(simulate(consumption, production).to_grid.sum())
    )


def test_evening_and_night_consumption_is_a_daily_mean_over_17_to_07() -> None:
    consumption = np.zeros(GRID.quarters)
    evening_or_night = (GRID.local_hour >= 17) | (GRID.local_hour < 7)
    consumption[evening_or_night] = 0.25
    context = _context(consumption, np.zeros(GRID.quarters))
    # 14 hours times 4 quarters times 0.25 kWh is 14 kWh a day.
    assert context.mean_evening_night_consumption_kwh == pytest.approx(14.0, rel=1e-3)


def test_midday_surplus_counts_only_production_above_consumption() -> None:
    consumption = np.full(GRID.quarters, 0.05)
    production = np.zeros(GRID.quarters)
    production[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 0.30
    context = _context(consumption, production)
    midday_quarters = int(((GRID.local_hour >= 11) & (GRID.local_hour < 15)).sum())
    assert context.midday_surplus_kwh == pytest.approx(midday_quarters * 0.25, rel=1e-6)


def test_household_facts_are_copied_so_rules_never_touch_arrays() -> None:
    context = _context(np.full(GRID.quarters, 0.1), np.zeros(GRID.quarters), daytime_occupancy=True)
    assert context.daytime_occupancy is True
    assert context.has_ev is False
    assert context.has_battery is False


def test_an_ev_charging_on_solar_is_reported_as_such() -> None:
    from ampeer_sim.types import EV, EVChargingBehaviour

    context = _context(
        np.full(GRID.quarters, 0.1),
        np.zeros(GRID.quarters),
        ev=EV(behaviour=EVChargingBehaviour.SOLAR),
    )
    assert context.has_ev is True
    assert context.ev_charges_on_solar is True


def test_the_headline_band_and_confidence_are_passed_through() -> None:
    context = _context(np.full(GRID.quarters, 0.1), np.zeros(GRID.quarters))
    assert context.headline.p50_eur == Decimal("600")
    assert context.confidence is Confidence.INDICATIVE
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --no-sync pytest tests/test_advice_facts.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'ampeer_advice.facts'`

- [ ] **Step 3: Implement**

Write `ampeer_advice/facts.py` with `EVENING_NIGHT_WINDOW = (17, 7)` and
`MIDDAY_WINDOW = (11, 15)` as module constants, a `_window_mask` helper that
handles a window wrapping past midnight the same way
`ampeer_sim.profiles.assets._window_mask` does, and `build_context` returning an
`AdviceContext` whose fields are exactly the ones the tests read. Midday surplus is
`float(np.clip(production - consumption, 0.0, None)[midday_mask].sum())`. The daily
mean is the window total divided by `grid.days`.

- [ ] **Step 4: Verify**

Run: `uv run --no-sync pytest tests/test_advice_facts.py -q`
Expected: PASS, 6 passed.

Run: `uv run --no-sync mypy ampeer_advice`
Expected: Success.

- [ ] **Step 5: Report**

Report the six field values your implementation produces for a flat 3500 kWh
household with no production, so the integration gate can sanity check them. Do not
commit.

---

### Task 3 (Lane B): national tariff values with a band

**Files:**
- Create: `ampeer_advice/tariffs.py`
- Create: `tests/test_advice_tariffs.py`

**Interfaces:**
- Consumes: `TariffSet` from `ampeer_sim.types`
- Produces:
  - `SOURCED_ON: date`
  - `TariffBand` dataclass with `low`, `mid`, `high` as `Decimal`
  - `SUPPLY_PRICE`, `FEED_IN_GROSS_FIXED`, `FEED_IN_COST`, `FEED_IN_NET_DYNAMIC`,
    `BATTERY_COST_PER_KWH`, all `TariffBand`
  - `baseline_tariffs() -> TariffSet` and
    `scenario_2027_tariffs(dynamic: bool = False, level: str = "mid") -> TariffSet`
    where `level` is one of `"low"`, `"mid"`, `"high"`

Values, all read on 2026-08-20, each with its source in a comment beside it:

| Constant | low | mid | high |
|---|---|---|---|
| `SUPPLY_PRICE` | 0.22 | 0.26 | 0.30 |
| `FEED_IN_GROSS_FIXED` | 0.050 | 0.065 | 0.077 |
| `FEED_IN_COST` | 0.0446 | 0.075 | 0.115 |
| `FEED_IN_NET_DYNAMIC` | 0.05 | 0.06 | 0.07 |
| `BATTERY_COST_PER_KWH` | 450 | 675 | 900 |

`baseline_tariffs()` returns the pre-2027 situation: `net_metering=True`,
`feed_in_price` equal to `SUPPLY_PRICE.mid`, all charges zero. Standing charges are
zero in both tariff sets on purpose, because the headline figure is a difference and
anything identical in both sides cancels; that comment belongs in the file.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --no-sync pytest tests/test_advice_tariffs.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Write `ampeer_advice/tariffs.py` with the constants above, each with a comment
naming its source and what it covers. Include a module docstring explaining that
these are national values with a band rather than a per-supplier table, and why: a
hand-maintained supplier table produces no error when it goes stale, only a
confident wrong number.

- [ ] **Step 4: Verify**

Run: `uv run --no-sync pytest tests/test_advice_tariffs.py -q`
Expected: PASS, 11 passed.

- [ ] **Step 5: Report**

Report the net feed-in figure per kWh at each of the three levels for a fixed
contract, and state whether it is negative at any of them. Do not commit.

---

### Task 4 (Lane C): the rule table and the confidence level

**Files:**
- Create: `ampeer_advice/rules.py`
- Create: `ampeer_advice/confidence.py`
- Create: `tests/test_advice_rules.py`

**Interfaces:**
- Consumes: `AdviceContext`, `Rule`, `FiredRule`, `Route`, `Confidence` from
  `ampeer_advice.types`; `SUPPLY_PRICE`, `FEED_IN_GROSS_FIXED`, `FEED_IN_COST` from
  `ampeer_advice.tariffs`
- Produces:
  - `RULES: tuple[Rule, ...]` in priority order
  - `evaluate(context: AdviceContext) -> tuple[FiredRule, ...]`
  - `RULE_IDS: frozenset[str]`
  - `confidence_for(filled_fields: int, has_meter_data: bool) -> Confidence`

The six rules, with their exact conditions:

| rule_id | route | priority | condition |
|---|---|---|---|
| `SHIFT_FLEXIBLE_LOAD` | SHIFT_BEHAVIOUR | 10 | `self_consumption_rate < 0.35 and not daytime_occupancy` |
| `CHARGE_EV_ON_SURPLUS` | SMART_CONTROL | 20 | `has_ev and not ev_charges_on_solar and midday_surplus_kwh > 500.0` |
| `CONSIDER_DYNAMIC_CONTRACT` | SMART_CONTROL | 30 | `not dynamic_contract and annual_production_kwh > 0 and annual_export_kwh / annual_production_kwh > 0.40` |
| `CONSIDER_BATTERY` | STORAGE | 40 | `not has_battery and annual_export_kwh > 1500.0 and mean_evening_night_consumption_kwh > 3.0` |
| `BATTERY_DOES_NOT_PAY_BACK` | STORAGE | 45 | set by `advise.py`, see below |
| `REVIEW_EXISTING_BATTERY` | STORAGE | 50 | `has_battery` |

`BATTERY_DOES_NOT_PAY_BACK` cannot be decided from `AdviceContext` alone, because it
needs the payback figure that `battery.py` computes. Its condition in `RULES` is
`lambda context: False`, and `advise.py` replaces `CONSIDER_BATTERY` with it when the
computed payback exceeds twelve years. `evaluate` therefore never emits both, and a
test asserts that.

Saving estimates:

- `SHIFT_FLEXIBLE_LOAD`: `365 * 1.0 kWh * (SUPPLY_PRICE.mid - net_feed_in)` where
  `net_feed_in = FEED_IN_GROSS_FIXED.mid - FEED_IN_COST.mid`, capped so it can never
  exceed `midday_surplus_kwh * (SUPPLY_PRICE.mid - net_feed_in)`. The 1.0 kWh is the
  shiftable block from `Household.shiftable_block_kwh`'s default, calibrated in the
  simulation spec.
- `CHARGE_EV_ON_SURPLUS`: `min(midday_surplus_kwh, 2000.0) * (SUPPLY_PRICE.mid - net_feed_in)`
- `CONSIDER_DYNAMIC_CONTRACT`: `annual_export_kwh * (FEED_IN_NET_DYNAMIC.mid - net_feed_in)`
- The three remaining rules return `None`. Their value is the advice itself, not a
  number, and inventing one would be exactly the false precision this project
  refuses elsewhere.

- [ ] **Step 1: Write the failing tests**

Write `tests/test_advice_rules.py` with a `_context(**overrides)` helper building an
`AdviceContext` with neutral defaults (`self_consumption_rate=0.5`,
`annual_production_kwh=3500.0`, `annual_export_kwh=1000.0`,
`annual_import_kwh=2000.0`, `mean_evening_night_consumption_kwh=5.0`,
`midday_surplus_kwh=800.0`, everything boolean `False`, `battery_capacity_kwh=None`,
a `Band` of 500/600/700, `Confidence.INDICATIVE`) and these tests:

1. `test_every_rule_id_is_unique`
2. `test_rules_are_in_priority_order`
3. `test_shift_flexible_load_fires_on_low_self_consumption_and_nobody_home`
4. `test_shift_flexible_load_does_not_fire_when_somebody_is_home`
5. `test_charge_ev_on_surplus_needs_an_ev_that_is_not_already_solar_charging`
6. `test_consider_dynamic_contract_needs_a_fixed_contract_and_heavy_export`
7. `test_consider_battery_needs_export_and_evening_demand`
8. `test_consider_battery_does_not_fire_when_a_battery_is_present`
9. `test_review_existing_battery_fires_only_with_a_battery`
10. `test_battery_does_not_pay_back_never_fires_from_the_table_alone`
11. `test_free_routes_are_always_ordered_before_storage`
12. `test_savings_are_decimal_or_none`
13. `test_no_rule_returns_dutch_text` (assert every `FiredRule` field is a str id,
    a `Route` or a `Decimal`, never a sentence: `assert " " not in fired.rule_id`)
14. `test_confidence_rises_with_the_number_of_filled_fields`
15. `test_meter_data_always_means_precise`

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --no-sync pytest tests/test_advice_rules.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`confidence_for` maps 0 to 4 filled fields to `INDICATIVE`, 5 to 9 to `GOOD`, and
anything with `has_meter_data=True` to `PRECISE` regardless of field count.

`evaluate` walks `RULES` in order, keeps the ones whose condition is true, and
returns `FiredRule` objects. It sorts by `route.value` then `priority`, so the free
routes always precede storage.

- [ ] **Step 4: Verify**

Run: `uv run --no-sync pytest tests/test_advice_rules.py -q`
Expected: PASS, 15 passed.

Run: `uv run --no-sync mypy ampeer_advice`
Expected: Success.

- [ ] **Step 5: Report**

Report which rules fire for the neutral context, and the estimated saving for each.
Do not commit.

---

### Task 5 (Lane D): Dutch text and the battery curve

**Files:**
- Create: `ampeer_advice/nl.py`
- Create: `ampeer_advice/battery.py`
- Create: `tests/test_advice_nl.py`
- Create: `tests/test_advice_battery.py`

**Interfaces:**
- Consumes: `Route`, `Confidence`, `BatteryAdvice` from `ampeer_advice.types`;
  `BATTERY_COST_PER_KWH` from `ampeer_advice.tariffs`
- Produces:
  - `RULE_TEXTS: dict[str, str]` keyed by rule id
  - `ROUTE_TITLES: dict[Route, str]`, `CONFIDENCE_LABELS: dict[Confidence, str]`
  - `text_for(rule_id: str) -> str`
  - `CAPACITIES: tuple[float, ...] = (3.0, 5.0, 7.0, 10.0, 15.0)`
  - `find_knee(curve: Sequence[tuple[float, Decimal]]) -> float`
  - `battery_advice(curve: Sequence[tuple[float, Decimal]]) -> BatteryAdvice`

The knee is defined, not eyeballed: take the marginal saving per extra kWh of the
first step as the reference, and recommend the largest capacity whose marginal
saving is still at least half of that reference.

Dutch text rules: no em-dashes, written for Rob rather than for a colleague, and
every rule id in `RULE_IDS` must have an entry.

- [ ] **Step 1: Write the failing tests**

`tests/test_advice_battery.py`:

```python
from __future__ import annotations

from decimal import Decimal

import pytest

from ampeer_advice.battery import CAPACITIES, battery_advice, find_knee


def test_the_capacities_are_the_five_the_spec_names() -> None:
    assert CAPACITIES == (3.0, 5.0, 7.0, 10.0, 15.0)


def test_the_knee_is_where_marginal_saving_halves() -> None:
    # 3 kWh earns 300; every kWh after that earns much less.
    curve = [
        (3.0, Decimal("300")),
        (5.0, Decimal("390")),  # 45 per kWh, still above half of 100
        (7.0, Decimal("420")),  # 15 per kWh, below half
        (10.0, Decimal("430")),
        (15.0, Decimal("435")),
    ]
    assert find_knee(curve) == 5.0


def test_a_perfectly_linear_curve_recommends_the_largest_capacity() -> None:
    curve = [(c, Decimal(str(c * 100))) for c in CAPACITIES]
    assert find_knee(curve) == 15.0


def test_a_curve_that_flattens_immediately_recommends_the_smallest() -> None:
    curve = [
        (3.0, Decimal("300")),
        (5.0, Decimal("305")),
        (7.0, Decimal("306")),
        (10.0, Decimal("307")),
        (15.0, Decimal("308")),
    ]
    assert find_knee(curve) == 3.0


def test_payback_uses_the_cost_band_so_it_has_a_spread() -> None:
    curve = [(c, Decimal(str(c * 100))) for c in CAPACITIES]
    advice = battery_advice(curve)
    assert advice.payback_years_p10 < advice.payback_years_p50 < advice.payback_years_p90


def test_the_curve_is_carried_through_for_the_frontend() -> None:
    curve = [(c, Decimal(str(c * 100))) for c in CAPACITIES]
    assert battery_advice(curve).curve == tuple(curve)


def test_a_curve_that_saves_nothing_reports_an_unreachable_payback() -> None:
    curve = [(c, Decimal("0")) for c in CAPACITIES]
    advice = battery_advice(curve)
    assert advice.payback_years_p50 > Decimal("100")
```

`tests/test_advice_nl.py`:

```python
from __future__ import annotations

import pytest

from ampeer_advice.nl import CONFIDENCE_LABELS, ROUTE_TITLES, RULE_TEXTS, text_for
from ampeer_advice.rules import RULE_IDS
from ampeer_advice.types import Confidence, Route


def test_every_rule_has_dutch_text() -> None:
    assert RULE_IDS <= set(RULE_TEXTS)


def test_no_text_belongs_to_a_rule_that_does_not_exist() -> None:
    assert set(RULE_TEXTS) <= RULE_IDS


def test_every_route_and_every_confidence_level_has_a_label() -> None:
    assert set(ROUTE_TITLES) == set(Route)
    assert set(CONFIDENCE_LABELS) == set(Confidence)


def test_no_em_dashes_anywhere() -> None:
    """Project convention: no em-dashes in user-facing Dutch text."""
    for text in list(RULE_TEXTS.values()) + list(ROUTE_TITLES.values()):
        assert "—" not in text, text


def test_text_for_rejects_an_unknown_rule() -> None:
    with pytest.raises(KeyError):
        text_for("NO_SUCH_RULE")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --no-sync pytest tests/test_advice_nl.py tests/test_advice_battery.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

Write both modules. `battery_advice` computes payback as capacity times
`BATTERY_COST_PER_KWH` divided by the annual saving at the recommended capacity,
using `low` for `p10`, `mid` for `p50` and `high` for `p90`. When the annual saving
is zero, return `Decimal("999")` rather than dividing by zero, and say so in a
comment: a battery that saves nothing has no payback time, and 999 is the honest
way to render that in a number field.

The six Dutch texts follow the fase 0.5 document. `BATTERY_DOES_NOT_PAY_BACK` must
say plainly that a battery is not worth it in this situation. That text is the proof
that the product is neutral and it must not be softened.

- [ ] **Step 4: Verify**

Run: `uv run --no-sync pytest tests/test_advice_nl.py tests/test_advice_battery.py -q`
Expected: PASS, 12 passed.

- [ ] **Step 5: Report**

Report the six Dutch texts verbatim so they can be read as copy rather than as code.
Do not commit.

---

## Phase 2: the integration gate

### Task 6: Compose, verify the seams, commit

**Files:**
- Create: `ampeer_advice/advise.py`
- Create: `tests/test_advise.py`
- Create: `tests/golden/advice_households.json`
- Modify: `docs/methodologie.md`

**Interfaces:**
- Consumes: everything from Phase 0 and Phase 1
- Produces: `advise(...) -> Advice`

- [ ] **Step 1: Check the seams before writing anything**

Run:

```bash
uv run --no-sync pytest tests/test_advice_facts.py tests/test_advice_tariffs.py \
  tests/test_advice_rules.py tests/test_advice_nl.py tests/test_advice_battery.py -q
uv run --no-sync mypy ampeer_sim ampeer_advice tools
git status --porcelain
```

Expected: all lanes green; `git status` shows only the paths in the ownership map
and nothing else. Any other path means a lane wrote outside its row, which is a
process failure worth reporting even when the change looks harmless.

- [ ] **Step 2: Write the composition root and its tests**

`advise()` takes the household, the two tariff sets, the grid, the providers and the
`Result` from `ampeer_sim.simulate.run_advice`, builds the context through
`build_context`, evaluates the rules, and when `CONSIDER_BATTERY` fired, runs the
capacity curve and replaces that rule with `BATTERY_DOES_NOT_PAY_BACK` if
`payback_years_p50 > 12`.

`tests/test_advise.py` must assert at minimum:

1. The returned `Advice` carries both `engine_version` and `advice_version`.
2. `routes` is always `(Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE)`.
3. `CONSIDER_BATTERY` and `BATTERY_DOES_NOT_PAY_BACK` never both appear.
4. A household with a twelve-year-plus payback gets `BATTERY_DOES_NOT_PAY_BACK`.
5. Every fired rule id has Dutch text.
6. A full advice completes in under 500 ms excluding the battery curve.

- [ ] **Step 3: Write the golden households**

`tests/golden/advice_households.json` reuses the six households from
`tests/golden/households.json` and records, per household, the expected fired rule
ids and the expected recommended route. Ids, not texts. If a case produces a
surprising set, read it and decide whether the model or the expectation is wrong
before recording it. Do not record whatever the code happened to produce.

- [ ] **Step 4: Extend the methodology**

Add three sections to `docs/methodologie.md` in plain Dutch, no em-dashes:

- Where the tariff figures come from, that they are national values with a band
  rather than per-supplier numbers, and why a per-supplier table would be worse.
- The correction to the 3 to 8 cent assumption, with the net figures.
- That the battery advice has a coarser band than the headline figure, because the
  capacity curve runs on the central case only.

- [ ] **Step 5: Run every gate exactly as CI will**

```bash
uv sync --locked --group dev
uv run ruff check ampeer_sim ampeer_advice tests tools
uv run ruff format --check ampeer_sim ampeer_advice tests tools
uv run mypy ampeer_sim ampeer_advice tools
uv run pytest --cov --cov-report=term
uv run bandit -c pyproject.toml -r ampeer_sim ampeer_advice tools
uv run pre-commit run --all-files
```

Coverage must stay at 98 or above. If it drops, add tests. Do not lower the floor.

Note: `ampeer_advice` must be added in **two** places in `pyproject.toml`, and to the
ruff, mypy and bandit invocations in `.github/workflows/ci.yml` and `security.yml`.

1. `[tool.setuptools.packages.find] include` — without this the editable install never
   maps the package and every `import ampeer_advice` fails at collection, with a
   `ModuleNotFoundError` that looks like a missing file rather than a packaging
   setting. Requires `uv sync` afterwards to regenerate the editable finder.
2. `[tool.coverage.run] source` — without this the contract test
   `test_every_top_level_package_is_measured_for_coverage` fails, which is exactly
   what that test is for.

Both were done centrally before the lanes started, in commit `cedfb9e`, precisely so
four concurrent lanes would not race on the same file. The first was missing from an
earlier revision of this plan; the foundation agent stopped and reported it rather
than editing a file outside its ownership row, which is the discipline working.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add the advice rule table with sourced national tariffs"
```

---

## Phase 3: three concurrent audits

### Task 7: Audit lens one, neutrality

Answer with evidence, modify nothing:

1. Can any rule read a field that relates to a commercial relationship? Prove it
   from the definition of `AdviceContext`.
2. Are the free routes emitted before storage for every input you can construct?
   Try to build a counterexample.
3. Is `BATTERY_DOES_NOT_PAY_BACK` reachable in practice? Construct a household that
   triggers it and report the numbers.
4. Does any Dutch text soften a negative recommendation, or nudge toward a purchase?
   Quote the text.
5. Would swapping a tariff value for a friendlier one change which rules fire? If so,
   which, and what does that say about how carefully those values must be sourced?

### Task 8: Audit lens two, are the numbers defensible

1. Every constant in `ampeer_advice/tariffs.py`: does it have a source and a date,
   and does the value match what that source says?
2. The savings estimators: recompute each by hand for one context and say whether
   the code agrees.
3. The knee definition: does the implementation match the spec's wording exactly?
   Construct a curve where a plausible alternative definition would give a different
   answer, and say which one the code picks.
4. Is any number in the package invented rather than sourced or derived? Name it.
5. Does the advice ever present a single figure without a band? Name where.

### Task 9: Audit lens three, does the boundary hold

1. Does `ampeer_advice` import Django, directly or transitively?
2. Is any Dutch text outside `nl.py`? Grep for common Dutch words in the package.
3. Does any rule receive a numpy array, directly or through a field?
4. Is money ever a float in this package, or energy ever a Decimal?
5. What is the single most likely way this rule table becomes unexplainable over the
   next six months, and what would make that harder?

---

## Self-review

**Spec coverage.** Spec section 2 maps onto Task 1; section 3 onto Task 3; section 4
onto Task 3; section 5 onto Tasks 1, 2 and 6; section 6 onto Task 4; section 7 onto
Task 5; section 8 onto Task 4; section 9 onto Tasks 4, 5 and 6; section 10 onto Task 6.

**One gap found and closed while reviewing.** The spec requires that `ampeer_advice`
is covered by the Django boundary check and by the coverage floor. Neither happens
automatically: `tests/test_boundaries.py` names one package and
`[tool.coverage.run] source` lists two. Both are now explicit steps, in Task 1 step 5
and Task 6 step 5, and the existing contract test will fail until the second is done.

**One thing an executor should not mistake for a defect.** `BATTERY_DOES_NOT_PAY_BACK`
has the condition `lambda context: False` in the rule table. That is deliberate and
documented in Task 4: the rule needs a payback figure that `AdviceContext` does not
carry, so `advise.py` substitutes it. A rule whose condition is always false looks
like a bug and is not.
