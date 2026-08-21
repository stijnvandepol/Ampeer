"""Turning nine answers into the objects the engine takes.

This is where a missing answer becomes a default, so it is where a default can
quietly become an invented input. Every default below is either a documented
national average that already lives in ampeer_sim, or an explicit 'we were not
told', never a guess dressed as an answer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from advice.assembly import build_battery_spec, build_household, build_pv_system, build_tariffs
from ampeer_sim.types import EVChargingBehaviour, ProfileCategory

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
