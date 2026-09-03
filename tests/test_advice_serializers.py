"""Validation is the boundary between a stranger's JSON and the model.

Two properties matter more than any individual rule. Unknown fields are
refused rather than ignored, so nothing can be smuggled into the stored record.
And every numeric field has an upper bound, because an unbounded number here is
not a wrong answer, it is a way to make the server compute for a long time.

Nothing here touches the database. Validation is a pure function of the payload,
and a test that opens a connection to prove it would be slower and more fragile
for no extra evidence.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

import advice.nl
import advice.serializers
import ampeer_advice.nl
from advice.nl import TEMPLATED_MESSAGES, VALIDATION_MESSAGES, message_for
from advice.serializers import (
    AZIMUTH_BUCKET_DEG,
    MAX_AZIMUTH_DEG,
    MAX_POSTCODE4,
    MAX_TILT_DEG,
    MIN_AZIMUTH_DEG,
    MIN_POSTCODE4,
    MIN_TILT_DEG,
    TILT_BUCKET_DEG,
    EstimateInputSerializer,
    RefineInputSerializer,
    bucket_azimuth,
    bucket_tilt,
)
from ampeer_sim.production.pvgis import PvgisProvider

VALID_ESTIMATE: dict[str, Any] = {
    "postcode4": "5401",
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "annual_consumption_kwh": 3500,
}

VALID_REFINE: dict[str, Any] = VALID_ESTIMATE | {
    "daytime_occupancy": True,
    "has_ev": True,
    # The plan drafted this as "IMMEDIATE", which is not a member of
    # EVChargingBehaviour. The enum has NIGHT, ARRIVAL and SOLAR.
    "ev_behaviour": "ARRIVAL",
    "has_heat_pump": False,
    "heat_demand_kwh": None,
    "dynamic_contract": False,
    "has_battery": False,
    "battery_capacity_kwh": None,
}


def test_a_complete_estimate_validates() -> None:
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["postcode4"] == "5401"


def test_the_two_rounds_declare_how_many_questions_they_asked() -> None:
    """The confidence label is derived from this count, and nothing else can
    derive it: a frozen dataclass cannot tell 'nobody is home' apart from the
    default that says the same thing. Round one asks four questions and yields
    five values, because orientation and tilt are one question about one roof."""
    assert EstimateInputSerializer.QUESTION_COUNT == 4
    assert RefineInputSerializer.QUESTION_COUNT == 9


@pytest.mark.parametrize(
    "postcode",
    [
        "540",
        "54011",
        "54O1",
        "",
        "1234 AB",
        " 5401",
        # `$` in a Python regex also matches just before a trailing newline, so
        # a pattern anchored with it would accept this. `\Z` does not.
        "5401\n",
        # `\d` matches every Unicode decimal digit, including these Arabic-Indic
        # ones, and str.isdigit() agrees, so the domain type would not catch it
        # either. A postcode column holding non-ASCII digits is a postcode
        # column nobody can group by.
        "٥٤٠١",
    ],
)
def test_a_postcode_that_is_not_four_digits_is_refused(postcode: str) -> None:
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"postcode4": postcode})
    assert not serializer.is_valid()
    assert "postcode4" in serializer.errors


@pytest.mark.parametrize("postcode", ["0000", "0999"])
def test_a_four_digit_number_that_is_not_a_dutch_postcode_is_refused(postcode: str) -> None:
    """Dutch postcodes start at 1000, so these have the shape without being one.

    Left in, the value reaches postcode4_to_latlon, which answers an unknown two
    digit prefix with a default centroid rather than an error. The household
    would then be advised on the weather of a place that does not exist, and
    nothing in the system would report anything wrong.
    """
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"postcode4": postcode})
    assert not serializer.is_valid()
    assert "postcode4" in serializer.errors


def test_a_full_postcode_cannot_be_submitted() -> None:
    """Storing six characters instead of four changes what this table is:
    four digits is a neighbourhood, six is a street."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"postcode4": "5401AB"})
    assert not serializer.is_valid()


def test_an_unknown_field_is_refused_rather_than_ignored() -> None:
    """DRF drops unknown keys by default. Dropping them silently means a caller
    can send `email` forever and believe it is stored, and it means a typo in a
    real field name is accepted as an omission."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"email": "a@b.nl"})
    assert not serializer.is_valid()
    assert "email" in str(serializer.errors)


def test_the_second_round_refuses_unknown_fields_too() -> None:
    """Strictness is inherited, not re-declared. The round that carries five
    more answers is the one with more to smuggle into."""
    serializer = RefineInputSerializer(data=VALID_REFINE | {"email": "a@b.nl"})
    assert not serializer.is_valid()
    assert "email" in str(serializer.errors)


def test_a_missing_answer_is_refused_rather_than_defaulted() -> None:
    """A default for a question that was asked is an invented input."""
    incomplete = {key: value for key, value in VALID_ESTIMATE.items() if key != "peak_power_wp"}
    serializer = EstimateInputSerializer(data=incomplete)
    assert not serializer.is_valid()
    assert "peak_power_wp" in serializer.errors


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("peak_power_wp", 0),
        ("peak_power_wp", -1000),
        ("peak_power_wp", 10_000_000),
        ("annual_consumption_kwh", -1.0),
        ("annual_consumption_kwh", 0.0),
        ("annual_consumption_kwh", 10_000_000.0),
        ("tilt_deg", -1),
        ("tilt_deg", 91),
        ("azimuth_deg", -181),
        ("azimuth_deg", 181),
    ],
)
def test_every_number_is_bounded_on_both_sides(field: str, value: float) -> None:
    """An unbounded input is not a wrong answer, it is a way to make the server
    work. A 10 MWp array is 243 simulations of a power station."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {field: value})
    assert not serializer.is_valid(), f"{field}={value} was accepted"
    assert field in serializer.errors


def test_a_fractional_roof_angle_is_rounded_to_a_whole_degree() -> None:
    """One value flows into the cache key, the PVGIS call and the PVSystem.
    Rounding anywhere else would mean the cached series describes a slightly
    different roof than the simulation assumes."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"tilt_deg": 34.6})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["tilt_deg"] == 35
    assert isinstance(serializer.validated_data["tilt_deg"], int)


def test_a_fractional_azimuth_is_rounded_and_then_grouped() -> None:
    """-12.4 was -12 until the grouping landed, and is -15 now.

    Both steps are visible in that one number and they stay separate steps: the
    round is what keeps a float out of the cache key, and the group is what
    keeps the key space walkable. The value is still an int, which is what the
    SmallIntegerField columns of ProductionCache require.
    """
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"azimuth_deg": -12.4})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["azimuth_deg"] == -15
    assert isinstance(serializer.validated_data["azimuth_deg"], int)


def test_rounding_happens_before_the_bound_and_not_instead_of_it() -> None:
    """Rounding must not become a way past the range check: 90.6 degrees still
    lands outside the range the PV model accepts."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"tilt_deg": 90.6})
    assert not serializer.is_valid()
    assert "tilt_deg" in serializer.errors


