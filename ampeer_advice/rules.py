"""The ordered rule table.

Rules are data, not code paths. A rule is a condition over ``AdviceContext``, a
route, a priority and a function that estimates what following it is worth. It
returns a rule id, never a sentence: the Dutch text lives in ``nl.py`` and is
attached at the edge, so a copy change and a behaviour change cannot break the
same test.

Conditions read fields, never arrays: a comparison between one named field and
one threshold is something you can point at when a household asks on a forum why
it got this advice, and that is the whole requirement. The thresholds themselves
are listed in chapter 13 of docs/methodologie.md, and tests/test_methodology.py
fails when the two disagree. No number is repeated here, because a threshold
quoted in a docstring is a second copy that nothing compares against.

Three of the six rules estimate no saving at all. Their value is the advice
itself, and attaching a euro figure to "have your existing battery checked"
would be the false precision this project refuses everywhere else.
"""

from __future__ import annotations

from ampeer_advice.types import AdviceContext, FiredRule, Route, Rule

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
            and context.export_after_free_routes_kwh > 1500.0
            and context.mean_evening_night_consumption_kwh > 3.0
        ),
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
    ),
    Rule(
        rule_id="REVIEW_EXISTING_BATTERY",
        route=Route.STORAGE,
        priority=50,
        condition=lambda context: context.has_battery,
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
            # Filled in by advise.py, which can measure it. See Rule.
            estimated_saving_eur=None,
        )
        for rule in RULES
        if rule.condition(context)
    ]
    fired.sort(key=lambda item: (item.route.value, _PRIORITY[item.rule_id]))
    return tuple(fired)
