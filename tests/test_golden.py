from __future__ import annotations

import ast
import dataclasses
import enum
import hashlib
import importlib
import inspect
import json
import pkgutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import ampeer_sim
from ampeer_sim import ENGINE_VERSION
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EV, EnergyFlows, EVChargingBehaviour, HeatPump, Household, PVSystem

GOLDEN: dict[str, dict[str, Any]] = json.loads(
    (Path(__file__).parent / "golden" / "households.json").read_text(encoding="utf-8")
)
GRID = YearGrid.for_year(2025)
WEATHER_YEAR = 2025
FLAT_FRACTIONS = np.full(GRID.quarters, 1.0 / GRID.quarters)


def _household(case: dict[str, Any]) -> Household:
    ev = None
    if "ev_behaviour" in case:
        ev = EV(
            behaviour=EVChargingBehaviour[case["ev_behaviour"]],
            annual_km=case["ev_annual_km"],
        )
    heat_pump = None
    if "heat_pump_demand_kwh" in case:
        heat_pump = HeatPump(heat_demand_kwh=case["heat_pump_demand_kwh"])
    return Household(
        postcode4=case["postcode4"],
        annual_consumption_kwh=case["annual_consumption_kwh"],
        daytime_occupancy=case["daytime_occupancy"],
        shiftable_block_kwh=case["shiftable_block_kwh"],
        ev=ev,
        heat_pump=heat_pump,
    )


def _run(case: dict[str, Any]) -> tuple[EnergyFlows, np.ndarray]:
    household = _household(case)
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0, tilt_deg=35)
    hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    consumption = compose_consumption(
        household,
        GRID,
        FLAT_FRACTIONS,
        temperature,
        weather_year=WEATHER_YEAR,
        production_kwh=production,
    )
    return simulate(consumption, production), consumption


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_household_self_consumption(name: str) -> None:
    case = GOLDEN[name]
    flows, _ = _run(case)
    assert flows.self_consumption_rate == pytest.approx(
        case["expected_self_consumption_rate"], abs=case["tolerance"]
    )


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_household_consumption_total(name: str) -> None:
    case = GOLDEN[name]
    _, consumption = _run(case)
    assert consumption.sum() == pytest.approx(case["expected_consumption_kwh"], rel=1e-3)


def test_the_hand_checkable_case_can_be_derived_by_hand() -> None:
    """Verify the pencil case rather than trusting the recorded number.

    With no shiftable block and no assets, consumption is exactly flat at
    3650 / 35040 kWh per quarter. Self consumption is then the integral of
    min(flat, production) over the year divided by the annual yield, which the
    assertion below recomputes directly instead of restating.
    """
    case = GOLDEN["hand_checkable"]
    system = PVSystem(peak_power_wp=case["peak_power_wp"], azimuth_deg=0, tilt_deg=35)
    hourly, _, _ = FallbackProvider(WEATHER_YEAR).hourly_series("5401", 0.0, 35.0)
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    flat = np.full(GRID.quarters, case["annual_consumption_kwh"] / GRID.quarters)

    by_hand = float(np.minimum(flat, production).sum() / production.sum())
    flows, _ = _run(case)
    assert flows.self_consumption_rate == pytest.approx(by_hand, abs=1e-9)


def test_charging_the_car_on_your_own_surplus_beats_charging_it_at_night() -> None:
    """The single most valuable piece of advice the product gives.

    Same household, same annual driving need, same energy. Only the moment of
    charging differs. If this gap ever collapses, either the model or the advice
    is wrong.
    """
    at_night, night_consumption = _run(GOLDEN["marloes_ev_at_night"])
    on_solar, solar_consumption = _run(GOLDEN["marloes_ev_on_solar"])

    assert solar_consumption.sum() == pytest.approx(night_consumption.sum(), rel=1e-6)
    assert on_solar.self_consumption_rate > at_night.self_consumption_rate + 0.30
    assert on_solar.to_grid.sum() < at_night.to_grid.sum()
    assert on_solar.from_grid.sum() < at_night.from_grid.sum()


def test_a_bigger_array_on_the_same_house_wastes_a_larger_share() -> None:
    small, _ = _run(GOLDEN["rob_fixed_contract"])
    large, _ = _run(GOLDEN["large_array_small_use"])
    assert large.self_consumption_rate < small.self_consumption_rate


def _engine_constants() -> tuple[tuple[str, str], ...]:
    """Every default value the engine carries, found rather than listed.

    A list written here would cover the constants somebody thought of, which is
    the shape of guard this repository keeps replacing with a derived one.

    Defaults and not every literal in the package. A default is the value the
    engine uses for a caller who does not override it, so it is part of what
    ampeer_sim promises, and all of the model figures in docs/methodologie.md
    live as one: the COP at seven degrees, its slope, the kilometres a year, the
    system loss. Constants inside a function body are not covered, and saying so
    is better than implying they are.
    """
    found: dict[str, type] = {}
    for module in pkgutil.walk_packages(ampeer_sim.__path__, "ampeer_sim."):
        imported = importlib.import_module(module.name)
        for name in dir(imported):
            candidate = getattr(imported, name)
            if (
                isinstance(candidate, type)
                and dataclasses.is_dataclass(candidate)
                and candidate.__module__.startswith("ampeer_sim")
            ):
                found[f"{candidate.__module__}.{candidate.__name__}"] = candidate

    def shown(value: object) -> str:
        # An enum member reprs as "<ProfileCategory.E1A: 'E1A'>", which carries
        # its own value and would move if the value moved without the member
        # moving. The member name is the thing being pinned.
        if isinstance(value, enum.Enum):
            return f"{type(value).__name__}.{value.name}"
        return repr(value)

    return tuple(
        sorted(
            (f"{qualified}.{field.name}", shown(field.default))
            for qualified, cls in found.items()
            for field in dataclasses.fields(cls)
            if field.default is not dataclasses.MISSING
        )
    )


#: Names that are module level constants of ampeer_sim and are not pinned below.
#:
#: One entry, and it is the version string itself. Pinning ENGINE_VERSION to the
#: table keyed by ENGINE_VERSION says nothing at all, and leaving it in would
#: make every version bump look like a constant that moved.
_NOT_PINNED = frozenset({"ampeer_sim.ENGINE_VERSION"})


