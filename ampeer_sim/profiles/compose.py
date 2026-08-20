"""Assemble the gross household consumption series.

The order of the steps is part of the model, not an implementation detail:
scale, shift for presence, add assets, and only then charge the EV on whatever
surplus is left.

Presence acts on the base shape alone. The shiftable block is a washing machine
and a dishwasher, and those are already inside the NEDU average. Nobody shifts a
heat pump by hand, so shifting one here would model advice we do not give.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.profiles.assets import (
    ev_grid_topup,
    ev_profile,
    ev_solar_profile,
    heat_pump_profile,
)
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
        from_sun = ev_solar_profile(household.ev, grid, surplus_kwh=surplus)
        series = series + from_sun + ev_grid_topup(household.ev, grid, from_sun)

    return series
