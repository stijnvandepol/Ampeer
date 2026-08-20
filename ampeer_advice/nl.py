"""Dutch texts for the advice layer, keyed by rule id.

This is the only file in the package that contains a sentence a user reads. The
rule table stays language free and returns ids, so a change of wording and a
change of behaviour can never break the same test, and a second language is one
extra file rather than a rewrite.

The texts are written for the person who wants to know whether they are being
taken for a ride, not for a colleague who already knows what a duck curve is.
Rules of the house: no em-dashes, no jargon that is not explained in the same
sentence, and never a recommendation to buy something that is dressed up as an
observation.
"""

from __future__ import annotations

from ampeer_advice.types import Confidence, Route

#: One entry per rule id in ``ampeer_advice.rules.RULE_IDS``. A test asserts
#: that the two sets are equal in both directions, so a new rule without text
#: fails the build and a text without a rule fails it too.
RULE_TEXTS: dict[str, str] = {
    "SHIFT_FLEXIBLE_LOAD": (
        "Verschuif de wasmachine, de droger en de vaatwasser naar het midden van de dag. "
        "U gebruikt nu maar een klein deel van uw eigen zonnestroom zelf, en vanaf 2027 "
        "is elke kWh die u zelf gebruikt een stuk meer waard dan diezelfde kWh die u "
        "teruglevert. Dit kost u niets, u hoeft er niets voor te kopen en u kunt er "
        "vandaag mee beginnen."
    ),
    "CHARGE_EV_ON_SURPLUS": (
        "Laad uw auto overdag op uw eigen zonnestroom in plaats van 's avonds. Op zonnige "
        "dagen heeft u midden op de dag genoeg over, en de meeste laadpalen en laadapps "
        "kunnen dat zelf regelen zodra u het een keer instelt. De auto is de grootste "
        "flexibele verbruiker in huis, dus hier zit meer winst dan in alle andere "
        "verschuivingen bij elkaar."
    ),
    "CONSIDER_DYNAMIC_CONTRACT": (
        "U levert een groot deel van uw opwek terug en zit op een vast contract. Op een "
        "dynamisch contract houdt u van elke teruggeleverde kWh doorgaans meer over, "
        "omdat daar geen vaste terugleverkosten op zitten. Daar staat tegenover dat uw "
        "prijs per uur meebeweegt, dus kijk eerst naar uw huidige contract en naar de "
        "opzegvergoeding voordat u overstapt."
    ),
    "CONSIDER_BATTERY": (
        "Ook nadat u de gratis stappen hierboven heeft gezet, houdt u veel stroom over, "
        "en u verbruikt 's avonds en 's nachts genoeg om een batterij weer leeg te maken. "
        "In uw situatie is een thuisbatterij het overwegen waard. Kijk eerst naar de "
        "terugverdientijd hieronder en naar de marge daaromheen, en vraag pas daarna "
        "offertes op. Wij verkopen zelf geen batterijen."
    ),
    "BATTERY_DOES_NOT_PAY_BACK": (
        "Een thuisbatterij is in uw situatie niet de moeite waard. De batterij verdient "
        "zichzelf pas na meer dan twaalf jaar terug, en dat is langer dan de garantie die "
        "erop zit. Als een verkoper u iets anders voorrekent, vraag dan met welke "
        "stroomprijs en welke terugleverkosten hij rekent. Wij verdienen niets aan dit "
        "advies, ook niet als u toch koopt."
    ),
    "REVIEW_EXISTING_BATTERY": (
        "U heeft al een thuisbatterij. Controleer of hij ook echt laadt met uw eigen "
        "overschot midden op de dag en 's avonds weer leegloopt, want veel batterijen "
        "staan standaard op een instelling die daar niet op stuurt. Een tweede batterij "
        "erbij zetten levert bijna nooit iets op zolang de eerste niet goed staat."
    ),
}

#: The three routes in the order they are always shown. The free ones come
#: first, and the titles say out loud which ones those are.
ROUTE_TITLES: dict[Route, str] = {
    Route.SHIFT_BEHAVIOUR: "Gratis: uw eigen ritme verschuiven",
    Route.SMART_CONTROL: "Gratis of bijna gratis: slimmer sturen met wat u al heeft",
    Route.STORAGE: "Investeren: stroom opslaan in een thuisbatterij",
}

#: How complete the input was. This label says nothing about the width of the
#: band, and the two are shown next to each other so nobody has to guess.
CONFIDENCE_LABELS: dict[Confidence, str] = {
    Confidence.INDICATIVE: "Indicatief",
    Confidence.GOOD: "Goed",
    Confidence.PRECISE: "Precies",
}


def text_for(rule_id: str) -> str:
    """Return the Dutch text for a rule id.

    Raises ``KeyError`` for an unknown id on purpose. A rule that fires without
    text is a defect, and returning an empty string would ship that defect to
    the reader as a blank advice instead of failing here.
    """
    return RULE_TEXTS[rule_id]
