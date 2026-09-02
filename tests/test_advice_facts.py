from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from ampeer_advice.facts import build_context
from ampeer_advice.types import AdviceContext, Confidence
from ampeer_sim.engine.run import simulate
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Band, Household, ProductionSource, Result

GRID = YearGrid.for_year(2025)


def _result() -> Result:
    return Result(
        engine_version="0.1.0",
        band=Band(Decimal("500"), Decimal("600"), Decimal("700"), runs=81),
        self_consumption_rate=0.3,
        production_source=ProductionSource.FALLBACK,
        profile_year=2025,
        weather_year=2025,
    )


def _context(
    consumption: np.ndarray, production: np.ndarray, **household_kwargs: object
) -> AdviceContext:
    household = Household(postcode4="5401", annual_consumption_kwh=3_500.0, **household_kwargs)  # type: ignore[arg-type]
    flows = simulate(consumption, production)
    return build_context(
        flows=flows,
        household=household,
        grid=GRID,
        result=_result(),
        confidence=Confidence.INDICATIVE,
        dynamic_contract=False,
    )


def test_annual_totals_come_straight_from_the_flows() -> None:
    consumption = np.full(GRID.quarters, 0.1)
    production = np.full(GRID.quarters, 0.2)
    context = _context(consumption, production)
    assert context.annual_production_kwh == pytest.approx(production.sum())
    assert context.annual_export_kwh == pytest.approx(
        float(simulate(consumption, production).to_grid.sum())
    )


def test_evening_and_night_consumption_is_a_daily_mean_over_17_to_07() -> None:
    consumption = np.zeros(GRID.quarters)
    evening_or_night = (GRID.local_hour >= 17) | (GRID.local_hour < 7)
    consumption[evening_or_night] = 0.25
    context = _context(consumption, np.zeros(GRID.quarters))
    # 14 hours times 4 quarters times 0.25 kWh is 14 kWh a day.
    assert context.mean_evening_night_consumption_kwh == pytest.approx(14.0, rel=1e-3)


def test_midday_surplus_counts_only_production_above_consumption() -> None:
    consumption = np.full(GRID.quarters, 0.05)
    production = np.zeros(GRID.quarters)
    production[(GRID.local_hour >= 11) & (GRID.local_hour < 15)] = 0.30
    context = _context(consumption, production)
    midday_quarters = int(((GRID.local_hour >= 11) & (GRID.local_hour < 15)).sum())
    assert context.midday_surplus_kwh == pytest.approx(midday_quarters * 0.25, rel=1e-6)


def test_household_facts_are_copied_so_rules_never_touch_arrays() -> None:
    context = _context(np.full(GRID.quarters, 0.1), np.zeros(GRID.quarters), daytime_occupancy=True)
    assert context.daytime_occupancy is True
    assert context.has_ev is False
    assert context.has_battery is False


def test_an_ev_charging_on_solar_is_reported_as_such() -> None:
    from ampeer_sim.types import EV, EVChargingBehaviour

    context = _context(
        np.full(GRID.quarters, 0.1),
        np.zeros(GRID.quarters),
        ev=EV(behaviour=EVChargingBehaviour.SOLAR),
    )
    assert context.has_ev is True
    assert context.ev_charges_on_solar is True


def test_the_headline_band_and_confidence_are_passed_through() -> None:
    context = _context(np.full(GRID.quarters, 0.1), np.zeros(GRID.quarters))
    assert context.headline.p50_eur == Decimal("600")
    assert context.confidence is Confidence.INDICATIVE
