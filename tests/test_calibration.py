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
from helpers.profiles import nedu_profile_path

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
#:
#: The name comes from the tool rather than being written again. The test below
#: skips when this file is absent, and a skip whose condition is an absence
#: cannot tell "not downloaded yet" from "looking in the wrong place".
RAW_PROFILES = nedu_profile_path(2025)

GRID = YearGrid.for_year(2025)
WEATHER_YEAR = 2025

#: Ceilings on a known disagreement, not targets: they may be tightened when the
#: model gets closer and must never be widened to make a change pass.
#:
#: Both stood at 0.05 until 2026-08-23, and only one of them was fitted. Measured
#: again on that date against the reference household: the worst monthly bucket
#: is July at 0.0230 and the worst hourly one is 17:00 at 0.0490. So the hourly
#: ceiling sat a fifth of a percentage point above the thing it measures and the
#: monthly one sat at more than twice it, doing nothing a regression would have
#: to get past. The monthly ceiling is 0.03, which is the measured 0.0230 with
#: room for ordinary movement and not much more.
#:
#: The hourly one came down to 0.04 on 2026-08-26, when the evening the entry in
#: docs/decisions.md asked about was repaired. The fallback's daily shape now
#: sits on solar noon at the location the yield table was measured at, 12:38 in
#: winter time, rather than on 12:00. Measured on the same reference household,
#: before and after:
#:
#:     worst hourly    17:00  0.0490   ->   11:00  0.0333
#:     worst monthly   July   0.0230   ->   July   0.0233
#:     export at 17:00 0.0061 -> 0.0234, at 18:00 0.0000 -> 0.0010
#:
#: 0.04 leaves the measured 0.0333 less room than the monthly ceiling has, and
#: it is the tightening that matters: it refuses the shape that was here before,
#: whose 0.0490 passed under 0.05 for a year.
MAX_MONTHLY_GAP = 0.03
MAX_HOURLY_GAP = 0.04

#: Two disagreements this file cannot close and should not be read as closing.
#:
#: The model still exports nothing at 19:00, where the country puts 0.0120 of
#: its year, and almost nothing at 18:00. Reaching those hours needs a longer
#: summer day, and every way of lengthening the day was measured on 2026-08-26
#: and refused: they fit this profile better and PVGIS's own hour of the day
#: worse, and the national profile is wide because it averages every roof
#: orientation in the country while this household faces south. The numbers are
#: above FALLBACK_DAYLIGHT_HOURS in ampeer_sim/production/pvgis.py.
#:
#: And the larger one, which is not the fallback's at all: PVGIS stamps its
#: hours in UTC, the grid runs in winter time, and nothing shifts the series
#: between them, so the path a visitor normally gets is an hour early. This
#: comparison never sees it, because it runs on the fallback on purpose.


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
    afternoon = [bucket for bucket in comparison.hourly if bucket.label >= "15:00"]
    six = next(bucket for bucket in afternoon if bucket.label == "18:00")
    assert six.measured > 0.02, "the country does export at six in the evening"

    for bucket in afternoon:
        assert bucket.modelled <= bucket.measured, (
            f"at {bucket.label} the model exports more than the country does, and this test "
            "exists because it exports less"
        )

    # The worst bucket rather than one chosen hour. Until 2026-08-23 this
    # asserted on 18:00 alone, where the gap was 0.0295 against a ceiling of
    # 0.05. The decline it is named for peaked an hour earlier, at 17:00 and
    # 0.0490, so the test watched a bucket with room to spare while the same
    # disagreement ran within two percent of the ceiling next door.
    worst = max(afternoon, key=lambda bucket: abs(bucket.gap))
    assert abs(worst.gap) <= MAX_HOURLY_GAP, (
        f"the daily gap grew at {worst.label}: {worst.gap:+.3f}"
    )


def test_the_model_still_exports_in_the_early_evening() -> None:
    """A floor under the repair of 2026-08-26, not another ceiling.

    The ceiling above says the disagreement may not grow. It does not say the
    evening exists. A shape that collapsed back to a day centred on 12:00 puts
    0.0061 of the year at 17:00, a quarter of what it puts there now, and it is
    caught above only because MAX_HOURLY_GAP came down to 0.04 in the same
    change; at the 0.05 it stood at for a year, that model passed.

    One hour and not two. 18:00 went from nothing to 0.0010, which is a real
    improvement and far too small to hold anything to. The floor sits below the
    measured 0.0234 because that is a share of an export total any unrelated
    model change moves a little. What it refuses is a model whose day is over at
    five.
    """
    comparison = compare_export_profile(
        _reference_export(), GRID, MEASURED_MONTHLY, MEASURED_HOURLY
    )
    hours = {bucket.label: bucket for bucket in comparison.hourly}
    assert hours["17:00"].modelled > 0.02, (
        f"the model puts {hours['17:00'].modelled:.4f} of its export at 17:00 and the country "
        f"puts {hours['17:00'].measured:.4f} there"
    )


