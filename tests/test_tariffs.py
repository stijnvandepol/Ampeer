from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from ampeer_sim.economics.tariffs import annual_cost, compare
from ampeer_sim.types import EnergyFlows, TariffSet

FIXED_2026 = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.27"),
    standing_charge_year=Decimal("120.00"),
    net_metering=True,
)
FIXED_2027 = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.05"),
    feed_in_fixed_cost_year=Decimal("90.00"),
    standing_charge_year=Decimal("120.00"),
    net_metering=False,
)


def _flows(from_grid: float, to_grid: float, steps: int = 4) -> EnergyFlows:
    zeros = np.zeros(steps)
    return EnergyFlows(
        consumption=np.full(steps, from_grid / steps),
        production=np.full(steps, to_grid / steps),
        self_consumption=zeros,
        from_grid=np.full(steps, from_grid / steps),
        to_grid=np.full(steps, to_grid / steps),
        battery_charge=zeros,
        battery_discharge=zeros,
    )


def test_cost_is_a_decimal() -> None:
    assert isinstance(annual_cost(_flows(1_000.0, 0.0), FIXED_2027), Decimal)


def test_pure_offtake_costs_price_times_volume_plus_standing_charge() -> None:
    cost = annual_cost(_flows(1_000.0, 0.0), FIXED_2027)
    assert cost == Decimal("390.000")


def test_a_household_that_never_feeds_in_is_not_billed_for_feeding_in() -> None:
    with_feed_in = annual_cost(_flows(1_000.0, 1.0), FIXED_2027)
    without_feed_in = annual_cost(_flows(1_000.0, 0.0), FIXED_2027)
    assert with_feed_in - without_feed_in == pytest.approx(
        Decimal("90.00") - Decimal("0.05"), abs=Decimal("0.001")
    )


def test_net_metering_cancels_feed_in_against_offtake() -> None:
    cost = annual_cost(_flows(2_000.0, 800.0), FIXED_2026)
    # 1200 kWh net offtake at 0.27 plus the standing charge.
    assert cost == Decimal("444.000")


def test_net_metering_never_pays_more_than_the_offtake_is_worth() -> None:
    cost = annual_cost(_flows(500.0, 2_000.0), FIXED_2026)
    surplus = Decimal("1500") * Decimal("0.27")
    assert cost == Decimal("120.000") - surplus


def test_without_net_metering_feed_in_earns_the_feed_in_price() -> None:
    cost = annual_cost(_flows(2_000.0, 800.0), FIXED_2027)
    expected = (
        Decimal("2000") * Decimal("0.27")
        - Decimal("800") * Decimal("0.05")
        + Decimal("90.00")
        + Decimal("120.00")
    )
    assert cost == expected


def test_a_dynamic_contract_prices_each_quarter_separately() -> None:
    tariffs = TariffSet(supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True)
    prices = np.array([0.10, 0.20, 0.30, 0.40])
    cost = annual_cost(_flows(400.0, 0.0), tariffs, prices_per_quarter=prices)
    assert cost == Decimal("100.000")


def test_a_dynamic_contract_requires_prices() -> None:
    tariffs = TariffSet(supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True)
    with pytest.raises(ValueError, match="dynamic"):
        annual_cost(_flows(400.0, 0.0), tariffs)


def test_a_dynamic_contract_rejects_a_mismatched_price_series() -> None:
    tariffs = TariffSet(supply_price=Decimal("0.27"), feed_in_price=Decimal("0.05"), dynamic=True)
    with pytest.raises(ValueError, match="same length"):
        annual_cost(_flows(400.0, 0.0), tariffs, prices_per_quarter=np.zeros(3))


def test_arbitrage_flows_reach_the_meter() -> None:
    steps = 4
    zeros = np.zeros(steps)
    flows = EnergyFlows(
        consumption=zeros,
        production=zeros,
        self_consumption=zeros,
        from_grid=zeros,
        to_grid=zeros,
        battery_charge=zeros,
        battery_discharge=zeros,
        grid_charge=np.full(steps, 250.0),
        grid_discharge=zeros,
    )
    # 1000 kWh bought for the battery is still 1000 kWh off the meter.
    assert annual_cost(flows, FIXED_2027) == Decimal("390.000")


def test_compare_returns_the_difference_between_two_tariff_sets() -> None:
    result = compare(_flows(2_000.0, 800.0), baseline=FIXED_2026, scenario=FIXED_2027)
    assert result.difference_eur == result.scenario_eur - result.baseline_eur
    assert result.difference_eur > 0


def test_feed_in_charges_scale_with_exported_volume() -> None:
    """Suppliers price feed-in charges per kWh, not as a flat annual fee.

    That is not only a different number but different behaviour: a per kWh
    charge falls hardest on the household with the largest array, which is
    exactly the audience this product is for.
    """
    tariffs = TariffSet(
        supply_price=Decimal("0.26"),
        feed_in_price=Decimal("0.065"),
        feed_in_cost_per_kwh=Decimal("0.075"),
    )
    small = annual_cost(_flows(0.0, 1_000.0), tariffs)
    large = annual_cost(_flows(0.0, 2_000.0), tariffs)
    # Net feed-in is 0.065 - 0.075 = -0.010 per kWh, so exporting costs money
    # and twice the export costs twice as much.
    assert small == Decimal("10.000")
    assert large == Decimal("20.000")


