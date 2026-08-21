from __future__ import annotations

from decimal import Decimal

import pytest

from ampeer_advice.battery import (
    CAPACITIES,
    MAX_ACCEPTABLE_PAYBACK_YEARS,
    battery_advice,
    find_knee,
)
from ampeer_advice.types import ScenarioBand

#: The inputs a curve built here says it moved. The real curve gets these from
#: ampeer_advice.tariffs; a test only needs them to be a non-empty list of
#: names, because what is asserted below is that they travel with the band.
VARIED = ("supply_price", "feed_in_price", "feed_in_cost_per_kwh")
PINNED = ("annual_consumption_kwh",)


def _band(low: str, mid: str, high: str) -> ScenarioBand:
    """One point on a capacity curve, measured at three tariff levels."""
    return ScenarioBand.over(
        values=[Decimal(low), Decimal(mid), Decimal(high)],
        mid=Decimal(mid),
        varied=VARIED,
        pinned=PINNED,
    )


def _flat_curve(euro_per_kwh: int) -> list[tuple[float, ScenarioBand]]:
    """A curve whose saving is exactly linear in capacity, at every level."""
    return [
        (
            capacity,
            _band(
                str(capacity * euro_per_kwh * 0.8),
                str(capacity * euro_per_kwh),
                str(capacity * euro_per_kwh * 1.2),
            ),
        )
        for capacity in CAPACITIES
    ]


def test_the_capacities_are_the_five_the_spec_names() -> None:
    assert CAPACITIES == (3.0, 5.0, 7.0, 10.0, 15.0)


def test_the_knee_is_where_marginal_saving_halves() -> None:
    """Both sides of the comparison are euro per kWh.

    The earlier version of this test asserted 5.0 on a curve whose second step
    earns 45 euro per kWh against a threshold of 50, and it passed only because
    find_knee compared a whole step's euro total against a per kWh threshold.
    The comment claimed 45 was above half of 100. It is not. Test and code
    agreed on the same arithmetic error, which is the failure mode a test is
    supposed to prevent.
    """
    curve = [
        (3.0, Decimal("300")),  # reference is 100 per kWh, so the threshold is 50
        (5.0, Decimal("420")),  # 120 over 2 kWh is 60 per kWh, above 50
        (7.0, Decimal("450")),  # 30 over 2 kWh is 15 per kWh, below 50
        (10.0, Decimal("460")),
        (15.0, Decimal("465")),
    ]
    assert find_knee(curve) == 5.0


def test_a_step_just_under_half_the_reference_ends_the_search() -> None:
    """The exact curve the old test used, now asserting the correct answer."""
    curve = [
        (3.0, Decimal("300")),  # reference 100 per kWh, threshold 50
        (5.0, Decimal("390")),  # 90 over 2 kWh is 45 per kWh, below 50
        (7.0, Decimal("420")),
        (10.0, Decimal("430")),
        (15.0, Decimal("435")),
    ]
    assert find_knee(curve) == 3.0


def test_a_perfectly_linear_curve_recommends_the_largest_capacity() -> None:
    curve = [(c, Decimal(str(c * 100))) for c in CAPACITIES]
    assert find_knee(curve) == 15.0


def test_a_curve_that_flattens_immediately_recommends_the_smallest() -> None:
    curve = [
        (3.0, Decimal("300")),
        (5.0, Decimal("305")),
        (7.0, Decimal("306")),
        (10.0, Decimal("307")),
        (15.0, Decimal("308")),
    ]
    assert find_knee(curve) == 3.0


def test_the_knee_is_taken_on_the_central_values_of_the_curve() -> None:
    """A household buys one battery, so the size has to be one choice.

    The curve is a band at every point, and sizing on the optimistic end of it
    would recommend more storage than the central case supports. This curve
    flattens at 5.0 in the middle and keeps climbing at its high end, so the two
    answers differ and the test can tell which one was used.
    """
    curve = [
        (3.0, _band("240", "300", "360")),
        (5.0, _band("336", "420", "900")),
        (7.0, _band("360", "450", "1400")),
        (10.0, _band("368", "460", "2000")),
        (15.0, _band("372", "465", "3000")),
    ]
    assert battery_advice(curve).sized_capacity_kwh == 5.0


def test_payback_varies_the_tariffs_as_well_as_the_battery_price() -> None:
    """The band used to move the battery price and pin everything else.

    That made its optimistic end the payback at the cheapest quote in the
    market under tariffs assumed exactly right, and it was published under the
    percentile names the headline uses. Both ends now move with the saving as
    well, which is nine priced combinations rather than three.
    """
    advice = battery_advice(_flat_curve(100))
    assert advice.payback_years.combinations == 9
    assert set(advice.payback_years.varied) == {*VARIED, "battery_cost_per_kwh"}
    assert advice.payback_years.pinned == PINNED
    assert advice.payback_years.low < advice.payback_years.mid < advice.payback_years.high


