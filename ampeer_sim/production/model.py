"""Scale a per-kWp production series onto the quarter grid.

The photovoltaic physics is not modelled here. PVGIS already accounts for
module temperature, reflection and spectral response, and reimplementing that
badly cost about ten percent when it was measured on 2026-08-20. What remains
here is linear: array size, system losses and ageing.
"""

from __future__ import annotations

import numpy as np

from ampeer_sim.timebase import QUARTERS_PER_HOUR, YearGrid
from ampeer_sim.types import PVSystem

#: Annual output loss of a crystalline panel, as a fraction.
DEGRADATION_PER_YEAR = 0.005

#: Never model a panel as worse than this, however old it is.
MAX_DEGRADATION = 0.20


def degradation_factor(install_year: int | None, reference_year: int) -> float:
    """Remaining output share of a panel of a given age."""
    if install_year is None:
        return 1.0
    age = max(0, reference_year - install_year)
    return 1.0 - min(age * DEGRADATION_PER_YEAR, MAX_DEGRADATION)


def production_series(
    production_w_per_kwp: np.ndarray,
    system: PVSystem,
    grid: YearGrid,
    weather_year: int,
    reference_year: int | None = None,
) -> np.ndarray:
    """Return production in kWh per quarter.

    Every factor applied here is linear, so interpolating first and scaling
    afterwards gives the same answer as the reverse. That was not true while we
    converted irradiance to power ourselves, which is why the spec argued about
    the order; the argument no longer applies now the conversion is gone.
    """
    aligned = grid.align_hourly_year(production_w_per_kwp, weather_year=weather_year)
    quarterly_w_per_kwp = grid.hourly_to_quarters(aligned)

    rated_kw = system.peak_power_wp / 1_000.0
    loss = 1.0 - system.system_loss_fraction
    aging = degradation_factor(system.install_year, reference_year or grid.year)

    power_kw = quarterly_w_per_kwp / 1_000.0 * rated_kw * loss * aging
    return power_kw / QUARTERS_PER_HOUR