def test_a_household_that_never_exports_pays_no_per_kwh_feed_in_charge() -> None:
    tariffs = TariffSet(
        supply_price=Decimal("0.26"),
        feed_in_price=Decimal("0.065"),
        feed_in_cost_per_kwh=Decimal("0.075"),
    )
    assert annual_cost(_flows(1_000.0, 0.0), tariffs) == Decimal("260.000")


# ---------------------------------------------------------------------------
# A tariff set that says two things this function cannot honour at once
# ---------------------------------------------------------------------------

QUARTERS_PER_DAY = 96


def _shaped_year() -> tuple[EnergyFlows, np.ndarray]:
    """A year with the export at midday, the offtake in the evening peak.

    Flat is the wrong fixture here and it is what the rest of this file uses.
    With one price all year, netting kilowatt hours and pricing them separately
    come to the same euro, so the term below is worth nothing and the fixture
    proves nothing. What makes saldering valuable is exactly that the exported
    kilowatt hour and the offtaken one are worth different amounts, which needs
    a day shape to exist.
    """
    steps = 365 * QUARTERS_PER_DAY
    quarter = np.arange(steps) % QUARTERS_PER_DAY
    midday = (quarter >= 40) & (quarter < 64)
    evening = (quarter >= 68) & (quarter < 88)

    export = np.where(midday, 1.0, 0.0)
    offtake = np.where(evening, 1.0, 0.0)
    export *= 2_600.0 / export.sum()
    offtake *= 3_500.0 / offtake.sum()

    prices = 0.10 + 0.22 * evening - 0.05 * midday
    zeros = np.zeros(steps)
    flows = EnergyFlows(
        consumption=offtake,
        production=export,
        self_consumption=zeros,
        from_grid=offtake,
        to_grid=export,
        battery_charge=zeros,
        battery_discharge=zeros,
    )
    return flows, prices


def test_net_metering_on_a_dynamic_tariff_is_refused_rather_than_dropped() -> None:
    """Both flags set is not a caller's mistake, and the branch dropped one.

    Saldering applies whatever the contract until 1 January 2027, so for a 2026
    household on a dynamic contract ``dynamic=True, net_metering=True`` is the
    accurate description. Until 2026-08-23 ``annual_cost`` took the dynamic
    branch of an if/elif and never looked at the netting, and returned a figure
    with no sign that half of what it was told had been ignored.

    Refusing rather than picking a reading. The netting settles a volume over a
    year and the dynamic path settles 35040 quarters, and which price the netted
    residual is worth is a question the supplier's terms answer rather than this
    function.
    """
    flows, prices = _shaped_year()
    contradictory = TariffSet(
        supply_price=Decimal("0.1333"),
        feed_in_price=Decimal("0.1333"),
        net_metering=True,
        dynamic=True,
    )
    with pytest.raises(ValueError, match="not modelled"):
        annual_cost(flows, contradictory, prices_per_quarter=prices)


def test_each_flag_on_its_own_still_prices() -> None:
    """The floor under the refusal, which is a raise on a conjunction.

    A guard on the wrong operator would refuse every dynamic tariff and every
    net metered one, and the suite would still be green on the test above.
    """
    flows, prices = _shaped_year()
    dynamic_only = TariffSet(
        supply_price=Decimal("0.1333"), feed_in_price=Decimal("0.1333"), dynamic=True
    )
    netting_only = TariffSet(
        supply_price=Decimal("0.1333"), feed_in_price=Decimal("0.1333"), net_metering=True
    )
    assert isinstance(annual_cost(flows, dynamic_only, prices_per_quarter=prices), Decimal)
    assert isinstance(annual_cost(flows, netting_only), Decimal)


def test_the_dropped_term_was_worth_refusing_over() -> None:
    """Why this is a raise and not a comment saying the flag wins.

    The two readings of that one tariff set, measured on 2026-08-23: pricing
    every quarter at the market price comes to 990 euro, netting the year and
    settling the residual comes to 119.97. A caller who wrote both flags got the
    first and asked for something that includes the second.

    Pinned as a floor rather than to the cent, so the fixture can be made more
    realistic without this becoming a number to update. What must not change is
    the order of magnitude: if this term ever shrinks to a rounding difference,
    the raise above is overreacting and should be revisited rather than kept.
    """
    flows, prices = _shaped_year()
    average = Decimal("0.1333")
    dynamic_only = TariffSet(supply_price=average, feed_in_price=average, dynamic=True)
    netting_only = TariffSet(supply_price=average, feed_in_price=average, net_metering=True)

    priced_per_quarter = annual_cost(flows, dynamic_only, prices_per_quarter=prices)
    netted_over_the_year = annual_cost(flows, netting_only)
    assert priced_per_quarter - netted_over_the_year > Decimal("500"), (
        f"the two readings are {priced_per_quarter - netted_over_the_year} euro apart, which is "
        "small enough that refusing to choose between them is heavier than the problem"
    )
