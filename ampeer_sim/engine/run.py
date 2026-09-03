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
    """Run the quarter-hour simulation and return the resulting energy flows.

    Checked against its own energy balance before returning, not just in
    tests. Both residuals are computed as remainders of the same values that
    feed into them, so they hold by construction today; the check exists for
    the day a change computes ``to_grid`` or ``from_grid`` some other way and
    stops that remainder relationship holding. Every caller in
    ``ampeer_advice`` prices whatever this returns, so that kind of bug has to
    fail loudly at this one seam instead of turning into a plausible wrong
    euro figure three layers up, caught only if a golden household happens to
    move.
    """
    if consumption.shape != production.shape:
        raise ValueError("consumption and production must have the same length")

    if battery_spec is None:
        flows = _without_battery(consumption, production)
        assert_energy_balance(flows)
        return flows

    steps = consumption.shape[0]
    battery = Battery(battery_spec)

    # Python lists, not numpy arrays, for the duration of the loop. Indexing a
    # numpy array with a scalar builds a np.float64 object every time, and this
    # loop does that roughly eight times per quarter for a year, five times over
    # when a capacity curve runs. Converting once at the edge and back at the
    # end moves the same doubles through plain float arithmetic instead.
    #
    # Bit for bit the same answer: tolist() is exact, and float and np.float64
    # are both IEEE 754 binary64, so every operation below produces the double
    # it produced before. The golden households assert to the cent and did not
    # move. This is a speed change; if it ever becomes a number change, those
    # tests are what says so.
    consumption_kwh = consumption.tolist()
    production_kwh = production.tolist()
    charge_wanted = charge_plan.tolist() if charge_plan is not None else [0.0] * steps
    discharge_wanted = discharge_plan.tolist() if discharge_plan is not None else [0.0] * steps
    allow_grid_charging = battery_spec.allow_grid_charging

    self_consumption = [0.0] * steps
    from_grid = [0.0] * steps
    to_grid = [0.0] * steps
    battery_charge = [0.0] * steps
    battery_discharge = [0.0] * steps
    grid_charge = [0.0] * steps
    grid_discharge = [0.0] * steps

    for step in range(steps):
        produced = production_kwh[step]
        consumed = consumption_kwh[step]
        direct = min(consumed, produced)
        self_consumption[step] = direct
        surplus = produced - direct
        deficit = consumed - direct

        stored = battery.charge(surplus, step)
        battery_charge[step] = stored
        surplus -= stored

        delivered = battery.discharge(deficit, step)
        battery_discharge[step] = delivered
        deficit -= delivered

        if allow_grid_charging and charge_wanted[step] > 0.0:
            grid_charge[step] = battery.charge(charge_wanted[step], step)
        if discharge_wanted[step] > 0.0:
            grid_discharge[step] = battery.discharge(discharge_wanted[step], step)

        from_grid[step] = deficit
        to_grid[step] = surplus

    flows = EnergyFlows(
        consumption=consumption,
        production=production,
        self_consumption=np.asarray(self_consumption),
        from_grid=np.asarray(from_grid),
        to_grid=np.asarray(to_grid),
        battery_charge=np.asarray(battery_charge),
        battery_discharge=np.asarray(battery_discharge),
        grid_charge=np.asarray(grid_charge),
        grid_discharge=np.asarray(grid_discharge),
    )
    assert_energy_balance(flows)
    return flows


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
            f"production does not balance at step {worst}: residual {production_residual[worst]!r}"
        )
