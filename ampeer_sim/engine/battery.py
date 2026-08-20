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
