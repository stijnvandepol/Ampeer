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

from typing import Any

import pytest

from advice.serializers import EstimateInputSerializer, RefineInputSerializer

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


def test_a_fractional_azimuth_is_rounded_too() -> None:
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"azimuth_deg": -12.4})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["azimuth_deg"] == -12
    assert isinstance(serializer.validated_data["azimuth_deg"], int)


def test_rounding_happens_before_the_bound_and_not_instead_of_it() -> None:
    """Rounding must not become a way past the range check: 90.6 degrees still
    lands outside the range the PV model accepts."""
    serializer = EstimateInputSerializer(data=VALID_ESTIMATE | {"tilt_deg": 90.6})
    assert not serializer.is_valid()
    assert "tilt_deg" in serializer.errors


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
