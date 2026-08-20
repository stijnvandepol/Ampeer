"""The single boundary where kWh become euro.

Nowhere else in the package does a price stand next to an energy series. Energy
sums are quantised before conversion so that float noise cannot leak into a
money figure.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from ampeer_sim.types import EnergyFlows, MoneyResult, TariffSet

#: Energy is rounded to a watt-hour before it becomes money.
KWH_PRECISION = Decimal("0.001")

#: Money is kept at three decimals internally and rounded for display elsewhere.
EUR_PRECISION = Decimal("0.001")


def _to_decimal(value: float, precision: Decimal) -> Decimal:
    return Decimal(repr(float(value))).quantize(precision)


def annual_cost(
    flows: EnergyFlows,
    tariffs: TariffSet,
    prices_per_quarter: np.ndarray | None = None,
) -> Decimal:
    """Return the annual electricity cost in euro. Negative means a net payout."""
    offtake_series = flows.total_import
    feed_in_series = flows.total_export
    offtake = _to_decimal(offtake_series.sum(), KWH_PRECISION)
    feed_in = _to_decimal(feed_in_series.sum(), KWH_PRECISION)

    if tariffs.dynamic:
        if prices_per_quarter is None:
            raise ValueError("a dynamic tariff needs a price series")
        if offtake_series.shape != prices_per_quarter.shape:
            raise ValueError("the price series must have the same length as the flow series")
        supply_cost = _to_decimal(float((offtake_series * prices_per_quarter).sum()), EUR_PRECISION)
        feed_in_revenue = _to_decimal(
            float((feed_in_series * prices_per_quarter).sum()), EUR_PRECISION
        )
    elif tariffs.net_metering:
        netted = min(feed_in, offtake)
        supply_cost = (offtake - netted) * tariffs.supply_price
        feed_in_revenue = (feed_in - netted) * tariffs.feed_in_price
    else:
        supply_cost = offtake * tariffs.supply_price
        feed_in_revenue = feed_in * tariffs.feed_in_price

    # The per kWh charge applies to every exported kWh regardless of contract
    # type, so it is subtracted once here rather than in each branch.
    feed_in_revenue -= feed_in * tariffs.feed_in_cost_per_kwh

    # Feed-in charges are levied on households that feed in. A household that
    # never exports is not billed for the privilege.
    feed_in_fixed = tariffs.feed_in_fixed_cost_year if feed_in > 0 else Decimal("0")

    total = supply_cost - feed_in_revenue + tariffs.standing_charge_year + feed_in_fixed
    return total.quantize(EUR_PRECISION)


def compare(
    flows: EnergyFlows,
    baseline: TariffSet,
    scenario: TariffSet,
    prices_per_quarter: np.ndarray | None = None,
) -> MoneyResult:
    """Price the same energy flows under two tariff sets."""
    return MoneyResult(
        baseline_eur=annual_cost(flows, baseline, prices_per_quarter),
        scenario_eur=annual_cost(flows, scenario, prices_per_quarter),
    )