def test_the_payback_band_is_wider_than_the_battery_price_alone_makes_it() -> None:
    """The correction, stated as an inequality rather than as a number.

    Varying the battery price alone gives 450/675 of the central payback at the
    low end and 900/675 at the high end. Anything narrower than that would mean
    the tariff band had been dropped again.
    """
    advice = battery_advice(_flat_curve(100))
    price_only_low = advice.payback_years.mid * Decimal("450") / Decimal("675")
    price_only_high = advice.payback_years.mid * Decimal("900") / Decimal("675")
    assert advice.payback_years.low < price_only_low
    assert advice.payback_years.high > price_only_high


def test_the_break_even_price_is_a_band_and_does_not_vary_the_battery_price() -> None:
    """It is the price a quote is compared against, so the price cannot move it.

    What does move it is the tariff level, because the break even price is the
    annual saving times the twelve year limit, and the saving is what nobody
    knows.
    """
    advice = battery_advice(_flat_curve(100))
    band = advice.break_even_cost_per_kwh
    assert band.varied == VARIED
    assert "battery_cost_per_kwh" not in band.varied
    assert band.low < band.mid < band.high
    assert band.combinations == 3


def test_no_money_figure_is_rounded_before_it_reaches_the_renderer() -> None:
    """Rounding lives in one place and this module is not it.

    The break even price used to be quantized here by PAYBACK_PRECISION, a
    constant whose docstring said "payback in years, to the hundredth". Editing
    that to a tenth of a year, which is a reasonable thing to want, would have
    rounded a price to the dime without a word of warning. This asserts the
    division arrives unrounded: 300 times 12 over 7 does not terminate at two
    decimals, and neither does 7 times 675 over 330.
    """
    curve = [(7.0, _band("264", "330", "396"))]
    advice = battery_advice(curve)
    assert advice.break_even_cost_per_kwh.mid == Decimal("330") * Decimal("12") / Decimal("7")
    cents = Decimal("0.01")
    assert advice.break_even_cost_per_kwh.mid != advice.break_even_cost_per_kwh.mid.quantize(cents)
    assert advice.payback_years.mid != advice.payback_years.mid.quantize(cents)


def test_a_knee_at_the_largest_simulated_capacity_says_so() -> None:
    """15.0 kWh means the search ran out of curve, not that the knee is at 15.

    The number alone cannot tell those apart, and the difference matters: in
    one case a larger battery is worse and in the other it may be better and
    was never measured.
    """
    assert battery_advice(_flat_curve(100)).sized_at_largest_simulated_capacity is True


def test_a_knee_inside_the_range_is_not_reported_as_a_limit() -> None:
    curve = [
        (3.0, _band("240", "300", "360")),
        (5.0, _band("244", "305", "366")),
        (7.0, _band("245", "306", "367")),
        (10.0, _band("246", "307", "368")),
        (15.0, _band("246", "308", "370")),
    ]
    advice = battery_advice(curve)
    assert advice.sized_capacity_kwh == 3.0
    assert advice.sized_at_largest_simulated_capacity is False


def test_the_curve_is_carried_through_for_the_frontend() -> None:
    curve = _flat_curve(100)
    assert battery_advice(curve).curve == tuple(curve)


def test_a_curve_that_saves_nothing_reports_an_unreachable_payback() -> None:
    curve = [(c, _band("0", "0", "0")) for c in CAPACITIES]
    advice = battery_advice(curve)
    assert advice.payback_years.mid > Decimal("100")
    assert advice.break_even_cost_per_kwh.mid == Decimal("0")


def test_the_payback_limit_is_the_twelve_years_the_dutch_text_names() -> None:
    assert MAX_ACCEPTABLE_PAYBACK_YEARS == Decimal("12")


def test_a_band_may_not_be_measured_around_a_middle_that_was_never_measured() -> None:
    """The invariant that keeps a band honest about its own centre.

    Every decision in this package is taken on the central value. If that value
    could come from somewhere other than the measured set, the figure decided on
    and the band shown around it would be two different measurements and nothing
    in the response would say so.
    """
    with pytest.raises(ValueError, match="central value"):
        ScenarioBand.over(
            values=[Decimal("1"), Decimal("3")],
            mid=Decimal("2"),
            varied=VARIED,
            pinned=PINNED,
        )


def test_a_band_with_nothing_measured_is_refused() -> None:
    """An empty measurement cannot be a band, and it cannot be a figure either.

    It would only happen through a programming fault, and the alternative to
    raising is a response that shows a band shaped like every other band with
    nothing behind it.
    """
    with pytest.raises(ValueError, match="at least one"):
        ScenarioBand.over(values=[], mid=Decimal("1"), varied=VARIED, pinned=PINNED)


def test_a_band_that_varies_nothing_is_refused() -> None:
    """A band with an empty ``varied`` is three copies of one number.

    It would render as a band and read as one, which is worse than sending a
    figure that is honestly alone.
    """
    with pytest.raises(ValueError, match="varies nothing"):
        ScenarioBand(
            low=Decimal("1"),
            mid=Decimal("2"),
            high=Decimal("3"),
            varied=(),
            pinned=PINNED,
            combinations=3,
        )


def test_a_band_that_runs_backwards_is_refused() -> None:
    with pytest.raises(ValueError, match="ordered"):
        ScenarioBand(
            low=Decimal("3"),
            mid=Decimal("2"),
            high=Decimal("1"),
            varied=VARIED,
            pinned=PINNED,
            combinations=3,
        )
