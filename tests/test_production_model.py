from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import PVGIS_STAMP_MINUTES_PAST_HOUR
from ampeer_sim.timebase import MINUTES_PER_QUARTER, QUARTERS_PER_HOUR, YearGrid
from ampeer_sim.types import PVSystem


def _flat_production(grid: YearGrid, w_per_kwp: float) -> np.ndarray:
    """An hourly series in watts per installed kWp, before system losses."""
    return np.full(grid.hours, w_per_kwp)


def test_rated_output_yields_rated_power_minus_losses() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, system_loss_fraction=0.14)
    series = production_series(_flat_production(grid, 1_000.0), system, grid, weather_year=2025)
    # 1000 W per kWp times 4 kWp, 14 percent loss, a quarter of an hour per step.
    assert series[0] == pytest.approx(4.0 * 0.86 * 0.25)


def test_darkness_yields_nothing() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35)
    series = production_series(_flat_production(grid, 0.0), system, grid, weather_year=2025)
    assert series.sum() == pytest.approx(0.0)


def test_output_scales_linearly_with_array_size() -> None:
    grid = YearGrid.for_year(2025)
    small = PVSystem(peak_power_wp=2_000, azimuth_deg=0, tilt_deg=35)
    large = PVSystem(peak_power_wp=6_000, azimuth_deg=0, tilt_deg=35)
    production = _flat_production(grid, 500.0)
    assert production_series(production, large, grid, weather_year=2025).sum() == pytest.approx(
        3 * production_series(production, small, grid, weather_year=2025).sum()
    )


def test_series_lands_on_the_quarter_grid() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35)
    series = production_series(_flat_production(grid, 500.0), system, grid, weather_year=2025)
    assert series.shape == (grid.quarters,)


def test_a_leap_weather_year_is_aligned_onto_a_non_leap_grid() -> None:
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35)
    series = production_series(np.full(8_784, 500.0), system, grid, weather_year=2024)
    assert series.shape == (grid.quarters,)


def test_degradation_reduces_output_for_an_older_system() -> None:
    grid = YearGrid.for_year(2025)
    fresh = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2025)
    aged = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2015)
    production = _flat_production(grid, 800.0)
    fresh_total = production_series(production, fresh, grid, weather_year=2025).sum()
    aged_total = production_series(production, aged, grid, weather_year=2025).sum()
    assert aged_total == pytest.approx(fresh_total * 0.95)


def test_degradation_is_capped() -> None:
    grid = YearGrid.for_year(2025)
    ancient = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=1960)
    fresh = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2025)
    production = _flat_production(grid, 800.0)
    ratio = (
        production_series(production, ancient, grid, weather_year=2025).sum()
        / production_series(production, fresh, grid, weather_year=2025).sum()
    )
    assert ratio == pytest.approx(0.80)


def test_the_model_places_hour_i_at_hour_i_and_moves_nothing_in_time() -> None:
    """Where the time base repair of 2026-08-27 deliberately did not go.

    PVGIS answers in UTC and the grid runs in continuous winter time, which is
    UTC plus one, and until that date nothing converted between them. The
    conversion went into the provider, because "PVGIS stamps in UTC" is a fact
    about PVGIS and this function is handed a bare array with no idea where it
    came from. A shift here would also have moved the offline shape, which is
    built in winter time already.

    So this pins the other half of that decision: whatever a provider hands
    over arrives on the grid in the hour it was given in. A single non-zero
    hour in an otherwise dark year stays inside that hour and does not lean
    into its neighbours' hours; where inside it the value sits is the anchor's
    business, and the assertion reads that from the same constant the model
    does rather than repeating it.

    Its centre and not its four quarters, because interpolation is a thing this
    function does on purpose. An hourly value is the mean of its hour, so a lone
    spike is spread across the neighbouring hours too: three quarters of it stays
    inside the hour and the rest leans into 10:00 and 12:00, symmetrically. What
    a shift would move, and interpolation does not, is the centre.

    The hour is 11:00, which is the one the defect moved things off, and 216 is
    an arbitrary day chosen so that the check is not accidentally about the
    first day of the year.
    """
    grid = YearGrid.for_year(2025)
    system = PVSystem(peak_power_wp=1_000, azimuth_deg=0, tilt_deg=35, system_loss_fraction=0.0)
    hourly = np.zeros(grid.hours)
    hourly[216 * 24 + 11] = 1_000.0

    series = production_series(hourly, system, grid, weather_year=2025)
    day = series[216 * 96 : 217 * 96]
    assert day.sum() == pytest.approx(series.sum(), rel=1e-12), (
        "the model moved energy into another day"
    )
    centre = float((np.arange(day.size) * day).sum() / day.sum())
    # Where inside its hour the value sits, in quarters. A quarter names the
    # quarter hour that starts at it, so its own middle is 7.5 minutes along,
    # and a value stamped `anchor` minutes past its hour lands that difference
    # further on.
    #
    # This was written as a flat 1.5 until 2026-08-29, which is the middle of
    # the hour and was right while every series was read as an hour mean. The
    # anchor became an argument on 2026-08-27 and defaults to PVGIS's stamp, so
    # the expected offset is now 0.1667 and not 1.5. Derived rather than
    # restated, because the two have to move together: a test carrying its own
    # copy of the convention is a test that passes after the convention changes.
    offset = (PVGIS_STAMP_MINUTES_PAST_HOUR - MINUTES_PER_QUARTER / 2) / MINUTES_PER_QUARTER
    assert centre == pytest.approx(11 * QUARTERS_PER_HOUR + offset, abs=1e-9), (
        f"the hour was handed over as 11:00 and arrived centred on quarter {centre:.2f}, "
        f"which is {centre / QUARTERS_PER_HOUR:.2f} on the grid's clock"
    )


def test_an_unknown_install_year_means_no_degradation() -> None:
    grid = YearGrid.for_year(2025)
    unknown = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=None)
    fresh = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2025)
    production = _flat_production(grid, 800.0)
    assert production_series(production, unknown, grid, weather_year=2025).sum() == pytest.approx(
        production_series(production, fresh, grid, weather_year=2025).sum()
    )
