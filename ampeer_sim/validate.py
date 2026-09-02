"""Check the model against a real annual statement.

Every other test asks whether the code matches the design. This one asks
whether the design matches reality, which is the only question a critic on a
forum will actually ask. It is a one command script on purpose: something you
run at every model change, not something you set aside an afternoon for.

What a statement cannot say, and why that matters here. ``REQUIRED_FIELDS``
has no place for an electric car or a heat pump, so ``check`` always models a
household that owns neither. Run this against the statement of a household that
does own one and the model spreads their consumption on the base shape, which
puts winter kilowatt hours in summer hours and flatters self consumption.
Measured on 2026-08-23 with a flat profile, on a household of 6969 kWh of which
3469 is a heat pump: offtake comes out 8.4 percent low and feed-in 23.2 percent
low, against a default tolerance of 10 percent. So the feed-in line reads OFF
and the reason is not in the model.

That is the worst kind of validation failure, because it points at the wrong
subsystem. The CLI therefore says out loud what it assumed, the same way it
already does about a flat profile.

Usage::

    python -m ampeer_sim.validate statement.json --profiles data/nedu-profiles-2025.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import (
    FallbackProvider,
    PvgisProvider,
    ResilientProductionProvider,
)
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.profiles.nedu import NeduFileProvider
from ampeer_sim.providers import ProductionProvider, ProfileProvider
from ampeer_sim.simulate import DEFAULT_WEATHER_YEAR
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Household, ProfileCategory, PVSystem

REQUIRED_FIELDS = (
    "postcode4",
    "annual_consumption_kwh",
    "peak_power_wp",
    "azimuth_deg",
    "tilt_deg",
    "daytime_occupancy",
    "measured_offtake_kwh",
    "measured_feed_in_kwh",
)

DEFAULT_TOLERANCE_PERCENT = 10.0
DEFAULT_PROFILE_YEAR = 2025

#: Borrowed rather than repeated. A second copy here would let this tool check
#: one weather year while the product runs another, and the answer would look
#: like a model that had drifted from reality rather than two years being
#: compared. That is the failure this module was given a note about on
#: 2026-08-23: a validation tool pointing at the wrong subsystem.


@dataclass(frozen=True)
class Statement:
    postcode4: str
    annual_consumption_kwh: float
    peak_power_wp: int
    azimuth_deg: float
    tilt_deg: float
    daytime_occupancy: bool
    measured_offtake_kwh: float
    measured_feed_in_kwh: float


@dataclass(frozen=True)
class Deviation:
    measured: float
    modelled: float
    label: str

    @property
    def relative_error(self) -> float:
        if self.measured == 0.0:
            return float("inf") if self.modelled != 0.0 else 0.0
        return abs(self.modelled - self.measured) / self.measured

    def within(self, tolerance_fraction: float) -> bool:
        return self.relative_error <= tolerance_fraction


class FlatProfileProvider:
    """A featureless stand-in for when no NEDU file has been ingested.

    Using it means the shape of the day comes from nowhere, so a validation run
    against it says very little. The CLI says so out loud.
    """

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        grid = YearGrid.for_year(year)
        return np.full(grid.quarters, 1.0 / grid.quarters)


def load_statement(path: Path) -> Statement:
    """Read a statement, refusing anything in it this tool would not use.

    The unknown field check is not tidiness. A statement is a small file
    somebody writes by hand for one run, and until 2026-08-23 every key outside
    REQUIRED_FIELDS was dropped without a word. A typo in a field name was
    therefore indistinguishable from a field ignored by design, and so was
    ``"heat_pump": true``, which describes something the model would have used
    if it could and which this tool has no way to honour. Both came back as a
    clean comparison against a household that is not the one on the statement.

    Missing and unknown are reported together. Raising on the missing field
    alone named the absence and never the typo that caused it, which is the
    less useful half of the answer.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    unknown = sorted(field for field in payload if field not in REQUIRED_FIELDS)

    # Both halves in one message, and this is the point rather than a nicety.
    # Raising on the missing field first named the absence and never the typo
    # that caused it, so "measured_feedin_kwh" read as "measured_feed_in_kwh is
    # missing" and the writer went looking for a field that was there.
    problems = []
    if missing:
        problems.append(f"missing {', '.join(missing)}")
    if unknown:
        problems.append(
            f"holds {', '.join(unknown)}, which this tool does not use: it models a "
            f"household with no electric car and no heat pump"
        )
    if problems:
        raise ValueError(f"statement {' and '.join(problems)}")
    return Statement(**{field: payload[field] for field in REQUIRED_FIELDS})


