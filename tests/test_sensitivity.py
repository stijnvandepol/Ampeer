from __future__ import annotations

import re
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from ampeer_sim.economics.sensitivity import VARIATIONS, band_from_differences, variation_grid
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.simulate import _apply_variations, run_advice
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
    BatterySpec,
    EnergyFlows,
    Household,
    ProductionSource,
    ProfileCategory,
    PVSystem,
    Result,
    TariffSet,
)

GRID = YearGrid.for_year(2025)


class _FlatProfileProvider:
    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


BASELINE = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.27"),
    standing_charge_year=Decimal("120.00"),
    net_metering=True,
)
SCENARIO = TariffSet(
    supply_price=Decimal("0.27"),
    feed_in_price=Decimal("0.05"),
    feed_in_fixed_cost_year=Decimal("90.00"),
    standing_charge_year=Decimal("120.00"),
)


def _advice(**overrides: object) -> Result:
    kwargs: dict[str, object] = {
        "household": Household(postcode4="5401", annual_consumption_kwh=3_500.0),
        "pv_system": PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35),
        "baseline": BASELINE,
        "scenario": SCENARIO,
        "grid": GRID,
        "profile_provider": _FlatProfileProvider(),
        "production_provider": FallbackProvider(2025),
        "weather_year": 2025,
    }
    kwargs.update(overrides)
    return run_advice(**kwargs)  # type: ignore[arg-type]


def test_band_is_ordered() -> None:
    band = band_from_differences([Decimal(str(value)) for value in range(100)])
    assert band.p10_eur <= band.p50_eur <= band.p90_eur
    assert band.runs == 100


def test_band_rejects_an_empty_run_set() -> None:
    with pytest.raises(ValueError, match="at least one"):
        band_from_differences([])


def test_there_is_more_than_one_variation() -> None:
    assert len(VARIATIONS) >= 4


def test_every_variation_moves_its_input_in_both_directions() -> None:
    for variation in VARIATIONS:
        assert variation.low < 1.0 < variation.high


def test_the_variation_grid_reaches_its_own_corners() -> None:
    grid = variation_grid()
    assert len(grid) == 3 ** len(VARIATIONS)
    all_low = {variation.name: variation.low for variation in VARIATIONS}
    all_high = {variation.name: variation.high for variation in VARIATIONS}
    assert all_low in grid
    assert all_high in grid


def test_run_advice_returns_a_result_with_a_measured_band() -> None:
    result = _advice()
    assert result.engine_version
    assert result.band.runs == 3 ** len(VARIATIONS)
    assert result.band.p10_eur < result.band.p90_eur
    assert result.production_source is ProductionSource.FALLBACK


def test_the_headline_figure_is_a_cost_increase() -> None:
    assert _advice().band.p50_eur > 0


def test_the_headline_figure_is_plausible_for_a_dutch_household() -> None:
    """A 3500 kWh household with 3.5 kWp should lose a few hundred euro a year."""
    band = _advice().band
    assert Decimal("300") < band.p50_eur < Decimal("1200")


def test_self_consumption_rate_is_a_fraction() -> None:
    assert 0.0 <= _advice().self_consumption_rate <= 1.0


def test_a_bigger_array_loses_more_when_net_metering_ends() -> None:
    small = _advice(pv_system=PVSystem(peak_power_wp=2_000, azimuth_deg=0, tilt_deg=35))
    large = _advice(pv_system=PVSystem(peak_power_wp=6_000, azimuth_deg=0, tilt_deg=35))
    assert large.band.p50_eur > small.band.p50_eur


def test_the_result_records_which_years_it_used() -> None:
    result = _advice()
    assert result.profile_year == 2025
    assert result.weather_year == 2025


def test_a_full_run_finishes_within_the_time_budget() -> None:
    started = time.perf_counter()
    _advice()
    assert time.perf_counter() - started < 2.0


# ---------------------------------------------------------------------------
# One grid size, stated in nine places
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where a claim about the size of the sensitivity grid can be written down.
_STATING = ("ampeer_sim", "ampeer_advice", "backend", "docs/methodologie.md")

#: A count standing beside the thing it counts.
#:
#: Anchored on the noun rather than on the digits alone, so an unrelated number
#: is not judged and does not have to be excused. The lookbehind keeps a decimal
#: out: "1,0 keer de capaciteit" and "2.6 times spread" are not grid sizes and
#: this must not report them, because a check that cries wolf is one nobody
#: reads by the third time.
_COUNT = re.compile(
    r"(?<![\d_.,])(\d+)[- ](cells?|runs?|pricings?|keer|simulations?|times)\b",
    re.IGNORECASE,
)


