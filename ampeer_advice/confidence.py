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


def confidence_for(filled_fields: int, has_meter_data: bool) -> Confidence:
    """Return the confidence label for this much input.

    Own quarter-hour meter data outranks any number of filled fields, because it
    replaces the synthetic profile itself rather than one of its parameters. A
    household with meter data and nothing else filled in is still PRECISE about
    the thing that dominates the answer.
    """
    if has_meter_data:
        return Confidence.PRECISE
    if filled_fields >= GOOD_FIELD_COUNT:
        return Confidence.GOOD
    return Confidence.INDICATIVE
