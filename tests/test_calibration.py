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
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from helpers.profiles import nedu_profile_path
from test_pvgis_provider import (
    MAX_HOUR_OF_DAY_GAP,
    PVGIS_HOUR_OF_DAY_WINTER_TIME,
    WINTER_TIME_MINUS_UTC_HOURS,
)

from ampeer_sim.calibration import compare_export_profile, hourly_share, monthly_share
from ampeer_sim.engine.run import simulate
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import (
    PVGIS_STAMP_MINUTES_PAST_HOUR,
    FallbackProvider,
    PvgisProvider,
    postcode4_to_latlon,
)
from ampeer_sim.profiles.compose import compose_consumption
from ampeer_sim.profiles.nedu import NeduFileProvider
from ampeer_sim.timebase import (
    HOURS_PER_DAY,
    MINUTES_PER_QUARTER,
    QUARTERS_PER_DAY,
    QUARTERS_PER_HOUR,
    YearGrid,
)
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

#: One disagreement this file cannot close and should not be read as closing.
#:
#: The model still exports nothing at 19:00, where the country puts 0.0120 of
#: its year, and almost nothing at 18:00. Reaching those hours needs a longer
#: summer day, and every way of lengthening the day was measured on 2026-08-26
#: and refused: they fit this profile better and PVGIS's own hour of the day
#: worse, and the national profile is wide because it averages every roof
#: orientation in the country while this household faces south. The numbers are
#: above FALLBACK_DAYLIGHT_HOURS in ampeer_sim/production/pvgis.py.
#:
#: The second one recorded here is gone as of 2026-08-27. PVGIS stamps its hours
#: in UTC, the grid runs in winter time, and nothing shifted the series between
#: them, so the path a visitor normally gets ran an hour early while everything
#: above it ran on the fallback and never saw that. The repair is in
#: UTC_TO_WINTER_TIME_HOURS and what it was worth is beside it; the section at
#: the foot of this file is the check that the primary path is now placed where
#: PVGIS put it, which is the half this file was missing.

#: How far the modelled hour of the day may sit from PVGIS's own, summed over
#: the 24 hours, once the series has been through the whole production path.
#:
#: Imported rather than defined here as of 2026-08-27, with the rule behind its
#: value and the second number that rule produces. Two ceilings stood on this
#: one distance, 0.05 here and 0.10 in tests/test_pvgis_provider.py, a factor of
#: two apart and only one of them fitted to a measurement.
#:
#: What this measures, said plainly, because the paragraph it replaces said
#: something else. It is a check on placement to the nearest hour and it cannot
#: see anything finer. Measured on 2026-08-27, feeding PVGIS's own measured day
#: back in through the provider and production_series: 0.0171. The account
#: written here until that date called all of it the hour to quarter
#: interpolation and said nothing else in the path moves a series sideways.
#: Something else does. PVGIS stamps its rows ten minutes past the hour and the
#: grid anchors an hourly value half past, so the series sits twenty minutes
#: late, and this comparison holds it against a reference whose rows carry the
#: same ten past while the buckets start on the hour. The two twenty minute
#: offsets cancel, which is why the figure is small.
#:
#: Shown rather than argued: place the same series on its own stamps, one
#: interpolation anchored at ten past instead of half past, and this distance
#: becomes 0.0904. The metric scores correct placement five times worse than the
#: displacement it lives with, so it must not be read as saying the day is where
#: PVGIS put it. What it does say is that the day is in the right hour, and it
#: says that well: with the rotation removed it reads 0.2698.
#:
#: The twenty minutes is pinned where it can be measured, in
#: test_the_pvgis_series_is_twenty_minutes_late_and_no_whole_rotation_helps in
#: tests/test_pvgis_provider.py, and priced above UTC_TO_WINTER_TIME_HOURS.
#: Whoever repairs it has to re-found this comparison at the same time, on a
#: reference resampled onto the grid's hours, or this test will call the repair
#: a regression.
#:
#: What the ceiling refuses, measured the same day by drifting the series away
#: from where it sits now:
#:
#:     as it stands                  0.0171
#:     three minutes                 0.0205 later, 0.0209 earlier
#:     a quarter of an hour          0.0680 later, 0.0682 earlier
#:     half an hour                  0.1354 either way
#:     a whole hour early, as it was 0.2698
#:
#: So at 0.02 it refuses a drift of three minutes where at 0.05 it refused
#: fifteen. That tightening is free here: this path is fed a canned response,
#: so the figure moves only when the code does.


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


