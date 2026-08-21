"""The one advice the frontend is built against, produced by the real code.

The frontend builds against a committed fixture rather than against a live API,
and a fixture written by hand is a description of a response that may never have
existed. So there is one function here, it calls the same renderer the API
calls, and both the generator and tests/test_frontend_contract.py go through it.
Two copies of this setup is how a fixture and the check that guards it drift
apart while both stay green.

The household is chosen on purpose. Seven kWp against 2200 kWh exports most of
what it makes, so the response exercises a battery block, a bandless figure, a
scenario band with nine combinations, and at least one fired rule whose
`saving_eur` is null. A fixture that only covers the easy shape is a fixture
that proves the easy shape.

Run as a script to rewrite the fixture:

    uv run --no-sync python tests/helpers/advice_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from ampeer_sim.types import ProfileCategory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "advice-response.json"

# backend/ is a Django project run from its own directory rather than a package
# anybody installs, so `advice.rendering` only becomes importable once it is on
# the path. Under pytest that happens through `pythonpath` in pyproject.toml;
# running this module as a script does not go through pytest.
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

#: The year the profile and the tariffs are expressed in.
PROFILE_YEAR = 2025

#: The weather year the production series is drawn from.
WEATHER_YEAR = 2023

#: Twenty characters, the shape the API issues, and visibly not a real one.
FIXTURE_TOKEN = "FIXTUREfixture00000000"


class FlatProfileProvider:
    """A perfectly flat consumption profile.

    Not a realistic household, and that is the point: the fixture has to be
    reproducible from this file alone, and the NEDU profiles are a data file
    that is not committed. The response shape does not depend on the profile,
    and the shape is the only thing this fixture is a statement about.
    """

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        from ampeer_sim.timebase import YearGrid

        quarters = YearGrid.for_year(year).quarters
        return np.full(quarters, 1.0 / quarters)


def build_reference_payload() -> dict[str, Any]:
    """The advice API's response for one fixed household, from the real code."""
    from advice.rendering import render
    from ampeer_advice.advise import advise
    from ampeer_advice.tariffs import baseline_tariffs, scenario_2027_tariffs
    from ampeer_sim.production.pvgis import FallbackProvider
    from ampeer_sim.simulate import run_advice
    from ampeer_sim.timebase import YearGrid
    from ampeer_sim.types import Household, PVSystem

    grid = YearGrid.for_year(PROFILE_YEAR)
    household = Household(postcode4="5401", annual_consumption_kwh=2200.0)
    pv_system = PVSystem(peak_power_wp=7000, azimuth_deg=0.0, tilt_deg=35.0)
    profile_provider = FlatProfileProvider()
    production_provider = FallbackProvider(WEATHER_YEAR)

    result = run_advice(
        household=household,
        pv_system=pv_system,
        baseline=baseline_tariffs(),
        scenario=scenario_2027_tariffs(),
        grid=grid,
        profile_provider=profile_provider,
        production_provider=production_provider,
        weather_year=WEATHER_YEAR,
    )
    advice = advise(
        household=household,
        pv_system=pv_system,
        scenario=scenario_2027_tariffs(),
        grid=grid,
        profile_provider=profile_provider,
        production_provider=production_provider,
        result=result,
        filled_fields=4,
        weather_year=WEATHER_YEAR,
    )
    return render(advice, result, token=FIXTURE_TOKEN)


def write_fixture() -> int:
    """Rewrite the committed fixture and report its size in bytes."""
    payload = build_reference_payload()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # newline is pinned to a line feed on purpose. On Windows the default
    # translates it to a carriage return pair, pre-commit's mixed-line-ending
    # hook then rewrites the file, and the commit fails. That happened three
    # times before anybody looked at why, which is what a papercut costs when
    # nobody writes it down.
    with FIXTURE.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return len(json.dumps(payload))


if __name__ == "__main__":
    print(f"wrote {write_fixture()} bytes to {FIXTURE}")
