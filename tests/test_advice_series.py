"""The year of quarter-hour flows, from the packing to the wire.

Two things are checked here and they are different in kind.

The first is arithmetic: a year of three flow series survives being squeezed
into two bytes a quarter, and the error it costs is the error the format
promises and no more. Every measurement below was taken on 2026-08-27 on the
household this module builds, and the input it is measured against is built
from the production model and a demand shape, never from the encoder. Reading
the byte arrays back and comparing them to themselves reports a reassuring zero
and proves only that rounding twice is rounding once, which is a mistake made
twice in this repository on 2026-08-27 before it was noticed.

The second is a privacy control and has nothing to do with bytes. The field
carries where its numbers came from, and a measured series may not leave over a
shareable token. Nothing produces a measured series today, which is exactly why
the test for it is written now: in phase 2 the same field carries a series off
a household's own meter, and adding the refusal then costs a migration over
every stored advice and leaves a gap between the first measured series and the
control over it.
"""

from __future__ import annotations

import ast
import base64
import dataclasses
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from django.urls import reverse
from rest_framework import serializers as drf_serializers
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

import advice.serializers
from advice.assembly import build_year
from advice.models import StoredAdvice
from advice.serializers import YearSerializer, year_field
from advice.series import (
    EXPORT_FLAG,
    MAGNITUDE_MASK,
    MEASURED,
    OWN_FULL_SCALE,
    QUARTERS_PER_YEAR,
    SYNTHETIC,
    EncodedYear,
    MeasuredSeriesRefused,
    decode_year,
    encode_year,
)
from ampeer_sim.production.model import production_series
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import EnergyFlows, PVSystem

#: The five keys the frontend was given, written out rather than read from the
#: serializer. Reading them from the thing under test would make this file
#: agree with whatever the serializer happens to declare, which is the property
#: a contract test must not have.
WIRE_KEYS = {"own", "meter", "ceilings", "provenance", "quarters"}

#: And the three inside `ceilings`, for the same reason.
CEILING_KEYS = {"own", "export", "grid"}

PROFILE_YEAR = 2025
WEATHER_YEAR = 2023
ANNUAL_CONSUMPTION_KWH = 3500.0
PEAK_POWER_WP = 3500

GRID = YearGrid.for_year(PROFILE_YEAR)

#: How far an annual total may move over the round trip, as a percentage.
#:
#: Measured on 2026-08-27 on the household below: own use drifts -0.00433
#: percent, export -0.00369 and offtake -0.00812. The ceiling is roughly twice
#: the worst of those, which is room for ordinary movement and not much more. A
#: quantisation that rounded rather than rounded to nearest, or a ceiling set
#: below the maximum, moves this by orders of magnitude rather than by a
#: fraction.
MAX_TOTAL_DRIFT_PCT = 0.02

#: How close the worst single quarter must sit to half a quantisation step.
#:
#: Both ends matter. Above 1.0 the format is losing more than it promises.
#: Below 0.9 the worst quarter is not reaching half a step, which on a year of
#: 35040 quarters means the top of the range is not being used, and the usual
#: reason for that is a ceiling that is not the maximum. Measured on 2026-08-27:
#: 0.99966, 0.99999 and 0.99997 on the three series.
MIN_WORST_QUARTER_RATIO = 0.9

ADVICE_PACKAGE = Path(advice.serializers.__file__).parent

#: The modules that may import the wire format directly.
#:
#: `assembly.py` builds an encoded year and stamps it, `serializers.py` is the
#: one door that turns one into the object a browser receives. Anything else
#: reaching into `advice.series` is a second exit with no provenance check on
#: it, which is the way a control that costs three lines stops being reached.
#: Pinned as a set for the same reason `tests/test_boundaries.py` pins the one
#: module allowed to open a socket: adding a third is where somebody has to say
#: why.
SERIES_IMPORTERS = {"assembly.py", "serializers.py"}


