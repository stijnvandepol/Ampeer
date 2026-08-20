"""The composition root: answers in, ``Result`` out.

This is the only module that knows about every other one. It performs no I/O
itself; providers do that.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import numpy as np

from ampeer_sim import ENGINE_VERSION
from ampeer_sim.economics.sensitivity import band_from_differences, is_central, variation_grid
from ampeer_sim.economics.tariffs import compare
from ampeer_sim.engine.run import simulate
from ampeer_sim.engine.strategies import build_plans
from ampeer_sim.production.model import production_series
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.providers import ProductionProvider, ProfileProvider
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
    BatterySpec,
    Household,
    MoneyResult,
    PVSystem,
    Result,
    Strategy,
    TariffSet,
)

#: The most recent PVGIS SARAH3 weather year we rely on.
DEFAULT_WEATHER_YEAR = 2023


def _apply_variations(
    household: Household,
    pv_system: PVSystem,
    tariffs: TariffSet,
    factors: dict[str, float],
) -> tuple[Household, PVSystem, TariffSet]:
    """Return the inputs with every uncertain value moved by its factor.

    Combined rather than one at a time, because a band whose runs each hold
    three of four assumptions at their central value can never reach its own
    corners.
    """
    for name, factor in factors.items():
        if name == "annual_consumption_kwh":
            household = dataclasses.replace(
                household, annual_consumption_kwh=household.annual_consumption_kwh * factor
            )
        elif name == "shiftable_block_kwh":
            household = dataclasses.replace(
                household, shiftable_block_kwh=household.shiftable_block_kwh * factor
            )
        elif name == "system_loss_fraction":
            pv_system = dataclasses.replace(
                pv_system,
                system_loss_fraction=min(pv_system.system_loss_fraction * factor, 0.99),
            )
        elif name == "feed_in_price":
            tariffs = dataclasses.replace(
                tariffs, feed_in_price=tariffs.feed_in_price * Decimal(repr(factor))
            )
        else:
            raise ValueError(f"unknown variation {name!r}")
    return household, pv_system, tariffs


def run_advice(
    household: Household,
    pv_system: PVSystem,
    baseline: TariffSet,
    scenario: TariffSet,
    grid: YearGrid,
    profile_provider: ProfileProvider,
    production_provider: ProductionProvider,
    battery_spec: BatterySpec | None = None,
    strategy: Strategy = Strategy.SELF_CONSUMPTION,
    prices_per_quarter: np.ndarray | None = None,
    weather_year: int = DEFAULT_WEATHER_YEAR,
) -> Result:
    """Run the central case plus every variation and return a ``Result``.

    The providers are asked once. Everything the variations touch is applied
    afterwards, which is what keeps the full factorial sensitivity analysis
    inside the two second budget and down to a single network call.
    """
    fractions = profile_provider.fractions(grid.year, household.profile_category)
    hourly_production, temperature, source = production_provider.hourly_series(
        household.postcode4, pv_system.azimuth_deg, pv_system.tilt_deg
    )

    charge_plan, discharge_plan = (
        build_plans(strategy, battery_spec, prices_per_quarter, grid)
        if battery_spec is not None
        else (None, None)
    )

    def one_run(
        run_household: Household, run_system: PVSystem, run_scenario: TariffSet
    ) -> tuple[MoneyResult, float]:
        production = production_series(
            hourly_production, run_system, grid, weather_year=weather_year
        )
        consumption = compose_consumption(
            run_household,
            grid,
            fractions,
            temperature,
            weather_year=weather_year,
            production_kwh=production,
        )
        flows = simulate(
            consumption,
            production,
            battery_spec=battery_spec,
            charge_plan=charge_plan,
            discharge_plan=discharge_plan,
        )
        money = compare(flows, baseline, run_scenario, prices_per_quarter)
        return money, flows.self_consumption_rate

    differences: list[Decimal] = []
    central_money: MoneyResult | None = None
    central_rate = 0.0

    for factors in variation_grid():
        money, rate = one_run(*_apply_variations(household, pv_system, scenario, factors))
        differences.append(money.difference_eur)
        if is_central(factors):
            central_money, central_rate = money, rate

    if central_money is None:  # pragma: no cover - the grid always holds the centre
        raise RuntimeError("the variation grid did not contain a central case")

    return Result(
        engine_version=ENGINE_VERSION,
        band=band_from_differences(differences),
        self_consumption_rate=central_rate,
        production_source=source,
        profile_year=grid.year,
        weather_year=weather_year,
        scenarios={"no_intervention": central_money},
    )
