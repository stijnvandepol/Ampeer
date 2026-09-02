"""Dutch validation messages for the advice API, keyed by an English id.

CLAUDE.md draws the line in one sentence: Dutch text never sits hardcoded in
the logic, and what a visitor reads lives in a separate layer keyed by an
English id so the rule table stays language free. Nine of these messages sat
inside ``advice.serializers`` until 2026-08-26, which meant a reword and a
change to what the form refuses were edits to the same lines, reviewed by the
same diff, and neither could be made without reading the other.

The tenth arrived on 2026-08-27 from ``advice.parsers``, where it had been a
module constant all along. It was missed because the check written for the
move read advice/serializers.py by name, so it proved a property of one file
while its commit claimed a property of the package. That is the reason the
scan in tests/test_advice_serializers.py now walks every module here.

``ampeer_advice.nl`` is that layer one floor down and cannot hold these. That
package must not know an HTTP form exists, and every message here is about a
field in a request body: ``onbekend veld`` is meaningless without the request
that carried the field. So the Django side needs its own language layer, and
this is it. The two files never import each other; they are the same idea
applied to two vocabularies.

These are not advice sentences, and the difference decides the register
question. An advice speaks to a household, so docs/decisions.md entry 1 fixes
it on "u"; a validation message names a field and says what is wrong with it,
so none of the messages below addresses anybody at all. That is a property
worth keeping rather than a coincidence, because the moment one of them says
"vul uw postcode in" it is a sentence a reader is spoken to in, and
tests/test_advice_serializers.py is where that is caught.

Nothing here is reworded. Every string is byte for byte what the API answered
before the move, which is what makes the move safe to make without asking, and
the pins that hold it are these. Counted on 2026-08-27: frontend/tests asserts
two of them verbatim, "onbekend veld" and "geen Nederlandse postcode", the
second in three files. tests/test_advice_api.py asserts "onbekend veld" and the
count message with its number substituted, over HTTP. tests/test_advice_serializers.py
reads all ten back out of the serializer or the parser the way a client does.
So a change of wording arrives as a red build, in two languages for the two the
frontend holds.

The line above said three in the frontend and two more in the API tests until
2026-08-27. Two of those five were the same message counted twice, which is the
kind of number that is only ever read as reassurance and never checked.
"""

from __future__ import annotations

#: One entry per message the advice package can raise, keyed by an English
#: identifier. The key is what the logic names; the value is the only place the
#: Dutch exists. A test pairs the two sets in both directions, so a message
#: nothing raises and a raise with no message both fail the build, and it reads
#: every module that imports this one rather than the serializers by name.
#:
#: The first two belong to the strict wrapper and the next seven to one field
#: each. Where a pair reads "required" and "forbidden" it is the same field seen
#: from the two sides of a flag: the detail must be there when the household
#: says yes and must not be there when it says no.
#:
#: The last belongs to no field and to no serializer: ``advice.parsers`` refuses
#: a body before any field exists, which is why it is the one entry raised
#: outside a serializer. It is in this table rather than a second one because it
#: is the same category of sentence, read by the same visitor, in the same
#: request.
VALIDATION_MESSAGES: dict[str, str] = {
    "UNKNOWN_FIELD": "onbekend veld",
    "MORE_UNKNOWN_FIELDS": "en nog {count} onbekende velden",
    "POSTCODE4_NOT_DUTCH": "geen Nederlandse postcode",
    "EV_BEHAVIOUR_REQUIRED": "verplicht wanneer er een elektrische auto is",
    "EV_BEHAVIOUR_FORBIDDEN": "alleen toegestaan met een elektrische auto",
    "HEAT_DEMAND_REQUIRED": "verplicht wanneer er een warmtepomp is",
    "HEAT_DEMAND_FORBIDDEN": "alleen toegestaan met een warmtepomp",
    "BATTERY_CAPACITY_REQUIRED": "verplicht wanneer er een thuisbatterij is",
    "BATTERY_CAPACITY_FORBIDDEN": "alleen toegestaan met een thuisbatterij",
    "TOO_DEEPLY_NESTED": "de JSON is te diep genest",
}

#: The messages that carry a value, which is the only reason ``message_for``
#: formats at all.
#:
#: Written down rather than inferred, because the failure it guards against is
#: silent in the wrong direction: a template whose caller forgets its value
#: raises ``KeyError`` inside ``str.format`` while answering a request, so the
#: visitor gets a 500 where they asked for a validation error. A test reads the
#: placeholders back out of the table and pins the set to this one, so adding a
#: value to any other message is a decision somebody makes here on purpose.
TEMPLATED_MESSAGES: frozenset[str] = frozenset({"MORE_UNKNOWN_FIELDS"})


def message_for(message_id: str, **values: object) -> str:
    """The Dutch validation message for one English id.

    Raises ``KeyError`` for an id that has no message, the way
    ``ampeer_advice.nl.text_for`` does and for the same reason: a fallback to
    the identifier would answer a stranger's request with an English key in a
    Dutch field, and nothing anywhere would say so. The pairing test is what
    should catch a missing entry, and it can only catch it if this refuses.

    The branch below carried ``# pragma: no cover`` until 2026-08-27, saying the
    pairing test made it unreachable.
    ``test_an_unknown_message_id_refuses_rather_than_falling_back`` reaches it
    on purpose, so the pragma was excluding a covered line and, worse, telling a
    reader this raise had never been run.
    """
    try:
        template = VALIDATION_MESSAGES[message_id]
    except KeyError:
        raise KeyError(f"no Dutch validation message for {message_id!r}") from None
    return template.format(**values)