# --------------------------------------------------------------------------
# The size of the ProductionCache key, which is a question about the three
# gunicorn workers rather than about disk.
# --------------------------------------------------------------------------

#: Read out of the provider rather than typed here, because it is the number
#: that turns a cache miss into an occupied worker and it lives in ampeer_sim.
PVGIS_TIMEOUT_S = float(inspect.signature(PvgisProvider.__init__).parameters["timeout_s"].default)

#: infra/entrypoint-api.sh, parsed for the same reason.
ENTRYPOINT = Path(__file__).resolve().parent.parent / "infra" / "entrypoint-api.sh"

#: How long the whole key space may take to walk, measured in hours of the
#: machine's own worst case capacity. Three workers give 72 worker hours a day,
#: so a space under this bound is walked in under a day and a half of
#: everything the service can do, after which every request is a hit and the
#: attack has nothing left to miss on. It is not a storage bound: a hundred
#: thousand rows of 60 kB is not a problem anybody would notice.
MAX_WORKER_HOURS_TO_EXHAUST = 100.0


def _gunicorn_workers() -> int:
    """How many synchronous workers serve the API, read from the entrypoint."""
    found = re.search(r"--workers\s+(\d+)", ENTRYPOINT.read_text(encoding="utf-8"))
    assert found is not None, f"{ENTRYPOINT.name} no longer says how many workers it starts"
    return int(found.group(1))


def _reachable_production_cache_keys() -> int:
    """Every distinct ProductionCache row a stranger's POST body can create.

    Three of the four key columns come out of the request. weather_year is
    fixed by a setting and is therefore one value, not a dimension. The
    postcode column holds a postcode century rather than a postcode, which is
    what ampeer_sim resolves on.
    """
    areas = MAX_POSTCODE4 // 100 - MIN_POSTCODE4 // 100 + 1
    azimuths = {bucket_azimuth(value) for value in range(MIN_AZIMUTH_DEG, MAX_AZIMUTH_DEG + 1)}
    tilts = {bucket_tilt(value) for value in range(MIN_TILT_DEG, MAX_TILT_DEG + 1)}
    return areas * len(azimuths) * len(tilts)


def test_the_production_cache_key_space_can_be_exhausted() -> None:
    """Why the number matters is worker occupancy, and not the disk it sits on.

    ProductionCache stands in front of PVGIS. PvgisProvider's timeout is 20
    seconds and ResilientProductionProvider only reaches the offline fallback
    after it expires, so one miss can hold one gunicorn worker for 20 seconds
    and there are three of them. What decides whether that is an outage or a
    slow morning is not how many rows the table can hold but whether the supply
    of misses runs out. On ungrouped whole degrees it does not: 90 postcode
    areas by 361 azimuths by 91 tilts is 2,956,590 keys, so a caller can name a
    roof nobody has ever named for as long as they care to, and the throttle
    does not help because sustaining three concurrent misses needs about 27
    identities an hour, which is one IPv6 /64.

    Grouping the two angles is what ends that, and it ends it by arithmetic
    rather than by making the attack more expensive. Once the space is small
    enough to be walked, it is walked, and after that every request is a hit.

    This computes the space from the two bucket constants rather than
    restating a number, so the constants and this argument cannot drift apart.
    """
    keys = _reachable_production_cache_keys()
    worker_hours = keys * PVGIS_TIMEOUT_S / _gunicorn_workers() / 3600.0
    assert worker_hours < MAX_WORKER_HOURS_TO_EXHAUST, (
        f"{keys} reachable ProductionCache keys, which is {worker_hours:.0f} hours of the "
        f"whole machine at a {PVGIS_TIMEOUT_S:.0f} second miss. A space that cannot be "
        "walked is a supply of misses that never runs out, and each one holds one of "
        f"{_gunicorn_workers()} workers."
    )


def test_two_roofs_nobody_could_tell_apart_share_one_cache_key() -> None:
    """The behavioural half, so the constant and the code cannot drift.

    38 and 44 degrees is a difference no visitor can measure about their own
    house, and before this grouping it was seven cache rows rather than one.
    """
    serializers_at = [
        EstimateInputSerializer(data=VALID_ESTIMATE | {"azimuth_deg": azimuth})
        for azimuth in (38, 44)
    ]
    for serializer in serializers_at:
        assert serializer.is_valid(), serializer.errors
    grouped = {serializer.validated_data["azimuth_deg"] for serializer in serializers_at}
    assert grouped == {45}, grouped


def test_the_seam_between_two_azimuth_buckets_is_where_it_is_declared() -> None:
    """Grouping is to the nearest multiple, not down to the one below.

    Nearest halves the worst error a household is advised on, from a whole
    bucket to half of one, and it leaves every compass direction the form can
    send exactly where it was. It also means the seam sits half a bucket up:
    37 and 38 degrees are on opposite sides of it, which is the honest place
    for a boundary test to look.
    """
    assert bucket_azimuth(37) == 30
    assert bucket_azimuth(38) == 45


@pytest.mark.parametrize(
    ("sent", "expected"),
    [
        # North, named from both ends of the range, is one key and not two.
        (MIN_AZIMUTH_DEG, MAX_AZIMUTH_DEG),
        (MAX_AZIMUTH_DEG, MAX_AZIMUTH_DEG),
        (-173, MAX_AZIMUTH_DEG),
        (173, MAX_AZIMUTH_DEG),
        # South is exact and stays exact.
        (0, 0),
        # The far side of the seam is an ordinary bucket again.
        (-172, -165),
        (172, 165),
    ],
)
def test_the_compass_has_no_seam_where_the_range_has_two_ends(sent: int, expected: int) -> None:
    """-180 and 180 are the same direction and must not be two rows.

    ampeer_sim already knows this: FallbackProvider._azimuth_gap measures round
    the circle precisely so the two are not read as opposites. A cache key
    compares for equality and cannot, so the fold happens here. The positive
    end is the one kept because that is the value RoofPicker.tsx sends for
    north.
    """
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"azimuth_deg": sent})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["azimuth_deg"] == expected


