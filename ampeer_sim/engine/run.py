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


def _without_battery(consumption: np.ndarray, production: np.ndarray) -> EnergyFlows:
    """The no-battery case has no state to carry, so it needs no loop.

    This is the hot path: every sensitivity variation runs through it, and the
    whole advice has a two second budget.
    """
    self_consumption = np.minimum(consumption, production)
    zeros = np.zeros_like(consumption)
    return EnergyFlows(
        consumption=consumption,
        production=production,
        self_consumption=self_consumption,
        from_grid=consumption - self_consumption,
        to_grid=production - self_consumption,
        battery_charge=zeros,
        battery_discharge=zeros,
        grid_charge=zeros,
        grid_discharge=zeros,
    )


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

    if battery_spec is None:
        return _without_battery(consumption, production)

    steps = consumption.shape[0]
    battery = Battery(battery_spec)
    charge_wanted = charge_plan if charge_plan is not None else np.zeros(steps)
    discharge_wanted = discharge_plan if discharge_plan is not None else np.zeros(steps)

    self_consumption = np.zeros(steps)
    from_grid = np.zeros(steps)
    to_grid = np.zeros(steps)
    battery_charge = np.zeros(steps)
    battery_discharge = np.zeros(steps)
    grid_charge = np.zeros(steps)
    grid_discharge = np.zeros(steps)

    for step in range(steps):
        direct = min(consumption[step], production[step])
        self_consumption[step] = direct
        surplus = production[step] - direct
        deficit = consumption[step] - direct

        stored = battery.charge(surplus)
        battery_charge[step] = stored
        surplus -= stored

        delivered = battery.discharge(deficit)
        battery_discharge[step] = delivered
        deficit -= delivered

        if battery_spec.allow_grid_charging and charge_wanted[step] > 0.0:
            grid_charge[step] = battery.charge(charge_wanted[step])
        if discharge_wanted[step] > 0.0:
            grid_discharge[step] = battery.discharge(discharge_wanted[step])

        from_grid[step] = deficit
        to_grid[step] = surplus

    return EnergyFlows(
        consumption=consumption,
        production=production,
        self_consumption=self_consumption,
        from_grid=from_grid,
        to_grid=to_grid,
        battery_charge=battery_charge,
        battery_discharge=battery_discharge,
        grid_charge=grid_charge,
        grid_discharge=grid_discharge,
    )


def assert_energy_balance(flows: EnergyFlows, tolerance: float = 1e-9) -> None:
    """Raise ``EnergyBalanceError`` if energy does not conserve on any quarter.

    Two equations, no correction terms, because energy the battery moves for
    price reasons is held in its own fields rather than folded into the
    household flows.
    """
    consumption_residual = (
        flows.consumption - flows.self_consumption - flows.battery_discharge - flows.from_grid
    )
    if np.any(np.abs(consumption_residual) > tolerance):
        worst = int(np.argmax(np.abs(consumption_residual)))
        raise EnergyBalanceError(
            f"consumption does not balance at step {worst}: "
            f"residual {consumption_residual[worst]!r}"
        )

    production_residual = (
        flows.production - flows.self_consumption - flows.battery_charge - flows.to_grid
    )
    if np.any(np.abs(production_residual) > tolerance):
        worst = int(np.argmax(np.abs(production_residual)))
        raise EnergyBalanceError(
            f"production does not balance at step {worst}: "
            f"residual {production_residual[worst]!r}"
        )