#: Keyed on the file as well as the number, and that is not tidiness. The first
#: version excused the digits alone, so every one of the nine places was free to
#: drift to 81 and be waved through: changing ampeer_advice/types.py to say 81
#: runs passed. An exception has to name where it applies, or it is a hole
#: wearing the shape of a rule.
NOT_THE_GRID_SIZE = {
    ("ampeer_sim/economics/sensitivity.py", "81"): (
        "what that docstring said until 2026-08-23, quoted there so the correction "
        "can be read rather than trusted"
    ),
    ("ampeer_sim/simulate.py", "216"): (
        "243 minus the 27 distinct simulations, which is what that optimisation stopped recomputing"
    ),
}


def _stated_counts() -> list[tuple[str, int, str]]:
    """Every count beside one of those nouns, as (where, line, the number)."""
    found: list[tuple[str, int, str]] = []
    for name in _STATING:
        path = REPO_ROOT / name
        files = [path] if path.is_file() else sorted(path.rglob("*.py"))
        for source in files:
            if "__pycache__" in source.parts:
                continue
            for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
                for match in _COUNT.finditer(line):
                    found.append((source.relative_to(REPO_ROOT).as_posix(), number, match.group(1)))
    return found


def test_every_place_that_states_the_grid_size_states_the_same_one() -> None:
    """The file that builds the grid was the one file that had it wrong.

    Until 2026-08-23 the docstring of ampeer_sim/economics/sensitivity.py said
    a factorial over four assumptions is 81 runs. There are five, and 3^5 is
    243. The fifth was added because leaving it out made the band silent about
    the most uncertain term in the answer, and the paragraph above the list did
    not follow it.

    Six other places said 243 and were right, which is what makes this worth a
    check rather than a correction: the number is spread across two packages,
    the API, and the published methodology, and one of them drifted without
    anything noticing. The size is derived here, so the day the grid grows all
    nine have to move with it.
    """
    grid = str(len(variation_grid()))
    wrong = [
        f"{where}:{line} says {number}, and the grid holds {grid}"
        for where, line, number in _stated_counts()
        if number != grid and (where, number) not in NOT_THE_GRID_SIZE
    ]
    assert not wrong, "the grid size is stated inconsistently:\n  " + "\n  ".join(wrong)

    # The other direction: an excuse that no longer describes anything is one
    # standing ready to wave through a number nobody meant.
    stated = {(where, number) for where, _, number in _stated_counts()}
    stale = sorted(key for key in NOT_THE_GRID_SIZE if key not in stated)
    assert not stale, f"these exceptions no longer describe anything: {stale}"


def test_the_grid_is_the_factorial_its_own_docstring_describes() -> None:
    """The owner's docstring, against the code directly under it.

    The check above compares the places to each other, so all nine could agree
    on a number the grid no longer has. This is the one that ties them to it.
    """
    source = (REPO_ROOT / "ampeer_sim" / "economics" / "sensitivity.py").read_text(encoding="utf-8")
    docstring = source.split('"""')[1]
    assert str(len(variation_grid())) in docstring, (
        f"the module docstring does not state {len(variation_grid())}, which is what "
        "variation_grid() returns"
    )
    assert len(variation_grid()) == 3 ** len(VARIATIONS), (
        "the grid is no longer three levels of every variation, so the factorial the "
        "docstring describes is not the one the code builds"
    )


def test_the_scan_reads_the_places_that_state_it() -> None:
    """The floor, since the check above is a statement over a set it builds.

    A pattern that stopped matching would leave it green over nothing, and this
    one is deliberately narrow enough that it could.
    """
    stated = _stated_counts()
    assert len(stated) >= 8, f"only found {stated}"
    files = {where for where, _, _ in stated}
    assert "ampeer_sim/economics/sensitivity.py" in files, (
        "the module that builds the grid no longer states its size, which is where the "
        "drift this guards against happened"
    )
    assert len(files) >= 4, f"only {sorted(files)} state it, and it is spread wider than that"


# ---------------------------------------------------------------------------
# The cache that turns 243 runs into 27, and the argument it rests on
# ---------------------------------------------------------------------------


def _energy_variations() -> list[str]:
    """The variations that move energy, decided by asking _apply_variations.

    Derived rather than listed. A list here would be a second copy of the
    knowledge in _apply_variations, kept in step by hand, and the whole point of
    the check below is that hand-kept copies of exactly this fact are what goes
    wrong.
    """
    household = Household(postcode4="5401", annual_consumption_kwh=3_500.0)
    system = PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35)
    moves = []
    for variation in VARIATIONS:
        run_household, run_system, _ = _apply_variations(
            household, system, SCENARIO, {variation.name: variation.low}
        )
        if (run_household, run_system) != (household, system):
            moves.append(variation.name)
    return moves


