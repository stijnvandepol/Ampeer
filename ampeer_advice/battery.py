"""Battery sizing: the capacity curve and the knee in it.

The curve says what a battery of a given size saves per year. Its shape is
always the same: the first kWh of storage is worth much more than the last one,
because the first one absorbs the surplus that occurs almost every sunny day
while the last one only earns its keep on the few days with the largest
surplus.

The knee is therefore defined here rather than judged by eye. Take the marginal
saving per extra kWh of the first step as the reference, then keep growing the
battery as long as the next step still brings in at least half of that
reference. Everything above the knee buys capacity that pays itself back ever
more slowly, and recommending it would be selling storage rather than advising
on it.

This module does no I/O and imports no Django, for the same reason as the rest
of the package: a battery recommendation that is one size too large produces no
error message, only an invoice.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from ampeer_advice.tariffs import BATTERY_COST_PER_KWH
from ampeer_advice.types import BatteryAdvice

#: The capacities that are simulated. Five points, because the curve is smooth
#: and more points cost time without moving the knee.
CAPACITIES: tuple[float, ...] = (3.0, 5.0, 7.0, 10.0, 15.0)

#: A battery that saves nothing has no payback time at all. Dividing by zero is
#: not an option and neither is hiding the case, so it is rendered as a number
#: that no reader will mistake for a real answer.
NO_PAYBACK_YEARS = Decimal("999.00")

#: Payback in years, to the hundredth. The band around it is far wider than
#: that, which is exactly why the band is reported next to it.
PAYBACK_PRECISION = Decimal("0.01")


def find_knee(curve: Sequence[tuple[float, Decimal]]) -> float:
    """Return the largest capacity that still earns its extra kWh.

    ``curve`` is a sequence of ``(capacity_kwh, annual_saving_eur)`` pairs. The
    reference is the marginal saving per extra kWh of the first step, that is
    the step from no battery at all up to the smallest capacity offered. A
    following step counts as worthwhile when the extra saving it brings is at
    least half of that reference, and the first step that fails ends the search:
    the curve only flattens, so nothing beyond that point can recover.
    """
    points = sorted(curve)
    first_capacity, first_saving = points[0]
    reference = first_saving / Decimal(str(first_capacity))
    threshold = reference / 2
    knee = first_capacity
    for (_, previous_saving), (capacity, saving) in pairwise(points):
        if saving - previous_saving < threshold:
            break
        knee = capacity
    return knee


def battery_advice(curve: Sequence[tuple[float, Decimal]]) -> BatteryAdvice:
    """Turn a capacity curve into a recommendation with a payback band.

    Payback is the investment divided by the annual saving at the recommended
    capacity. The investment comes from the national cost band, so the payback
    inherits that band: ``low`` gives the optimistic end, ``high`` the
    pessimistic one. That is a coarser band than the headline figure carries,
    because the curve is computed on the central scenario only.
    """
    points = tuple(sorted(curve))
    capacity = find_knee(points)
    saving = next(value for size, value in points if size == capacity)

    def payback(cost_per_kwh: Decimal) -> Decimal:
        if saving <= Decimal("0"):
            return NO_PAYBACK_YEARS
        investment = Decimal(str(capacity)) * cost_per_kwh
        return (investment / saving).quantize(PAYBACK_PRECISION)

    return BatteryAdvice(
        recommended_capacity_kwh=capacity,
        annual_saving_eur=saving,
        payback_years_p10=payback(BATTERY_COST_PER_KWH.low),
        payback_years_p50=payback(BATTERY_COST_PER_KWH.mid),
        payback_years_p90=payback(BATTERY_COST_PER_KWH.high),
        curve=points,
    )