@pytest.mark.parametrize(
    ("sent", "expected"),
    [(MIN_TILT_DEG, 0), (MAX_TILT_DEG, 90), (2, 0), (3, 5), (88, 90)],
)
def test_a_tilt_is_grouped_and_stays_inside_the_range(sent: int, expected: int) -> None:
    """Flat and vertical are the two ends of a roof, and neither wraps.

    Both ends are already multiples of the bucket, so grouping cannot push a
    value out of the range the PV model accepts, which is what would otherwise
    make this a second bounds check.
    """
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"tilt_deg": sent})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["tilt_deg"] == expected
    assert MIN_TILT_DEG <= serializer.validated_data["tilt_deg"] <= MAX_TILT_DEG


def test_grouping_is_stable_rather_than_decided_by_the_last_bits_of_a_float() -> None:
    """A value that lands in two buckets on two runs is two rows for one roof.

    The check is that every reachable value is a fixed point of its own bucket:
    grouping a grouped value returns it. That is the property a float division
    cannot promise and integer arithmetic can.
    """
    for value in range(MIN_AZIMUTH_DEG, MAX_AZIMUTH_DEG + 1):
        once = bucket_azimuth(value)
        assert bucket_azimuth(once) == once, value
        assert once % AZIMUTH_BUCKET_DEG == 0, value
    for value in range(MIN_TILT_DEG, MAX_TILT_DEG + 1):
        once = bucket_tilt(value)
        assert bucket_tilt(once) == once, value
        assert once % TILT_BUCKET_DEG == 0, value


def test_a_complete_refine_validates() -> None:
    serializer = RefineInputSerializer(data=VALID_REFINE)
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("behaviour", ["NIGHT", "ARRIVAL", "SOLAR"])
def test_every_charging_behaviour_the_engine_knows_is_accepted(behaviour: str) -> None:
    """The choice list is derived from the enum rather than copied, so this
    fails the day a member is added and the form is not updated."""
    serializer = RefineInputSerializer(data=VALID_REFINE | {"ev_behaviour": behaviour})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["ev_behaviour"] == behaviour


def test_an_unknown_charging_behaviour_is_refused() -> None:
    serializer = RefineInputSerializer(data=VALID_REFINE | {"ev_behaviour": "WHENEVER"})
    assert not serializer.is_valid()
    assert "ev_behaviour" in serializer.errors


def test_claiming_an_ev_without_saying_when_it_charges_is_refused() -> None:
    """The charging moment is most of the answer for a household with an EV.
    Filling it in with a default would be inventing the input that matters
    most."""
    serializer = RefineInputSerializer(data=VALID_REFINE | {"ev_behaviour": None})
    assert not serializer.is_valid()
    assert "ev_behaviour" in serializer.errors


def test_a_charging_behaviour_without_an_ev_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_ev": False, "ev_behaviour": "NIGHT"}
    )
    assert not serializer.is_valid()
    assert "ev_behaviour" in serializer.errors


def test_a_household_without_an_ev_validates() -> None:
    serializer = RefineInputSerializer(data=VALID_REFINE | {"has_ev": False, "ev_behaviour": None})
    assert serializer.is_valid(), serializer.errors


def test_claiming_a_battery_without_a_capacity_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_battery": True, "battery_capacity_kwh": None}
    )
    assert not serializer.is_valid()
    assert "battery_capacity_kwh" in serializer.errors


def test_a_capacity_without_a_battery_is_refused() -> None:
    """Two fields that contradict each other must not both be stored: whichever
    one the assembly happens to read decides the answer."""
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_battery": False, "battery_capacity_kwh": 10.0}
    )
    assert not serializer.is_valid()
    assert "battery_capacity_kwh" in serializer.errors


def test_claiming_a_heat_pump_without_a_heat_demand_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_heat_pump": True, "heat_demand_kwh": None}
    )
    assert not serializer.is_valid()
    assert "heat_demand_kwh" in serializer.errors


def test_a_heat_demand_without_a_heat_pump_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_heat_pump": False, "heat_demand_kwh": 8_000.0}
    )
    assert not serializer.is_valid()
    assert "heat_demand_kwh" in serializer.errors


def test_a_battery_larger_than_any_home_battery_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_battery": True, "battery_capacity_kwh": 5_000.0}
    )
    assert not serializer.is_valid()
    assert "battery_capacity_kwh" in serializer.errors


def test_a_heat_demand_above_the_safety_bound_is_refused() -> None:
    serializer = RefineInputSerializer(
        data=VALID_REFINE | {"has_heat_pump": True, "heat_demand_kwh": 5_000_000.0}
    )
    assert not serializer.is_valid()
    assert "heat_demand_kwh" in serializer.errors


def test_every_contradiction_is_reported_at_once() -> None:
    """A form that reveals one problem per round trip trains people to guess.
    All three cross-field rules report together."""
    serializer = RefineInputSerializer(
        data=VALID_REFINE
        | {
            "has_ev": True,
            "ev_behaviour": None,
            "has_heat_pump": True,
            "heat_demand_kwh": None,
            "has_battery": True,
            "battery_capacity_kwh": None,
        }
    )
    assert not serializer.is_valid()
    assert set(serializer.errors) == {"ev_behaviour", "heat_demand_kwh", "battery_capacity_kwh"}


def test_a_payload_that_is_not_an_object_is_refused() -> None:
    """The strict wrapper must not swallow a list or a string on its way to the
    field loop, and it must not crash on one either."""
    serializer = EstimateInputSerializer(data=["5401"])
    assert not serializer.is_valid()


# ---------------------------------------------------------------------------
# The Dutch lives in advice/nl.py, and the rest of the package names it in
# English
# ---------------------------------------------------------------------------

SERIALIZERS_SOURCE = Path(advice.serializers.__file__)
NL_SOURCE = Path(advice.nl.__file__)
ADVICE_PACKAGE = NL_SOURCE.parent


def _advice_modules() -> list[Path]:
    """Every module in the advice package that may not hold Dutch.

    Derived by walking the package rather than listed, which is the whole point
    of this function. Until 2026-08-27 the scan below read one path by name and
    a commit claimed on that evidence that the package held no Dutch. It held
    one more message: ``advice/parsers.py`` refused an over-nested body with a
    Dutch sentence written into the module, and a check reading one file had
    nothing to say about it. A list would have had the same hole, one edit
    later.

    ``nl.py`` is the exception and the only one, because it is the layer the
    Dutch is supposed to be in.
    """
    return [
        path
        for path in sorted(ADVICE_PACKAGE.rglob("*.py"))
        if "__pycache__" not in path.parts and path.name != "nl.py"
    ]


