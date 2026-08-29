"""Turning nine answers into the objects the engine takes.

This is where a missing answer becomes a default, so it is where a default can
quietly become an invented input. Every default below is either a documented
national average that already lives in ampeer_sim, or an explicit 'we were not
told', never a guess dressed as an answer.
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from typing import Any

import numpy as np
import pytest

from advice.assembly import (
    build_battery_spec,
    build_household,
    build_pv_system,
    build_tariffs,
    build_year,
    year_series,
)
from advice.series import MEASURED, SYNTHETIC
from ampeer_sim.types import EnergyFlows, EVChargingBehaviour, ProfileCategory

ESTIMATE: dict[str, Any] = {
    "postcode4": "5401",
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "annual_consumption_kwh": 3500.0,
}

REFINE: dict[str, Any] = ESTIMATE | {
    "daytime_occupancy": True,
    "has_ev": True,
    "ev_behaviour": "NIGHT",
    "has_heat_pump": True,
    "heat_demand_kwh": 6000.0,
    "dynamic_contract": True,
    "has_battery": True,
    "battery_capacity_kwh": 10.0,
}


def test_an_estimate_becomes_a_household_with_nothing_assumed_about_the_extras() -> None:
    household = build_household(ESTIMATE)
    assert household.postcode4 == "5401"
    assert household.annual_consumption_kwh == 3500.0
    assert household.ev is None
    assert household.heat_pump is None
    assert household.profile_category is ProfileCategory.E1A


def test_a_household_that_was_not_asked_is_not_assumed_to_be_home() -> None:
    """Round one never asks. False here is the model's stated default and it is
    also the conservative direction: a household assumed to be home would show
    a higher self-consumption rate and a smaller shock than it will get."""
    assert build_household(ESTIMATE).daytime_occupancy is False


def test_a_refine_carries_every_answer_into_the_household() -> None:
    household = build_household(REFINE)
    assert household.daytime_occupancy is True
    assert household.ev is not None
    assert household.ev.behaviour is EVChargingBehaviour.NIGHT
    assert household.heat_pump is not None
    assert household.heat_pump.heat_demand_kwh == 6000.0


def test_saying_no_to_an_asset_leaves_it_out_entirely() -> None:
    household = build_household(REFINE | {"has_ev": False, "ev_behaviour": None})
    assert household.ev is None


def test_saying_no_to_a_heat_pump_leaves_it_out_entirely() -> None:
    household = build_household(REFINE | {"has_heat_pump": False, "heat_demand_kwh": None})
    assert household.heat_pump is None


def test_the_roof_becomes_a_pv_system() -> None:
    system = build_pv_system(ESTIMATE)
    assert system.peak_power_wp == 3500
    assert system.azimuth_deg == 0.0
    assert system.tilt_deg == 35.0


def test_a_household_without_a_battery_gets_no_battery_spec() -> None:
    assert build_battery_spec(ESTIMATE) is None
    assert build_battery_spec(REFINE | {"has_battery": False, "battery_capacity_kwh": None}) is None


def test_an_existing_battery_gets_a_spec_scaled_to_its_capacity() -> None:
    """Power is derived from capacity rather than asked. Nobody knows their
    inverter rating, and a 0.5C rate is what domestic systems ship with.

    The 5.0 kW below pins that rate. The assembly re-exports the engine's
    BATTERY_C_RATE rather than writing 0.5 down a second time, so this is also
    what fails if the battery the household reports and the battery the advice
    prices stop being the same class of hardware.
    """
    spec = build_battery_spec(REFINE)
    assert spec is not None
    assert spec.capacity_kwh == 10.0
    assert spec.max_charge_kw == pytest.approx(5.0)
    assert spec.max_discharge_kw == pytest.approx(5.0)
    assert spec.allow_grid_charging is False


def test_the_baseline_still_has_net_metering_and_the_scenario_does_not() -> None:
    """The whole product is the difference between these two."""
    baseline, scenario, _ = build_tariffs(ESTIMATE)
    assert baseline.net_metering is True
    assert scenario.net_metering is False


def test_an_alternative_contract_is_always_built_so_the_rule_can_compare() -> None:
    """CONSIDER_DYNAMIC_CONTRACT needs both to say anything, including for a
    household that already has a dynamic contract and might be better off
    without one.

    The two sets are told apart by their prices and not by TariffSet.dynamic.
    That flag means 'price this against an hourly price series' and
    ampeer_advice.tariffs holds no such series, so it stays False on both: the
    dynamic contract is modelled by its average net price over the solar hours.
    Asserting the flag would assert something this layer does not do.
    """
    _, scenario, alternative = build_tariffs(ESTIMATE)
    assert alternative.feed_in_price != scenario.feed_in_price
    assert alternative.feed_in_cost_per_kwh == Decimal("0")
    assert scenario.feed_in_cost_per_kwh > Decimal("0")


def test_a_household_already_on_a_dynamic_contract_is_priced_as_one() -> None:
    """The scenario is what this household faces, and the alternative is the
    other contract, whichever way round that is. Building the dynamic set as
    the scenario for everybody would price a fixed contract's feed-in charge
    away for a household that pays it."""
    _, scenario, alternative = build_tariffs(REFINE)
    assert scenario.feed_in_cost_per_kwh == Decimal("0")
    assert alternative.feed_in_cost_per_kwh > Decimal("0")


def test_the_scenario_charges_for_feeding_in() -> None:
    """The correction that halved the headline: the published three to eight
    cent is gross, and the cost per exported kWh eats almost all of it."""
    _, scenario, _ = build_tariffs(ESTIMATE)
    assert scenario.feed_in_cost_per_kwh > Decimal("0")


#: One common year at 96 quarters a day, which is the only length
#: `advice.series` accepts besides a leap year.
QUARTERS_IN_A_YEAR = 365 * 96


def _flows(
    self_consumption: list[float],
    from_grid: list[float],
    to_grid: list[float],
    battery_discharge: list[float] | None = None,
    grid_charge: list[float] | None = None,
    grid_discharge: list[float] | None = None,
) -> EnergyFlows:
    """A handful of quarters, balanced the way the engine balances them.

    `consumption` and `production` are derived from the other columns by the
    two equations `ampeer_sim.engine.run.assert_energy_balance` enforces, so a
    case written here is a case the engine could have produced rather than an
    arbitrary set of arrays.
    """
    direct = np.asarray(self_consumption, dtype=float)
    offtake = np.asarray(from_grid, dtype=float)
    feed_in = np.asarray(to_grid, dtype=float)
    discharge = np.asarray(battery_discharge or [0.0] * len(direct), dtype=float)
    charge = np.zeros_like(direct)
    return EnergyFlows(
        consumption=direct + discharge + offtake,
        production=direct + charge + feed_in,
        self_consumption=direct,
        from_grid=offtake,
        to_grid=feed_in,
        battery_charge=charge,
        battery_discharge=discharge,
        grid_charge=np.asarray(grid_charge or [0.0] * len(direct), dtype=float),
        grid_discharge=np.asarray(grid_discharge or [0.0] * len(direct), dtype=float),
    )


def test_the_wire_reads_the_meter_and_not_the_household_side_of_it() -> None:
    """Which offtake the picture draws, when a battery trades on price.

    `from_grid` and `to_grid` are what this household took and fed in for its
    own sake. `total_import` and `total_export` add what a battery moved across
    the meter because the price told it to. The byte is called the meter and a
    bill is written from the meter, so the meter is what it carries; drawing
    the household side would put a plate beside a euro figure that disagrees
    with it.

    Nothing produces this case today and that is why it is written here. On
    every path the service runs, `grid_charge` and `grid_discharge` are zero,
    so the two readings are identical and a test built from a real run cannot
    tell them apart.
    """
    flows = _flows(
        self_consumption=[0.0, 1.0],
        from_grid=[2.0, 0.0],
        to_grid=[0.0, 3.0],
        grid_charge=[0.5, 0.0],
        grid_discharge=[0.0, 0.25],
    )
    own, export, grid = year_series(flows)

    assert list(grid) == [2.5, 0.0], "offtake dropped the kilowatt hours the battery bought"
    assert list(export) == [0.0, 3.25], "feed-in dropped the kilowatt hours the battery sold"
    assert list(own) == [0.0, 1.0]
    assert list(flows.from_grid) != list(grid), "the household side would have read differently"


def test_own_use_is_direct_use_and_never_direct_use_plus_discharge() -> None:
    """What a battery gives back is not counted as own use of the roof.

    `EnergyFlows.self_consumption_rate` gives the reason: discharged energy has
    already paid the round trip loss, and with grid charging it holds kilowatt
    hours this roof never made. The visible consequence is asserted rather than
    hidden, because it looks like a bug in a plate: on a quarter where the
    battery discharges, own use plus offtake is less than what was consumed.
    """
    flows = _flows(
        self_consumption=[1.0],
        from_grid=[0.5],
        to_grid=[0.0],
        battery_discharge=[2.0],
    )
    own, _export, grid = year_series(flows)

    assert list(own) == [1.0]
    assert own[0] + grid[0] < flows.consumption[0]
    assert flows.consumption[0] == 3.5


def test_a_year_built_here_is_stamped_synthetic_and_the_stamp_is_not_a_parameter() -> None:
    """The one thing this file may say about where the numbers came from.

    Everything phase 0.5 can produce is a national profile scaled to a figure
    somebody typed in. A caller able to pass `MEASURED` would be a caller able
    to claim a meter reading for a standard profile, which is the mistake the
    field exists to make impossible, so the signature is asserted and not only
    the value.
    """
    quarters = QUARTERS_IN_A_YEAR
    flows = _flows(
        self_consumption=[0.1] * quarters,
        from_grid=[0.2] * quarters,
        to_grid=[0.0] * quarters,
    )
    encoded = build_year(flows)

    assert encoded.provenance == SYNTHETIC
    assert encoded.quarters == quarters
    assert set(inspect.signature(build_year).parameters) == {"flows"}, (
        f"build_year now takes {sorted(inspect.signature(build_year).parameters)}; a "
        f"provenance argument here is a way to stamp {MEASURED} on a standard profile"
    )
