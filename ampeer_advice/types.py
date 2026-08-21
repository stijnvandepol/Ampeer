"""Value types for the advice layer.

``AdviceContext`` is the only thing a rule may read. It holds derived facts and
no numpy arrays, so a rule condition stays readable to someone who does not know
what a simulation is. That is the requirement: when somebody asks on a forum why
they got this advice, you must be able to point at the rule.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, auto

from ampeer_sim.types import Band


class Route(Enum):
    """The three routes, always presented in this order.

    The free ones come first even when they yield nothing. That ordering is a
    property of the output, not a sorting choice the frontend may revisit.
    """

    SHIFT_BEHAVIOUR = 1
    SMART_CONTROL = 2
    STORAGE = 3


class Confidence(Enum):
    """How complete the input was. Says nothing about the width of the band."""

    INDICATIVE = auto()
    GOOD = auto()
    PRECISE = auto()


@dataclass(frozen=True)
class ScenarioBand:
    """A band measured by pricing one simulated year at named input levels.

    This is not a percentile band and it must never be rendered under the
    p10, p50 and p90 names ``Band`` uses. Those are the tenth and ninetieth
    percentile of a full factorial of 243 runs. These three are the smallest,
    the central and the largest value of a handful of deliberately chosen input
    combinations, so naming them percentiles would claim a distribution that was
    never sampled. The names differ in the response for exactly that reason: a
    reader comparing the two bands has to be able to see that they are not the
    same kind of statement.

    ``low`` and ``high`` are ordered by value and not by input level. At the
    high end of the tariff band the feed-in charge is high as well, so a high
    input level does not produce a high outcome, and labelling the ends by their
    inputs would print a band that runs backwards. ``mid`` is the value at the
    central combination, which is the one every decision in this package is
    taken on.

    ``varied`` names what moved and ``pinned`` names the uncertain inputs that
    did not. Both travel with the band into the response, because a band that
    does not say what it is a band over reads as though it covered everything.
    """

    low: Decimal
    mid: Decimal
    high: Decimal
    #: Inputs that were moved to produce this band.
    varied: tuple[str, ...]
    #: Inputs that are uncertain and were held at their central value anyway.
    #: The real spread is therefore wider than this band, never narrower.
    pinned: tuple[str, ...]
    #: How many input combinations were priced to obtain it.
    combinations: int

    def __post_init__(self) -> None:
        if not self.low <= self.mid <= self.high:
            raise ValueError(f"a band must be ordered, got {self.low}, {self.mid}, {self.high}")
        if not self.varied:
            raise ValueError("a band that varies nothing is not a band")

    @classmethod
    def over(
        cls,
        values: Iterable[Decimal],
        mid: Decimal,
        varied: tuple[str, ...],
        pinned: tuple[str, ...],
    ) -> ScenarioBand:
        """Build a band from every measured value plus the central one.

        ``mid`` has to be one of the measured values. If the central case were
        allowed to come from somewhere else, the figure the advice is decided on
        would not be the figure the band was measured around, and nothing in the
        response would show it.
        """
        measured = tuple(values)
        if not measured:
            raise ValueError("a band needs at least one measured value")
        if mid not in measured:
            raise ValueError(f"the central value {mid} is not among the measured {measured}")
        return cls(
            low=min(measured),
            mid=mid,
            high=max(measured),
            varied=varied,
            pinned=pinned,
            combinations=len(measured),
        )


@dataclass(frozen=True)
class AdviceContext:
    """Everything a rule may look at, and nothing else."""

    self_consumption_rate: float
    annual_production_kwh: float
    annual_export_kwh: float
    annual_import_kwh: float
    #: Mean daily consumption between 17:00 and 07:00 local time.
    mean_evening_night_consumption_kwh: float
    #: Annual production that exceeded consumption between 11:00 and 15:00.
    midday_surplus_kwh: float
    #: Export left after the free routes have been applied and measured. On the
    #: first pass this equals annual_export_kwh, because nothing has been applied
    #: yet; only the storage rules read it, and they run on the second pass. The
    #: spec and the Dutch copy both promise storage is judged on what is left
    #: over, so judging it on today's export would make the text untrue.
    export_after_free_routes_kwh: float
    daytime_occupancy: bool
    has_ev: bool
    ev_charges_on_solar: bool
    has_battery: bool
    battery_capacity_kwh: float | None
    dynamic_contract: bool
    headline: Band
    confidence: Confidence


@dataclass(frozen=True)
class FiredRule:
    """A rule that matched. Carries an id, never a sentence.

    The saving is a band and not a single amount. It is the figure a household
    is asked to act on, so the one number it used to be was the plainest breach
    of the rule this product is built on: never a figure without a band around
    it. ``None`` still means no figure was measured at all, which three of the
    rules do on purpose.
    """

    rule_id: str
    route: Route
    estimated_saving_eur: ScenarioBand | None


@dataclass(frozen=True)
class Rule:
    """A rule decides whether, never how much.

    Estimating a euro figure from the context meant three rules pricing the same
    kilowatt hours independently, so their numbers could not be added up, and it
    meant valuing a shifted kWh at 0.27 euro where the engine measures 0.16. The
    saving is now measured by simulating the intervention, which is additive by
    construction and uses the same code path as the answer it belongs to.
    """

    rule_id: str
    route: Route
    priority: int
    condition: Callable[[AdviceContext], bool]


@dataclass(frozen=True)
class BatteryAdvice:
    """What a battery would do, not what the household should do.

    The capacity field is named sized rather than recommended on purpose. It
    is the knee of the curve and it is filled in even when the verdict is
    BATTERY_DOES_NOT_PAY_BACK, so a field called recommended would let a
    refusal render as a product suggestion.
    """

    #: The knee of the measured curve. This one carries no band on purpose: it
    #: is a choice out of the capacities that were simulated, not an estimate of
    #: an unknown quantity, and a band around a choice would be theatre. The
    #: response says so rather than leaving the reader to work it out.
    sized_capacity_kwh: float
    #: True when the knee is the largest capacity that was simulated, which
    #: means the search ran out of curve rather than finding a knee. The real
    #: knee may lie above it, so the sizing is a lower bound in that case and
    #: the response has to be able to say which of the two it is.
    sized_at_largest_simulated_capacity: bool
    annual_saving_eur: ScenarioBand
    #: Payback in years at the recommended capacity. A band over the installed
    #: price and the tariff level, never a single figure: the price alone spans
    #: a factor two.
    payback_years: ScenarioBand
    #: (capacity_kwh, annual_saving_eur) for every capacity that was simulated.
    curve: tuple[tuple[float, ScenarioBand], ...]
    #: The installed price per kWh at which payback lands exactly on the twelve
    #: year limit. Quotes below it pay back in time, quotes above it do not.
    #: This is the figure in the advice the reader can act on most directly,
    #: because unlike the 2027 feed-in tariff the price of a battery is
    #: something they can go and ask for, and that is exactly why it may not be
    #: a single mid-scenario number: it would be a threshold to act on
    #: presented as a certainty.
    break_even_cost_per_kwh: ScenarioBand


@dataclass(frozen=True)
class Advice:
    engine_version: str
    advice_version: str
    confidence: Confidence
    headline: Band
    fired: tuple[FiredRule, ...]
    routes: tuple[Route, ...]
    battery: BatteryAdvice | None