# ---------------------------------------------------------------------------
# The path a visitor actually gets, held against the hour PVGIS puts its energy
# ---------------------------------------------------------------------------
#
# Everything above runs on the offline fallback, on purpose: a calibration test
# that needs the network is a calibration test that gets skipped. The cost of
# that was a whole year in which the primary path was an hour out and nothing
# here could see it. What follows keeps the same principle and closes the hole:
# PVGIS's own measured hour of the day is handed back to the provider in the
# UTC stamps PVGIS delivers it in, and the assertion is that it comes out of the
# production path at the hours PVGIS put it at. No network, and the reference is
# a measurement rather than a shape this file invented.


def _pvgis_year_as_delivered() -> dict[str, Any]:
    """A PVGIS response whose every day repeats PVGIS's own hour of the day.

    ``PVGIS_HOUR_OF_DAY_WINTER_TIME`` is the nine year distribution for this
    plane written in winter time. What PVGIS sent over the wire is the same
    distribution stamped in UTC, so the row stamped hour h carries the share
    measured for winter time hour h plus one. Imported rather than copied: two
    tables of 24 measured shares that are supposed to be the same table will
    not stay it.

    Written as that lookup and not as ``np.roll(table, -1)`` since 2026-08-27,
    and the difference is not cosmetic. A roll is the inverse of the rotation
    the provider performs, so a payload built with one and asserted against the
    table it came from passes for any pair of provider and test that happen to
    roll by the same amount, including a pair that both roll by the wrong
    amount. What survives is the one thing here that is not the engine's own
    arithmetic: the shares are measured, and the hour offset is a property of
    the clock the country keeps rather than of this code. The row a share lands
    in is now written where a reader can check it against the timestamp.
    """
    offset = int(WINTER_TIME_MINUS_UTC_HOURS)
    as_utc = [
        PVGIS_HOUR_OF_DAY_WINTER_TIME[(hour + offset) % HOURS_PER_DAY]
        for hour in range(HOURS_PER_DAY)
    ]
    start = date(GRID.year, 1, 1)
    return {
        "outputs": {
            "hourly": [
                {
                    "time": f"{start + timedelta(days=day):%Y%m%d}:{hour:02d}10",
                    "P": float(watts),
                    "T2m": 10.0,
                }
                for day in range(GRID.days)
                for hour, watts in enumerate(as_utc)
            ]
        }
    }


def _stamped_centre(payload: dict[str, Any]) -> float:
    """Where the payload's own timestamps put its energy, in winter time hours.

    Read out of the rows rather than taken from whatever built them, and read
    without asking the engine anything, so this survives a change of placement.
    That is the point of it: the disagreement it measures is between two models
    of the sky and must not move when a clock does.
    """
    weighted = 0.0
    total = 0.0
    for row in payload["outputs"]["hourly"]:
        clock = row["time"].split(":")[1]
        stamped = int(clock[:2]) + int(clock[2:]) / 60.0 + WINTER_TIME_MINUS_UTC_HOURS
        weighted += row["P"] * stamped
        total += row["P"]
    return weighted / total


class _OneCannedYear:
    """The smallest thing PvgisProvider will accept in place of a session."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def get(self, url: str, params: dict[str, Any], timeout: float) -> _OneCannedYear:
        return self

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


PLACEMENT_SYSTEM = PVSystem(peak_power_wp=3_500, azimuth_deg=0.0, tilt_deg=35.0)


def _pvgis_quarters() -> np.ndarray:
    """PVGIS's own measured day, back through the provider and the model."""
    provider = PvgisProvider(
        weather_year=WEATHER_YEAR,
        session=_OneCannedYear(_pvgis_year_as_delivered()),  # type: ignore[arg-type]
    )
    hourly, _, _ = provider.hourly_series("5401", 0.0, 35.0)
    return production_series(hourly, PLACEMENT_SYSTEM, GRID, weather_year=WEATHER_YEAR)


def _fallback_quarters() -> np.ndarray:
    """The offline shape through the same model, for the same roof."""
    hourly, _, _ = FallbackProvider(WEATHER_YEAR).hourly_series("5401", 0.0, 35.0)
    return production_series(hourly, PLACEMENT_SYSTEM, GRID, weather_year=WEATHER_YEAR)


def _hour_of_day_centre(quarters: np.ndarray) -> float:
    """The energy centroid over the hour of the day, in winter time hours.

    One number rather than a distance over 24 buckets, because a bucket is an
    hour wide and the disagreements this is for are minutes.
    """
    minute_of_day = (
        np.arange(GRID.quarters) % QUARTERS_PER_DAY
    ) * MINUTES_PER_QUARTER + MINUTES_PER_QUARTER / 2.0
    return float((quarters * (minute_of_day / 60.0)).sum() / quarters.sum())


