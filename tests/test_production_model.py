from __future__ import annotations

import numpy as np
import pytest

from ampeer_sim.production.model import production_series
from ampeer_sim.timebase import YearGrid
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


def test_an_unknown_install_year_means_no_degradation() -> None:
    grid = YearGrid.for_year(2025)
    unknown = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=None)
    fresh = PVSystem(peak_power_wp=4_000, azimuth_deg=0, tilt_deg=35, install_year=2025)
    production = _flat_production(grid, 800.0)
    assert production_series(production, unknown, grid, weather_year=2025).sum() == pytest.approx(
        production_series(production, fresh, grid, weather_year=2025).sum()
    )
