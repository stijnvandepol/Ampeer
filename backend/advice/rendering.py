"""An Advice into the JSON a browser receives.

Money leaves as a string. JSON has floats and no decimals, so an amount that
passes through a JSON number is rounded by whichever parser touches it last,
which is precisely the error the Decimal rule elsewhere in this project exists
to prevent. Rounding to cents therefore happens here, in `money`.

Here, with one exception, and the exception is written down rather than glossed
over. `headline` arrives from `ampeer_sim.economics.sensitivity` already rounded
to two decimals by Python's `round`, which breaks a tie to the nearest even
digit where `money` breaks it away from zero. `round(700.125, 2)` is 700.12 and
`money(Decimal("700.125"))` is "700.13", so two amounts of equal value can leave
this file a cent apart. `money` is a no-op on the headline and cannot undo that
rounding; the simulation core is where it happens and this package does not
reach into it. `tests/test_advice_rendering.py` pins both conventions so the
difference cannot widen unnoticed, and every other amount in the response
arrives at the three decimals `ampeer_sim.economics.tariffs` works in and is
rounded to cents here for the first time.

Nothing in this file writes a sentence. Every word a reader sees comes out of
ampeer_advice.nl, keyed by a rule id or an enum, so a change of wording and a
change of behaviour still cannot break the same test.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ampeer_advice.nl import (
    CONFIDENCE_LABELS,
    MODELLED_CONSUMPTION_BASIS_TEXTS,
    ROUTE_TITLES,
    SIZING_BASIS_TEXTS,
    action_for,
    label_for,
    production_source_text,
    text_for,
)
from ampeer_advice.types import Advice, BatteryAdvice, Route, ScenarioBand
from ampeer_sim.types import Band, Result

#: Every amount that still carries its full precision is quantized here and
#: nowhere else. Two rounding conventions in one document is how a total stops
#: matching its own parts, which is why the one exception is named in the module
#: docstring instead of being left for a reader to find.
CENTS = Decimal("0.01")

#: Payback in years, to the hundredth. It lives here because it is a display
#: precision and nothing else: it used to sit in ampeer_advice.battery, where
#: it also quantized the break even price, so editing "payback to the tenth of
#: a year" would have silently rounded a euro amount to the dime. A time and an
#: amount are two quantities and they get two constants.
YEARS = Decimal("0.01")

#: The order a reader sees. The two free routes come first whatever they are
#: worth, and an empty one is still sent, so the frontend never has to know
#: this order in order to restore it.
ROUTE_ORDER: tuple[Route, ...] = (Route.SHIFT_BEHAVIOUR, Route.SMART_CONTROL, Route.STORAGE)


def money(value: Decimal) -> str:
    """The one place an amount in euro is turned into text."""
    return str(value.quantize(CENTS, rounding=ROUND_HALF_UP))


def _years(value: Decimal) -> str:
    """A payback time as text. Years, not euro, so `money` must not touch it.

    Same rounding rule as `money`, on purpose, so that two figures in one
    response never disagree about which way a half goes. A different precision,
    also on purpose: a payback time is not an amount.
    """
    return str(value.quantize(YEARS, rounding=ROUND_HALF_UP))


def _band(band: Band) -> dict[str, Any]:
    """The headline band: genuine percentiles, so it is named for them.

    p10 and p90 here are the tenth and ninetieth percentile of `runs` factorial
    simulations. Nothing else in this response may borrow these key names. A
    band measured at three chosen input levels is rendered by
    `_scenario_band` under low, mid and high instead, because two different
    kinds of statement that look identical are worse than one that is missing.
    """
    return {
        "p10": money(band.p10_eur),
        "p50": money(band.p50_eur),
        "p90": money(band.p90_eur),
        "runs": band.runs,
    }


def _scenario_band(band: ScenarioBand, render: Callable[[Decimal], str]) -> dict[str, Any]:
    """A band measured at named input levels, and the list of what those were.

    `varied` and `pinned` are part of the payload rather than a footnote in a
    document nobody opens. Without them the reader cannot tell a band over the
    battery price alone from a band over everything, and this product publishes
    both in the same response.
    """
    return {
        "low": render(band.low),
        "mid": render(band.mid),
        "high": render(band.high),
        "varied": list(band.varied),
        "pinned": list(band.pinned),
        # The same two lists in words. The identifiers above come from the
        # simulation core and are English; a Dutch reader was being shown
        # "supply_price" verbatim. Translating in the frontend would put a
        # second copy of the model's vocabulary there, which drifts the first
        # time an assumption is added, so the names live in nl.py beside the
        # advice text and cross the boundary already translated.
        "varied_text": [label_for(name) for name in band.varied],
        "pinned_text": [label_for(name) for name in band.pinned],
        "combinations": band.combinations,
    }


def _routes(advice: Advice) -> list[dict[str, Any]]:
    return [
        {
            "route": route.name,
            "title": ROUTE_TITLES[route],
            "rules": [
                {
                    "rule_id": fired.rule_id,
                    # The one line version, for the block at the top of the
                    # page. Same advice, said shorter; the paragraph below is
                    # the one that carries the reasoning and the caveats.
                    "action": action_for(fired.rule_id),
                    "text": text_for(fired.rule_id),
                    # A band, never one amount. This is the figure that decides
                    # whether somebody rearranges their week, and it used to
                    # leave here as a single number while the document beside
                    # it promised there would never be one.
                    #
                    # None rather than 0.00. Three rules estimate nothing at
                    # all on purpose, and a zero would read as a measurement
                    # that was never taken.
                    "saving_eur": (
                        _scenario_band(fired.estimated_saving_eur, money)
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
    basis = (
        "LIMITED_BY_LARGEST_SIMULATED_CAPACITY"
        if battery.sized_at_largest_simulated_capacity
        else "CHOSEN_FROM_SIMULATED_CAPACITIES"
    )
    return {
        "verdict": _verdict(advice),
        # The one figure in this block without a band, and it says so in its own
        # shape. A capacity is a choice out of the five sizes that were
        # simulated, not an estimate of something unknown, so a band around it
        # would be decoration. `basis` also distinguishes a knee that was found
        # from a search that ran out of curve at the largest size on offer,
        # where the honest reading is "at least this large".
        "sized_capacity_kwh": {
            "value": battery.sized_capacity_kwh,
            "band": None,
            "basis": basis,
            "basis_text": SIZING_BASIS_TEXTS[basis],
        },
        "annual_saving_eur": _scenario_band(battery.annual_saving_eur, money),
        # A band, never one figure. The installed price spans a factor two and
        # the tariffs it is priced against carry a band of their own, and
        # collapsing either would decide "worth it" or "not worth it" on a
        # number that carries no such certainty. `varied` and `pinned` travel
        # with it: these ends are the extremes of nine priced combinations and
        # not the tenth and ninetieth percentile of anything, which is what the
        # p10 and p90 names on this block used to claim.
        "payback_years": _scenario_band(battery.payback_years, _years),
        "break_even_cost_per_kwh": _scenario_band(battery.break_even_cost_per_kwh, money),
        # (capacity, saving) pairs. The capacity is the horizontal axis and one
        # of the five sizes that were simulated, so it is a coordinate rather
        # than a figure about this household; the saving at each of them is a
        # band like every other amount here.
        "curve": [[capacity, _scenario_band(saving, money)] for capacity, saving in battery.curve],
    }


#: How far the modelled year may sit from what was entered and still be called
#: unchanged, in kilowatt hours.
#:
#: One, and it is a tolerance on floating point rather than a judgement about
#: anything. `scale_to_annual` scales the base profile to exactly the figure
#: entered, and `apply_presence` moves energy between quarters without creating
#: or destroying any, so a household with no car and no heat pump comes back to
#: the entered figure to within the arithmetic. The smallest asset this model
#: can add is a heat pump at 1 kWh of heat demand; every real one is hundreds.
CONSUMPTION_UNCHANGED_TOLERANCE_KWH = 1.0


def _modelled_consumption(advice: Advice, entered_kwh: float) -> dict[str, Any]:
    """The year's total consumption, with why it carries no band.

    Rounded to a whole kilowatt hour. Energy is a float here as everywhere, and
    the tenths of this one are the profile's arithmetic rather than anything
    measured; a reader checking it against their annual bill is working in
    hundreds.

    The basis is decided by comparing the series against the figure entered,
    not by reading `has_ev` and `has_heat_pump` off the request. Those flags say
    what was asked for and this comparison says what happened to the year every
    other figure in the response was computed from. A flag set on a request
    whose asset never reached the series would make the flag version say
    something untrue, and it is exactly the sentence about the annual bill that
    would then be shown to a household it cannot apply to.
    """
    modelled = float(advice.flows.consumption.sum())
    unchanged = abs(modelled - entered_kwh) < CONSUMPTION_UNCHANGED_TOLERANCE_KWH
    basis = "ENTERED_UNCHANGED" if unchanged else "ENTERED_PLUS_ASSETS"
    return {
        "value": round(modelled),
        "band": None,
        "basis": basis,
        "basis_text": MODELLED_CONSUMPTION_BASIS_TEXTS[basis],
    }


#: What the annual consumption in an answer rests on. Two words rather than a
#: bare boolean, because this travels on the wire and a reader of the payload
#: should not have to know which way round a flag was named.
TYPED_CONSUMPTION = "TYPED"
MEASURED_CONSUMPTION = "MEASURED"


def render(
    advice: Advice,
    result: Result,
    token: str,
    year: dict[str, Any] | None = None,
    entered_consumption_kwh: float | None = None,
    consumption_measured: bool = False,
) -> dict[str, Any]:
    """The whole response, JSON-safe, with no Decimal left in it.

    `year` arrives already built and already checked. This module may not build
    it: `tests/test_advice_series.py` pins the two modules that may import
    `advice.series` at all, so that the one function which decides whether a
    quarter-hour series may leave over a shareable token cannot be walked
    around by a third module assembling the same dict. What reaches here is
    what `advice.serializers.year_field` returned, and this file only decides
    the key it lands under.

    The key is absent rather than null when there is none, which is the shape
    the frontend was given: an optional object. Absent and null are the same
    thing to a reader and not to a parser, and this response already carries
    `battery: null` and `saving_eur: null` for figures that were measured and
    came out empty. A year that was never built is a different statement from a
    year that came out empty, so it is spelled differently.
    """
    payload: dict[str, Any] = {
        "token": token,
        # Top level, never nested. A caveat in a footnote is a caveat nobody
        # reads.
        "confidence": advice.confidence.name,
        # The Dutch word beside it, from nl.py. The API is the boundary where
        # language enters, so the frontend never writes one of these three
        # words itself.
        "confidence_label": CONFIDENCE_LABELS[advice.confidence],
        # Where the annual consumption came from, which the confidence word
        # alone cannot say: a household that accepted a figure read off its own
        # meter and one that answered nine questions both read GOOD, and only
        # one of them measured the input that moves the answer most.
        "consumption_source": MEASURED_CONSUMPTION if consumption_measured else TYPED_CONSUMPTION,
        "headline": _band(advice.headline),
        "routes": _routes(advice),
        "battery": _battery(advice),
        "engine_version": advice.engine_version,
        "advice_version": advice.advice_version,
        # The enum name, for a machine, and the sentence, for a reader. A
        # reader told "FALLBACK" learns nothing; one told the sun figures
        # came from an offline table knows how much weight to give the
        # answer. Same boundary as varied_text: the Dutch lives in nl.py.
        "production_source": result.production_source.name,
        "production_source_text": production_source_text(result.production_source.name),
        "profile_year": result.profile_year,
        "weather_year": result.weather_year,
        # The consumption the model actually used: what the visitor entered,
        # plus whatever the car and the heat pump added on top.
        #
        # It is here because of what the question repair in decision 26 cannot
        # do on its own. That repair asks the visitor for their consumption
        # WITHOUT those assets, and its one failure mode is a visitor who reads
        # the total off their annual bill anyway. That visitor is otherwise
        # indistinguishable from a correct one: they lose between 26,5 and 59,2
        # percent of their answer and nothing anywhere reports a problem.
        # Showing the total back does not repair that reading and is not meant
        # to. It makes it VISIBLE, which is the difference between a wrong
        # answer a household can catch and one nobody can.
        #
        # In the bandless shape, which is the response's own way of saying a
        # figure legitimately has none. This one is an echo of an input rather
        # than an estimate of anything, so a band would be decoration, and
        # `test_no_figure_anywhere_in_the_response_arrives_without_a_band`
        # is what makes that a statement in the document rather than an
        # omission from it.
    }
    if entered_consumption_kwh is not None:
        payload["modelled_consumption_kwh"] = _modelled_consumption(advice, entered_consumption_kwh)
    if year is not None:
        payload["year"] = year
    return payload
