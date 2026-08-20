"""The ordered rule table.

Rules are data, not code paths. A rule is a condition over ``AdviceContext``, a
route, a priority and a function that estimates what following it is worth. It
returns a rule id, never a sentence: the Dutch text lives in ``nl.py`` and is
attached at the edge, so a copy change and a behaviour change cannot break the
same test.

Conditions read fields, never arrays. ``context.self_consumption_rate < 0.35``
is something you can point at when a household asks on a forum why it got this
advice, and that is the whole requirement.

Three of the six rules estimate no saving at all. Their value is the advice
itself, and attaching a euro figure to "have your existing battery checked"
would be the false precision this project refuses everywhere else.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ampeer_advice.tariffs import FEED_IN_NET_DYNAMIC, SUPPLY_PRICE, net_feed_in_fixed
from ampeer_advice.types import AdviceContext, FiredRule, Route, Rule

#: Energy is rounded to a watt-hour before it becomes money and money is kept at
#: cents, the same convention as the money boundary in ``ampeer_sim``.
KWH_PRECISION = Decimal("0.001")
EUR_PRECISION = Decimal("0.01")

#: Net euro per exported kWh on a fixed contract in the central case. This is
#: negative in the central case: the feed-in charge exceeds the compensation.
#: Every estimate below leans on that, so it is computed once and named.
NET_FEED_IN_FIXED = net_feed_in_fixed("mid")

#: What one kWh used at home is worth compared to exporting it: the supply price
#: avoided plus the net feed-in given up. With a negative net feed-in the second
#: term adds to the value rather than subtracting from it.
SELF_USE_VALUE_PER_KWH = SUPPLY_PRICE.mid - NET_FEED_IN_FIXED

#: What one exported kWh is worth more on a dynamic contract than on a fixed
#: one. Dynamic feed-in is already a net figure, see ``tariffs.py``.
DYNAMIC_GAIN_PER_KWH = FEED_IN_NET_DYNAMIC.mid - NET_FEED_IN_FIXED

#: The shiftable block is one kWh, the default of ``Household.shiftable_block_kwh``
#: calibrated in the simulation spec. One block a day, every day.
SHIFTABLE_BLOCK_KWH = 1.0
DAYS_PER_YEAR = 365

#: An EV cannot absorb an unlimited midday surplus: it has to be at home when the
#: sun shines and it only holds so much. 2000 kWh a year is roughly 10.000 km of
#: driving, above which the surplus is no longer the binding constraint.
EV_SURPLUS_CAP_KWH = 2_000.0


def _euro(kwh: float, price_per_kwh: Decimal) -> Decimal:
    """The one place in this module where energy becomes money.

    Energy is float because it carries an uncertainty of percents; money is
    Decimal because a cent is a cent. The conversion happens here and nowhere
    else, so no price ever stands next to an energy figure by accident.
    """
    quantity = Decimal(repr(float(kwh))).quantize(KWH_PRECISION)
    return (quantity * price_per_kwh).quantize(EUR_PRECISION, rounding=ROUND_HALF_UP)


def _shift_flexible_load_saving(context: AdviceContext) -> Decimal | None:
    """One shiftable block a day, capped by the surplus that actually exists."""
    shiftable_kwh = min(DAYS_PER_YEAR * SHIFTABLE_BLOCK_KWH, context.midday_surplus_kwh)
    return _euro(shiftable_kwh, SELF_USE_VALUE_PER_KWH)


def _charge_ev_on_surplus_saving(context: AdviceContext) -> Decimal | None:
    """Surplus the car can plausibly absorb, valued as self-use instead of export."""
    return _euro(min(context.midday_surplus_kwh, EV_SURPLUS_CAP_KWH), SELF_USE_VALUE_PER_KWH)


def _consider_dynamic_contract_saving(context: AdviceContext) -> Decimal | None:
    """Every exported kWh earns the difference between the two feed-in regimes."""
    return _euro(context.annual_export_kwh, DYNAMIC_GAIN_PER_KWH)


def _no_estimate(context: AdviceContext) -> Decimal | None:
    """No figure, on purpose.

    These rules recommend an investigation, not a transaction. A euro amount
    here would be invented rather than derived, and an invented number is
    exactly the failure mode this project is built against.
    """
    return None


RULES: tuple[Rule, ...] = (
    Rule(
        rule_id="SHIFT_FLEXIBLE_LOAD",
        route=Route.SHIFT_BEHAVIOUR,
        priority=10,
        # Below 35 percent self-consumption there is room to move, and with
        # somebody home during the day the easy shifting has usually happened.
        condition=lambda context: (
            context.self_consumption_rate < 0.35 and not context.daytime_occupancy
        ),
        saving=_shift_flexible_load_saving,
    ),
    Rule(
        rule_id="CHARGE_EV_ON_SURPLUS",
        route=Route.SMART_CONTROL,
        priority=20,
        # An EV that already charges on solar has nothing to gain here.
        condition=lambda context: (
            context.has_ev
            and not context.ev_charges_on_solar
            and context.midday_surplus_kwh > 500.0
        ),
        saving=_charge_ev_on_surplus_saving,
    ),
    Rule(
        rule_id="CONSIDER_DYNAMIC_CONTRACT",
        route=Route.SMART_CONTROL,
        priority=30,
        # Exporting more than 40 percent of production is where the difference
        # between the two feed-in regimes starts to outweigh the hassle. The
        # production guard is not decoration: a household without panels would
        # otherwise divide by zero.
        condition=lambda context: (
            not context.dynamic_contract
            and context.annual_production_kwh > 0
            and context.annual_export_kwh / context.annual_production_kwh > 0.40
        ),
        saving=_consider_dynamic_contract_saving,
    ),
    Rule(
        rule_id="CONSIDER_BATTERY",
        route=Route.STORAGE,
        priority=40,
        # Storage needs both something to store and somebody to use it later.
        # Under 3.0 kWh between 17:00 and 07:00 the battery is full at sunset
        # and still full at sunrise.
        condition=lambda context: (
            not context.has_battery
            and context.annual_export_kwh > 1500.0
            and context.mean_evening_night_consumption_kwh > 3.0
        ),
        saving=_no_estimate,
    ),
    Rule(
        rule_id="BATTERY_DOES_NOT_PAY_BACK",
        route=Route.STORAGE,
        priority=45,
        # Deliberately always false, and not a defect. This rule needs the
        # payback figure that battery.py computes, which AdviceContext does not
        # carry because rules judge facts about the household rather than
        # results of a second simulation. advise.py substitutes this rule for
        # CONSIDER_BATTERY when the central payback exceeds twelve years, which
        # is also what keeps the two mutually exclusive.
        condition=lambda context: False,
        saving=_no_estimate,
    ),
    Rule(
        rule_id="BATTERY_DEPENDS_ON_PRICE",
        route=Route.STORAGE,
        priority=46,
        # Also deliberately always false, for the same reason as the rule above.
        # This is the honest outcome when the payback lands inside the cost band
        # rather than clearly on one side of it: at 450 euro per kWh it pays
        # back in time and at 900 it does not, so the answer genuinely depends
        # on the quote. Collapsing that to a yes or a no would be exactly the
        # single number without a band that CLAUDE.md forbids.
        condition=lambda context: False,
        saving=_no_estimate,
    ),
    Rule(
        rule_id="REVIEW_EXISTING_BATTERY",
        route=Route.STORAGE,
        priority=50,
        condition=lambda context: context.has_battery,
        saving=_no_estimate,
    ),
)

RULE_IDS: frozenset[str] = frozenset(rule.rule_id for rule in RULES)

_PRIORITY: dict[str, int] = {rule.rule_id: rule.priority for rule in RULES}


def evaluate(context: AdviceContext) -> tuple[FiredRule, ...]:
    """Return every rule that matches, free routes first.

    The ordering is by route and then by priority, so the routes that cost the
    household nothing are always presented before the one that costs money. That
    is a property of the output rather than a sorting choice a frontend may
    revisit, which is why it is fixed here and not there.
    """
    fired = [
        FiredRule(
            rule_id=rule.rule_id,
            route=rule.route,
            estimated_saving_eur=rule.saving(context),
        )
        for rule in RULES
        if rule.condition(context)
    ]
    fired.sort(key=lambda item: (item.route.value, _PRIORITY[item.rule_id]))
    return tuple(fired)