#: Dutch words that are not also English words.
#:
#: A heuristic, and honest about it: a list of words cannot decide what language
#: a string is in, and the message this project would most like to catch is the
#: one written next year in vocabulary nobody thought of. That is what
#: test_the_serializer_module_names_only_ids_fields_and_one_pattern is for. This
#: list exists because it names what it found, which is the difference between a
#: reader fixing the string and a reader going looking for it.
#:
#: Every entry is checked against the English docstrings in the modules the
#: scan below reads, docstrings included: Dutch in a docstring is not a string a
#: visitor reads, but it is the same rule in CLAUDE.md and one grep is cheaper
#: than two. Words that exist in both languages are left out on purpose, "of"
#: and "die" and "met" among them, because a false positive here would be a red
#: build over an English sentence.
#:
#: "de" and "te" were added on 2026-08-27 and the reason is worth writing down,
#: because it is evidence about what this list is worth. The message that walked
#: past the boundary, "de JSON is te diep genest", contains no word this list
#: held: it has three of the four Dutch articles and not the fourth, so widening
#: the scan to the whole package would have found nothing. Measured over the
#: twenty modules the scan reads: with the two words added and parsers.py fixed,
#: zero literals match, so neither word costs a false positive here today.
#:
#: That is a repair and not a proof of the method. A list of words cannot decide
#: what language a string is in, and the next message to slip past will be
#: written in vocabulary nobody thought of either. What the list is for is
#: naming what it found, so a reader fixes a string instead of going looking for
#: it; the categorical scan below is the half that does not depend on guessing
#: vocabulary, and it reads one module.
DUTCH_MARKERS = frozenset(
    {
        "alleen",
        "de",
        "deze",
        "dit",
        "een",
        "elke",
        "geen",
        "het",
        "hier",
        "jij",
        "jouw",
        "kies",
        "kunt",
        "mag",
        "moet",
        "niet",
        "nog",
        "onbekend",
        "onbekende",
        "ongeldig",
        "ongeldige",
        "te",
        "toegestaan",
        "uw",
        "veld",
        "velden",
        "verplicht",
        "vul",
        "waarde",
        "wanneer",
        "wij",
        "zijn",
    }
)

_WORDS = re.compile(r"[A-Za-zÀ-ÿ]+")

#: What makes a string literal something a person reads.
#:
#: Quoted verbatim in the failure message of the scan below, because a guard
#: whose failure nobody can act on gets deleted, and "this string is not English"
#: is only actionable next to the definition of "this string".
#:
#: The two halves are separable on purpose. Whether a literal is prose is decided
#: by its shape and needs no vocabulary at all. Whether prose is English is
#: decided by ``ENGLISH_PROSE_WORDS``, which is a list of the language that is
#: allowed rather than a list of the language that is not.
PROSE_RULE = (
    "A literal is prose when, after format placeholders are removed, two or more "
    "of its whitespace separated chunks contain a word, where a word is a run of "
    "two or more letters and a chunk holding an underscore or a digit is an "
    "identifier rather than a word. Prose is the shape a person reads; anything "
    "else is a token a machine reads, which is why a field name, a JSON key, a "
    "message id, a URL fragment, a header name, a dotted import path and a regex "
    "all pass without being listed anywhere. Prose outside advice/nl.py has to be "
    "English, and English is decided by ENGLISH_PROSE_WORDS in "
    "tests/test_advice_serializers.py: every word of it has to be in that set. "
    "A Dutch sentence a visitor reads belongs in advice/nl.py behind an English "
    "id. An English sentence an operator or a developer reads belongs where it "
    "is, and costs the words it adds to that set."
)

#: The English the advice package is allowed to speak, word by word.
#:
#: This set is the repair to a guard that had been reported closed twice and
#: falsified twice. On 2026-08-27 a review added
#: ``SERVICE_UNAVAILABLE_MESSAGE = "Aanvraag mislukt, probeer straks opnieuw"``
#: to advice/views.py, ran both scans that existed, and both passed. Two separate
#: holes, and they are the same hole twice: ``DUTCH_MARKERS`` above held none of
#: aanvraag, mislukt, probeer, straks or opnieuw, and it never could have, because
#: a list of the words of the language you are excluding is a guess about what
#: somebody will write next year; and the categorical scan read
#: advice/serializers.py by name, so views.py was not read at all.
#:
#: Inverting the vocabulary is what fixes the shape rather than the instance. The
#: language that is *allowed* in this package is closed and small, because
#: CLAUDE.md sends everything a visitor reads to a language layer and leaves
#: behind only what an operator or a developer reads. Measured on 2026-08-27 over
#: backend/advice: 26 prose literals holding 110 distinct words, and every one of
#: them is SQL, ``manage.py`` output, or an internal error message. A Dutch
#: sentence fails this set whatever words it is written in, and so does an
#: English sentence written for a visitor, which is the same defect wearing the
#: other language.
#:
#: Twenty six of those words arrived while this was being written, from
#: advice/series.py, a module a different branch added the same afternoon. That
#: is the walk in ``_advice_modules`` doing its job and the price being paid in
#: public: a new module is inside this check on the day it lands, and it costs
#: whoever lands it the English it introduces.
#:
#: Derived by running the classifier over the package and then reading all 110,
#: which is the part that keeps it from being circular. An allowlist of the
#: literals found would prove only that the package equals itself, which is the
#: mistake this file has already made twice in another form. An allowlist of
#: words is auditable against a dictionary by anyone, line by line, without
#: reference to this repository, and the test below named for the Dutch the
#: product already speaks calibrates it against Dutch this file neither wrote nor
#: chose: 34 strings out of the two language layers, of which it refuses 31 and
#: reads none as English.
#:
#: The price is one line of diff per new English word, and it is deliberate. It
#: is the same price ``_recognised_literals`` charges below, for the same reason:
#: a string appearing in this package without a reason is worth a line in a
#: review.
ENGLISH_PROSE_WORDS = frozenset(
    {
        "advice",
        "advices",
        "ago",
        "an",
        "and",
        "answer",
        "append",
        "as",
        "assumes",
        "at",
        "audit",
        "battery",
        "be",
        "been",
        "both",
        # 2026-09-01, from purge_expired_advice.py reporting the third table it
        # now sweeps. This is the one line of diff per new English word that the
        # note above says is the price, paid.
        "cache",
        "cannot",
        "consumption",
        "container",
        "counter",
        "day",
        "delete",
        "deleted",
        "deleting",
        "directions",
        "drop",
        "exactly",
        "exists",
        "exit",
        "expected",
        "expired",
        "expires",
        "expiry",
        "file",
        "from",
        "got",
        "has",
        "have",
        "healthcheck",
        "here",
        "hold",
        "host",
        "if",
        "instead",
        "invented",
        "is",
        "its",
        "length",
        "log",
        "may",
        "more",
        "must",
        "name",
        "needs",
        "no",
        "non",
        "not",
        "of",
        "oldest",
        "on",
        "once",
        "one",
        "only",
        "or",
        "over",
        "overdue",
        "packing",
        "passed",
        "past",
        "period",
        "private",
        # 2026-09-01, same line and same reason as "cache" above.
        "production",
        "profile",
        "provenance",
        "purge",
        "purged",
        "quarter",
        "quarters",
        "readable",
        "refusing",
        "report",
        "retention",
        "row",
        "rows",
        "running",
        "same",
        "series",
        "served",
        "set",
        "shareable",
        "shortfall",
        "storage",
        "store",
        "stored",
        "surplus",
        "table",
        "than",
        "the",
        "them",
        "three",
        "throttle",
        "timer",
        "to",
        "token",
        "unknown",
        "unrecognised",
        "updated",
        "used",
        "verdict",
        "where",
        "which",
        "whose",
        "with",
        "year",
        "zero",
    }
)

