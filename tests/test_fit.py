"""The measured fit, held against data whose answer is known.

Every case here builds its window by running the real pipeline at a known
annual consumption and then reading the meter off it. That is what makes the
first test evidence rather than decoration: the figure the fit has to find is
one this file chose, and a fit that simply echoed the typed figure back would
fail it by the whole distance between the two.
"""

from __future__ import annotations

import numpy as np
import pytest

import ampeer_sim.fit as fit_module
from ampeer_sim.economics.sensitivity import VARIATIONS
from ampeer_sim.engine.run import simulate
from ampeer_sim.fit import (
    BRACKET_HIGH_FACTOR,
    MIN_WEEKS,
    QUARTERS_PER_WEEK,
    ConsumptionFit,
    MeasuredWindow,
    fit_annual_consumption,
)
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Household, ProfileCategory, PVSystem

WEATHER_YEAR = 2023
GRID = YearGrid.for_year(2025)

#: The figure every window below is generated at, and the one the fit has to
#: recover without being told.
TRUE_ANNUAL_KWH = 4000.0

#: Eight whole weeks from the first quarter of the year. Enough for the
#: leave-one-week-out band to have something to leave out.
WINDOW_WEEKS = 8


class FlatProfiles:
    """The same featureless provider the other pure tests use."""

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


def _household(annual_kwh: float) -> Household:
    return Household(postcode4="5401", annual_consumption_kwh=annual_kwh, daytime_occupancy=False)


SYSTEM = PVSystem(peak_power_wp=3500, azimuth_deg=0.0, tilt_deg=35.0)


def _year_flows(annual_kwh: float) -> tuple[np.ndarray, np.ndarray]:
    """Run the real pipeline once and hand back both meter series."""
    household = _household(annual_kwh)
    hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
        household.postcode4, SYSTEM.azimuth_deg, SYSTEM.tilt_deg
    )
    production = production_series(hourly, SYSTEM, GRID, weather_year=WEATHER_YEAR)
    consumption = compose_consumption(
        household,
        GRID,
        FlatProfiles().fractions(GRID.year, household.profile_category),
        temperature,
        weather_year=WEATHER_YEAR,
        production_kwh=production,
    )
    flows = simulate(consumption, production)
    return flows.total_import, flows.total_export


def _window(weeks: int = WINDOW_WEEKS, annual_kwh: float = TRUE_ANNUAL_KWH) -> MeasuredWindow:
    imported, exported = _year_flows(annual_kwh)
    index = np.arange(weeks * QUARTERS_PER_WEEK, dtype=np.int64)
    return MeasuredWindow(
        quarter_index=index,
        offtake_kwh=imported[index],
        feed_in_kwh=exported[index],
    )


def _fit(typed_kwh: float, window: MeasuredWindow | None = None) -> ConsumptionFit | None:
    return fit_annual_consumption(
        household=_household(typed_kwh),
        pv_system=SYSTEM,
        grid=GRID,
        window=_window() if window is None else window,
        profile_provider=FlatProfiles(),
        production_provider=FallbackProvider(WEATHER_YEAR),
        weather_year=WEATHER_YEAR,
    )


def test_the_fit_recovers_a_figure_the_typed_one_is_thirty_percent_below() -> None:
    """The test that makes the rest of this file worth running.

    The household types 2800 and the meter was generated at 4000. A fit that
    returned the typed figure, or anything anchored to it, misses by 1200 kWh.
    """
    fit = _fit(TRUE_ANNUAL_KWH * 0.7)
    assert fit is not None
    assert fit.p50_kwh == pytest.approx(TRUE_ANNUAL_KWH, rel=0.01)
    assert fit.contradicts(TRUE_ANNUAL_KWH * 0.7)


def test_the_fit_recovers_the_same_figure_from_thirty_percent_above() -> None:
    """The other side, so the answer is the meter's and not the bracket's."""
    fit = _fit(TRUE_ANNUAL_KWH * 1.3)
    assert fit is not None
    assert fit.p50_kwh == pytest.approx(TRUE_ANNUAL_KWH, rel=0.01)


def test_a_typed_figure_the_meter_agrees_with_is_not_contradicted() -> None:
    """Silence is an answer, and this is the case that has to produce it."""
    fit = _fit(TRUE_ANNUAL_KWH)
    assert fit is not None
    assert not fit.contradicts(TRUE_ANNUAL_KWH)


def test_a_discrepancy_inside_the_models_own_uncertainty_is_not_reported() -> None:
    """The floor, from the side that has to stay quiet.

    ``economics.sensitivity`` moves annual consumption by a tenth either way
    when it builds the euro band, because the figure people type is rarely
    exact. A five percent disagreement is inside that, so the euro band already
    treats it as noise and this must not announce it as a finding.
    """
    fit = _fit(TRUE_ANNUAL_KWH * 0.95)
    assert fit is not None
    assert not fit.contradicts(TRUE_ANNUAL_KWH * 0.95)


def test_a_discrepancy_outside_it_is_reported() -> None:
    """And from the side that has to speak, so the floor is not a mute button."""
    fit = _fit(TRUE_ANNUAL_KWH * 0.85)
    assert fit is not None
    assert fit.contradicts(TRUE_ANNUAL_KWH * 0.85)


