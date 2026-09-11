"""Fit one household parameter to its own meter, without reading its shape.

This is phase 3, and it is deliberately not what phase 3 first looks like.

The obvious reading of "real data as input" is to replace the national profile
with the household's own measured series. Three things forbid it. A measured
quarter-hour year cannot exist, because raw quarters are folded to hours after
ninety days. A measured series says when somebody is home, and an advice is
retrievable for ninety days through a token its holder can hand to anyone,
which is what ``advice.series.SHAREABLE_PROVENANCE`` exists to stop. And the
meter measures net offtake, so recovering gross consumption from it needs the
production model added back in, which is the double counting
``docs/methodologie.md`` warns about in its second chapter.

So this module fits instead of decomposing. The model runs over the window the
meter actually covers, and one scalar is moved until the model reproduces what
the meter saw. Meter quantities against meter quantities: no production model
is inverted, and a car and a heat pump stay inside the model throughout, so the
carve-out that ``docs/analysis/2026-08-24-double-counting.md`` measured and
rejected is not needed here either.

Offtake is fitted and feed-in is not. Modelled import rises monotonically with
annual consumption, so a bisection on it is safe and terminates. That leaves
export as an independent observable rather than a second degree of freedom: if
the modelled export still disagrees with the meter after the fit has matched
import, what is wrong is the description of the installation, not the
consumption. A household is better served by being told that than by a second
parameter quietly absorbing it.

The band is measured and not chosen, which is the rule ``types.Band`` states
for the euro band. Refitting with one whole week withheld at a time measures
exactly the thing this route should worry about: whether the answer depends on
which weeks happened to be in the window. A household whose winter week carries
the answer gets a wide band, and a wide band is what the caller uses to decide
to say nothing at all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

import numpy as np

from ampeer_sim.economics.sensitivity import VARIATIONS
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.providers import ProductionProvider, ProfileProvider
from ampeer_sim.simulate import DEFAULT_WEATHER_YEAR
from ampeer_sim.timebase import QUARTERS_PER_DAY, YearGrid
from ampeer_sim.types import Household, PVSystem
from ampeer_sim.validate import Deviation

#: The search is bracketed rather than unbounded. A meter that disagrees with
#: the typed figure by more than these factors is not a household that mistyped
#: its annual total; it is a wrong link, a wrong year, or a device sending
#: something other than quarter energies. Returning nothing is the honest
#: answer there, and the caller has a refusal for it.
BRACKET_LOW_FACTOR = 0.2
BRACKET_HIGH_FACTOR = 5.0

#: One kilowatt hour on an annual figure of thousands. Tighter than anything the
#: rest of the model can distinguish, so the stopping point is never what limits
#: the answer.
TOLERANCE_KWH = 1.0

#: Bisection halves the bracket every step, so 40 steps take a 25-fold bracket
#: below a millionth of its width. Reaching this cap means the objective is not
#: behaving monotonically, which is a fault rather than a slow convergence.
MAX_ITERATIONS = 40

#: Whole weeks, so a leave-one-out refit removes a whole weekly cycle rather
#: than a slice that changes the weekday mix and moves the answer for that
#: reason instead of the one being measured.
QUARTERS_PER_WEEK = 7 * QUARTERS_PER_DAY

#: The two arrays one candidate annual consumption produces: modelled import
#: and modelled export, both per quarter over the whole grid. Named so the
#: bisection's signature stays readable.
_FlowsFor = Callable[[float], tuple[np.ndarray, np.ndarray]]


def _consumption_variation() -> tuple[float, float]:
    """How far the model already believes a typed annual figure can be off.

    Looked up rather than repeated. ``economics.sensitivity`` moves this input
    by a tenth either way when it builds the euro band, with the reason written
    beside it: the annual figure people type in is rarely exact. The floor below
    has to move with that number, because the two are the same claim about the
    same quantity, and a copy here would let the band announce a correction the
    euro band treats as noise.
    """
    for variation in VARIATIONS:
        if variation.name == "annual_consumption_kwh":
            return variation.low, variation.high
    raise ValueError("economics.sensitivity no longer varies annual_consumption_kwh")


#: Below this there is no spread to speak of: two refits produce two numbers and
#: a p10 and p90 drawn through them would be a hard-coded percentage wearing a
#: measurement's clothes.
MIN_WEEKS = 3


@dataclass(frozen=True)
class MeasuredWindow:
    """Measured grid flows at the quarters where a reading actually exists.

    Sparse on purpose. ``quarter_index`` holds positions in a ``YearGrid``, and
    nothing here fills a gap, interpolates one, or renormalises around one: a
    quarter that never arrived simply takes no part in the comparison. That is
    what keeps a household with a week of missing data from having its missing
    energy silently redistributed over the rest of the year, which is the
    failure mode ``profiles.nedu.validate_fractions`` cannot catch because the
    series it sees still sums to one.
    """

    quarter_index: np.ndarray
    offtake_kwh: np.ndarray
    feed_in_kwh: np.ndarray

    def __post_init__(self) -> None:
        if not (self.quarter_index.shape == self.offtake_kwh.shape == self.feed_in_kwh.shape):
            raise ValueError("a window's three arrays must have the same length")
        if self.quarter_index.size and np.any(np.diff(self.quarter_index) <= 0):
            raise ValueError("quarter_index must be strictly increasing")

    @property
    def weeks(self) -> np.ndarray:
        """Which whole week of the grid each quarter falls in."""
        return self.quarter_index // QUARTERS_PER_WEEK

    def without_week(self, week: int) -> MeasuredWindow:
        keep = self.weeks != week
        return MeasuredWindow(
            quarter_index=self.quarter_index[keep],
            offtake_kwh=self.offtake_kwh[keep],
            feed_in_kwh=self.feed_in_kwh[keep],
        )


@dataclass(frozen=True)
class ConsumptionFit:
    """A measured band on annual base consumption, in kWh.

    The p10/p50/p90/runs names are ``types.Band``'s, so a reader recognises the
    shape. The units are not: ``Band`` is euro and therefore Decimal, this is
    energy and therefore float, and the two must not be made to look
    interchangeable.

    ``export_deviation`` is the observable the fit did not use. It is carried
    here rather than discarded because it is the only thing in the answer that
    can say the installation was described wrongly.
    """

    p10_kwh: float
    p50_kwh: float
    p90_kwh: float
    runs: int
    export_deviation: Deviation
    quarters_used: int

    def contradicts(self, typed_kwh: float) -> bool:
        """Whether the meter disagrees with what the household typed.

        This is the whole threshold, and it is deliberately not a percentage.
        A figure inside the band is one the measurements do not contradict, so
        there is nothing to report; a figure outside it is contradicted. Little
        or erratic data widens the band, a wide band swallows the typed figure,
        and the answer becomes silence without any constant having decided it.
        """
        return not (self.p10_kwh <= typed_kwh <= self.p90_kwh)


def fit_annual_consumption(
    household: Household,
    pv_system: PVSystem,
    grid: YearGrid,
    window: MeasuredWindow,
    profile_provider: ProfileProvider,
    production_provider: ProductionProvider,
    weather_year: int = DEFAULT_WEATHER_YEAR,
) -> ConsumptionFit | None:
    """Return a band on this household's annual base consumption, or nothing.

    Nothing, rather than a number, whenever the answer would not be worth the
    weight a number carries: fewer than ``MIN_WEEKS`` whole weeks in the
    window, or an objective that does not cross zero inside the bracket.
    """
    weeks = np.unique(window.weeks)
    if weeks.size < MIN_WEEKS:
        return None

    hourly, temperature, _ = production_provider.hourly_series(
        household.postcode4, pv_system.azimuth_deg, pv_system.tilt_deg
    )
    production = production_series(hourly, pv_system, grid, weather_year=weather_year)
    fractions = profile_provider.fractions(grid.year, household.profile_category)

    def flows_for(annual_kwh: float) -> tuple[np.ndarray, np.ndarray]:
        candidate = replace(household, annual_consumption_kwh=annual_kwh)
        consumption = compose_consumption(
            candidate,
            grid,
            fractions,
            temperature,
            weather_year=weather_year,
            production_kwh=production,
        )
        flows = simulate(consumption, production)
        return flows.total_import, flows.total_export

    full = _fit_one(window, household.annual_consumption_kwh, flows_for)
    if full is None:
        return None

    refits = [
        value
        for week in weeks
        if (
            value := _fit_one(
                window.without_week(int(week)),
                household.annual_consumption_kwh,
                flows_for,
            )
        )
        is not None
    ]
    if len(refits) < MIN_WEEKS:
        return None

    p10, p50, p90 = (float(v) for v in np.percentile(refits, [10.0, 50.0, 90.0]))
    # Leave-one-week-out measures only how much the answer depended on which
    # weeks arrived. On a household whose weeks agree that spread is near zero,
    # and a band of no width calls every figure but its own wrong, including a
    # correct one a few kilowatt hours away. So the band is never narrower than
    # the uncertainty the model already carries on this very input.
    low_factor, high_factor = _consumption_variation()
    _, export = flows_for(full)
    return ConsumptionFit(
        p10_kwh=min(p10, p50 * low_factor),
        p50_kwh=p50,
        p90_kwh=max(p90, p50 * high_factor),
        runs=len(refits),
        export_deviation=Deviation(
            measured=float(window.feed_in_kwh.sum()),
            modelled=float(export[window.quarter_index].sum()),
            label="feed_in",
        ),
        quarters_used=int(window.quarter_index.size),
    )


def _fit_one(
    window: MeasuredWindow,
    typed_kwh: float,
    flows_for: _FlowsFor,
) -> float | None:
    """Bisect annual consumption until modelled import matches the meter.

    The objective is summed over the window's own quarters and nowhere else,
    so a gap costs coverage and never energy.
    """
    measured = float(window.offtake_kwh.sum())

    def residual(annual_kwh: float) -> float:
        imported, _ = flows_for(annual_kwh)
        return float(imported[window.quarter_index].sum()) - measured

    low = typed_kwh * BRACKET_LOW_FACTOR
    high = typed_kwh * BRACKET_HIGH_FACTOR
    if residual(low) > 0.0 or residual(high) < 0.0:
        return None

    for _ in range(MAX_ITERATIONS):
        middle = (low + high) / 2.0
        if high - low < TOLERANCE_KWH:
            return middle
        if residual(middle) < 0.0:
            low = middle
        else:
            high = middle
    return None