#: ``{count}`` and ``%s`` are the caller's value, not the author's word.
_PROSE_PLACEHOLDER = re.compile(r"\{[^{}]*\}|%[0-9.]*[a-z]")

#: A word: two or more letters, in any alphabet, with no digit and no underscore.
_PROSE_WORD = re.compile(r"[^\W\d_]{2,}")


def _prose_words(text: str) -> list[str]:
    """The words of a literal, or nothing at all if it is not prose.

    ``PROSE_RULE`` above is the prose half of this function in words. Returning
    an empty list for a token rather than raising or flagging is what lets the
    scan below run over every literal in the package without an allowlist: the
    forty-five JSON keys of rendering.py, the field names of the migrations and
    the message ids of the serializers are all one chunk each and answer here
    with nothing. That is the answer to the objection in docs/decisions.md
    entry 18, which is why the categorical scan stayed on one file: an allowlist
    wide enough for those was said to be wide enough for a Dutch sentence. True
    of an allowlist of strings and false of a rule about shape, because a JSON
    key is one chunk and a sentence is not.
    """
    chunks: list[list[str]] = []
    for chunk in _PROSE_PLACEHOLDER.sub(" ", text).split():
        if "_" in chunk or any(char.isdigit() for char in chunk):
            continue
        found = [word.lower() for word in _PROSE_WORD.findall(chunk)]
        if found:
            chunks.append(found)
    if len(chunks) < 2:
        return []
    return [word for chunk in chunks for word in chunk]


def _words_that_are_not_english(text: str) -> list[str]:
    """The words of one literal that are not in ``ENGLISH_PROSE_WORDS``.

    Empty for a token, since a token has no words. So this answers the whole
    question in one place: a literal is a defect exactly when this is non-empty.
    """
    return sorted({word for word in _prose_words(text) if word not in ENGLISH_PROSE_WORDS})


def _foreign_prose(tree: ast.Module) -> dict[str, list[str]]:
    """Every literal that reads as prose and holds a word that is not English.

    Docstrings are out of scope and the line is drawn where the rule is: a
    docstring is prose a developer reads and is under the same CLAUDE.md rule,
    but holding it to a closed vocabulary would mean listing the English of
    every explanation in the package, which is thousands of words and a set
    nobody could audit. Docstrings and comments are covered by the raw text scan
    in tests/test_advise.py, which reads the file rather than the syntax tree.
    What this function reads is the strings the program hands out.
    """
    offenders: dict[str, list[str]] = {}
    for text in _string_literals(tree, with_docstrings=False):
        unknown = _words_that_are_not_english(text)
        if unknown:
            offenders[text] = unknown
    return offenders


