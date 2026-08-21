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

    @property
    def spec(self) -> BatterySpec:
        return self._spec

    @property
    def headroom_kwh(self) -> float:
        return self._usable_capacity_kwh - self.soc_kwh

    def charge(self, offered_kwh: float) -> float:
        """Take energy from a source. Returns the energy actually taken."""
        if offered_kwh <= 0.0:
            return 0.0
        capacity_limit = (self._usable_capacity_kwh - self.soc_kwh) / self._one_way_efficiency
        taken = min(offered_kwh, self._charge_limit_per_quarter, capacity_limit)
        self.soc_kwh += taken * self._one_way_efficiency
        return taken

    def discharge(self, wanted_kwh: float) -> float:
        """Deliver energy to the household. Returns the energy actually delivered."""
        if wanted_kwh <= 0.0:
            return 0.0
        stored_limit = self.soc_kwh * self._one_way_efficiency
        delivered = min(wanted_kwh, self._discharge_limit_per_quarter, stored_limit)
        self.soc_kwh -= delivered / self._one_way_efficiency
        self.throughput_kwh += delivered
        return delivered