def _consumption() -> np.ndarray:
    """A household's demand, in kWh per quarter, built from nothing under test.

    Not the NEDU profile, which is a data file this repository may not commit,
    and not a flat line either: a flat year quantises far better than a real
    one and would report an error the format does not actually have. This is a
    morning and an evening peak on a base load, with a seasonal swing, a
    heavier weekend and day to day variation from a seeded generator, scaled to
    the annual figure. The seed is fixed so the measurements above are a
    statement about a specific year rather than about an average of runs.
    """
    hour = GRID.local_hour.astype(float)
    day = np.arange(GRID.quarters) // 96
    shape = (
        0.55
        + 0.80 * np.exp(-(((hour - 7.5) / 1.4) ** 2))
        + 1.60 * np.exp(-(((hour - 19.0) / 2.0) ** 2))
    )
    season = 1.0 + 0.30 * np.cos(2 * np.pi * day / GRID.days)
    weekend = np.where(day % 7 >= 5, 1.18, 1.0)
    rng = np.random.default_rng(20260827)
    per_day = rng.lognormal(0.0, 0.18, GRID.days)[day]
    jitter = rng.lognormal(0.0, 0.10, GRID.quarters)
    raw = shape * season * weekend * per_day * jitter
    return np.asarray(raw / raw.sum() * ANNUAL_CONSUMPTION_KWH)


def reference_household_year() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One year of flows: own use, export, offtake, in kWh per quarter.

    The production half comes out of the offline production model, so this runs
    without a network and the shape is the one the engine itself would use. The
    three flows are then the definition and not a model of anything: a
    household uses the smaller of what it makes and what it needs, feeds in
    what is left over and takes the rest off the grid. That construction is
    also why no quarter holds both directions, which is the property the meter
    byte rests on.

    Public rather than underscored because `tests/test_dpia.py` measures the
    size of this household's payload, and `docs/dpia.md` quotes that figure by
    naming this file. Two households would make the document quote a
    measurement of something else.
    """
    watts, _temperature, _source = FallbackProvider(WEATHER_YEAR).hourly_series("5401", 0.0, 35.0)
    system = PVSystem(peak_power_wp=PEAK_POWER_WP, azimuth_deg=0.0, tilt_deg=35.0)
    production = production_series(watts, system, GRID, weather_year=WEATHER_YEAR)
    used = _consumption()
    own = np.minimum(used, production)
    return own, production - own, used - own


def reference_household_flows() -> EnergyFlows:
    """The same year as the engine hands it over, so `build_year` can be fed.

    Built here from the three series above rather than by running the engine,
    for the reason the module docstring gives about circular measurement: the
    mapping from flows to wire is what `tests/test_advice_assembly.py` checks,
    and a fixture produced by the code under test would agree with whatever
    that code became. What this asserts by construction is only the identity
    the engine also satisfies, that consumption is direct use plus offtake and
    production is direct use plus feed-in.
    """
    own, export, grid = reference_household_year()
    zeros = np.zeros_like(own)
    return EnergyFlows(
        consumption=own + grid,
        production=own + export,
        self_consumption=own,
        from_grid=grid,
        to_grid=export,
        battery_charge=zeros,
        battery_discharge=zeros,
    )


def _three_series(
    encoded: EncodedYear,
) -> list[tuple[str, np.ndarray, np.ndarray, int]]:
    """Each flow beside what it decodes to, and the steps its byte is cut into."""
    own, export, grid = reference_household_year()
    back_own, back_export, back_grid = decode_year(encoded)
    return [
        ("own", own, back_own, OWN_FULL_SCALE),
        ("export", export, back_export, MAGNITUDE_MASK),
        ("grid", grid, back_grid, MAGNITUDE_MASK),
    ]


def _advice_modules() -> list[Path]:
    """Every module in the advice package, walked rather than listed."""
    return [
        path for path in sorted(ADVICE_PACKAGE.rglob("*.py")) if "__pycache__" not in path.parts
    ]


def _imports_the_wire_format(tree: ast.Module) -> bool:
    """Whether a module reads advice.series, judged on its imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "advice.series":
            return True
        if isinstance(node, ast.Import) and any(
            alias.name == "advice.series" for alias in node.names
        ):
            return True
    return False