def test_no_bucket_disagrees_by_more_than_the_recorded_ceiling() -> None:
    """Each family against its own ceiling.

    This compared both against ``max`` of the two until 2026-08-23, which was
    the same figure while both were 0.05 and stops being it the moment either
    is tightened. A ceiling that only counts while it is the loosest one is not
    a ceiling.
    """
    comparison = compare_export_profile(
        _reference_export(), GRID, MEASURED_MONTHLY, MEASURED_HOURLY
    )
    for buckets, ceiling, family in (
        (comparison.monthly, MAX_MONTHLY_GAP, "monthly"),
        (comparison.hourly, MAX_HOURLY_GAP, "hourly"),
    ):
        worst = max(buckets, key=lambda bucket: abs(bucket.gap))
        assert abs(worst.gap) <= ceiling, (
            f"the worst {family} bucket is {worst.label} at {worst.gap:+.4f}, over {ceiling}"
        )


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


def test_the_profile_name_is_derived_from_the_tool_that_writes_it() -> None:
    """The floor under a skip that nobody would notice standing.

    RAW_PROFILES gates a skipif. If the name it points at stopped being the
    name tools/ingest_profiles.py writes, the file would never be there, the
    skip would fire on every machine and in CI, and the message would read
    exactly as it does on a machine that simply has not downloaded it.

    So the name is read from the tool. What this asserts is that the reading
    still works and still depends on the year, because a template that lost its
    year would resolve to one fixed name and be wrong for every other.
    """
    from helpers.profiles import INGEST, nedu_profile_name

    name = nedu_profile_name(2025)
    assert name.endswith(".csv"), f"the tool writes {name!r}, which is not a csv"
    assert "2025" in name, f"{name!r} does not carry the year it was asked for"
    assert nedu_profile_name(2030) != name, (
        "the destination does not depend on the year, so every year would land on one file"
    )
    assert name in INGEST.read_text(encoding="utf-8").replace("{year}", "2025"), (
        f"{name!r} is not what {INGEST.name} builds; the derivation has drifted from "
        "the source it is supposed to be reading"
    )


# ---------------------------------------------------------------------------
# A series that does not belong to the grid it is bucketed against
# ---------------------------------------------------------------------------

LEAP_GRID = YearGrid.for_year(2024)


def test_a_series_from_another_year_is_refused_by_both_share_functions() -> None:
    """One of the two used to answer, and its answer looked healthy.

    ``hourly_share`` selects with a boolean mask the grid's own length, so numpy
    refused a mismatched series for it. ``monthly_share`` walks month boundaries
    by index, and a slice that runs past the end of a numpy array is clipped
    rather than refused. Measured on 2026-08-23 against a 365 day grid: a leap
    year series came back with shares summing to 0.997268, and a series 30000
    values long came back summing to exactly 1.000000 with January at 0.0992
    where it should be 0.0849.

    The second is why this is a raise. A total of one is what a correct
    distribution looks like, so there was nothing in the output to notice, and
    this module is the one that decides whether the model resembles the country.

    Reachable rather than theoretical: ``NeduFileProvider`` returns whatever
    rows the ingested file holds, skipping any with an empty cell, and 2024 is
    a leap year with 35136 quarters against the 35040 of this grid.
    """
    for label, series in (
        ("leap year", np.ones(LEAP_GRID.quarters)),
        ("truncated", np.ones(30_000)),
    ):
        for function in (monthly_share, hourly_share):
            with pytest.raises(ValueError, match="quarters and this series carries"):
                function(series, GRID)
            assert series.size != GRID.quarters, f"the {label} case is not a mismatch at all"


def test_the_refusal_does_not_catch_a_series_that_does_belong() -> None:
    """The floor, since a guard on the wrong comparison refuses everything.

    Both functions still answer for a series of the grid's own length, and for
    a leap year grid with the leap year length, so the check is on the pair and
    not on one hard coded number.
    """
    assert sum(monthly_share(np.ones(GRID.quarters), GRID)) == pytest.approx(1.0)
    assert sum(hourly_share(np.ones(GRID.quarters), GRID)) == pytest.approx(1.0)
    assert sum(monthly_share(np.ones(LEAP_GRID.quarters), LEAP_GRID)) == pytest.approx(1.0)
    assert monthly_share(np.ones(LEAP_GRID.quarters), LEAP_GRID)[1] == pytest.approx(
        29 / 366, rel=1e-6
    ), "February 2024 has 29 days and the leap grid should say so"
