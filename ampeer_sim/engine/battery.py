"""A quarter-hour battery state model.

``charge`` speaks in energy taken from the source and ``discharge`` in energy
delivered to the household. Both are the quantities the energy balance needs;
the losses live inside. Getting those two the wrong way round is the classic
way to make a battery look better than it is, so both directions are tested.
"""

from __future__ import annotations

import math

from ampeer_sim.timebase import QUARTERS_PER_HOUR
from ampeer_sim.types import BatterySpec


class Battery:
    """One battery, stepped a quarter of an hour at a time.

    ``charge`` and ``discharge`` are called twice per quarter for a whole year,
    so roughly 140.000 times per simulation and five times that for a capacity
    curve. Everything in them that does not change is therefore computed once,
    in ``__init__``: the two power limits per quarter and the usable capacity.
    ``BatterySpec`` is a frozen dataclass, so none of the three can move
    underneath this object.

    That is a speed change and never a number change. The same division of the
    same two floats gives the same double whether it runs once or a hundred
    thousand times, and the golden households prove it: they are asserted to
    the cent and did not shift.
    """

    def __init__(self, spec: BatterySpec) -> None:
        self._spec = spec
        self._one_way_efficiency = math.sqrt(spec.round_trip_efficiency)
        self._charge_limit_per_quarter = spec.max_charge_kw / QUARTERS_PER_HOUR
        self._discharge_limit_per_quarter = spec.max_discharge_kw / QUARTERS_PER_HOUR
        self._usable_capacity_kwh = spec.usable_capacity_kwh
        self.soc_kwh = 0.0
        self.throughput_kwh = 0.0
        # Which quarter the budgets below belong to. -1 is before the first, so
        # the first call of any quarter opens it.
        self._quarter = -1
        self._charged_this_quarter = 0.0
        self._discharged_this_quarter = 0.0

    @property
    def spec(self) -> BatterySpec:
        return self._spec

    @property
    def headroom_kwh(self) -> float:
        return self._usable_capacity_kwh - self.soc_kwh

    def _open(self, quarter: int) -> None:
        """Start a quarter, if this is not the one already open.

        The power limits are per quarter and the loop calls in twice: once for
        the household's own surplus and once for a price-driven plan. Until
        2026-08-23 each call carried its own limit, so a battery rated at 2 kW
        moved 4 kW in a quarter whenever both fired, which is the shape of
        mistake the module docstring above warns about.
        """
        if quarter != self._quarter:
            self._quarter = quarter
            self._charged_this_quarter = 0.0
            self._discharged_this_quarter = 0.0

    def charge(self, offered_kwh: float, quarter: int) -> float:
        """Take energy from a source. Returns the energy actually taken.

        ``quarter`` says which quarter this is, and has no default. A default
        would mean one quarter open forever, so every existing caller would
        quietly start sharing an allowance, and a caller that meant to step
        would look like one that did not. Required, so the answer is stated.
        """
        self._open(quarter)
        if offered_kwh <= 0.0:
            return 0.0
        allowance = self._charge_limit_per_quarter - self._charged_this_quarter
        if allowance <= 0.0:
            return 0.0
        capacity_limit = (self._usable_capacity_kwh - self.soc_kwh) / self._one_way_efficiency
        taken = min(offered_kwh, allowance, capacity_limit)
        self.soc_kwh += taken * self._one_way_efficiency
        self._charged_this_quarter += taken
        return taken

    def discharge(self, wanted_kwh: float, quarter: int) -> float:
        """Deliver energy to the household. Returns the energy actually delivered.

        ``quarter`` as above, and for the same reason: the loop asks twice.
        """
        self._open(quarter)
        if wanted_kwh <= 0.0:
            return 0.0
        allowance = self._discharge_limit_per_quarter - self._discharged_this_quarter
        if allowance <= 0.0:
            return 0.0
        stored_limit = self.soc_kwh * self._one_way_efficiency
        delivered = min(wanted_kwh, allowance, stored_limit)
        self.soc_kwh -= delivered / self._one_way_efficiency
        self.throughput_kwh += delivered
        self._discharged_this_quarter += delivered
        return delivered