def test_a_year_survives_the_round_trip_to_within_half_a_step() -> None:
    """The error the format costs, against the error it promises.

    Half a quantisation step is the most a round to nearest can lose, so the
    upper bound is arithmetic rather than a tolerance somebody chose. The lower
    bound is the half that gives this test teeth: a worst quarter well under
    half a step means the top of the byte range is never reached, and the
    ordinary cause of that is a ceiling set to a percentile of the series
    instead of its maximum.
    """
    own, export, grid = reference_household_year()
    encoded = encode_year(own, export, grid)

    for name, before, after, full in _three_series(encoded):
        step = encoded.ceilings[name] / full
        worst = float(np.abs(before - after).max())
        ratio = worst / (step / 2.0)
        assert ratio <= 1.0 + 1e-9, (
            f"{name} loses {worst * 1000:.3f} Wh in its worst quarter, more than the "
            f"{step / 2 * 1000:.3f} Wh half step the format costs"
        )
        assert ratio >= MIN_WORST_QUARTER_RATIO, (
            f"{name} never reaches half a step: {ratio:.5f} of it. The byte range is "
            "not being used, which is what a percentile ceiling looks like"
        )


def test_the_annual_totals_survive_the_round_trip() -> None:
    """A picture may lose a quarter. A year that no longer adds up is a defect.

    Each of these three figures also appears in the advice as a euro amount, so
    a series whose total drifts is a picture that contradicts the number
    printed beside it.
    """
    own, export, grid = reference_household_year()
    encoded = encode_year(own, export, grid)

    for name, before, after, _full in _three_series(encoded):
        drift = (after.sum() - before.sum()) / before.sum() * 100.0
        assert abs(drift) <= MAX_TOTAL_DRIFT_PCT, (
            f"{name} drifts {drift:+.5f} percent over the round trip, past the "
            f"{MAX_TOTAL_DRIFT_PCT} percent this format allows"
        )


def test_no_quarter_comes_back_on_the_wrong_side_of_the_meter() -> None:
    """The one error that is a defect rather than a loss of fidelity.

    A magnitude rounding away to zero is a small quarter drawn as nothing. A
    quarter that exported coming back as offtake is the picture telling a
    household the opposite of what happened, and the direction lives in a bit
    that rounding cannot touch, so the count here is zero and not small.
    """
    own, export, grid = reference_household_year()
    back_own, back_export, back_grid = decode_year(encode_year(own, export, grid))
    del back_own

    flipped = int(np.sum((export > 0) & (back_grid > 0)) + np.sum((grid > 0) & (back_export > 0)))
    assert flipped == 0, f"{flipped} quarters came back on the wrong side of the meter"


def test_the_direction_lives_in_the_high_bit_and_the_magnitude_under_it() -> None:
    """The packing itself, read out of the bytes rather than through the decoder.

    Going through `decode_year` would test the two halves against each other,
    which passes for any pair of functions that agree. This reads the array the
    browser reads.
    """
    own, export, grid = reference_household_year()
    encoded = encode_year(own, export, grid)

    meter = np.frombuffer(base64.b64decode(encoded.meter), dtype=np.uint8)
    assert np.array_equal((meter & EXPORT_FLAG) > 0, export > 0), (
        "the export flag is not set on exactly the quarters that exported"
    )
    assert int((meter & MAGNITUDE_MASK).max()) == MAGNITUDE_MASK, (
        "no quarter reaches the top of the seven bit magnitude, so the ceiling is "
        "above the maximum and resolution is being thrown away"
    )


def test_the_ceilings_are_the_maxima_so_nothing_is_clipped() -> None:
    """The reason the payload carries maxima and the renderer does the clipping.

    A percentile ceiling makes a prettier plate, and it throws away the
    brightest quarters of the year irreversibly. Measured on 2026-08-27 on this
    household: a p99 ceiling would flatten 205 quarters of own use, 120 of
    export and 231 of offtake, and none of them could be recovered by a
    renderer that wanted them back.
    """
    own, export, grid = reference_household_year()
    encoded = encode_year(own, export, grid)

    for name, before, after, _full in _three_series(encoded):
        assert encoded.ceilings[name] == pytest.approx(float(before.max()))
        assert float(after.max()) == pytest.approx(float(before.max()))

        clipped = int((before > float(np.percentile(before[before > 0], 99))).sum())
        assert clipped > 50, (
            f"a p99 ceiling would clip only {clipped} quarters of {name}, so this "
            "measurement no longer supports the choice it is here to support"
        )


