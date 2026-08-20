"""The model held against measured Dutch data.

The other four test layers ask whether the code matches the design. This one
asks whether the design matches the country, using the only measured Dutch
series available without a single user having connected anything: the NEDU
feed-in profile of connections that export.

The reference is committed as aggregate shares rather than the series itself.
Twelve monthly and twenty four hourly figures are a fact about the dataset and
not a copy of it, which matters while the redistribution terms are unconfirmed,
and it lets this run in CI where the raw file does not exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ampeer_sim.calibration import compare_export_profile, hourly_share, monthly_share
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.profiles.nedu import NeduFileProvider
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import Household, ProfileCategory, PVSystem

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "nedu_ami_i_shares.json").read_text(encoding="utf-8")
)
MEASURED_MONTHLY: tuple[float, ...] = tuple(REFERENCE["monthly_share"])
MEASURED_HOURLY: tuple[float, ...] = tuple(REFERENCE["hourly_share"])

#: Only present on a machine that has run tools/ingest_profiles.py. Gitignored,
#: because the redistribution terms of the NEDU files are not confirmed.
RAW_PROFILES = Path(__file__).resolve().parent.parent / "data" / "nedu-profiles-2025.csv"

GRID = YearGrid.for_year(2025)
WEATHER_YEAR = 2025

#: Measured on 2026-08-21 against the reference household. These are ceilings on
#: a known disagreement, not targets: they may be tightened when the model gets
#: closer and must never be widened to make a change pass.
MAX_MONTHLY_GAP = 0.05
MAX_HOURLY_GAP = 0.05


def _reference_export() -> np.ndarray:
    """The export series of the reference household, on the offline provider.

    FallbackProvider rather than PVGIS on purpose: a calibration test that needs
    the network is a calibration test that gets skipped.
    """
    household = Household(postcode4="5401", annual_consumption_kwh=3_500.0)
    system = PVSystem(peak_power_wp=3_500, azimuth_deg=0.0, tilt_deg=35.0)
    hourly, temperature, _ = FallbackProvider(WEATHER_YEAR).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(hourly, system, GRID, weather_year=WEATHER_YEAR)
    fractions = np.full(GRID.quarters, 1.0 / GRID.quarters)
    consumption = compose_consumption(
        household,
        GRID,
        fractions,
        temperature,
        weather_year=WEATHER_YEAR,
        production_kwh=production,
    )
    return simulate(consumption, production).to_grid


def test_the_reference_shares_are_a_complete_distribution() -> None:
    assert sum(MEASURED_MONTHLY) == pytest.approx(1.0, abs=1e-5)
    assert sum(MEASURED_HOURLY) == pytest.approx(1.0, abs=1e-5)
    assert len(MEASURED_MONTHLY) == 12
    assert len(MEASURED_HOURLY) == 24


def test_the_reference_carries_its_provenance() -> None:
    """A number without a source is an invented number, however true it looks."""
    assert REFERENCE["series"] == "E1A_AMI_I"
    assert REFERENCE["read_on"] == "2026-08-20"
    assert "NEDU" in REFERENCE["source"]


def test_shares_of_a_flat_series_are_proportional_to_bucket_size() -> None:
    """The share functions must measure the series and not the calendar."""
    flat = np.full(GRID.quarters, 1.0)
    assert sum(monthly_share(flat, GRID)) == pytest.approx(1.0)
    assert monthly_share(flat, GRID)[0] == pytest.approx(31 / 365, rel=1e-6)
    assert all(share == pytest.approx(1 / 24, rel=1e-6) for share in hourly_share(flat, GRID))


def test_a_series_that_exports_nothing_cannot_be_compared() -> None:
    with pytest.raises(ValueError, match="exports nothing"):
        monthly_share(np.zeros(GRID.quarters), GRID)


def test_the_modelled_export_follows_the_measured_season() -> None:
    """The export lands in the right half of the year, month by month.

    An earlier version of this asserted that the peak month matched exactly. It
    does not, and it should not have been asked to: over nine weather years May
    and June differ by 0.15 percent in this location, and May has a day more, so
    which of the two wins is noise rather than a property of the model. A test
    that pins noise fails for reasons nobody can act on, and gets deleted.

    What is worth pinning is the season. Both curves must peak in high summer,
    and the share of the year that leaves the meter between April and September
    must agree, because that is what decides how much of the problem the end of
    net metering actually creates.
    """
    comparison = compare_export_profile(
        _reference_export(), GRID, MEASURED_MONTHLY, MEASURED_HOURLY
    )
    high_summer = {"month 5", "month 6", "month 7"}
    assert max(comparison.monthly, key=lambda bucket: bucket.modelled).label in high_summer
    assert max(comparison.monthly, key=lambda bucket: bucket.measured).label in high_summer

    summer = comparison.monthly[3:9]
    modelled_summer = sum(bucket.modelled for bucket in summer)
    measured_summer = sum(bucket.measured for bucket in summer)
    assert modelled_summer == pytest.approx(measured_summer, abs=0.05), (
        f"April to September: model {modelled_summer:.3f}, measured {measured_summer:.3f}"
    )

    worst = comparison.largest_monthly_gap
    assert abs(worst.gap) <= MAX_MONTHLY_GAP, f"{worst.label}: {worst.gap:+.3f}"


def test_the_modelled_export_stops_earlier_in_the_day_than_the_country_does() -> None:
    """A known, explained disagreement, pinned so it cannot grow unnoticed.

    The measured series averages every roof orientation in the country. West
    facing arrays keep exporting into the evening and east facing ones start
    earlier, so the national curve is wider than any single house can be. The
    reference household faces south, so its export collapses in the late
    afternoon while the country is still exporting.

    This is not a defect to fix in the engine; it is a limitation of modelling
    one orientation, and it belongs in docs/methodologie.md rather than in a
    bug report. It is pinned here so that if the gap ever grows, somebody finds
    out from a red test rather than from a reader.
    """
    comparison = compare_export_profile(
        _reference_export(), GRID, MEASURED_MONTHLY, MEASURED_HOURLY
    )
    evening = next(bucket for bucket in comparison.hourly if bucket.label == "18:00")
    assert evening.measured > 0.02, "the country does export at six in the evening"
    assert evening.modelled < evening.measured, "the model should be the narrower one"
    assert abs(evening.gap) <= MAX_HOURLY_GAP, f"the daily gap grew: {evening.gap:+.3f}"


def test_no_bucket_disagrees_by_more_than_the_recorded_ceiling() -> None:
    comparison = compare_export_profile(
        _reference_export(), GRID, MEASURED_MONTHLY, MEASURED_HOURLY
    )
    assert comparison.worst_gap <= max(MAX_MONTHLY_GAP, MAX_HOURLY_GAP)


@pytest.mark.skipif(not RAW_PROFILES.exists(), reason="run tools/ingest_profiles.py first")
def test_the_committed_reference_still_matches_the_raw_profile_file() -> None:
    """The aggregate fixture must stay a true summary of the series it came from.

    Only runs where the raw file has been ingested. Without this, the committed
    shares could drift from the data they claim to describe and nothing would
    say so, which is the same failure this whole layer exists to catch.
    """
    measured = NeduFileProvider(RAW_PROFILES).feed_in_fractions(2025, ProfileCategory.E1A)
    assert monthly_share(measured, GRID) == pytest.approx(MEASURED_MONTHLY, abs=1e-5)
    assert hourly_share(measured, GRID) == pytest.approx(MEASURED_HOURLY, abs=1e-5)
