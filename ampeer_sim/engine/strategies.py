"""Battery control strategies and the foresight rule they must obey.

Day-ahead prices for a day are published at about 13:00 the day before, so a
strategy may plan one day at a time. Looking further is knowledge nobody has,
and it is exactly how optimistic battery quotes are produced.

The rule is enforced structurally rather than by comment: ``_plan_one_day``
receives one day of prices and cannot reach the rest of the array. Breaking the
rule means changing a function signature, which is the kind of boundary that
survives a year of edits.
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
    level as well as on the difference, which is why a fixed cent threshold
    would be wrong.
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

    charge_limit = spec.max_charge_kw / QUARTERS_PER_HOUR
    discharge_limit = spec.max_discharge_kw / QUARTERS_PER_HOUR
    steps_needed = int(np.ceil(spec.usable_capacity_kwh / charge_limit))

    cheapest = np.argsort(prices_day, kind="stable")[:steps_needed]
    dearest = np.argsort(-prices_day, kind="stable")[:steps_needed]

    _fill(charge, cheapest, charge_limit, spec.usable_capacity_kwh)
    _fill(discharge, dearest, discharge_limit, spec.usable_capacity_kwh)
    return charge, discharge


def _fill(plan: np.ndarray, order: np.ndarray, per_step: float, budget: float) -> None:
    for index in order:
        if budget <= 0.0:
            return
        amount = min(per_step, budget)
        plan[index] = amount
        budget -= amount


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
        day_charge, day_discharge = _plan_one_day(prices_per_quarter[start:stop], spec, margin)
        charge[start:stop] = day_charge
        discharge[start:stop] = day_discharge
    return charge, discharge
