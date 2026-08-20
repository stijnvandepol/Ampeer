"""Value types for the advice layer.

``AdviceContext`` is the only thing a rule may read. It holds derived facts and
no numpy arrays, so a rule condition stays readable to someone who does not know
what a simulation is. That is the requirement: when somebody asks on a forum why
they got this advice, you must be able to point at the rule.
"""

from __future__ import annotations

from collections.abc import Callable
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
    """A rule that matched. Carries an id, never a sentence."""

    rule_id: str
    route: Route
    estimated_saving_eur: Decimal | None


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

    sized_capacity_kwh: float
    annual_saving_eur: Decimal
    payback_years_p10: Decimal
    payback_years_p50: Decimal
    payback_years_p90: Decimal
    #: (capacity_kwh, annual_saving_eur) for every capacity that was simulated.
    curve: tuple[tuple[float, Decimal], ...]
    #: The installed price per kWh at which payback lands exactly on the twelve
    #: year limit. Quotes below this pay back in time, quotes above it do not.
    #: This is the one figure in the whole advice the reader can act on directly,
    #: because unlike the 2027 feed-in tariff, the price of a battery is
    #: something they can go and ask for.
    break_even_cost_per_kwh: Decimal


@dataclass(frozen=True)
class Advice:
    engine_version: str
    advice_version: str
    confidence: Confidence
    headline: Band
    fired: tuple[FiredRule, ...]
    routes: tuple[Route, ...]
    battery: BatteryAdvice | None