def test_a_quarter_holding_both_directions_is_refused_rather_than_packed() -> None:
    """The assumption the second byte rests on, asserted instead of believed.

    One byte holds the meter because a quarter is a surplus or a shortfall and
    not both, which is true by construction of the flows and measured at zero
    quarters over a full year. If it ever stops being true, the packing would
    silently drop one of the two directions and the picture would show the
    wrong side of the meter, so the encoder raises.
    """
    own, export, grid = reference_household_year()
    both = grid.copy()
    both[export > 0] = 1.0

    with pytest.raises(ValueError, match="both directions"):
        encode_year(own, export, both)


def test_a_direction_a_household_never_uses_encodes_as_zero() -> None:
    """A ceiling of zero is an answer and not an error.

    A flat with no panels imports every quarter of the year and exports none of
    them, and a division by that ceiling would be the one place this module
    could produce a NaN on a real household.
    """
    own, export, grid = reference_household_year()
    nothing = np.zeros_like(export)
    encoded = encode_year(own, nothing, grid + export)

    assert encoded.ceilings["export"] == 0.0
    _own, back_export, back_grid = decode_year(encoded)
    del _own
    assert not np.any(np.isnan(back_export))
    assert float(np.abs(back_export).max()) == 0.0
    assert float(back_grid.max()) > 0.0


@pytest.mark.parametrize(
    ("mangle", "message"),
    [
        (lambda own, export, grid: (own[:-1], export, grid), "same length"),
        (lambda own, export, grid: (own[:96], export[:96], grid[:96]), "not a year"),
    ],
)
def test_a_series_that_is_not_a_matching_year_is_refused(mangle: Any, message: str) -> None:
    """Both shapes a caller can get wrong, refused with the reason named.

    A short array would otherwise encode happily and arrive at a browser that
    allocated 365 by 96 for it, which draws a year with a hole in it rather
    than raising anywhere.
    """
    own, export, grid = reference_household_year()
    with pytest.raises(ValueError, match=message):
        encode_year(*mangle(own, export, grid))


def test_an_unrecognised_provenance_is_refused_at_the_encoder() -> None:
    """There are two answers to where a series came from and no third.

    A typo would otherwise sail past the shareability check below, which asks
    whether the value is in the shareable set and would read anything it does
    not recognise as not shareable, or, one edit later, as shareable.
    """
    own, export, grid = reference_household_year()
    with pytest.raises(ValueError, match="provenance"):
        encode_year(own, export, grid, provenance="ESTIMATED")


def test_the_serializer_declares_the_five_keys_the_frontend_was_given() -> None:
    """The published contract, against names written out in this file.

    Read from the serializer on one side and typed out on the other, because a
    contract test that derives both sides from the same object agrees with
    whatever that object became.
    """
    assert set(YearSerializer().fields) == WIRE_KEYS
    assert set(advice.serializers.YearCeilingsSerializer().fields) == CEILING_KEYS
    assert QUARTERS_PER_YEAR == {35040, 35136}


def test_a_year_survives_the_round_trip_through_the_real_serializer() -> None:
    """Encoder to serializer to JSON to bytes and back, the way a browser gets it.

    The encoder's own round trip is checked above and it proves nothing about
    the wire: base64 in a Python string and base64 in a rendered response are
    the same characters only if nothing in between decides to re-encode, quote
    or truncate them. So this goes through the serializer the API declares and
    through DRF's renderer, and decodes what comes out the other end.
    """
    own, export, grid = reference_household_year()
    payload = year_field(build_year(reference_household_flows()))

    body = json.loads(JSONRenderer().render(payload).decode("utf-8"))
    assert set(body) == WIRE_KEYS
    assert set(body["ceilings"]) == CEILING_KEYS
    assert body["provenance"] == SYNTHETIC
    assert body["quarters"] == GRID.quarters

    back_own, back_export, back_grid = decode_year(
        EncodedYear(
            own=body["own"],
            meter=body["meter"],
            ceilings=body["ceilings"],
            provenance=body["provenance"],
            quarters=body["quarters"],
        )
    )
    for before, after in ((own, back_own), (export, back_export), (grid, back_grid)):
        drift = (after.sum() - before.sum()) / before.sum() * 100.0
        assert abs(drift) <= MAX_TOTAL_DRIFT_PCT
        assert after.shape == before.shape


