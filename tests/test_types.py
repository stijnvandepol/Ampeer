from __future__ import annotations

import dataclasses
from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.providers import ProductionProvider
from ampeer_sim.types import (
    BatterySpec,
    EnergyFlows,
    EVChargingBehaviour,
    Household,
    ProductionSource,
    PVSystem,
)


def test_household_is_frozen() -> None:
    household = Household(postcode4="5401", annual_consumption_kwh=3500.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        household.annual_consumption_kwh = 4000.0  # type: ignore[misc]


def test_pv_system_rejects_impossible_orientation() -> None:
    with pytest.raises(ValueError, match="tilt"):
        PVSystem(peak_power_wp=3500, azimuth_deg=0, tilt_deg=95)


def test_battery_spec_rejects_efficiency_above_one() -> None:
    with pytest.raises(ValueError, match="round_trip_efficiency"):
        BatterySpec(
            capacity_kwh=5.0,
            max_charge_kw=2.5,
            max_discharge_kw=2.5,
            round_trip_efficiency=1.2,
            usable_dod=0.9,
            allow_grid_charging=False,
        )


def test_energy_flows_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        EnergyFlows(
            consumption=np.zeros(4),
            production=np.zeros(4),
            self_consumption=np.zeros(4),
            from_grid=np.zeros(3),
            to_grid=np.zeros(4),
            battery_charge=np.zeros(4),
            battery_discharge=np.zeros(4),
        )


def test_ev_charging_behaviour_members() -> None:
    assert {behaviour.name for behaviour in EVChargingBehaviour} == {
        "NIGHT",
        "ARRIVAL",
        "SOLAR",
    }


def test_fake_provider_satisfies_production_protocol() -> None:
    class FakeProduction:
        def hourly_series(
            self, postcode4: str, azimuth_deg: float, tilt_deg: float
        ) -> tuple[np.ndarray, np.ndarray, ProductionSource]:
            return np.zeros(8760), np.zeros(8760), ProductionSource.FALLBACK

    assert isinstance(FakeProduction(), ProductionProvider)


def test_money_values_are_decimal() -> None:
    from ampeer_sim.types import MoneyResult

    result = MoneyResult(
        baseline_eur=Decimal("1200.00"),
        scenario_eur=Decimal("1840.00"),
    )
    assert result.difference_eur == Decimal("640.00")


# ---------------------------------------------------------------------------
# Money is Decimal, energy is float
# ---------------------------------------------------------------------------

#: How a field's name says which of the two it carries.
#:
#: The order matters and the reason is a mistake worth recording: a first pass
#: read `break_even_cost_per_kwh` as energy because it ends in `_kwh`, and
#: `feed_in_cost_per_kwh` with it. Both are prices. Anything per kilowatt hour
#: is money, and the suffix rule has to be applied to the longer name first or
#: it reports the two most carefully typed fields in the package as defects.
_MONEY_SUFFIXES = ("_eur", "_cost_year")
_MONEY_INFIXES = ("_per_kwh",)
_ENERGY_SUFFIXES = ("_kwh", "_kw")


def _model_dataclasses() -> dict[type, str]:
    """Every dataclass in the two pure packages, found rather than listed.

    A list written here would cover the classes somebody thought of, which is
    the shape of guard this repository keeps replacing.
    """
    import importlib
    import pkgutil

    import ampeer_advice
    import ampeer_sim

    found: dict[type, str] = {}
    for package in (ampeer_sim, ampeer_advice):
        for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            imported = importlib.import_module(module.name)
            for name in dir(imported):
                candidate = getattr(imported, name)
                if isinstance(candidate, type) and dataclasses.is_dataclass(candidate):
                    found[candidate] = f"{candidate.__module__}.{candidate.__name__}"
    return found


def _carries_money(annotation: object) -> bool:
    """Decimal, or a band whose own members are Decimal."""
    import typing

    if annotation is Decimal:
        return True
    if isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        hints = typing.get_type_hints(annotation)
        return any(hints.get(field.name) is Decimal for field in dataclasses.fields(annotation))
    return False


def _classified() -> tuple[list[tuple[str, object]], list[tuple[str, object]]]:
    import typing

    money: list[tuple[str, object]] = []
    energy: list[tuple[str, object]] = []
    for cls, qualified in sorted(_model_dataclasses().items(), key=lambda item: item[1]):
        for field in dataclasses.fields(cls):
            annotation = typing.get_type_hints(cls).get(field.name, field.type)
            name = f"{qualified}.{field.name}"
            if field.name.endswith(_MONEY_SUFFIXES) or any(
                infix in field.name for infix in _MONEY_INFIXES
            ):
                money.append((name, annotation))
            elif field.name.endswith(_ENERGY_SUFFIXES):
                energy.append((name, annotation))
    return money, energy


def test_every_amount_in_euros_is_a_decimal() -> None:
    """The separation CLAUDE.md calls hard, checked rather than trusted.

    A euro held as a float is the defect that does not announce itself: it
    produces a number that looks right, is wrong in the cent, and reaches a
    household as the figure it decides on. Nothing else in the suite asks what
    type a field has; the rendering tests check what a Decimal turns into and
    the golden tests check the values, both downstream of this.

    Measured on 2026-08-22: ten fields carry money and all ten already satisfy
    this, so nothing changes today except that breaking it fails.
    """
    import typing

    money, _ = _classified()
    wrong = [
        (name, annotation)
        for name, annotation in money
        if not all(
            _carries_money(argument)
            for argument in (
                [argument for argument in typing.get_args(annotation) if argument is not type(None)]
                or [annotation]
            )
        )
    ]
    assert not wrong, "euro amounts that are not Decimal:\n" + "\n".join(
        f"  {name}: {annotation}" for name, annotation in wrong
    )


def test_every_quantity_in_kilowatt_hours_is_a_float() -> None:
    """The other half, and it is not symmetry for its own sake.

    Energy comes out of measurements and models with an uncertainty of percent.
    A Decimal there would be false precision, and it would invite the arithmetic
    that turns a measurement into an exact quantity.
    """
    import typing

    _, energy = _classified()
    wrong = [
        (name, annotation)
        for name, annotation in energy
        if not all(
            argument is float or argument is int or "ndarray" in str(argument)
            for argument in (
                [argument for argument in typing.get_args(annotation) if argument is not type(None)]
                or [annotation]
            )
        )
    ]
    assert not wrong, "energy quantities that are not float:\n" + "\n".join(
        f"  {name}: {annotation}" for name, annotation in wrong
    )


def test_the_two_checks_above_actually_find_fields() -> None:
    """Neither of them can pass by classifying nothing.

    A suffix list that stopped matching, a walk that imported no module, or a
    package rename would leave both green over an empty list. The counts are
    floors rather than exact numbers, because a new field should not have to
    touch this test to be allowed to exist.
    """
    money, energy = _classified()
    assert len(money) >= 8, f"only {len(money)} money fields found: {[n for n, _ in money]}"
    assert len(energy) >= 15, f"only {len(energy)} energy fields found"
    assert any("feed_in_cost_per_kwh" in name for name, _ in money), (
        "a price per kilowatt hour is no longer classified as money, which is the "
        "misreading this test was written around"
    )
