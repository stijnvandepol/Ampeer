"""The confidence level, derived from how complete the input was.

The label and the band are two different things and they stay separate. The band
comes measured out of the simulation; this label says only how much the
household told us. A narrow band under the label INDICATIVE is therefore not a
contradiction but information: the model is confident about the answer to the
question that was actually asked.

That separation is what keeps the label honest. If completeness of input were
allowed to narrow the band, or a narrow band allowed to raise the label, the two
would reinforce each other and a confident wrong number would look like a
precise right one.
"""

from __future__ import annotations

from ampeer_advice.types import Confidence

#: From this many filled input fields the answer is called GOOD. Below it the
#: model is filling in national averages for most of what it needs, which is
#: worth an answer but not worth a strong word for it.
GOOD_FIELD_COUNT = 5


def confidence_for(
    filled_fields: int, has_meter_data: bool, consumption_measured: bool = False
) -> Confidence:
    """Return the confidence label for this much input.

    Own quarter-hour meter data outranks any number of filled fields, because it
    replaces the synthetic profile itself rather than one of its parameters. A
    household with meter data and nothing else filled in is still PRECISE about
    the thing that dominates the answer.

    ``consumption_measured`` is the narrower thing phase 3 actually does, and it
    deliberately stops at GOOD. A fitted annual consumption is a parameter read
    off the meter instead of typed, which is the same kind of improvement the
    nine questions make and not a different kind. The distinction is the one
    ``docs/methodologie.md`` draws for itself: the questions each replace a
    parameter of the standard profile, and quarter-hour data replaces that
    profile. Until something replaces the profile, PRECISE would be claiming
    the larger of the two.

    It is still worth a rung. The figure it measures is the single input that
    moves the answer most, so an estimate built on four questions and a measured
    annual total knows more than its field count says.
    """
    if has_meter_data:
        return Confidence.PRECISE
    if consumption_measured or filled_fields >= GOOD_FIELD_COUNT:
        return Confidence.GOOD
    return Confidence.INDICATIVE
