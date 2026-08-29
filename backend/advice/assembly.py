"""Nine answers into the objects the engine takes.

This is the file where a question nobody answered becomes a default, which
makes it the file where an invented input would enter. Every default here is
either already documented in ampeer_sim as a national average, or an explicit
absence: `ev=None` says we were not told, and the engine treats it that way.
Nothing here guesses a value and presents it as an answer.

`build_year` at the bottom is here for the same reason and not despite it. The
provenance stamped on a quarter-hour series is a statement about where the
inputs came from, and this is the file that knows: in this phase they were
typed into a form and scaled onto a national profile, so the series is
synthetic as a matter of fact rather than as a default nobody overrode.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from advice.series import SYNTHETIC, EncodedYear, encode_year

# BATTERY_C_RATE below is charge and discharge power as a fraction of capacity.
# Domestic batteries ship at roughly 0.5C, a 5 kWh unit at 2.2 kW and a 13.5 kWh
# unit at 5 kW, so the power is derived from the capacity rather than asked:
# nobody knows their inverter rating. It is a property of the hardware class and
# not a guess about this household.
#
# Imported rather than written down again. ampeer_advice.advise sizes the
# capacity curve for the battery this household could buy with exactly this
# rate, and a second copy of one hardware assumption is two numbers that can
# drift apart while the response keeps presenting them as one battery.
from ampeer_advice.advise import BATTERY_C_RATE
from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs
from ampeer_sim.types import (
    EV,
    BatterySpec,
    EnergyFlows,
    EVChargingBehaviour,
    HeatPump,
    Household,
    PVSystem,
    TariffSet,
)

__all__ = [
    "BATTERY_C_RATE",
    "build_battery_spec",
    "build_household",
    "build_pv_system",
    "build_tariffs",
    "build_year",
    "year_series",
]


def build_household(data: dict[str, Any]) -> Household:
    ev = (
        EV(behaviour=EVChargingBehaviour[data["ev_behaviour"]])
        if data.get("has_ev") and data.get("ev_behaviour")
        else None
    )
    heat_pump = (
        HeatPump(heat_demand_kwh=float(data["heat_demand_kwh"]))
        if data.get("has_heat_pump") and data.get("heat_demand_kwh")
        else None
    )
    return Household(
        postcode4=data["postcode4"],
        annual_consumption_kwh=float(data["annual_consumption_kwh"]),
        # Round one does not ask. False is the dataclass default and also the
        # conservative direction: assuming somebody is home would raise their
        # self-consumption rate and understate the shock.
        daytime_occupancy=bool(data.get("daytime_occupancy", False)),
        ev=ev,
        heat_pump=heat_pump,
    )


def build_pv_system(data: dict[str, Any]) -> PVSystem:
    return PVSystem(
        peak_power_wp=int(data["peak_power_wp"]),
        azimuth_deg=float(data["azimuth_deg"]),
        tilt_deg=float(data["tilt_deg"]),
    )


def build_battery_spec(data: dict[str, Any]) -> BatterySpec | None:
    """The battery this household already owns, if any.

    This is not the battery the advice sizes. That one comes from the capacity
    curve in ampeer_advice.battery and is chosen, not reported.
    """
    if not data.get("has_battery") or not data.get("battery_capacity_kwh"):
        return None
    capacity = float(data["battery_capacity_kwh"])
    power = capacity * BATTERY_C_RATE
    return BatterySpec(capacity_kwh=capacity, max_charge_kw=power, max_discharge_kw=power)


def build_tariffs(data: dict[str, Any]) -> tuple[TariffSet, TariffSet, TariffSet]:
    """Return (baseline, scenario, alternative_contract_scenario).

    The third set is the 2027 regime priced on the contract this household does
    not have. It is built for everybody, including a household that already has
    a dynamic contract: the rule that compares the two has to be able to say
    that switching back would be better, and it cannot say that from one tariff
    set.

    The two are told apart by their prices and not by ``TariffSet.dynamic``,
    which stays False on both. That flag means "price this against an hourly
    price series", and ampeer_advice.tariffs holds no such series: it models a
    dynamic contract by its average net price over the solar hours.
    """
    dynamic_requested = bool(data.get("dynamic_contract", False))
    return (
        baseline_tariffs(),
        scenario_2027_tariffs(dynamic=dynamic_requested),
        scenario_2027_tariffs(dynamic=not dynamic_requested),
    )


def year_series(flows: EnergyFlows) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The three series the wire carries, read out of the engine's own flows.

    Returned in the encoder's argument order: what the household used of its
    own production, what went to the grid and what came off it, in kWh per
    quarter.

    Two readings were available for the second and third and they are not the
    same statement. `from_grid` and `to_grid` are what this household took and
    fed in for its own sake; `total_import` and `total_export` add the energy a
    battery moved across the meter for price reasons. The meter is what this
    byte is named after and what a bill is written from, so the meter is what
    it carries. Measured on 2026-08-27: identical today, to the last bit, on
    every path this service runs, because `build_battery_spec` leaves
    `allow_grid_charging` at its default of False and `ampeer_advice.advise`
    passes no charge or discharge plan, so `grid_charge` and `grid_discharge`
    are zero in all 35040 quarters. The choice only starts to matter when
    price-driven trading arrives, and on that day drawing `from_grid` would
    show a plate that disagrees with the bill beside it.

    `own` is direct use and deliberately not direct use plus battery discharge.
    `EnergyFlows.self_consumption_rate` gives the reason in full: discharged
    energy has already paid the round trip loss, and with grid charging it
    contains kilowatt hours this roof never made. The visible consequence is
    that on a quarter where a battery discharges, `own` plus `grid` is less
    than what the household consumed, which is true rather than tidy.
    """
    return flows.self_consumption, flows.total_export, flows.total_import


def build_year(flows: EnergyFlows) -> EncodedYear:
    """One household's simulated year, packed for the wire and stamped.

    The stamp is not a parameter. Everything this phase can produce is built
    from a national NEDU profile scaled to a figure somebody typed into a form,
    plus modelled assets, so `SYNTHETIC` is a description of the input and
    there is no branch here that could honestly write anything else. A caller
    able to pass `MEASURED` would be a caller able to claim a meter reading for
    a series that came out of a standard profile, which is the mistake this
    field exists to make impossible.

    Phase 2 changes what reaches this function and not what this function
    says. A measured series arrives through the meter coupling, which is a
    different source and belongs in a builder that knows about it;
    `advice.serializers.year_field` is where the two meet, and it is where the
    refusal to serve a measured series over a shareable token lives.
    """
    return encode_year(*year_series(flows), provenance=SYNTHETIC)