def _modelled_hour_of_day() -> np.ndarray:
    """The share of the modelled year's production falling in each reference hour.

    Bucketed on the grid rather than on the local clock, which is why
    ``hourly_share`` is not used here: it buckets by ``grid.local_hour``, which
    follows summer time, and the reference this is compared against is a fixed
    winter time distribution. Mixing the two would blur every summer hour into
    the next one and hide exactly the kind of one hour error this exists for.

    The buckets are the reference's own hours and not clock hours, and that is
    the correction of 2026-08-29. A PVGIS row is stamped ten minutes past, so
    the hour it speaks for runs from twenty to the hour until twenty past the
    next one, which in quarters is ``[4k - 1.333, 4k + 2.667)``. Bucketing the
    model on clock hours instead compared it against windows shifted from its
    own by ten minutes, and that misalignment cancelled against the twenty
    minute lag the series carried until 2026-08-27: the metric read 0.0171,
    which looked like a well placed series and was two errors of opposite sign.
    Repairing the placement made it read 0.0904 and the fault was in the ruler.

    Integrated over the window rather than sampled at its centre, so the two
    partial quarters at either end carry the fraction of themselves that falls
    inside it. The five weights sum to four, which is the check that the window
    is an hour wide however the stamp moves.
    """
    quarters = _pvgis_quarters()

    stamp_in_quarters = PVGIS_STAMP_MINUTES_PAST_HOUR / MINUTES_PER_QUARTER
    weights = (1.0 - stamp_in_quarters, 1.0, 1.0, 1.0, stamp_in_quarters)
    assert sum(weights) == pytest.approx(QUARTERS_PER_HOUR, abs=1e-12)

    padded = np.pad(quarters, 2)
    windowed = sum(
        weight * padded[2 + offset : 2 + offset + quarters.size]
        for offset, weight in zip((-2, -1, 0, 1, 2), weights, strict=True)
    )
    at_hour = np.asarray(windowed).reshape(GRID.days, HOURS_PER_DAY, QUARTERS_PER_HOUR)[:, :, 0]
    by_hour = at_hour.sum(axis=0)
    return np.asarray(by_hour / by_hour.sum())


def test_the_pvgis_path_puts_the_day_where_pvgis_put_it() -> None:
    """The check the year of running this file on the fallback alone did not do.

    Until 2026-08-27 the answer to this was 0.2698 against a ceiling of 0.05,
    and no test in the repository asked. The primary path placed PVGIS's UTC
    hour i at grid hour i, so a visitor's whole production series sat an hour
    early: self consumption 28.16 percent instead of 29.13, export 2583 kWh
    instead of 2548, and nine euro too much on the headline figure. The numbers
    and the household are above UTC_TO_WINTER_TIME_HOURS.

    Not a test of the constant. The reference is PVGIS's own measurement and the
    quantity is where the energy lands, so this stays honest if somebody
    reimplements the conversion, moves it to another module, or replaces the
    rotation with something cleverer.

    To the hour, and only to the hour. The reference's rows carry PVGIS's stamp
    of ten past and these buckets start on the hour, so a series twenty minutes
    late scores better here than one placed on its stamps. That is the state
    the engine is in and the reason is above MAX_HOUR_OF_DAY_GAP, with the
    minutes pinned separately in tests/test_pvgis_provider.py.
    """
    measured = np.array(PVGIS_HOUR_OF_DAY_WINTER_TIME)
    gap = float(np.abs(_modelled_hour_of_day() - measured / measured.sum()).sum())
    assert gap <= MAX_HOUR_OF_DAY_GAP, (
        f"the modelled hour of the day is {gap:.4f} away from PVGIS's own, over "
        f"{MAX_HOUR_OF_DAY_GAP}. It was 0.0171 when this was measured, 0.2698 while "
        "the series was placed an hour early, and 0.0904 for a series placed on PVGIS's "
        "own stamps, which is the repair this comparison has to be re-founded for"
    )


def test_the_modelled_peak_hour_is_the_one_solar_noon_falls_in() -> None:
    """The same claim in the form a reader can check against a clock.

    The gap above is a distance and a distance can be small for the wrong
    reason. This says where the top of the day is: solar noon at 5.61 degrees
    east is 12:38 in continuous winter time, so the fullest hour of the modelled
    year is the one running from 12:00, and the hour is derived from the
    longitude the postcode maps to rather than written down.

    An hour early puts it at 11:00, which is what shipped until 2026-08-27.
    """
    longitude = postcode4_to_latlon("5401")[1]
    solar_noon = 13.0 - longitude / 15.0
    peak = int(np.argmax(_modelled_hour_of_day()))
    assert peak == int(solar_noon), (
        f"the modelled year is fullest at {peak}:00 in winter time and solar noon at "
        f"{longitude} degrees east is {solar_noon:.2f}"
    )


