from __future__ import annotations

import re
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from ampeer_sim.economics.sensitivity import VARIATIONS, band_from_differences, variation_grid
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.simulate import run_advice
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import (
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