def test_the_serializer_refuses_a_year_that_is_not_the_shape_it_declares() -> None:
    """Strictness on the way out, not only on the way in.

    An extra key is a key the frontend never learns about and a wrong quarter
    count is an array a browser allocates the wrong grid for. Both would go out
    unremarked if this object were assembled as a dict literal, which is the
    reason it is a serializer.
    """
    good = year_field(build_year(reference_household_flows()))

    for broken in (good | {"scale": 1}, good | {"quarters": 96}):
        serializer = YearSerializer(data=broken)
        assert not serializer.is_valid()


@pytest.mark.django_db
def test_a_measured_series_is_never_served_on_the_token_route() -> None:
    """A measured quarter-hour series may not leave over a shareable token.

    This test looks strange today and the strangeness is the point. Nothing in
    this repository produces a measured series: phase 0.5 has no meter
    coupling, so every year the API can build is a national profile scaled to a
    figure somebody typed into a form. The measured series below is therefore
    constructed here rather than obtained, so that the refusal is exercised on
    a real object instead of on an argument nothing ever passes.

    Why now rather than in phase 2. An advice is retrievable for ninety days
    through a token its holder can forward to anyone, with no account and no
    second factor behind it, and a measured series says when somebody is home.
    Built now the control is one call. Added when the first measured series
    exists, it needs a migration over every stored advice and leaves a gap in
    between during which the rule is written in a document and enforced
    nowhere.

    The route half is what makes this more than a unit test of a raise, and
    what it establishes is uncomfortable rather than reassuring: the second
    half below writes a measured year straight into a row and the token route
    hands it back, every byte of it. That is not a defect in the route. The
    route is a lookup, it serves what is stored, and it is pinned to do exactly
    that by `tests/test_advice_api.py`. It is the reason the door in
    `advice.serializers` is the whole of the control. Nothing filters on the
    way out, so anything that reaches the row is readable by whoever the link
    reaches, and a check added at read time later would leave every row written
    before it untouched.

    The write path is where that door stands, and it is exercised against the
    real endpoint in
    `tests/test_advice_api.py::test_the_real_route_refuses_a_measured_series_
    rather_than_storing_it`. Until 2026-08-27 this test could not do that half:
    nothing handed a year to the serializer at all, so it assembled a stored
    row itself and the refusal it checked was reachable from no route.
    """
    own, export, grid = reference_household_year()

    measured = encode_year(own, export, grid, provenance=MEASURED)
    with pytest.raises(MeasuredSeriesRefused):
        year_field(measured)

    stored = StoredAdvice.create(
        inputs={}, advice={"year": year_field(build_year(reference_household_flows()))}
    )
    fetched = APIClient().get(reverse("advice-detail", args=[stored.token]))
    assert fetched.status_code == 200

    served = fetched.json()["year"]
    assert served["provenance"] == SYNTHETIC, (
        "the token route served a series that did not come from a national profile"
    )
    back_own, _back_export, _back_grid = decode_year(
        EncodedYear(
            own=served["own"],
            meter=served["meter"],
            ceilings=served["ceilings"],
            provenance=served["provenance"],
            quarters=served["quarters"],
        )
    )
    assert back_own.shape == own.shape


@pytest.mark.django_db
def test_the_token_route_filters_nothing_which_is_why_the_door_is_at_the_write() -> None:
    """The unpleasant half, asserted rather than assumed.

    A reader could take the test above to mean the token route checks
    provenance. It does not. `StoredAdviceView` reads a row and returns its
    `advice` column, and this writes a measured year into that column without
    going through `year_field` at all, which is precisely what a phase 2
    writer added carelessly would do.

    It is worth a test of its own for two reasons. It says out loud that the
    control is a write-time control, so nobody looks for it on the read side
    and concludes it is missing. And it is what makes the refusal load
    bearing: if the route filtered, a leak would be one bad response, and
    because it does not, a leak is a row that stays readable for ninety days
    by anyone holding the link.
    """
    own, export, grid = reference_household_year()
    smuggled = dataclasses.asdict(encode_year(own, export, grid, provenance=MEASURED))

    stored = StoredAdvice.create(inputs={}, advice={"year": smuggled})
    served = APIClient().get(reverse("advice-detail", args=[stored.token])).json()["year"]

    assert served == smuggled, (
        "the token route no longer serves what is stored verbatim, so the sentence "
        "above about where the control has to sit needs rewriting rather than deleting"
    )
    assert served["provenance"] == MEASURED


