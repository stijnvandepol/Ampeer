"""Where a stranger's JSON becomes something the model may see.

Two rules run through everything below. Unknown fields are refused rather than
dropped, because a silently ignored field means a caller can send an email
address forever and believe it was stored, and a typo in a real field name reads
as an omission. And every number is bounded on both sides, because an unbounded
number is not a wrong answer but a way to make the server compute.

No Dutch is written here. The messages this module refuses with are validation
messages rather than advice, so they cannot live in ``ampeer_advice.nl``, which
must not know an HTTP form exists; they live in ``advice.nl`` instead, keyed by
an English id, and this file names the id. Until 2026-08-26 they were typed out
below, which put nine sentences a stranger reads inside the rules that decide
what is refused. tests/test_advice_serializers.py fails if one comes back.

One thing here runs the other way. ``year_field`` at the bottom validates what
this service is about to send rather than what it just received, and it is the
only function that turns an ``advice.series.EncodedYear`` into the object the
response carries. It is a serializer and not a dict literal for two reasons:
the published contract the frontend builds against is then declared in one
place rather than described in a comment, and the rule that a measured
quarter-hour series may not leave over a shareable token has somewhere to sit
that every producer has to pass.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar

from rest_framework import serializers
from rest_framework.settings import api_settings

from advice.nl import message_for
from advice.series import (
    PROVENANCE,
    PROVENANCE_KEY,
    QUARTERS_PER_YEAR,
    EncodedYear,
    refuse_unless_shareable,
)
from ampeer_sim.types import EVChargingBehaviour

# The four maxima below are safety bounds and nothing else: wide enough that no
# real household is refused, narrow enough that one request cannot occupy the
# machine. A single advice runs a 243-cell sensitivity grid, so the cost of a
# request scales with the array and the demand it describes. None of these
# numbers is a claim about what Dutch households own and none should be read as
# one; the honest statement is only that no plausible dwelling comes near them.

#: ampeer_sim.types.PVSystem refuses anything above 50_000 Wp outright, so this
#: sits under the domain limit rather than restating it.
MAX_PEAK_POWER_WP = 30_000
MAX_ANNUAL_CONSUMPTION_KWH = 50_000.0
MAX_HEAT_DEMAND_KWH = 40_000.0
MAX_BATTERY_CAPACITY_KWH = 100.0

# The minima come from the domain types, which raise rather than return a wrong
# number. PVSystem requires peak_power_wp > 0, Household requires
# annual_consumption_kwh > 0 and BatterySpec requires capacity_kwh > 0. DRF's
# min_value is inclusive, so each floor sits just above zero.
MIN_PEAK_POWER_WP = 1
MIN_ANNUAL_CONSUMPTION_KWH = 1.0
MIN_HEAT_DEMAND_KWH = 1.0
MIN_BATTERY_CAPACITY_KWH = 0.5

# Copied from PVSystem.__post_init__, which raises outside these ranges. Zero is
# south, negative is east, positive is west, matching PVGIS and ampeer_sim.
MIN_AZIMUTH_DEG = -180
MAX_AZIMUTH_DEG = 180
MIN_TILT_DEG = 0
MAX_TILT_DEG = 90

#: Four ASCII digits, anchored with ``\Z`` rather than ``$``. ``$`` also matches
#: just before a trailing newline, and ``\d`` matches every Unicode decimal
#: digit, which ``str.isdigit()`` in Household would accept as well. Neither
#: belongs in a column that is grouped by neighbourhood.
POSTCODE4_PATTERN = r"^[0-9]{4}\Z"

#: Dutch postcodes start at 1000. Four digits is a shape, not a place, and the
#: pattern above cannot tell the two apart: "0123" has the shape and is not a
#: postcode. Left unchecked it reaches ampeer_sim.production.pvgis, whose
#: postcode4_to_latlon falls back to a default centroid for an unrecognised two
#: digit prefix, so the household would be advised on the weather of somewhere
#: it does not live, with nothing anywhere reporting a problem.
MIN_POSTCODE4 = 1000
MAX_POSTCODE4 = 9999

#: Rounded to whole degrees, here and nowhere else, so one value reaches the
#: cache key, the PVGIS call and the PVSystem. A float in a cache key means a
#: hit computed for a slightly different roof than the simulation then assumes,
#: and nobody knows their roof angle to better than a degree anyway.
_ROUNDED_TO_WHOLE_DEGREES = ("azimuth_deg", "tilt_deg")


#: How many unknown field names one error response repeats back. Naming the
#: offending field is the whole point of refusing rather than dropping it, and
#: ten is more than a form with nine fields can plausibly get wrong at once. The
#: cap exists because the list came from the request: a body of one megabyte of
#: distinct keys was echoed back in full as roughly two and a half megabytes of
#: JSON, so the endpoint amplified whatever a caller sent it.
MAX_REPORTED_UNKNOWN_FIELDS = 10


class StrictSerializer(serializers.Serializer[dict[str, Any]]):
    """A serializer that refuses what it does not recognise."""

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            unknown = sorted(set(data) - set(self.fields))
            if unknown:
                errors: dict[str, Any] = {
                    name: message_for("UNKNOWN_FIELD")
                    for name in unknown[:MAX_REPORTED_UNKNOWN_FIELDS]
                }
                remaining = len(unknown) - MAX_REPORTED_UNKNOWN_FIELDS
                if remaining > 0:
                    # Under DRF's own key for an error that belongs to the body
                    # rather than to one field, so a client that walks the
                    # response per field never mistakes the count for one.
                    errors[api_settings.NON_FIELD_ERRORS_KEY] = [
                        message_for("MORE_UNKNOWN_FIELDS", count=remaining)
                    ]
                raise serializers.ValidationError(errors)
        validated: dict[str, Any] = super().to_internal_value(data)
        return validated


class EstimateInputSerializer(StrictSerializer):
    """Round one: four questions, five values.

    Orientation and tilt are one question about one roof, which is why the
    question count below is four and not five. That count decides the
    confidence label, so it is a property of the form and not of this class's
    field list.
    """

    QUESTION_COUNT: ClassVar[int] = 4

    # trim_whitespace defaults to True on every DRF CharField, and it runs
    # before the validators, so " 5401" and "5401\n" would reach the regex as
    # "5401" and be accepted. What lands in the column should be what the caller
    # sent, so the trimming is off and the pattern decides alone.
    postcode4 = serializers.RegexField(POSTCODE4_PATTERN, trim_whitespace=False)
    peak_power_wp = serializers.IntegerField(
        min_value=MIN_PEAK_POWER_WP, max_value=MAX_PEAK_POWER_WP
    )
    azimuth_deg = serializers.IntegerField(min_value=MIN_AZIMUTH_DEG, max_value=MAX_AZIMUTH_DEG)
    tilt_deg = serializers.IntegerField(min_value=MIN_TILT_DEG, max_value=MAX_TILT_DEG)
    annual_consumption_kwh = serializers.FloatField(
        min_value=MIN_ANNUAL_CONSUMPTION_KWH, max_value=MAX_ANNUAL_CONSUMPTION_KWH
    )

    def validate_postcode4(self, value: str) -> str:
        """Refuse a four digit string that is not a Dutch postcode."""
        if not MIN_POSTCODE4 <= int(value) <= MAX_POSTCODE4:
            raise serializers.ValidationError(message_for("POSTCODE4_NOT_DUTCH"))
        return value

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        # IntegerField refuses 34.6 outright. Rounding before validation keeps a
        # slider that emits fractions working, without letting a float reach the
        # cache key. It happens before the range check and not instead of it:
        # 90.6 rounds to 91 and is still refused.
        if isinstance(data, dict):
            data = dict(data)
            for name in _ROUNDED_TO_WHOLE_DEGREES:
                value = data.get(name)
                if isinstance(value, float):
                    data[name] = round(value)
        return super().to_internal_value(data)


class RefineInputSerializer(EstimateInputSerializer):
    """Round two: five more questions, nine in total."""

    QUESTION_COUNT: ClassVar[int] = 9

    daytime_occupancy = serializers.BooleanField()
    has_ev = serializers.BooleanField()
    # Derived from the enum rather than copied, so a new member cannot be
    # accepted by the engine and refused by the form.
    ev_behaviour = serializers.ChoiceField(
        choices=[behaviour.name for behaviour in EVChargingBehaviour],
        allow_null=True,
        default=None,
    )
    has_heat_pump = serializers.BooleanField()
    heat_demand_kwh = serializers.FloatField(
        min_value=MIN_HEAT_DEMAND_KWH,
        max_value=MAX_HEAT_DEMAND_KWH,
        allow_null=True,
        default=None,
    )
    dynamic_contract = serializers.BooleanField()
    has_battery = serializers.BooleanField()
    battery_capacity_kwh = serializers.FloatField(
        min_value=MIN_BATTERY_CAPACITY_KWH,
        max_value=MAX_BATTERY_CAPACITY_KWH,
        allow_null=True,
        default=None,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Every yes must bring the detail that makes it usable.

        A default here would be an invented number in the place it matters
        most: when an EV charges decides most of the answer for a household
        that has one. And a capacity without a battery is two fields that
        disagree, where whichever one the assembly reads first decides the
        result.

        All three pairs report together. A form that reveals one problem per
        round trip teaches people to guess.
        """
        errors: dict[str, str] = {}
        # Four English names per row and no sentence in sight. The table says
        # which flag governs which detail; advice.nl says what the household
        # reads when it is wrong. Read it as a rule table, because that is what
        # it has to stay for a second language to cost one file.
        for flag, detail, required_message_id, forbidden_message_id in (
            (
                "has_ev",
                "ev_behaviour",
                "EV_BEHAVIOUR_REQUIRED",
                "EV_BEHAVIOUR_FORBIDDEN",
            ),
            (
                "has_heat_pump",
                "heat_demand_kwh",
                "HEAT_DEMAND_REQUIRED",
                "HEAT_DEMAND_FORBIDDEN",
            ),
            (
                "has_battery",
                "battery_capacity_kwh",
                "BATTERY_CAPACITY_REQUIRED",
                "BATTERY_CAPACITY_FORBIDDEN",
            ),
        ):
            present = attrs.get(detail) is not None
            if attrs[flag] and not present:
                errors[detail] = message_for(required_message_id)
            elif not attrs[flag] and present:
                errors[detail] = message_for(forbidden_message_id)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class YearCeilingsSerializer(StrictSerializer):
    """What each byte of 255 or 127 stands for, in kWh per quarter.

    Three floats and not one, because export and offtake carry their own
    ceiling: sharing one would spend the meter byte's seven bits on export,
    which peaks more than three times as high, and leave offtake with a third
    of the resolution it could have had for free.

    Energy in kWh is float here and everywhere, which is the rule in CLAUDE.md
    rather than a shortcut. These are the ends of a measured range, and no
    amount in euro appears anywhere in this object.
    """

    own = serializers.FloatField(min_value=0.0)
    export = serializers.FloatField(min_value=0.0)
    grid = serializers.FloatField(min_value=0.0)


