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

Nothing here rounds anything. It used to round two of its outputs with a
constant called PAYBACK_PRECISION, documented as "payback in years, to the
hundredth", which also quantized the break even price in euro. Changing that
constant to a tenth of a year, an entirely reasonable edit to a payback time,
would have rounded a price to the dime with nothing to show for it. Display
precision belongs to whatever displays the figure, so both now leave here at
full precision and ``backend/advice/rendering.py`` decides how they are
written down.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from itertools import pairwise

from ampeer_advice.tariffs import BATTERY_COST_PER_KWH
from ampeer_advice.types import BatteryAdvice, ScenarioBand

#: The name the payback band adds to the inputs it varied. Named rather than
#: written inline, because tests/test_advice_nl.py pairs every name a band can
#: emit with the Dutch table in nl.py, and a name buried in a tuple literal is
#: one that pairing has to be told about by hand instead of reading.
BATTERY_PRICE_INPUT = "battery_cost_per_kwh"

#: The capacities that are simulated. Five points, because the curve is smooth
#: and more points cost time without moving the knee.
CAPACITIES: tuple[float, ...] = (3.0, 5.0, 7.0, 10.0, 15.0)

#: A battery that saves nothing has no payback time at all. Dividing by zero is
#: not an option and neither is hiding the case, so it is rendered as a number
#: that no reader will mistake for a real answer.
NO_PAYBACK_YEARS = Decimal("999.00")

#: A battery that has not paid for itself within this many years has not paid
#: for itself, because the warranty runs out around ten. This is the only
#: definition of it in the package: advise.py held a second copy of the same
#: number, and because the verdict read that one while the break even price and
#: the published methodology read this one, changing either one alone moved the
#: sentence a household is shown without moving the price printed beside it or
#: the number in the document, and the whole suite stayed green.
#: ``tests/test_advise.py`` now fails on a second definition anywhere in the
#: package.
MAX_ACCEPTABLE_PAYBACK_YEARS = Decimal("12")


def find_knee(curve: Sequence[tuple[float, Decimal]]) -> float:
    """Return the largest capacity that still earns its extra kWh.

    ``curve`` is a sequence of ``(capacity_kwh, annual_saving_eur)`` pairs. The
    reference is the marginal saving per extra kWh of the first step, that is
    the step from no battery at all up to the smallest capacity offered. A
    following step counts as worthwhile when the extra saving it brings is at
    least half of that reference, and the first step that fails ends the search.

    Stopping there rests on the curve not recovering. It very nearly does not:
    measured on 2026-08-23 over the golden capacity curves, the marginal saving
    is non-increasing except for rises of at most 0.0005 euro per kWh, against
    thresholds of tens of euro per kWh. Near enough is not the same as true, so
    the weaker property the break actually needs, that the steps clearing the
    threshold form an unbroken run from the start, is asserted in
    ``tests/test_advise.py`` rather than assumed here.

    When no step ever falls below the threshold the answer is the largest
    capacity in ``curve``, which means the search ran out of curve rather than
    finding a knee: the true knee may be larger still. The number alone cannot
    say which of the two happened, so ``battery_advice`` records it in a field
    of its own rather than leaving the reader to notice that the answer happens
    to equal the top of ``CAPACITIES``.
    """
    points = sorted(curve)
    first_capacity, first_saving = points[0]
    reference = first_saving / Decimal(str(first_capacity))
    threshold = reference / 2
    knee = first_capacity
    for (previous_capacity, previous_saving), (capacity, saving) in pairwise(points):
        # Both sides must be euro per kWh. Comparing a whole step's euro total
        # against a per kWh threshold made every step look worthwhile, because
        # the steps are two to five kWh wide, and that sized batteries larger
        # than this docstring promises. It failed in the direction that sells
        # more storage, which is the direction this product must never fail in.
        width = Decimal(str(capacity - previous_capacity))
        if (saving - previous_saving) / width < threshold:
            break
        knee = capacity
    return knee


def battery_advice(curve: Sequence[tuple[float, ScenarioBand]]) -> BatteryAdvice:
    """Turn a capacity curve into a recommendation with a payback band.

    Every point on the curve arrives as a band already, because the saving a
    battery makes depends on the tariffs it is priced against. Payback is the
    investment divided by that saving, so its band is the product of two
    things that both move: the installed price, which spans a factor two
    nationally, and the tariff level, which moves the saving itself. All nine
    combinations are priced and the extremes of them are the ends of the band.

    That is deliberately wider than the band this function used to report. The
    old one moved the battery price only and left the tariffs at their central
    value, which made the optimistic end read as payback at the cheapest quote
    in the market under tariffs assumed to be exactly right. It was published
    under the names p10 and p50 and p90, which claimed percentiles of a
    distribution nobody had sampled, and it favoured the battery.

    It is still not the full picture, and the band says so itself: annual
    consumption, the size of the shiftable block and the system loss stay at
    their central values here, because the curve costs five year simulations
    per level and a factorial over those would cost a hundred and thirty five.
    They travel in ``pinned``, so the response can state that the true spread
    is wider than the one it shows rather than implying the opposite.

    The knee is taken on the central values of the curve. It has to be a single
    choice, because a household buys one battery, and the central case is the
    one every other decision in this package is taken on.
    """
    points = tuple(sorted(curve, key=lambda point: point[0]))
    central = [(capacity, band.mid) for capacity, band in points]
    capacity = find_knee(central)
    saving = next(band for size, band in points if size == capacity)

    def payback(cost_per_kwh: Decimal, annual_saving: Decimal) -> Decimal:
        if annual_saving <= Decimal("0"):
            return NO_PAYBACK_YEARS
        investment = Decimal(str(capacity)) * cost_per_kwh
        return investment / annual_saving

    def break_even(annual_saving: Decimal) -> Decimal:
        if annual_saving <= Decimal("0"):
            return Decimal("0")
        return annual_saving * MAX_ACCEPTABLE_PAYBACK_YEARS / Decimal(str(capacity))

    costs = (BATTERY_COST_PER_KWH.low, BATTERY_COST_PER_KWH.mid, BATTERY_COST_PER_KWH.high)
    savings = (saving.low, saving.mid, saving.high)

    return BatteryAdvice(
        sized_capacity_kwh=capacity,
        sized_at_largest_simulated_capacity=capacity == points[-1][0],
        annual_saving_eur=saving,
        payback_years=ScenarioBand.over(
            values=[payback(cost, value) for cost in costs for value in savings],
            mid=payback(BATTERY_COST_PER_KWH.mid, saving.mid),
            varied=(*saving.varied, BATTERY_PRICE_INPUT),
            pinned=saving.pinned,
        ),
        curve=points,
        break_even_cost_per_kwh=ScenarioBand.over(
            values=[break_even(value) for value in savings],
            mid=break_even(saving.mid),
            # The battery price is what this figure is compared against, so it
            # cannot be one of the things that moves it. Varying it here would
            # be asking at which price the price is worth paying.
            varied=saving.varied,
            pinned=saving.pinned,
        ),
    )