#: How far apart the two providers may put the same roof's day, in minutes.
#:
#: Nothing compared them until 2026-08-27, and the omission has a shape: every
#: calibrated and version pinned number in this repository is measured on the
#: offline fallback, because a test that needs the network is a test that gets
#: skipped, and every number a visitor reads comes off PVGIS. Two paths that
#: disagree about the hour of the day produce one set of goldens and another set
#: of answers, and no test in either half can see it.
#:
#: Measured on 2026-08-27, both through production_series for the same roof at
#: postcode 5401, as the energy centroid over the hour of the day in winter
#: time: the fallback at 12.6263 and PVGIS at 12.8859, so the fallback is 15.6
#: minutes earlier. That is not one disagreement but two, and they run opposite
#: ways.
#:
#: Twenty minutes of it is placement and does not belong to either provider's
#: model of the sky: PVGIS stamps ten past the hour, the grid anchors half past,
#: and the argument is above UTC_TO_WINTER_TIME_HOURS. Take that out and PVGIS's
#: own day sits at 12.5525, which is 4.4 minutes earlier than the fallback
#: rather than 15.6 later. The 4.4 is the real disagreement and it is the second
#: check below: the offline shape is a half sine symmetric about solar noon at
#: 12.626, and the nine years PVGIS averaged are not symmetric about it. They
#: are morning heavy, which the same call says twice, since it also gives east
#: 979.35 kWh per kWp against west 948.91.
#:
#: The ceiling is on the total and is one sided on purpose. It refuses the gap
#: growing and admits the repair, which would bring it to 4.4 the other way.
MAX_PROVIDER_PLACEMENT_GAP_MINUTES = 16.0

#: How far the offline shape's centre may sit from where PVGIS's own timestamps
#: put PVGIS's day, in minutes. Measured on 2026-08-27: PVGIS at 12.5525 in
#: winter time against the offline shape's 12.6263, so 4.4 minutes, the fallback
#: later.
#:
#: PVGIS's side is read off the response rather than off the modelled series, so
#: this is the half that survives a repair of the placement and it is the one
#: worth a ceiling of its own. A half sine centred on solar noon cannot express
#: a morning heavy day and is not being asked to; what this refuses is that
#: disagreement growing without anybody deciding it should.
MAX_FALLBACK_SHAPE_OFFSET_MINUTES = 6.0


def test_the_two_providers_put_the_day_in_the_same_place() -> None:
    """The pairing this file was missing, and the reason it was missing.

    Everything above runs on the fallback and the section above this one runs
    on PVGIS, and until 2026-08-27 nothing held one against the other. That is
    exactly the seam a placement error hides in: the goldens are measured on one
    provider and read on the other, so a whole year passed with the live path an
    hour out while every test in the repository was green.

    Two assertions because there are two disagreements. The first is the total,
    which is what a visitor is exposed to, and it moves when the placement does.
    The second reads PVGIS's side off the timestamps in the response instead of
    off the modelled series, so it survives a change of placement and measures
    only what the two models of the sky disagree about.
    """
    fallback_centre = _hour_of_day_centre(_fallback_quarters())
    pvgis_centre = _hour_of_day_centre(_pvgis_quarters())
    gap = (pvgis_centre - fallback_centre) * 60.0
    assert abs(gap) <= MAX_PROVIDER_PLACEMENT_GAP_MINUTES, (
        f"the fallback centres its day on {fallback_centre:.4f} in winter time and the PVGIS "
        f"path on {pvgis_centre:.4f}, which is {gap:+.1f} minutes apart, over "
        f"{MAX_PROVIDER_PLACEMENT_GAP_MINUTES}. It was +15.6 when this was measured, of which "
        "+20.0 is the stamp offset above UTC_TO_WINTER_TIME_HOURS"
    )

    as_pvgis_stamped_it = _stamped_centre(_pvgis_year_as_delivered())
    remaining = (as_pvgis_stamped_it - fallback_centre) * 60.0
    assert abs(remaining) <= MAX_FALLBACK_SHAPE_OFFSET_MINUTES, (
        f"PVGIS's own timestamps put its day at {as_pvgis_stamped_it:.4f} in winter time and "
        f"the offline shape sits at {fallback_centre:.4f}, which is {remaining:+.1f} minutes "
        f"apart, over {MAX_FALLBACK_SHAPE_OFFSET_MINUTES}. It was -4.4 when this was measured"
    )