def test_every_variation_moves_the_answer_on_a_fixed_contract() -> None:
    """A dimension that changes nothing is a band claiming a width it lacks.

    The grid is a full factorial over five assumptions, and a variation wired
    to the wrong object, or applied multiplicatively to a value that happens to
    be zero, still produces its three cells and still counts towards the 243.
    It simply produces the same answer three times.

    The tariff set here is the one the product builds rather than this file's
    own fixture, because whether a variation is inert depends on the value it
    is handed. On a fixed contract all five move. On a dynamic one they do not,
    which is the test below.
    """
    from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs

    household = Household(postcode4="5401", annual_consumption_kwh=3_500.0)
    system = PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35)
    fixed = scenario_2027_tariffs(dynamic=False)
    central = _advice(baseline=baseline_tariffs(), scenario=fixed)

    inert = []
    for variation in VARIATIONS:
        moved = set()
        for factor in (variation.low, variation.high):
            run_household, run_system, run_scenario = _apply_variations(
                household, system, fixed, {variation.name: factor}
            )
            moved.add(
                _advice(
                    household=run_household,
                    pv_system=run_system,
                    baseline=baseline_tariffs(),
                    scenario=run_scenario,
                ).band.p50_eur
            )
        if moved == {central.band.p50_eur}:
            inert.append(variation.name)
    assert not inert, (
        f"{inert} produce their three cells and the same answer in all of them, so the band "
        "rests on fewer assumptions than it counts"
    )


def test_a_dynamic_contract_leaves_one_of_the_five_inert() -> None:
    """A known and measured overstatement, pinned so it cannot grow or vanish quietly.

    ``scenario_2027_tariffs(dynamic=True)`` sets ``feed_in_cost_per_kwh`` to
    zero and says why: on a dynamic contract the compensation is already net of
    charges. ``_apply_variations`` moves that assumption by multiplying it, and
    zero times either factor is zero, so the fifth dimension of the grid is
    constant for every household that ticks the dynamic contract box.

    Measured on 2026-08-23 on the reference household: the 243 cells produce 81
    distinct outcomes, each appearing exactly three times. The percentiles are
    unaffected, so the band itself is right. What is wrong is the count beside
    it: ``band.runs`` says 243 and ``HeadlineBand.tsx`` shows that figure to the
    visitor as "doorrekeningen".

    ``scenario_2027_levels`` in ampeer_advice already refuses to make this claim
    for the other band, in as many words: naming an input that does not actually
    differ would make the band claim a width it does not have. The same argument
    has not been applied here, and whether it should is recorded in
    docs/decisions.md rather than decided in a test.
    """
    from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs

    dynamic = scenario_2027_tariffs(dynamic=True)
    assert dynamic.feed_in_cost_per_kwh == Decimal("0"), (
        "the dynamic scenario now carries a feed-in charge, so this whole pinning is stale"
    )

    result = _advice(baseline=baseline_tariffs(), scenario=dynamic)
    assert result.band.runs == 3 ** len(VARIATIONS), (
        "the run count no longer reports every cell, which is the thing recorded here"
    )

    household = Household(postcode4="5401", annual_consumption_kwh=3_500.0)
    system = PVSystem(peak_power_wp=3_500, azimuth_deg=0, tilt_deg=35)
    inert = next(v for v in VARIATIONS if v.name == "feed_in_cost_per_kwh")
    for factor in (inert.low, inert.high):
        _, _, moved = _apply_variations(household, system, dynamic, {inert.name: factor})
        assert moved == dynamic, (
            f"{inert.name} at {factor} now changes the dynamic tariff set, so the count beside "
            "the band is no longer three times what it rests on"
        )


def test_the_grid_simulates_once_per_distinct_pair_and_prices_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The saving the comment claims, counted rather than asserted in prose.

    Two of the varied assumptions are prices, so the 243 cells of the grid hold
    3 to the power of the number that move energy, and the rest are repricings
    of a series already computed. The comment records 8.70 seconds before this
    optimisation and 1.06 after, on the battery path where the loop is Python.

    Counted here because a cache is the kind of thing that stops working
    silently. Widening the key to include the tariffs would put all 243
    simulations back, cost nothing in correctness, and show up nowhere except a
    stopwatch that only one test looks at.
    """
    import ampeer_sim.simulate as composition_root
    from ampeer_sim.engine.run import simulate as real_simulate

    calls = 0

    # The signature is written out rather than forwarded through *args, so the
    # day it changes this stops type checking instead of quietly counting
    # something else.
    def counting(
        consumption: np.ndarray,
        production: np.ndarray,
        battery_spec: BatterySpec | None = None,
        charge_plan: np.ndarray | None = None,
        discharge_plan: np.ndarray | None = None,
    ) -> EnergyFlows:
        nonlocal calls
        calls += 1
        return real_simulate(consumption, production, battery_spec, charge_plan, discharge_plan)

    monkeypatch.setattr(composition_root, "simulate", counting)
    result = _advice()

    expected = 3 ** len(_energy_variations())
    assert calls == expected, (
        f"the grid ran {calls} simulations where {expected} distinct input pairs exist; "
        "the flows cache is not doing what simulate.py says it does"
    )
    assert result.band.runs == 3 ** len(VARIATIONS), (
        f"the band is built from {result.band.runs} pricings, and the grid holds "
        f"{3 ** len(VARIATIONS)}"
    )
    assert calls < result.band.runs, "nothing was saved, so there is no cache to speak of"