def test_the_band_never_sits_inside_the_sensitivity_grids_own_spread() -> None:
    """Pinned to the source rather than to the numbers 0.9 and 1.1.

    If the sensitivity grid ever widens what it believes about a typed annual
    figure, this floor widens with it. A copied constant here would let the two
    disagree silently, and the correction would start reporting differences the
    euro band still calls noise.
    """
    low, high = next((v.low, v.high) for v in VARIATIONS if v.name == "annual_consumption_kwh")
    fit = _fit(TRUE_ANNUAL_KWH)
    assert fit is not None
    assert fit.p10_kwh <= fit.p50_kwh * low
    assert fit.p90_kwh >= fit.p50_kwh * high


def test_too_few_weeks_returns_nothing_rather_than_a_number() -> None:
    """A band drawn through two refits would be a percentage in disguise."""
    assert _fit(TRUE_ANNUAL_KWH, window=_window(weeks=MIN_WEEKS - 1)) is None


def test_a_meter_outside_the_bracket_returns_nothing() -> None:
    """Not a clamped edge value, which would read as a real answer."""
    typed = TRUE_ANNUAL_KWH / (BRACKET_HIGH_FACTOR * 2.0)
    assert _fit(typed) is None


def test_a_gap_costs_coverage_and_not_energy() -> None:
    """Half the quarters removed must not move the answer, only its weight."""
    full = _window()
    keep = np.arange(full.quarter_index.size) % 2 == 0
    holed = MeasuredWindow(
        quarter_index=full.quarter_index[keep],
        offtake_kwh=full.offtake_kwh[keep],
        feed_in_kwh=full.feed_in_kwh[keep],
    )
    fit = _fit(TRUE_ANNUAL_KWH * 0.7, window=holed)
    assert fit is not None
    assert fit.p50_kwh == pytest.approx(TRUE_ANNUAL_KWH, rel=0.02)
    assert fit.quarters_used == int(keep.sum())


def test_the_export_deviation_reports_the_observable_the_fit_did_not_use() -> None:
    """Import is fitted, so export is left free to disagree and to say so."""
    fit = _fit(TRUE_ANNUAL_KWH * 0.7)
    assert fit is not None
    assert fit.export_deviation.label == "feed_in"
    assert fit.export_deviation.within(0.05)


def test_a_window_refuses_arrays_that_do_not_line_up() -> None:
    with pytest.raises(ValueError, match="same length"):
        MeasuredWindow(
            quarter_index=np.array([0, 1], dtype=np.int64),
            offtake_kwh=np.array([0.1]),
            feed_in_kwh=np.array([0.0, 0.0]),
        )


def test_a_window_refuses_quarters_out_of_order() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        MeasuredWindow(
            quarter_index=np.array([5, 5], dtype=np.int64),
            offtake_kwh=np.array([0.1, 0.1]),
            feed_in_kwh=np.array([0.0, 0.0]),
        )


def test_the_iteration_cap_returns_nothing_rather_than_a_half_bisected_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap exists to refuse, and an untested refusal is a guess.

    One iteration cannot narrow a twenty-five fold bracket to a kilowatt hour,
    so this is the path where the objective has stopped behaving. It must hand
    back nothing: a midpoint after one halving is a number with no claim on it
    at all, and it would read exactly like a fitted one.
    """
    monkeypatch.setattr("ampeer_sim.fit.MAX_ITERATIONS", 1)
    assert _fit(TRUE_ANNUAL_KWH * 0.7) is None


def test_a_refit_that_fails_takes_the_whole_band_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reached here by force, because the data cannot reach it.

    Every leave-one-week-out refit sits on the same bracket as the full fit, so
    in practice they converge whenever it does. The guard is still the
    difference between a band measured over three refits and a band measured
    over one, and this is the only way to run it.
    """
    calls: list[int] = []
    real = fit_module._fit_one

    def once(*args: object, **kwargs: object) -> float | None:
        calls.append(1)
        return real(*args, **kwargs) if len(calls) == 1 else None  # type: ignore[arg-type]

    monkeypatch.setattr("ampeer_sim.fit._fit_one", once)
    assert _fit(TRUE_ANNUAL_KWH * 0.7) is None


def test_the_floor_refuses_a_sensitivity_grid_that_stopped_varying_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the grid drops this input, the floor has nothing to stand on.

    Failing loudly is the point. Quietly falling back to a literal tenth would
    leave the band claiming a source it no longer has.
    """
    monkeypatch.setattr("ampeer_sim.fit.VARIATIONS", ())
    with pytest.raises(ValueError, match="no longer varies"):
        _fit(TRUE_ANNUAL_KWH * 0.7)


def test_the_floor_finds_its_variation_by_name_and_not_by_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It happens to be first in the grid today, and that is not a contract."""
    reordered = tuple(sorted(VARIATIONS, key=lambda v: v.name != "shiftable_block_kwh"))
    assert reordered[0].name == "shiftable_block_kwh"
    monkeypatch.setattr("ampeer_sim.fit.VARIATIONS", reordered)
    fit = _fit(TRUE_ANNUAL_KWH)
    assert fit is not None
    assert fit.p10_kwh < fit.p50_kwh < fit.p90_kwh
