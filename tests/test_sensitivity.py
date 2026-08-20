from __future__ import annotations

import time
from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.economics.sensitivity import VARIATIONS, band_from_differences, variation_grid
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.simulate import run_advice
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
    Household,
    ProductionSource,
    ProfileCategory,
    PVSystem,
    Result,
    TariffSet,
)

GRID = YearGrid.for_year(2025)


class _FlatProfileProvider:
    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


BASELINE = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.27"),
    standing_charge_year=Decimal("120.00"),
    net_metering=True,
)
SCENARIO = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.05"),
    feed_in_fixed_cost_year=Decimal("90.00"),
    standing_charge_year=Decimal("120.00"),
)


def _advice(**overrides: object) -> Result:
    kwargs: dict[str, object] = {
        "household": Household(postcode4="5401", annual_consumption_kwh=3_500.0),
        "pv_system": PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35),
        "baseline": BASELINE,
        "scenario": SCENARIO,
        "grid": GRID,
        "profile_provider": _FlatProfileProvider(),
        "production_provider": FallbackProvider(2025),
        "weather_year": 2025,
    }
    kwargs.update(overrides)
    return run_advice(**kwargs)  # type: ignore[arg-type]


def test_band_is_ordered() -> None:
    band = band_from_differences([Decimal(str(value)) for value in range(100)])
    assert band.p10_eur <= band.p50_eur <= band.p90_eur
    assert band.runs == 100


def test_band_rejects_an_empty_run_set() -> None:
    with pytest.raises(ValueError, match="at least one"):
        band_from_differences([])


def test_there_is_more_than_one_variation() -> None:
    assert len(VARIATIONS) >= 4


def test_every_variation_moves_its_input_in_both_directions() -> None:
    for variation in VARIATIONS:
        assert variation.low < 1.0 < variation.high


def test_the_variation_grid_reaches_its_own_corners() -> None:
    grid = variation_grid()
    assert len(grid) == 3 ** len(VARIATIONS)
    all_low = {variation.name: variation.low for variation in VARIATIONS}
    all_high = {variation.name: variation.high for variation in VARIATIONS}
    assert all_low in grid
    assert all_high in grid


def test_run_advice_returns_a_result_with_a_measured_band() -> None:
    result = _advice()
    assert result.engine_version
    assert result.band.runs == 3 ** len(VARIATIONS)
    assert result.band.p10_eur < result.band.p90_eur
    assert result.production_source is ProductionSource.FALLBACK


def test_the_headline_figure_is_a_cost_increase() -> None:
    assert _advice().band.p50_eur > 0


def test_the_headline_figure_is_plausible_for_a_dutch_household() -> None:
    """A 3500 kWh household with 3.5 kWp should lose a few hundred euro a year."""
    band = _advice().band
    assert Decimal("300") < band.p50_eur < Decimal("1200")


def test_self_consumption_rate_is_a_fraction() -> None:
    assert 0.0 <= _advice().self_consumption_rate <= 1.0


def test_a_bigger_array_loses_more_when_net_metering_ends() -> None:
    small = _advice(pv_system=PVSystem(peak_power_wp=2_000, azimuth_deg=0, tilt_deg=35))
    large = _advice(pv_system=PVSystem(peak_power_wp=6_000, azimuth_deg=0, tilt_deg=35))
    assert large.band.p50_eur > small.band.p50_eur


def test_the_result_records_which_years_it_used() -> None:
    result = _advice()
    assert result.profile_year == 2025
    assert result.weather_year == 2025


def test_a_full_run_finishes_within_the_time_budget() -> None:
    started = time.perf_counter()
    _advice()
    assert time.perf_counter() - started < 2.0