def _engine_module_constants() -> tuple[tuple[str, str], ...]:
    """Every module level constant the engine carries, found rather than listed.

    The half of decision 8 that was missing. ``_engine_constants`` above reads
    dataclass field defaults, which was the whole of the pin until a review on
    2026-08-26 noticed the shape of the hole: the values that actually decide a
    household's answer mostly are not dataclass defaults. ORIENTATION_FACTORS,
    MONTHLY_MEAN_PRODUCTION_W_PER_KWP, FALLBACK_SOLAR_NOON_HOUR,
    DEGRADATION_PER_YEAR and UTC_TO_WINTER_TIME_HOURS are module level constants
    to a name, and every one of them could move while ENGINE_VERSION stood
    still. Three engine versions in a row have now produced an identical
    dataclass row while the numbers underneath moved twice, which is that hole
    with a measurement on it.

    Found by reading each module's own source rather than by walking ``dir()``.
    A ``dir()`` walk cannot tell a constant a module defines from one it imports,
    so MONTHLY_MEAN_PRODUCTION_W_PER_KWP would appear twice, under
    fallback_yield and under pvgis, and moving an import would look like a
    constant moving. The parse names exactly what each file assigns at module
    level.

    Pinned as a digest of the repr and not as the repr. Four of these are tables:
    _POSTCODE_CENTROIDS reprs to 1873 characters, and a snapshot holding two of
    those is not something anybody reads, while wrapping it across implicit
    string concatenation would make a one character change to a coordinate show
    up as a reflowed block. The failure message carries the live value instead,
    which is the half a reader needs; the pinned half only has to be able to
    differ.
    """
    modules = [ampeer_sim] + [
        importlib.import_module(found_module.name)
        for found_module in pkgutil.walk_packages(ampeer_sim.__path__, "ampeer_sim.")
    ]
    found: dict[str, object] = {}
    for imported in modules:
        for node in ast.parse(inspect.getsource(imported)).body:
            targets: list[ast.expr] = (
                [node.target]
                if isinstance(node, ast.AnnAssign)
                else list(getattr(node, "targets", []))
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    found[f"{imported.__name__}.{target.id}"] = getattr(imported, target.id)

    arrays = sorted(name for name, value in found.items() if isinstance(value, np.ndarray))
    assert not arrays, (
        f"{arrays} are numpy arrays, whose repr elides its middle past a threshold set by "
        "global print options, so a digest of it would silently stop distinguishing values"
    )
    return tuple(
        sorted(
            (name, hashlib.sha256(repr(value).encode("utf-8")).hexdigest()[:16])
            for name, value in found.items()
            if name not in _NOT_PINNED
        )
    )


def _golden_answers() -> tuple[tuple[str, float], ...]:
    """The numbers the six golden households are asserted to produce.

    Only the expected values. A tolerance is slack around an answer rather than
    an answer, so widening one is not an engine change and must not be able to
    look like one. That tolerances should not quietly widen is a separate rule
    with its own guard in tests/test_advise.py.
    """
    return tuple(
        sorted(
            (f"{name}.{key}", float(value))
            for name, case in GOLDEN.items()
            for key, value in case.items()
            if key.startswith("expected_")
        )
    )


def _difference(
    actual: tuple[tuple[str, object], ...], pinned: tuple[tuple[str, object], ...]
) -> str:
    """What moved, so a failure names the value rather than the mismatch."""
    found, recorded = dict(actual), dict(pinned)
    return "\n".join(
        f"  {name}: pinned {recorded.get(name)!r}, found {found.get(name)!r}"
        for name in sorted(set(found) | set(recorded))
        if found.get(name) != recorded.get(name)
    )


def _live_constant_values(
    actual: tuple[tuple[str, str], ...], pinned: tuple[tuple[str, str], ...]
) -> str:
    """The current value of every constant whose digest no longer matches.

    A digest tells you that something moved and never what to. This reads the
    value back out of the module so the failure names it, which is the whole
    reason the pinned side is allowed to be a digest. Long tables are cut off
    rather than printed in full: the point is to recognise the value, and the
    diff of the module holding it is where it is read properly.
    """
    moved = sorted(set(dict(actual)) | set(dict(pinned)))
    lines = []
    for name in moved:
        if dict(actual).get(name) == dict(pinned).get(name):
            continue
        module_name, _, attribute = name.rpartition(".")
        try:
            shown = repr(getattr(importlib.import_module(module_name), attribute))
        except (ImportError, AttributeError):
            shown = "gone: no such name in that module any more"
        lines.append(f"  {name} = {shown[:200]}{'...' if len(shown) > 200 else ''}")
    return "\n".join(lines)


def test_the_model_constants_are_pinned_to_the_engine_version() -> None:
    """A stored advice must stay reproducible.

    CLAUDE.md asks every calculation to log the engine version, and every
    calculation does: simulate() stamps it, advise() carries it through, the API
    returns it, and the audit log records it beside the token digest. All of
    that answers "which engine produced this number" with a hand written string
    that nothing forces to move. Change the COP and every advice from before and
    after the change says 0.1.0, and the older one can no longer be reproduced
    or defended.

    ADVICE_VERSION already has this guard, pinned to the rule table in
    tests/test_advise.py. ENGINE_VERSION is the half that produces the numbers,
    and until now the only test touching it asserted it was a string with two
    dots in it.

    Nothing here needs a companion test proving it can fail on an empty reading.
    The assertion is an equality against a non-empty tuple, so a walk that
    imported nothing compares () against twenty-three rows and fails. A pairing
    that tested membership would need that companion; this one carries its own
    floor.
    """
    snapshot = {
        "0.1.0": (
            ("ampeer_sim.types.BatterySpec.allow_grid_charging", "False"),
            ("ampeer_sim.types.BatterySpec.round_trip_efficiency", "0.9"),
            ("ampeer_sim.types.BatterySpec.usable_dod", "0.9"),
            ("ampeer_sim.types.EV.annual_km", "12000"),
            ("ampeer_sim.types.EV.charge_power_kw", "3.7"),
            ("ampeer_sim.types.EV.kwh_per_100km", "18.0"),
            ("ampeer_sim.types.EnergyFlows.grid_charge", "None"),
            ("ampeer_sim.types.EnergyFlows.grid_discharge", "None"),
            ("ampeer_sim.types.HeatPump.base_temperature_c", "15.0"),
            ("ampeer_sim.types.HeatPump.cop_at_7c", "3.5"),
            ("ampeer_sim.types.HeatPump.cop_slope_per_c", "0.06"),
            ("ampeer_sim.types.Household.daytime_occupancy", "False"),
            ("ampeer_sim.types.Household.ev", "None"),
            ("ampeer_sim.types.Household.heat_pump", "None"),
            ("ampeer_sim.types.Household.profile_category", "ProfileCategory.E1A"),
            ("ampeer_sim.types.Household.shiftable_block_kwh", "1.0"),
            ("ampeer_sim.types.PVSystem.install_year", "None"),
            ("ampeer_sim.types.PVSystem.system_loss_fraction", "0.14"),
            ("ampeer_sim.types.TariffSet.dynamic", "False"),
            ("ampeer_sim.types.TariffSet.feed_in_cost_per_kwh", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.feed_in_fixed_cost_year", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.net_metering", "False"),
            ("ampeer_sim.types.TariffSet.standing_charge_year", "Decimal('0')"),
        ),
        # 0.2.0 moved the offline production model, not a dataclass default, so
        # this row is 0.1.0's unchanged. That is the honest reading of the pin:
        # it says which constants an engine version computes with, and a version
        # that changed the arithmetic around them still has to name them.
        "0.2.0": (
            ("ampeer_sim.types.BatterySpec.allow_grid_charging", "False"),
            ("ampeer_sim.types.BatterySpec.round_trip_efficiency", "0.9"),
            ("ampeer_sim.types.BatterySpec.usable_dod", "0.9"),
            ("ampeer_sim.types.EV.annual_km", "12000"),
            ("ampeer_sim.types.EV.charge_power_kw", "3.7"),
            ("ampeer_sim.types.EV.kwh_per_100km", "18.0"),
            ("ampeer_sim.types.EnergyFlows.grid_charge", "None"),
            ("ampeer_sim.types.EnergyFlows.grid_discharge", "None"),
            ("ampeer_sim.types.HeatPump.base_temperature_c", "15.0"),
            ("ampeer_sim.types.HeatPump.cop_at_7c", "3.5"),
            ("ampeer_sim.types.HeatPump.cop_slope_per_c", "0.06"),
            ("ampeer_sim.types.Household.daytime_occupancy", "False"),
            ("ampeer_sim.types.Household.ev", "None"),
            ("ampeer_sim.types.Household.heat_pump", "None"),
            ("ampeer_sim.types.Household.profile_category", "ProfileCategory.E1A"),
            ("ampeer_sim.types.Household.shiftable_block_kwh", "1.0"),
            ("ampeer_sim.types.PVSystem.install_year", "None"),
            ("ampeer_sim.types.PVSystem.system_loss_fraction", "0.14"),
            ("ampeer_sim.types.TariffSet.dynamic", "False"),
            ("ampeer_sim.types.TariffSet.feed_in_cost_per_kwh", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.feed_in_fixed_cost_year", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.net_metering", "False"),
            ("ampeer_sim.types.TariffSet.standing_charge_year", "Decimal('0')"),
        ),
        # 0.3.0 converted PVGIS's UTC stamps onto the grid's winter time, which
        # is a module level constant and a rotation rather than a dataclass
        # default, so this row is 0.2.0's unchanged for the third time running.
        # Three identical rows is the finding that produced
        # test_the_module_constants_are_pinned_to_the_engine_version below: not
        # one of the three engine versions moved a value this pin can see.
        "0.3.0": (
            ("ampeer_sim.types.BatterySpec.allow_grid_charging", "False"),
            ("ampeer_sim.types.BatterySpec.round_trip_efficiency", "0.9"),
            ("ampeer_sim.types.BatterySpec.usable_dod", "0.9"),
            ("ampeer_sim.types.EV.annual_km", "12000"),
            ("ampeer_sim.types.EV.charge_power_kw", "3.7"),
            ("ampeer_sim.types.EV.kwh_per_100km", "18.0"),
            ("ampeer_sim.types.EnergyFlows.grid_charge", "None"),
            ("ampeer_sim.types.EnergyFlows.grid_discharge", "None"),
            ("ampeer_sim.types.HeatPump.base_temperature_c", "15.0"),
            ("ampeer_sim.types.HeatPump.cop_at_7c", "3.5"),
            ("ampeer_sim.types.HeatPump.cop_slope_per_c", "0.06"),
            ("ampeer_sim.types.Household.daytime_occupancy", "False"),
            ("ampeer_sim.types.Household.ev", "None"),
            ("ampeer_sim.types.Household.heat_pump", "None"),
            ("ampeer_sim.types.Household.profile_category", "ProfileCategory.E1A"),
            ("ampeer_sim.types.Household.shiftable_block_kwh", "1.0"),
            ("ampeer_sim.types.PVSystem.install_year", "None"),
            ("ampeer_sim.types.PVSystem.system_loss_fraction", "0.14"),
            ("ampeer_sim.types.TariffSet.dynamic", "False"),
            ("ampeer_sim.types.TariffSet.feed_in_cost_per_kwh", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.feed_in_fixed_cost_year", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.net_metering", "False"),
            ("ampeer_sim.types.TariffSet.standing_charge_year", "Decimal('0')"),
        ),
        # 0.4.0 moved where inside its hour an hourly value is read, which is
        # an argument to an interpolation and a module level constant, not a
        # dataclass default. So this row is 0.3.0's unchanged for the fourth
        # time running, and the pin below is the one that sees the change.
        "0.4.0": (
            ("ampeer_sim.types.BatterySpec.allow_grid_charging", "False"),
            ("ampeer_sim.types.BatterySpec.round_trip_efficiency", "0.9"),
            ("ampeer_sim.types.BatterySpec.usable_dod", "0.9"),
            ("ampeer_sim.types.EV.annual_km", "12000"),
            ("ampeer_sim.types.EV.charge_power_kw", "3.7"),
            ("ampeer_sim.types.EV.kwh_per_100km", "18.0"),
            ("ampeer_sim.types.EnergyFlows.grid_charge", "None"),
            ("ampeer_sim.types.EnergyFlows.grid_discharge", "None"),
            ("ampeer_sim.types.HeatPump.base_temperature_c", "15.0"),
            ("ampeer_sim.types.HeatPump.cop_at_7c", "3.5"),
            ("ampeer_sim.types.HeatPump.cop_slope_per_c", "0.06"),
            ("ampeer_sim.types.Household.daytime_occupancy", "False"),
            ("ampeer_sim.types.Household.ev", "None"),
            ("ampeer_sim.types.Household.heat_pump", "None"),
            ("ampeer_sim.types.Household.profile_category", "ProfileCategory.E1A"),
            ("ampeer_sim.types.Household.shiftable_block_kwh", "1.0"),
            ("ampeer_sim.types.PVSystem.install_year", "None"),
            ("ampeer_sim.types.PVSystem.system_loss_fraction", "0.14"),
            ("ampeer_sim.types.TariffSet.dynamic", "False"),
            ("ampeer_sim.types.TariffSet.feed_in_cost_per_kwh", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.feed_in_fixed_cost_year", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.net_metering", "False"),
            ("ampeer_sim.types.TariffSet.standing_charge_year", "Decimal('0')"),
        ),
        # 0.5.0 moved no dataclass default. The row is identical to 0.4.0's and
        # it is here because the version moved: a version with no row is what
        # this test refuses, and "nothing changed" is a claim worth recording
        # rather than an excuse for leaving the table silent.
        "0.5.0": (
            ("ampeer_sim.types.BatterySpec.allow_grid_charging", "False"),
            ("ampeer_sim.types.BatterySpec.round_trip_efficiency", "0.9"),
            ("ampeer_sim.types.BatterySpec.usable_dod", "0.9"),
            ("ampeer_sim.types.EV.annual_km", "12000"),
            ("ampeer_sim.types.EV.charge_power_kw", "3.7"),
            ("ampeer_sim.types.EV.kwh_per_100km", "18.0"),
            ("ampeer_sim.types.EnergyFlows.grid_charge", "None"),
            ("ampeer_sim.types.EnergyFlows.grid_discharge", "None"),
            ("ampeer_sim.types.HeatPump.base_temperature_c", "15.0"),
            ("ampeer_sim.types.HeatPump.cop_at_7c", "3.5"),
            ("ampeer_sim.types.HeatPump.cop_slope_per_c", "0.06"),
            ("ampeer_sim.types.Household.daytime_occupancy", "False"),
            ("ampeer_sim.types.Household.ev", "None"),
            ("ampeer_sim.types.Household.heat_pump", "None"),
            ("ampeer_sim.types.Household.profile_category", "ProfileCategory.E1A"),
            ("ampeer_sim.types.Household.shiftable_block_kwh", "1.0"),
            ("ampeer_sim.types.PVSystem.install_year", "None"),
            ("ampeer_sim.types.PVSystem.system_loss_fraction", "0.14"),
            ("ampeer_sim.types.TariffSet.dynamic", "False"),
            ("ampeer_sim.types.TariffSet.feed_in_cost_per_kwh", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.feed_in_fixed_cost_year", "Decimal('0')"),
            ("ampeer_sim.types.TariffSet.net_metering", "False"),
            ("ampeer_sim.types.TariffSet.standing_charge_year", "Decimal('0')"),
        ),
    }
    assert ENGINE_VERSION in snapshot, (
        f"ENGINE_VERSION is {ENGINE_VERSION!r} and this table has no row for it. "
        "A version that moved without recording what it computes leaves the "
        "advice stamped with it unexplainable."
    )
    actual = _engine_constants()
    assert actual == snapshot[ENGINE_VERSION], (
        "the engine computes with different constants than the version says:\n"
        + _difference(actual, snapshot[ENGINE_VERSION])
        + f"\nEither restore the value or move ENGINE_VERSION past {ENGINE_VERSION} "
        "and add a row above. docs/methodologie.md holds the source for each of "
        "these, so a change here is a change there too."
    )


def test_the_module_constants_are_pinned_to_the_engine_version() -> None:
    """The other half of decision 8, missing until 2026-08-27.

    One row and not three. The dataclass table above carries 0.1.0 and 0.2.0
    because those rows were written while those versions were current; the
    values these names held then were never recorded, and reconstructing them
    from the history to fill the table in would be manufacturing a record of a
    check that did not run. This pin starts where it starts and says so.

    What it costs is the same friction decision 8 already buys: moving a table,
    a threshold or a location in ampeer_sim means moving ENGINE_VERSION and
    adding a row here. What it buys is that 0.2.0 and 0.3.0 could not have
    happened silently. 0.2.0 moved FALLBACK_SOLAR_NOON_HOUR and every entry of
    ORIENTATION_FACTORS; 0.3.0 added UTC_TO_WINTER_TIME_HOURS. Neither is a
    dataclass default, and neither would have made the pin above blink.
    """
    snapshot = {
        "0.3.0": (
            ("ampeer_sim.economics.sensitivity.CENTRAL_FACTOR", "d0ff5974b6aa52cf"),
            ("ampeer_sim.economics.sensitivity.VARIATIONS", "4b3b6cc9ab933edf"),
            ("ampeer_sim.economics.tariffs.EUR_PRECISION", "66341319baafc19a"),
            ("ampeer_sim.economics.tariffs.KWH_PRECISION", "66341319baafc19a"),
            ("ampeer_sim.engine.strategies.FORESIGHT_HORIZON_DAYS", "6b86b273ff34fce1"),
            ("ampeer_sim.engine.strategies.HYBRID_SAFETY_MARGIN", "9f29a130438b8117"),
            (
                "ampeer_sim.production.fallback_yield.MONTHLY_MEAN_PRODUCTION_W_PER_KWP",
                "0678f9f6b8831e49",
            ),
            ("ampeer_sim.production.fallback_yield.MONTHLY_MEAN_TEMPERATURE", "115c55510054006f"),
            ("ampeer_sim.production.fallback_yield.ORIENTATION_FACTORS", "79fe2b88af8001d3"),
            ("ampeer_sim.production.fallback_yield.TABLE_LONGITUDE", "4b9c27c3a3718066"),
            ("ampeer_sim.production.model.DEGRADATION_PER_YEAR", "07e17407c7918077"),
            ("ampeer_sim.production.model.MAX_DEGRADATION", "44896b09365746b5"),
            ("ampeer_sim.production.pvgis.FALLBACK_DAYLIGHT_HOURS", "77c52f3feed5acdd"),
            ("ampeer_sim.production.pvgis.FALLBACK_SOLAR_NOON_HOUR", "456baac0519e7bbe"),
            ("ampeer_sim.production.pvgis.PVGIS_URL", "83e0554d696623d2"),
            ("ampeer_sim.production.pvgis.RADIATION_DATABASE", "d4666808263aa56c"),
            ("ampeer_sim.production.pvgis.REFERENCE_LOSS_PERCENT", "8aed642bf5118b9d"),
            ("ampeer_sim.production.pvgis.REFERENCE_PEAK_POWER_KW", "d0ff5974b6aa52cf"),
            ("ampeer_sim.production.pvgis.UTC_TO_WINTER_TIME_HOURS", "6b86b273ff34fce1"),
            ("ampeer_sim.production.pvgis._DEFAULT_CENTROID", "45a1d875efbe8796"),
            ("ampeer_sim.production.pvgis._POSTCODE_CENTROIDS", "7c3619d3e0959da1"),
            ("ampeer_sim.profiles.assets.ARRIVAL_WINDOW", "e8c3a86ba10aea79"),
            ("ampeer_sim.profiles.assets.MIN_COP", "d0ff5974b6aa52cf"),
            ("ampeer_sim.profiles.assets.NIGHT_WINDOW", "7b5f404e02b3e494"),
            ("ampeer_sim.profiles.nedu.BASE_SERIES_SUFFIX", "ef3d560c808a0096"),
            ("ampeer_sim.profiles.nedu.FEED_IN_SERIES_SUFFIX", "6f8e0f7c337b21bd"),
            ("ampeer_sim.profiles.nedu.FIRST_DATA_COLUMN", "4e07408562bedb8b"),
            ("ampeer_sim.profiles.nedu.HEADER_ROWS", "7902699be42c8a8e"),
            ("ampeer_sim.profiles.nedu.NAME_ROW", "5feceb66ffc86f38"),
            ("ampeer_sim.profiles.nedu.SINGLE_REGISTER", "b1741201e5ef1384"),
            ("ampeer_sim.profiles.nedu.SUM_TOLERANCE", "1187132475a4431d"),
            ("ampeer_sim.profiles.nedu.YEAR_ROW", "6b86b273ff34fce1"),
            ("ampeer_sim.profiles.presence.EVENING_WINDOW", "e8c3a86ba10aea79"),
            ("ampeer_sim.profiles.presence.MIDDAY_WINDOW", "cbd2debb98ebecca"),
            ("ampeer_sim.simulate.DEFAULT_WEATHER_YEAR", "d398b29d3dbbb9bf"),
            ("ampeer_sim.timebase.DST_SWITCH_QUARTER", "2c624232cdd22177"),
            ("ampeer_sim.timebase.HOURS_PER_DAY", "c2356069e9d1e79c"),
            ("ampeer_sim.timebase.MINUTES_PER_DAY", "a4ff3ad278c7b057"),
            ("ampeer_sim.timebase.MINUTES_PER_QUARTER", "e629fa6598d73276"),
            ("ampeer_sim.timebase.QUARTERS_PER_DAY", "7b1a278f5abe8e9d"),
            ("ampeer_sim.timebase.QUARTERS_PER_HOUR", "4b227777d4dd1fc6"),
            ("ampeer_sim.validate.DEFAULT_PROFILE_YEAR", "b2b2f104d32c6389"),
            ("ampeer_sim.validate.DEFAULT_TOLERANCE_PERCENT", "f1e42019aecc858f"),
            ("ampeer_sim.validate.REQUIRED_FIELDS", "45b84058cdd90331"),
        ),
        # 0.4.0 put the last twenty minutes of the PVGIS placement right. The
        # anchor became an argument rather than the 1.5 written into
        # hourly_to_quarters, so two names appear here that 0.3.0 did not have:
        # PVGIS_STAMP_MINUTES_PAST_HOUR, which the model hands the interpolation
        # for a PVGIS series, and HOURLY_MEAN_ANCHOR_MINUTES, which is what a
        # series that says nothing about itself gets. This is the row that would
        # have blinked, and the reason the pin exists.
        "0.4.0": (
            ("ampeer_sim.economics.sensitivity.CENTRAL_FACTOR", "d0ff5974b6aa52cf"),
            ("ampeer_sim.economics.sensitivity.VARIATIONS", "4b3b6cc9ab933edf"),
            ("ampeer_sim.economics.tariffs.EUR_PRECISION", "66341319baafc19a"),
            ("ampeer_sim.economics.tariffs.KWH_PRECISION", "66341319baafc19a"),
            ("ampeer_sim.engine.strategies.FORESIGHT_HORIZON_DAYS", "6b86b273ff34fce1"),
            ("ampeer_sim.engine.strategies.HYBRID_SAFETY_MARGIN", "9f29a130438b8117"),
            (
                "ampeer_sim.production.fallback_yield.MONTHLY_MEAN_PRODUCTION_W_PER_KWP",
                "0678f9f6b8831e49",
            ),
            ("ampeer_sim.production.fallback_yield.MONTHLY_MEAN_TEMPERATURE", "115c55510054006f"),
            ("ampeer_sim.production.fallback_yield.ORIENTATION_FACTORS", "79fe2b88af8001d3"),
            ("ampeer_sim.production.fallback_yield.TABLE_LONGITUDE", "4b9c27c3a3718066"),
            ("ampeer_sim.production.model.DEGRADATION_PER_YEAR", "07e17407c7918077"),
            ("ampeer_sim.production.model.MAX_DEGRADATION", "44896b09365746b5"),
            ("ampeer_sim.production.pvgis.FALLBACK_DAYLIGHT_HOURS", "77c52f3feed5acdd"),
            ("ampeer_sim.production.pvgis.FALLBACK_SOLAR_NOON_HOUR", "456baac0519e7bbe"),
            ("ampeer_sim.production.pvgis.PVGIS_STAMP_MINUTES_PAST_HOUR", "f1e42019aecc858f"),
            ("ampeer_sim.production.pvgis.PVGIS_URL", "83e0554d696623d2"),
            ("ampeer_sim.production.pvgis.RADIATION_DATABASE", "d4666808263aa56c"),
            ("ampeer_sim.production.pvgis.REFERENCE_LOSS_PERCENT", "8aed642bf5118b9d"),
            ("ampeer_sim.production.pvgis.REFERENCE_PEAK_POWER_KW", "d0ff5974b6aa52cf"),
            ("ampeer_sim.production.pvgis.UTC_TO_WINTER_TIME_HOURS", "6b86b273ff34fce1"),
            ("ampeer_sim.production.pvgis._DEFAULT_CENTROID", "45a1d875efbe8796"),
            ("ampeer_sim.production.pvgis._POSTCODE_CENTROIDS", "7c3619d3e0959da1"),
            ("ampeer_sim.profiles.assets.ARRIVAL_WINDOW", "e8c3a86ba10aea79"),
            ("ampeer_sim.profiles.assets.MIN_COP", "d0ff5974b6aa52cf"),
            ("ampeer_sim.profiles.assets.NIGHT_WINDOW", "7b5f404e02b3e494"),
            ("ampeer_sim.profiles.nedu.BASE_SERIES_SUFFIX", "ef3d560c808a0096"),
            ("ampeer_sim.profiles.nedu.FEED_IN_SERIES_SUFFIX", "6f8e0f7c337b21bd"),
            ("ampeer_sim.profiles.nedu.FIRST_DATA_COLUMN", "4e07408562bedb8b"),
            ("ampeer_sim.profiles.nedu.HEADER_ROWS", "7902699be42c8a8e"),
            ("ampeer_sim.profiles.nedu.NAME_ROW", "5feceb66ffc86f38"),
            ("ampeer_sim.profiles.nedu.SINGLE_REGISTER", "b1741201e5ef1384"),
            ("ampeer_sim.profiles.nedu.SUM_TOLERANCE", "1187132475a4431d"),
            ("ampeer_sim.profiles.nedu.YEAR_ROW", "6b86b273ff34fce1"),
            ("ampeer_sim.profiles.presence.EVENING_WINDOW", "e8c3a86ba10aea79"),
            ("ampeer_sim.profiles.presence.MIDDAY_WINDOW", "cbd2debb98ebecca"),
            ("ampeer_sim.simulate.DEFAULT_WEATHER_YEAR", "d398b29d3dbbb9bf"),
            ("ampeer_sim.timebase.DST_SWITCH_QUARTER", "2c624232cdd22177"),
            ("ampeer_sim.timebase.HOURLY_MEAN_ANCHOR_MINUTES", "26c9a96ce053a14d"),
            ("ampeer_sim.timebase.HOURS_PER_DAY", "c2356069e9d1e79c"),
            ("ampeer_sim.timebase.MINUTES_PER_DAY", "a4ff3ad278c7b057"),
            ("ampeer_sim.timebase.MINUTES_PER_QUARTER", "e629fa6598d73276"),
            ("ampeer_sim.timebase.QUARTERS_PER_DAY", "7b1a278f5abe8e9d"),
            ("ampeer_sim.timebase.QUARTERS_PER_HOUR", "4b227777d4dd1fc6"),
            ("ampeer_sim.validate.DEFAULT_PROFILE_YEAR", "b2b2f104d32c6389"),
            ("ampeer_sim.validate.DEFAULT_TOLERANCE_PERCENT", "f1e42019aecc858f"),
            ("ampeer_sim.validate.REQUIRED_FIELDS", "45b84058cdd90331"),
        ),
        # 0.5.0 added ampeer_sim.fit, and with it six names. None of them enters
        # a simulated number: the fit proposes a corrected annual consumption and
        # the advice that follows is computed by the same engine from whatever
        # figure the household accepted. They are written down anyway, because
        # the figure that was accepted was produced by these six, and an advice
        # whose input came from a fit nobody can reproduce is exactly the gap
        # this table exists to close.
        "0.5.0": (
            ("ampeer_sim.economics.sensitivity.CENTRAL_FACTOR", "d0ff5974b6aa52cf"),
            ("ampeer_sim.economics.sensitivity.VARIATIONS", "4b3b6cc9ab933edf"),
            ("ampeer_sim.economics.tariffs.EUR_PRECISION", "66341319baafc19a"),
            ("ampeer_sim.economics.tariffs.KWH_PRECISION", "66341319baafc19a"),
            ("ampeer_sim.engine.strategies.FORESIGHT_HORIZON_DAYS", "6b86b273ff34fce1"),
            ("ampeer_sim.engine.strategies.HYBRID_SAFETY_MARGIN", "9f29a130438b8117"),
            ("ampeer_sim.fit.BRACKET_HIGH_FACTOR", "a19a1584344c1f37"),
            ("ampeer_sim.fit.BRACKET_LOW_FACTOR", "44896b09365746b5"),
            ("ampeer_sim.fit.MAX_ITERATIONS", "d59eced1ded07f84"),
            ("ampeer_sim.fit.MIN_WEEKS", "4e07408562bedb8b"),
            ("ampeer_sim.fit.QUARTERS_PER_WEEK", "12f26af0dcdfae8f"),
            ("ampeer_sim.fit.TOLERANCE_KWH", "d0ff5974b6aa52cf"),
            (
                "ampeer_sim.production.fallback_yield.MONTHLY_MEAN_PRODUCTION_W_PER_KWP",
                "0678f9f6b8831e49",
            ),
            ("ampeer_sim.production.fallback_yield.MONTHLY_MEAN_TEMPERATURE", "115c55510054006f"),
            ("ampeer_sim.production.fallback_yield.ORIENTATION_FACTORS", "79fe2b88af8001d3"),
            ("ampeer_sim.production.fallback_yield.TABLE_LONGITUDE", "4b9c27c3a3718066"),
            ("ampeer_sim.production.model.DEGRADATION_PER_YEAR", "07e17407c7918077"),
            ("ampeer_sim.production.model.MAX_DEGRADATION", "44896b09365746b5"),
            ("ampeer_sim.production.pvgis.FALLBACK_DAYLIGHT_HOURS", "77c52f3feed5acdd"),
            ("ampeer_sim.production.pvgis.FALLBACK_SOLAR_NOON_HOUR", "456baac0519e7bbe"),
            ("ampeer_sim.production.pvgis.PVGIS_STAMP_MINUTES_PAST_HOUR", "f1e42019aecc858f"),
            ("ampeer_sim.production.pvgis.PVGIS_URL", "83e0554d696623d2"),
            ("ampeer_sim.production.pvgis.RADIATION_DATABASE", "d4666808263aa56c"),
            ("ampeer_sim.production.pvgis.REFERENCE_LOSS_PERCENT", "8aed642bf5118b9d"),
            ("ampeer_sim.production.pvgis.REFERENCE_PEAK_POWER_KW", "d0ff5974b6aa52cf"),
            ("ampeer_sim.production.pvgis.UTC_TO_WINTER_TIME_HOURS", "6b86b273ff34fce1"),
            ("ampeer_sim.production.pvgis._DEFAULT_CENTROID", "45a1d875efbe8796"),
            ("ampeer_sim.production.pvgis._POSTCODE_CENTROIDS", "7c3619d3e0959da1"),
            ("ampeer_sim.profiles.assets.ARRIVAL_WINDOW", "e8c3a86ba10aea79"),
            ("ampeer_sim.profiles.assets.MIN_COP", "d0ff5974b6aa52cf"),
            ("ampeer_sim.profiles.assets.NIGHT_WINDOW", "7b5f404e02b3e494"),
            ("ampeer_sim.profiles.nedu.BASE_SERIES_SUFFIX", "ef3d560c808a0096"),
            ("ampeer_sim.profiles.nedu.FEED_IN_SERIES_SUFFIX", "6f8e0f7c337b21bd"),
            ("ampeer_sim.profiles.nedu.FIRST_DATA_COLUMN", "4e07408562bedb8b"),
            ("ampeer_sim.profiles.nedu.HEADER_ROWS", "7902699be42c8a8e"),
            ("ampeer_sim.profiles.nedu.NAME_ROW", "5feceb66ffc86f38"),
            ("ampeer_sim.profiles.nedu.SINGLE_REGISTER", "b1741201e5ef1384"),
            ("ampeer_sim.profiles.nedu.SUM_TOLERANCE", "1187132475a4431d"),
            ("ampeer_sim.profiles.nedu.YEAR_ROW", "6b86b273ff34fce1"),
            ("ampeer_sim.profiles.presence.EVENING_WINDOW", "e8c3a86ba10aea79"),
            ("ampeer_sim.profiles.presence.MIDDAY_WINDOW", "cbd2debb98ebecca"),
            ("ampeer_sim.simulate.DEFAULT_WEATHER_YEAR", "d398b29d3dbbb9bf"),
            ("ampeer_sim.timebase.DST_SWITCH_QUARTER", "2c624232cdd22177"),
            ("ampeer_sim.timebase.HOURLY_MEAN_ANCHOR_MINUTES", "26c9a96ce053a14d"),
            ("ampeer_sim.timebase.HOURS_PER_DAY", "c2356069e9d1e79c"),
            ("ampeer_sim.timebase.MINUTES_PER_DAY", "a4ff3ad278c7b057"),
            ("ampeer_sim.timebase.MINUTES_PER_QUARTER", "e629fa6598d73276"),
            ("ampeer_sim.timebase.QUARTERS_PER_DAY", "7b1a278f5abe8e9d"),
            ("ampeer_sim.timebase.QUARTERS_PER_HOUR", "4b227777d4dd1fc6"),
            ("ampeer_sim.validate.DEFAULT_PROFILE_YEAR", "b2b2f104d32c6389"),
            ("ampeer_sim.validate.DEFAULT_TOLERANCE_PERCENT", "f1e42019aecc858f"),
            ("ampeer_sim.validate.REQUIRED_FIELDS", "45b84058cdd90331"),
        ),
    }
    assert ENGINE_VERSION in snapshot, (
        f"ENGINE_VERSION is {ENGINE_VERSION!r} and this table has no row for it. "
        "A module level constant is as much a part of what an engine computes with "
        "as a dataclass default, and an advice stamped with a version whose "
        "constants nobody wrote down cannot be reproduced either."
    )
    actual = _engine_module_constants()
    assert actual == snapshot[ENGINE_VERSION], (
        "the engine computes with different module level constants than the version says:\n"
        + _difference(actual, snapshot[ENGINE_VERSION])
        + "\nThe values behind those digests, as they stand now:\n"
        + _live_constant_values(actual, snapshot[ENGINE_VERSION])
        + f"\nEither restore the value or move ENGINE_VERSION past {ENGINE_VERSION} "
        "and add a row above."
    )


def test_the_golden_answers_are_pinned_to_the_engine_version() -> None:
    """The other way the engine's numbers move without the version moving.

    A constant can stay put while the arithmetic around it changes, and the
    golden households are where that shows: six answers computed end to end. The
    tests above already fail when one of them drifts, which is what makes
    updating tests/golden/households.json the ordinary response, and that edit
    is a single file with no mention of a version anywhere in it.

    Pinning them here does not make the goldens harder to update. It makes
    updating them say which engine the new answers belong to.
    """
    snapshot = {
        "0.1.0": (
            ("hand_checkable.expected_consumption_kwh", 3650.0),
            ("hand_checkable.expected_self_consumption_rate", 0.9381),
            ("large_array_small_use.expected_consumption_kwh", 2200.0),
            ("large_array_small_use.expected_self_consumption_rate", 0.1134),
            ("marloes_ev_at_night.expected_consumption_kwh", 5700.0),
            ("marloes_ev_at_night.expected_self_consumption_rate", 0.2557),
            ("marloes_ev_on_solar.expected_consumption_kwh", 5700.0),
            ("marloes_ev_on_solar.expected_self_consumption_rate", 0.7572),
            ("rob_fixed_contract.expected_consumption_kwh", 3500.0),
            ("rob_fixed_contract.expected_self_consumption_rate", 0.332),
            ("sander_heat_pump.expected_consumption_kwh", 6802.0),
            ("sander_heat_pump.expected_self_consumption_rate", 0.5032),
        ),
        # 0.2.0 centred the offline daily shape on solar noon and stopped
        # normalising it against a closed form that was 0.29 percent high. Five
        # of the six rates moved up between 0.001 and 0.009 and sander's moved
        # down by 0.006; tests/golden/README.md says why each went the way it
        # did. No tolerance moved, and no household's postcode, array or demand
        # moved either, so every difference below is the engine and nothing else.
        "0.2.0": (
            ("hand_checkable.expected_consumption_kwh", 3650.0),
            ("hand_checkable.expected_self_consumption_rate", 0.9391),
            ("large_array_small_use.expected_consumption_kwh", 2200.0),
            ("large_array_small_use.expected_self_consumption_rate", 0.1194),
            ("marloes_ev_at_night.expected_consumption_kwh", 5700.0),
            ("marloes_ev_at_night.expected_self_consumption_rate", 0.2647),
            ("marloes_ev_on_solar.expected_consumption_kwh", 5700.0),
            ("marloes_ev_on_solar.expected_self_consumption_rate", 0.7661),
            ("rob_fixed_contract.expected_consumption_kwh", 3500.0),
            ("rob_fixed_contract.expected_self_consumption_rate", 0.341),
            ("sander_heat_pump.expected_consumption_kwh", 6802.0),
            ("sander_heat_pump.expected_self_consumption_rate", 0.4977),
        ),
        # 0.3.0 moved the PVGIS path by an hour and left every figure below
        # exactly where 0.2.0 put it. That is not a value going unrecorded: the
        # six households above run on FallbackProvider, on purpose, so that the
        # suite needs no network, and the fallback builds its day in the grid's
        # winter time already. A row identical to the one above it is the honest
        # entry for an engine version whose change this file cannot reach, and
        # tests/golden/README.md says the same in prose with the numbers that did
        # move. The check that did reach it is in tests/test_calibration.py.
        "0.3.0": (
            ("hand_checkable.expected_consumption_kwh", 3650.0),
            ("hand_checkable.expected_self_consumption_rate", 0.9391),
            ("large_array_small_use.expected_consumption_kwh", 2200.0),
            ("large_array_small_use.expected_self_consumption_rate", 0.1194),
            ("marloes_ev_at_night.expected_consumption_kwh", 5700.0),
            ("marloes_ev_at_night.expected_self_consumption_rate", 0.2647),
            ("marloes_ev_on_solar.expected_consumption_kwh", 5700.0),
            ("marloes_ev_on_solar.expected_self_consumption_rate", 0.7661),
            ("rob_fixed_contract.expected_consumption_kwh", 3500.0),
            ("rob_fixed_contract.expected_self_consumption_rate", 0.341),
            ("sander_heat_pump.expected_consumption_kwh", 6802.0),
            ("sander_heat_pump.expected_self_consumption_rate", 0.4977),
        ),
        # 0.4.0. The six households run on FallbackProvider, whose day is built
        # in winter time and read at the same stamp it is built on, so moving
        # the PVGIS anchor leaves five of the six exactly where they were. Only
        # sander_heat_pump moves, because a heat pump reads a temperature series
        # through the same anchor and its degree hours shift with it.
        "0.4.0": (
            ("hand_checkable.expected_consumption_kwh", 3650.0),
            ("hand_checkable.expected_self_consumption_rate", 0.9391),
            ("large_array_small_use.expected_consumption_kwh", 2200.0),
            ("large_array_small_use.expected_self_consumption_rate", 0.1194),
            ("marloes_ev_at_night.expected_consumption_kwh", 5700.0),
            ("marloes_ev_at_night.expected_self_consumption_rate", 0.2647),
            ("marloes_ev_on_solar.expected_consumption_kwh", 5700.0),
            ("marloes_ev_on_solar.expected_self_consumption_rate", 0.7661),
            ("rob_fixed_contract.expected_consumption_kwh", 3500.0),
            ("rob_fixed_contract.expected_self_consumption_rate", 0.341),
            ("sander_heat_pump.expected_consumption_kwh", 6802.0),
            ("sander_heat_pump.expected_self_consumption_rate", 0.4977),
        ),
        # 0.5.0 moved no golden answer. ampeer_sim.fit takes no part in a
        # simulation, so all twelve figures are 0.4.0's to the digit, and that is
        # the point of copying them here rather than pointing at the row above: a
        # reader comparing two advices across the bump can see that nothing they
        # depend on moved.
        "0.5.0": (
            ("hand_checkable.expected_consumption_kwh", 3650.0),
            ("hand_checkable.expected_self_consumption_rate", 0.9391),
            ("large_array_small_use.expected_consumption_kwh", 2200.0),
            ("large_array_small_use.expected_self_consumption_rate", 0.1194),
            ("marloes_ev_at_night.expected_consumption_kwh", 5700.0),
            ("marloes_ev_at_night.expected_self_consumption_rate", 0.2647),
            ("marloes_ev_on_solar.expected_consumption_kwh", 5700.0),
            ("marloes_ev_on_solar.expected_self_consumption_rate", 0.7661),
            ("rob_fixed_contract.expected_consumption_kwh", 3500.0),
            ("rob_fixed_contract.expected_self_consumption_rate", 0.341),
            ("sander_heat_pump.expected_consumption_kwh", 6802.0),
            ("sander_heat_pump.expected_self_consumption_rate", 0.4977),
        ),
    }
    assert ENGINE_VERSION in snapshot, (
        f"ENGINE_VERSION is {ENGINE_VERSION!r} and no golden answers are recorded for it"
    )
    actual = _golden_answers()
    assert actual == snapshot[ENGINE_VERSION], (
        "the golden households no longer hold the answers this engine version promises:\n"
        + _difference(actual, snapshot[ENGINE_VERSION])
        + f"\nIf the engine changed on purpose, move ENGINE_VERSION past {ENGINE_VERSION} "
        "and record the new answers above."
    )