def _docstring_node_ids(tree: ast.Module) -> set[int]:
    """The identity of every docstring node, so the scans can tell one apart.

    By identity rather than by value, because a docstring and a message can be
    the same characters and only one of them is a defect.
    """
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _string_literals(tree: ast.Module, *, with_docstrings: bool) -> list[str]:
    skip = set() if with_docstrings else _docstring_node_ids(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def _dutch_literals(tree: ast.Module) -> list[str]:
    """Every string literal in a module that reads as Dutch."""
    return [
        text
        for text in _string_literals(tree, with_docstrings=True)
        if DUTCH_MARKERS & {word.lower() for word in _WORDS.findall(text)}
    ]


def _recognised_literals() -> set[str]:
    """The strings advice/serializers.py is allowed to contain.

    Three kinds and no fourth: a message id from advice.nl, the name of a field
    on one of the two serializers, and the postcode pattern. Read from those
    places rather than typed out, so adding a field does not make this red.
    """
    fields = set(EstimateInputSerializer().fields) | set(RefineInputSerializer().fields)
    return set(VALIDATION_MESSAGES) | fields | {advice.serializers.POSTCODE4_PATTERN}


def _unrecognised_literals(tree: ast.Module) -> list[str]:
    return [
        text
        for text in _string_literals(tree, with_docstrings=False)
        if text not in _recognised_literals()
    ]


def test_no_dutch_prose_is_left_anywhere_in_the_advice_package() -> None:
    """CLAUDE.md: Dutch text never sits hardcoded in the logic.

    Nine messages sat in advice/serializers.py until 2026-08-26, which is
    recorded in docs/decisions.md under what was not decided. They read to a
    stranger who posted a form, so they are as user-facing as an advice
    sentence, and they were interleaved with the rules that decide what is
    refused: the table of three flag-and-detail pairs carried six Dutch
    sentences in the same tuples as the field names.

    Three shapes of this check have now been written and two of them were
    falsified by a review within a day, so the history is the argument for the
    third.

    The first read advice/serializers.py by name and a commit claimed on that
    evidence that the package held no Dutch; advice/parsers.py held
    ``de JSON is te diep genest`` at the time. The second walked the package and
    matched a list of Dutch words; a review added
    ``SERVICE_UNAVAILABLE_MESSAGE = "Aanvraag mislukt, probeer straks opnieuw"``
    to advice/views.py and it passed, because the list held none of those five
    words and because the categorical half was still bound to one named module.

    Both failures are the same mistake in two disguises: a check built out of a
    guess about what somebody will write next. The third shape does not guess.
    It asks what shape a literal has, and then holds the prose to the vocabulary
    of the language that is *allowed* here, which is closed and countable where
    the excluded one is neither. ``PROSE_RULE`` is that rule in words and the
    failure below prints it, because a reader who trips this needs to know
    whether they are being asked to move a string or to add a word.

    The wordlist runs too and its result is reported second. It cannot refute
    anything any more, since a hit is by definition also foreign prose; what it
    still does is say the word "Dutch" out loud when it recognises one, which is
    the difference between a reader fixing a string and a reader wondering what
    the scan wants.
    """
    modules = _advice_modules()
    sources = {path: ast.parse(path.read_text(encoding="utf-8")) for path in modules}

    foreign = {
        path.relative_to(ADVICE_PACKAGE.parent).as_posix(): _foreign_prose(tree)
        for path, tree in sources.items()
        if _foreign_prose(tree)
    }
    named_dutch = {
        path.relative_to(ADVICE_PACKAGE.parent).as_posix(): sorted(set(_dutch_literals(tree)))
        for path, tree in sources.items()
        if _dutch_literals(tree)
    }
    assert not foreign and not named_dutch, (
        "prose in the advice package that is not English:\n  "
        + "\n  ".join(
            f"{path}: {text!r} -> {', '.join(words)}"
            for path, offenders in sorted(foreign.items())
            for text, words in sorted(offenders.items())
        )
        + f"\n\nrecognised as Dutch by DUTCH_MARKERS: {named_dutch or 'none of it'}"
        + f"\n\nThe rule: {PROSE_RULE}"
    )

    # A scan that reads nothing passes. The floor is well under the twenty
    # modules present on 2026-08-27 so that deleting one is not a red build, and
    # well over zero so that a glob that stops matching is.
    assert len(modules) >= 15, f"only {len(modules)} modules were read, so this scanned nothing"

    # Named because these three are the ones the boundary has actually been
    # broken in, and because the exception has to stay exactly one file wide.
    names = {path.name for path in modules}
    assert {"serializers.py", "parsers.py", "views.py"} <= names, (
        f"the scan missed a known module: {names}"
    )
    assert "nl.py" not in names, "the language layer itself is being scanned for Dutch"


def _dutch_the_product_speaks() -> list[str]:
    """Every Dutch string the two language layers hold, read out of them.

    An independent corpus in the only sense that matters here: none of it was
    written for this test, none of it was chosen by this test, and all of it is
    Dutch that a household actually reads. ``ENGLISH_PROSE_WORDS`` was derived
    from the modules it guards, so a check that ran only over those modules
    would be the package agreeing with itself. This is the other side.
    """
    return [
        str(text)
        for table in (
            ampeer_advice.nl.RULE_TEXTS,
            ampeer_advice.nl.ROUTE_TITLES,
            ampeer_advice.nl.SIZING_BASIS_TEXTS,
            ampeer_advice.nl.CONFIDENCE_LABELS,
            ampeer_advice.nl.INPUT_LABELS,
            ampeer_advice.nl.PRODUCTION_SOURCE_TEXTS,
            VALIDATION_MESSAGES,
        )
        for text in table.values()
    ]


def test_the_prose_rule_refuses_the_dutch_the_product_already_speaks() -> None:
    """What the rule can do and where it stops, measured rather than claimed.

    Run on 2026-08-27 over the 34 strings the two language layers hold: 31 are
    refused as prose that is not English, none is read as English, and 3 are not
    prose at all. Those three are ``Indicatief``, ``Goed`` and ``Precies``, the
    confidence labels, and they are one word each.

    That is the honest edge of ``PROSE_RULE`` and it is pinned here so it cannot
    quietly widen. A single word is a token to this scan, because the package is
    full of single words that have to be tokens: forty-five JSON keys, ten
    message ids, every field name in the migrations. One real instance already
    sits inside that edge. advice/apps.py holds ``verbose_name = "Advies"``, one
    Dutch word, and this scan calls it a token. It reaches nobody today because
    ``django.contrib.admin`` is not in ``INSTALLED_APPS``
    (backend/ampeer/settings/base.py, which says so in a comment), so the only
    thing that would render it is not installed. Named here rather than left for
    the next reviewer to find, since an unnamed gap is what the previous two
    rounds of this check were made of.
    """
    corpus = _dutch_the_product_speaks()
    assert len(corpus) >= 30, f"only {len(corpus)} strings were read, so this measured nothing"

    read_as_english = [
        text for text in corpus if _prose_words(text) and not _words_that_are_not_english(text)
    ]
    assert read_as_english == [], (
        "the vocabulary accepts Dutch the product speaks, so it has been widened past "
        f"English: {read_as_english}"
    )

    not_prose = {text for text in corpus if not _prose_words(text)}
    assert not_prose == {"Indicatief", "Goed", "Precies"}, (
        "the set of Dutch strings this rule cannot see has changed. It is meant to be the "
        f"three one word confidence labels and nothing else, and it is now {sorted(not_prose)}"
    )


def test_the_serializer_module_names_only_ids_fields_and_one_pattern() -> None:
    """The categorical half, because a wordlist is a guess about vocabulary.

    Every string literal outside a docstring has to be a message id, a field
    name or the postcode pattern. A message in any language fails this,
    including a one word one that no list of Dutch markers would carry, and so
    does an English sentence being passed to a caller as text.

    The cost is that a genuinely new kind of literal makes this red and has to
    be argued for in `_recognised_literals`. That is the intended price: this
    module turns a stranger's JSON into something the model may see, and a
    string appearing in it without a reason is worth one line of diff.

    This one stays on one file while the wordlist scan above went package wide,
    and the reason is that the allowlist is this module's contract rather than
    the package's. Measured over the twenty modules on 2026-08-27: rendering.py
    holds 45 literals that are JSON keys, purge_expired_advice.py holds SQL
    fragments and English operator output, models.py holds two English database
    constraint messages, and the migrations hold field names. An allowlist wide
    enough to admit all of those would admit a Dutch sentence as well, so
    widening it would trade a check for the appearance of one.
    """
    offenders = _unrecognised_literals(ast.parse(SERIALIZERS_SOURCE.read_text(encoding="utf-8")))
    assert not offenders, (
        "advice/serializers.py holds a string that is not a message id, a field name or "
        "the postcode pattern:\n  " + "\n  ".join(repr(text[:90]) for text in offenders)
    )


def test_both_scans_go_red_on_what_they_were_written_for() -> None:
    """A guard that has never failed is a guard nobody has tested.

    The first source below is the heat pump message exactly as it stood in
    serializers.py before the move, so this asserts the scan would have caught
    the state this test was written to end. The second is why there are two
    scans: "onjuist" is Dutch, is one word, and is not in the marker list,
    which is the shape of message a list of words will always miss. The
    wordlist reports nothing on it and the categorical scan names it.
    """
    moved_back = ast.parse('errors["heat_demand_kwh"] = "verplicht wanneer er een warmtepomp is"')
    assert _dutch_literals(moved_back) == ["verplicht wanneer er een warmtepomp is"]

    smuggled = ast.parse('raise serializers.ValidationError("onjuist")')
    assert _dutch_literals(smuggled) == []
    assert _unrecognised_literals(smuggled) == ["onjuist"]

    # The third source is the message that actually walked past, exactly as it
    # stood in advice/parsers.py until 2026-08-27. It is here because it failed
    # twice over: the scan never read that file, and the marker list held none
    # of its words either, so widening the scan alone would still have reported
    # a clean package. Removing "de" or "te" from DUTCH_MARKERS turns this line
    # red, which is what stops the two words being tidied away as noise.
    walked_past = ast.parse('TOO_DEEPLY_NESTED = "de JSON is te diep genest"')
    assert _dutch_literals(walked_past) == ["de JSON is te diep genest"]


def test_the_prose_scan_goes_red_on_the_sentence_that_falsified_the_last_two() -> None:
    """The line a review added to advice/views.py on 2026-08-27, kept as evidence.

    Both guards that existed passed on it, and neither did so by accident. The
    wordlist held none of its five words, and no wordlist would have: they are
    ordinary Dutch and there is no end to the supply. The categorical scan was
    bound to advice/serializers.py, so views.py was outside it entirely.

    Neither escape is available now, and the three lines below say which is
    which. ``_dutch_literals`` is still blind to it, so this test also records
    that the wordlist is not what closed the boundary. ``_unrecognised_literals``
    is still bound to the serializer's contract and would never have read this
    module. ``_words_that_are_not_english`` names all five, and names them
    without anyone having had to think of them first, which is the whole
    difference between this shape and the two it replaces.
    """
    escaped = "Aanvraag mislukt, probeer straks opnieuw"
    added_to_views = ast.parse(f'SERVICE_UNAVAILABLE_MESSAGE = "{escaped}"')

    assert _dutch_literals(added_to_views) == []
    assert _words_that_are_not_english(escaped) == [
        "aanvraag",
        "mislukt",
        "opnieuw",
        "probeer",
        "straks",
    ]
    assert _foreign_prose(added_to_views) == {
        escaped: ["aanvraag", "mislukt", "opnieuw", "probeer", "straks"]
    }

    # The shapes the falsification round was asked to try, because one sentence
    # is one sentence. A short imperative, a sentence carrying a number, and a
    # two word noun phrase, sharing no word with each other or with the line
    # above. All three were written into advice/views.py, advice/rendering.py
    # and advice/service.py on 2026-08-27, the suite was run red on each, and
    # each file was restored.
    assert _words_that_are_not_english("Probeer straks opnieuw") == [
        "opnieuw",
        "probeer",
        "straks",
    ]
    assert _words_that_are_not_english("Berekening duurt ongeveer 5 seconden") == [
        "berekening",
        "duurt",
        "ongeveer",
        "seconden",
    ]
    assert _words_that_are_not_english("Slimme laadpaal") == ["laadpaal", "slimme"]

    # And the direction that has to stay quiet, or the guard is noise: the
    # English the package already speaks passes, including the SQL and the
    # operator output that decision 18 said an allowlist could never admit
    # without admitting a Dutch sentence with them. Admitting words rather than
    # strings is what makes that false.
    assert _words_that_are_not_english("DROP TABLE IF EXISTS ") == []
    assert _words_that_are_not_english(" day(s) past its expiry") == []
    assert _words_that_are_not_english("a battery advice needs exactly one storage verdict") == []


def _imports_the_language_layer(tree: ast.Module) -> bool:
    """Whether a module reads advice.nl, judged on its imports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "advice.nl":
            return True
        if isinstance(node, ast.Import) and any(alias.name == "advice.nl" for alias in node.names):
            return True
    return False


def test_every_message_id_the_package_names_has_dutch_and_the_other_way_round() -> None:
    """The pairing that makes the id table checkable, in both directions.

    An id named in the logic with no entry in advice/nl.py raises KeyError while
    answering a request, which reaches a visitor as a 500 where they asked for a
    validation error. An entry nothing names is Dutch nobody reads, which is the
    state a language layer decays into.

    The ids are read out of the source rather than listed here, because six of
    the ten reach `message_for` through a loop variable and a scan for
    `message_for("...")` call sites would silently cover four.

    Which sources are read is decided by the imports, not by a path. Every
    module that imports advice.nl is one whose upper case string literals have
    to be message ids, so advice/parsers.py joined this test on 2026-08-27 by
    importing the layer rather than by being named here, and a third module will
    join it the same way. That is also what keeps the heuristic safe: the
    package holds upper case literals that are not ids at all, "BATTERY_C_RATE"
    in assembly.py and "ADVICE_GENERATED" in models.py among them, and neither
    module reads the language layer.
    """
    sources = {
        path: tree
        for path, tree in (
            (path, ast.parse(path.read_text(encoding="utf-8"))) for path in _advice_modules()
        )
        if _imports_the_language_layer(tree)
    }
    # A floor rather than an equality, so a third module joins by importing the
    # layer and is held to the same rule on its first commit. A module dropping
    # out is the direction worth refusing: it means ids are named somewhere this
    # test no longer reads.
    assert {"serializers.py", "parsers.py"} <= {path.name for path in sources}, (
        f"a module stopped reading advice.nl: {sorted(path.name for path in sources)}"
    )

    named = {
        text
        for tree in sources.values()
        for text in _string_literals(tree, with_docstrings=False)
        if text.isidentifier() and text.isupper()
    }
    assert named == set(VALIDATION_MESSAGES), (
        "the advice package names "
        f"{sorted(named - set(VALIDATION_MESSAGES))} without a Dutch message, and "
        f"advice/nl.py holds {sorted(set(VALIDATION_MESSAGES) - named)} that nothing names"
    )


def test_an_unknown_message_id_refuses_rather_than_falling_back() -> None:
    """A fallback to the id would answer a stranger with an English constant in
    a field where the frontend prints Dutch, and nothing would report it."""
    with pytest.raises(KeyError, match="no Dutch validation message"):
        message_for("NO_SUCH_MESSAGE")


def test_only_the_declared_message_carries_a_value() -> None:
    """`message_for` formats, so a placeholder is a promise the caller must keep.

    A template whose caller forgets its value raises inside str.format while a
    request is being answered, so the failure lands on a visitor rather than on
    a build. Pinning the set of templates against the placeholders actually
    written in the table is what keeps that from being introduced by a reword.
    """
    templated = {
        message_id
        for message_id, text in VALIDATION_MESSAGES.items()
        if re.search(r"\{[a-z_]*\}", text)
    }
    assert templated == set(TEMPLATED_MESSAGES)
    assert message_for("MORE_UNKNOWN_FIELDS", count=40) == "en nog 40 onbekende velden"


def test_no_validation_message_addresses_the_household() -> None:
    """The register decision does not reach this file, so this holds the line.

    docs/decisions.md entry 1 fixes the product on "u", and the scan that keeps
    it that way lives in tests/test_advice_nl.py and reads ampeer_advice/nl.py
    by path. It does not see advice/nl.py, so a validation message written in
    "je" would be green there and would sit next to an advice written in "u".

    None of these messages speaks to anybody: they name a field and say what is
    wrong with it. Keeping it that way is cheaper than keeping a second copy of
    the register constant in step with the first, and it fails loudly on the
    first message that does address a reader, which is the moment somebody has
    to decide whether this file joins that decision.
    """
    tree = ast.parse(NL_SOURCE.read_text(encoding="utf-8"))
    second_person = re.compile(r"(?<![A-Za-zÀ-ÿ])(u|uw|uzelf|je|jij|jouw|jezelf)(?![A-Za-zÀ-ÿ])")
    offenders = [text for text in VALIDATION_MESSAGES.values() if second_person.search(text)]
    assert not offenders, (
        "a validation message addresses the household:\n  "
        + "\n  ".join(repr(text) for text in offenders)
        + "\nThat makes it part of the register decision in docs/decisions.md, which "
        "tests/test_advice_nl.py enforces on ampeer_advice/nl.py only."
    )
    assert VALIDATION_MESSAGES, "the table is empty, so the assertion above read nothing"
    assert set(VALIDATION_MESSAGES.values()) <= set(
        _string_literals(tree, with_docstrings=False)
    ), "advice/nl.py holds messages this test cannot see in its source"


def _message(errors: dict[str, Any], field: str) -> str:
    """One error as the client receives it, whether DRF wrapped it in a list."""
    value = errors[field]
    return str(value[0] if isinstance(value, list) else value)


@pytest.mark.parametrize(
    ("payload", "field", "expected"),
    [
        (VALID_ESTIMATE | {"postcode4": "0999"}, "postcode4", "geen Nederlandse postcode"),
        (VALID_ESTIMATE | {"colour": "groen"}, "colour", "onbekend veld"),
        (
            VALID_REFINE | {"has_ev": True, "ev_behaviour": None},
            "ev_behaviour",
            "verplicht wanneer er een elektrische auto is",
        ),
        (
            VALID_REFINE | {"has_ev": False, "ev_behaviour": "NIGHT"},
            "ev_behaviour",
            "alleen toegestaan met een elektrische auto",
        ),
        (
            VALID_REFINE | {"has_heat_pump": True, "heat_demand_kwh": None},
            "heat_demand_kwh",
            "verplicht wanneer er een warmtepomp is",
        ),
        (
            VALID_REFINE | {"has_heat_pump": False, "heat_demand_kwh": 8_000.0},
            "heat_demand_kwh",
            "alleen toegestaan met een warmtepomp",
        ),
        (
            VALID_REFINE | {"has_battery": True, "battery_capacity_kwh": None},
            "battery_capacity_kwh",
            "verplicht wanneer er een thuisbatterij is",
        ),
        (
            VALID_REFINE | {"has_battery": False, "battery_capacity_kwh": 10.0},
            "battery_capacity_kwh",
            "alleen toegestaan met een thuisbatterij",
        ),
    ],
)
def test_the_words_a_visitor_reads_survived_the_move(
    payload: dict[str, Any], field: str, expected: str
) -> None:
    """Byte for byte, through the serializer rather than out of the table.

    Moving text is only safe if it arrives unchanged, and the table on its own
    cannot show that: an id typed wrongly at one call site swaps two messages
    while both tables stay correct. So this reads the error the way a client
    does. Three of these strings are asserted verbatim in frontend/tests and
    one more in tests/test_advice_api.py, which is the other half of the same
    guarantee.
    """
    serializer: EstimateInputSerializer
    serializer = (
        RefineInputSerializer(data=payload)
        if "has_ev" in payload
        else EstimateInputSerializer(data=payload)
    )
    assert not serializer.is_valid()
    assert _message(dict(serializer.errors), field) == expected


def test_the_over_nested_body_still_reads_the_same_to_a_caller() -> None:
    """The tenth message, pinned through the parser rather than the table.

    advice/parsers.py held this sentence as a module constant until 2026-08-27.
    The relocation is only safe if the sentence arrives unchanged, and reading
    it back out of VALIDATION_MESSAGES would prove nothing about the call site:
    an id typed wrongly there answers a caller with a different message while
    both tables stay correct.

    So this drives the parser the way DRF does and reads the detail the way a
    client does. tests/test_advice_api.py asserts the same refusal over HTTP,
    which is the other half: that one shows a visitor gets a 400, this one shows
    which words the 400 carries.
    """
    from io import BytesIO

    from rest_framework.exceptions import ParseError

    from advice.parsers import BoundedJSONParser

    with pytest.raises(ParseError) as raised:
        BoundedJSONParser().parse(BytesIO(b"[" * 200_000))
    assert str(raised.value.detail) == "de JSON is te diep genest"


def test_the_overflow_count_is_still_a_sentence_with_a_number_in_it() -> None:
    """The one message that carries a value, checked where it is assembled.

    tests/test_advice_api.py pins this string at 40 unknown fields over HTTP.
    Here it is pinned at the serializer, because the number is now substituted
    in advice/nl.py and the call site passes it by keyword, so a rename of that
    keyword would fail in front of a visitor with a KeyError from str.format.
    """
    from rest_framework.settings import api_settings

    unknown = {f"field_{index}": index for index in range(15)}
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | unknown)
    assert not serializer.is_valid()
    assert _message(dict(serializer.errors), api_settings.NON_FIELD_ERRORS_KEY) == (
        "en nog 5 onbekende velden"
    )
