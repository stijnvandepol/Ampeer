"""Derive the facts the rule table judges on.

A rule reads ``context.self_consumption_rate < 0.35``, never a numpy array.
This module is the only place where the two worlds touch: arrays come in,
plain numbers come out. Everything a rule may look at is computed here, so a
rule condition stays readable to somebody who has never seen a simulation.

The two time windows are defined here and nowhere else. A second module with
its own idea of what "evening" means would give no error, only two advices
that disagree.
"""

from __future__ import annotations

import numpy as np

from ampeer_advice.types import AdviceContext, Confidence
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import BatterySpec, EnergyFlows, EVChargingBehaviour, Household, Result

#: Evening and night is 17:00 up to 07:00 local time. It wraps past midnight,
#: which is why ``YearGrid.window_mask`` has two branches. This is the window a battery
#: has to serve: demand while the sun is gone.
EVENING_NIGHT_WINDOW = (17, 7)

#: Midday is 11:00 up to 15:00 local time, the same window
#: ``ampeer_sim.profiles.presence.MIDDAY_WINDOW`` uses, so a load that the
#: presence model moves into the midday window lands in the surplus this module
#: measures.
MIDDAY_WINDOW = (11, 15)


def build_context(
    flows: EnergyFlows,
    household: Household,
    grid: YearGrid,
    result: Result,
    confidence: Confidence,
    dynamic_contract: bool,
    battery: BatterySpec | None = None,
) -> AdviceContext:
    """Reduce one simulated year to the handful of numbers the rules judge on.

    Every energy figure is read off ``flows`` rather than off the household
    input, so the facts describe the year that was actually simulated. The
    metered totals are used, because that is what a supplier bills.
    """
    evening_night = grid.window_mask(EVENING_NIGHT_WINDOW)
    midday = grid.window_mask(MIDDAY_WINDOW)

    # Surplus is production above consumption at that same quarter. Taking
    # ``to_grid`` instead would hide the surplus a battery already absorbed,
    # and the question here is how much energy is going spare at midday, not
    # how much of it currently leaves the property.
    surplus = np.clip(flows.production - flows.consumption, 0.0, None)

    has_battery = battery is not None or bool(
        np.any(flows.battery_charge > 0.0) or np.any(flows.battery_discharge > 0.0)
    )

    return AdviceContext(
        self_consumption_rate=flows.self_consumption_rate,
        annual_production_kwh=float(flows.production.sum()),
        annual_export_kwh=float(flows.total_export.sum()),
        annual_import_kwh=float(flows.total_import.sum()),
        mean_evening_night_consumption_kwh=float(flows.consumption[evening_night].sum())
        / grid.days,
        midday_surplus_kwh=float(surplus[midday].sum()),
        # Nothing has been applied yet on this pass, so the residual equals
        # today's export. advise.py rebuilds the context with the measured
        # figure before the storage rules are evaluated.
        export_after_free_routes_kwh=float(flows.total_export.sum()),
        daytime_occupancy=household.daytime_occupancy,
        has_ev=household.ev is not None,
        ev_charges_on_solar=household.ev is not None
        and household.ev.behaviour is EVChargingBehaviour.SOLAR,
        has_battery=has_battery,
        #: ``EnergyFlows`` does not carry the spec, and reconstructing a
        #: capacity from the charge series would be a guess dressed up as a
        #: measurement, so this stays None unless the caller that owns the spec
        #: hands it over.
        battery_capacity_kwh=battery.capacity_kwh if battery is not None else None,
        dynamic_contract=dynamic_contract,
        headline=result.band,
        confidence=confidence,
    )
