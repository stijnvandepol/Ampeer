from __future__ import annotations

from decimal import Decimal

from ampeer_advice.battery import CAPACITIES, battery_advice, find_knee


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


def test_payback_uses_the_cost_band_so_it_has_a_spread() -> None:
    curve = [(c, Decimal(str(c * 100))) for c in CAPACITIES]
    advice = battery_advice(curve)
    assert advice.payback_years_p10 < advice.payback_years_p50 < advice.payback_years_p90


def test_the_curve_is_carried_through_for_the_frontend() -> None:
    curve = [(c, Decimal(str(c * 100))) for c in CAPACITIES]
    assert battery_advice(curve).curve == tuple(curve)


def test_a_curve_that_saves_nothing_reports_an_unreachable_payback() -> None:
    curve = [(c, Decimal("0")) for c in CAPACITIES]
    advice = battery_advice(curve)
    assert advice.payback_years_p50 > Decimal("100")