def check(
    statement: Statement,
    profile_provider: ProfileProvider,
    production_provider: ProductionProvider,
    profile_year: int = DEFAULT_PROFILE_YEAR,
    weather_year: int = DEFAULT_WEATHER_YEAR,
) -> list[Deviation]:
    """Model the statement's household and compare both meter totals."""
    grid = YearGrid.for_year(profile_year)
    household = Household(
        postcode4=statement.postcode4,
        annual_consumption_kwh=statement.annual_consumption_kwh,
        daytime_occupancy=statement.daytime_occupancy,
    )
    system = PVSystem(
        peak_power_wp=statement.peak_power_wp,
        azimuth_deg=statement.azimuth_deg,
        tilt_deg=statement.tilt_deg,
    )
    hourly, temperature, _ = production_provider.hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(hourly, system, grid, weather_year=weather_year)
    consumption = compose_consumption(
        household,
        grid,
        profile_provider.fractions(profile_year, household.profile_category),
        temperature,
        weather_year=weather_year,
        production_kwh=production,
    )
    flows = simulate(consumption, production)
    return [
        Deviation(statement.measured_offtake_kwh, float(flows.total_import.sum()), "offtake"),
        Deviation(statement.measured_feed_in_kwh, float(flows.total_export.sum()), "feed_in"),
    ]


def _build_providers(
    source: str, profiles: Path | None, weather_year: int
) -> tuple[ProfileProvider, ProductionProvider]:
    profile_provider: ProfileProvider
    if profiles is not None:
        profile_provider = NeduFileProvider(profiles)
    else:
        profile_provider = FlatProfileProvider()
        print("warning: no --profiles given, using a flat profile. Results say little.")

    production_provider: ProductionProvider
    if source == "offline":
        production_provider = FallbackProvider(weather_year)
    else:
        production_provider = ResilientProductionProvider(
            PvgisProvider(weather_year=weather_year), FallbackProvider(weather_year)
        )
    return profile_provider, production_provider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the model against a real statement.")
    parser.add_argument("statement", type=Path)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PERCENT)
    parser.add_argument("--profiles", type=Path, default=None)
    parser.add_argument("--profile-year", type=int, default=DEFAULT_PROFILE_YEAR)
    parser.add_argument("--weather-year", type=int, default=DEFAULT_WEATHER_YEAR)
    parser.add_argument("--source", choices=("pvgis", "offline"), default="pvgis")
    args = parser.parse_args(argv)

    profile_provider, production_provider = _build_providers(
        args.source, args.profiles, args.weather_year
    )
    deviations = check(
        load_statement(args.statement),
        profile_provider=profile_provider,
        production_provider=production_provider,
        profile_year=args.profile_year,
        weather_year=args.weather_year,
    )

    print(
        "note: this models a household with no electric car and no heat pump. "
        "A statement from a household that has one will read OFF for a reason "
        "that is not in the model."
    )

    tolerance = args.tolerance / 100.0
    failed = False
    for deviation in deviations:
        status = "ok" if deviation.within(tolerance) else "OFF"
        print(
            f"{status:>3} {deviation.label:<8} measured {deviation.measured:9.1f} kWh  "
            f"modelled {deviation.modelled:9.1f} kWh  "
            f"error {deviation.relative_error * 100:5.1f} percent"
        )
        failed = failed or not deviation.within(tolerance)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