def test_the_refusal_is_about_the_token_and_not_about_the_word() -> None:
    """The phase 2 door, so that the check above cannot be read as a ban.

    A measured series is not forbidden. It is forbidden on a payload anybody
    holding a link can open. Saying so with an argument means the phase in
    which a measured series becomes serveable is a decision at a call site,
    which is reviewable, rather than the deletion of a check, which is not.

    Nothing passes False today and the scan below is what keeps that sentence
    true rather than remembered.
    """
    own, export, grid = reference_household_year()
    measured = encode_year(own, export, grid, provenance=MEASURED)

    behind_an_account = year_field(measured, shareable_token=False)
    assert behind_an_account["provenance"] == MEASURED

    passed_false = [
        path.name
        for path in _advice_modules()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.keyword)
        and node.arg == "shareable_token"
        and isinstance(node.value, ast.Constant)
        and node.value.value is False
    ]
    assert not passed_false, (
        f"{sorted(set(passed_false))} switches the shareable token check off. That is the "
        "phase 2 call site, and it needs an account behind it before it is written"
    )


def test_the_serializer_defaults_to_the_safe_reading() -> None:
    """A caller that says nothing gets the refusal, not the exemption.

    Every advice this service stores is reachable by a shareable token, so the
    default has to be the one that assumes it is. A default of False would make
    the control something a caller has to remember to ask for.
    """
    own, export, grid = reference_household_year()
    measured = encode_year(own, export, grid, provenance=MEASURED)

    with pytest.raises(MeasuredSeriesRefused):
        YearSerializer(data=year_field(measured, shareable_token=False)).is_valid(
            raise_exception=True
        )
    assert YearSerializer().shareable_token is True


def test_only_the_two_named_modules_reach_into_the_wire_format() -> None:
    """One door out, kept singular by pinning who may open the format at all.

    `advice.series` holds the packing and the provenance constants;
    `advice.serializers.year_field` is the only function that turns an encoded
    year into the object a response carries, and it is the only place the
    shareability check runs. A third module importing the format directly could
    build that object itself and the check would never see it.

    Judged on the import rather than on a call, for the reason
    `docs/decisions.md` gives for the outbound module: a module that imports the
    format can build the dict on any line added later.
    """
    modules = _advice_modules()
    assert len(modules) >= 15, f"only {len(modules)} modules were read, so this scanned nothing"

    importers = {
        path.name
        for path in modules
        if _imports_the_wire_format(ast.parse(path.read_text(encoding="utf-8")))
    }
    assert importers == SERIES_IMPORTERS, (
        f"advice.series is imported by {sorted(importers)}, and the door out of the wire "
        f"format is only singular while that set is {sorted(SERIES_IMPORTERS)}"
    )


def test_the_encoded_year_carries_no_second_way_out() -> None:
    """No convenience beside the data that skips the door.

    An `as_dict` on the dataclass would produce the wire object without ever
    reaching the provenance check, and it is exactly the method somebody adds
    while wiring the field up. The five names below are the fields themselves.
    """
    fields = {field.name for field in dataclasses.fields(EncodedYear)}
    assert fields == WIRE_KEYS, (
        f"the encoded year no longer carries the wire keys: {sorted(fields)}"
    )

    extras = {name for name in dir(EncodedYear) if not name.startswith("_")} - fields
    assert not extras, (
        f"EncodedYear now offers {sorted(extras)} beside its fields, which is a way to "
        "build the wire object without passing the shareability check"
    )


def test_the_refusal_is_a_programming_fault_and_not_a_bad_request() -> None:
    """Which exception, and why it matters that it is not a validation error.

    Nothing a stranger posts chooses a provenance. If this ever fires it is
    server code pairing a measured series with a shareable token, and that
    should read as a fault rather than as a 400 telling a visitor their form
    was wrong.
    """
    assert issubclass(MeasuredSeriesRefused, ValueError)
    assert not issubclass(MeasuredSeriesRefused, drf_serializers.ValidationError)
