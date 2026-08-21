"""An Advice into the JSON a browser receives.

Money leaves as a string. JSON has floats and no decimals, so an amount that
passes through a JSON number is rounded by whichever parser touches it last,
which is precisely the error the Decimal rule elsewhere in this project exists
to prevent. Rounding therefore happens once, here, in `money`.

Nothing in this file writes a sentence. Every word a reader sees comes out of
ampeer_advice.nl, keyed by a rule id or an enum, so a change of wording and a
change of behaviour still cannot break the same test.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ampeer_advice.battery import PAYBACK_PRECISION
from ampeer_advice.nl import CONFIDENCE_LABELS, ROUTE_TITLES, text_for
from ampeer_advice.types import Advice, BatteryAdvice, Route
from ampeer_sim.types import Band, Result

#: Every amount in a response is quantized here and nowhere else. Two rounding
#: conventions in one document is how a total stops matching its own parts.
CENTS = Decimal("0.01")

#: The order a reader sees. The two free routes come first whatever they are
#: worth, and an empty one is still sent, so the frontend never has to know
#: this order in order to restore it.
ROUTE_ORDER: tuple[Route, ...] = (Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE)


def money(value: Decimal) -> str:
    """The one place an amount in euro is turned into text."""
    return str(value.quantize(CENTS, rounding=ROUND_HALF_UP))


def _years(value: Decimal) -> str:
    """A payback time as text. Years, not euro, so `money` must not touch it.

    The precision is imported from the module that computes these figures
    rather than chosen again here: this is the same quantity rendered, not a
    second convention for it. `money` stays the only place an amount is
    formatted, and a payback time is not an amount.
    """
    return str(value.quantize(PAYBACK_PRECISION, rounding=ROUND_HALF_UP))


def _band(band: Band) -> dict[str, Any]:
    return {
        "p10": money(band.p10_eur),
        "p50": money(band.p50_eur),
        "p90": money(band.p90_eur),
        "runs": band.runs,
    }


def _routes(advice: Advice) -> list[dict[str, Any]]:
    return [
        {
            "route": route.name,
            "title": ROUTE_TITLES[route],
            "rules": [
                {
                    "rule_id": fired.rule_id,
                    "text": text_for(fired.rule_id),
                    # None rather than 0.00. Three rules estimate nothing at
                    # all on purpose, and a zero would read as a measurement
                    # that was never taken.
                    "saving_eur": (
                        money(fired.estimated_saving_eur)
                        if fired.estimated_saving_eur is not None
                        else None
                    ),
                }
                for fired in advice.fired
                if fired.route is route
            ],
        }
        for route in ROUTE_ORDER
    ]


def _verdict(advice: Advice) -> str:
    """The storage outcome, read back from the rules rather than recomputed.

    ampeer_advice.advise owns the payback thresholds and substitutes one of
    CONSIDER_BATTERY, BATTERY_DEPENDS_ON_PRICE or BATTERY_DOES_NOT_PAY_BACK
    into the single storage slot whenever it computed a battery. Deciding the
    verdict again here would be a second copy of the most consequential
    judgement in the product, free to contradict the Dutch text printed beside
    it.

    There is exactly one such rule when a battery advice exists: the rule that
    asks for one requires the household not to own a battery, and the only
    other storage rule requires that it does. Anything else is a composition
    fault, and a battery block with no stated conclusion is worse to publish
    than an error, so it raises.
    """
    storage = [fired.rule_id for fired in advice.fired if fired.route is Route.STORAGE]
    if len(storage) != 1:
        raise ValueError(
            f"a battery advice needs exactly one storage verdict, got {sorted(storage)}"
        )
    return storage[0]


def _battery(advice: Advice) -> dict[str, Any] | None:
    if advice.battery is None:
        return None
    battery: BatteryAdvice = advice.battery
    return {
        "verdict": _verdict(advice),
        "sized_capacity_kwh": battery.sized_capacity_kwh,
        "annual_saving_eur": money(battery.annual_saving_eur),
        # A band, never one figure. The installed price this is derived from
        # spans a factor two, and collapsing it to a midpoint would decide
        # "worth it" or "not worth it" on a number that carries no such
        # certainty.
        "payback_years": {
            "p10": _years(battery.payback_years_p10),
            "p50": _years(battery.payback_years_p50),
            "p90": _years(battery.payback_years_p90),
        },
        "break_even_cost_per_kwh": money(battery.break_even_cost_per_kwh),
        "curve": [[capacity, money(saving)] for capacity, saving in battery.curve],
    }


def render(advice: Advice, result: Result, token: str) -> dict[str, Any]:
    """The whole response, JSON-safe, with no Decimal left in it."""
    return {
        "token": token,
        # Top level, never nested. A caveat in a footnote is a caveat nobody
        # reads.
        "confidence": advice.confidence.name,
        # The Dutch word beside it, from nl.py. The API is the boundary where
        # language enters, so the frontend never writes one of these three
        # words itself.
        "confidence_label": CONFIDENCE_LABELS[advice.confidence],
        "headline": _band(advice.headline),
        "routes": _routes(advice),
        "battery": _battery(advice),
        "engine_version": advice.engine_version,
        "advice_version": advice.advice_version,
        "production_source": result.production_source.name,
        "profile_year": result.profile_year,
        "weather_year": result.weather_year,
    }