class YearSerializer(StrictSerializer):
    """The optional ``year`` object, which is the published contract for it.

    Declared as a serializer rather than assembled as a dict so that the shape
    a browser is built against is stated once, in a form that refuses anything
    else. ``StrictSerializer`` carries that over: an extra key here would be a
    key the frontend never learns about and nothing would say so.

    The provenance rule is the reason this class exists at all. A synthetic
    series is a national profile scaled to a figure the visitor typed, so it
    holds nothing they did not enter themselves. A measured one comes off their
    meter and says when somebody is home, and every advice is retrievable for
    ninety days by anyone holding its link. Refusing the pairing costs three
    lines today; in phase 2 it costs a migration over every stored advice and
    leaves a gap between the first measured series and the control over it.

    ``shareable_token`` defaults to True because every advice this service
    stores is reachable by exactly such a token, so the safe reading is the
    one a caller gets by saying nothing.
    """

    own = serializers.CharField()
    meter = serializers.CharField()
    ceilings = YearCeilingsSerializer()
    provenance = serializers.ChoiceField(choices=sorted(PROVENANCE))
    quarters = serializers.ChoiceField(choices=sorted(QUARTERS_PER_YEAR))

    def __init__(self, *args: Any, shareable_token: bool = True, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.shareable_token = shareable_token

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Refuse a measured series on a payload anybody with the link can open."""
        if self.shareable_token:
            refuse_unless_shareable(attrs[PROVENANCE_KEY])
        return attrs


def year_field(encoded: EncodedYear, *, shareable_token: bool = True) -> dict[str, Any]:
    """The one door an encoded year passes through on its way to a browser.

    One door on purpose, and ``advice.series.EncodedYear`` carries no method of
    its own that produces this dict, because a convenience beside the data
    would be a second exit with no check on it. tests/test_advice_series.py
    pins the two modules that may import ``advice.series`` at all, this one and
    ``advice.assembly``, which is what keeps the door singular as the field is
    wired up: a third module reaching into the format could build the object
    itself and the check below would never see it.

    ``shareable_token=False`` is the phase 2 caller: an advice reached through
    an account rather than through a link its holder can forward. Nothing
    passes False today, and the argument exists so that the phase in which a
    measured series becomes serveable is a decision at a call site rather than
    the deletion of this check.
    """
    serializer = YearSerializer(data=asdict(encoded), shareable_token=shareable_token)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)
