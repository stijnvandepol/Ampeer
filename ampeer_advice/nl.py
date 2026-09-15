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
    "BATTERY_DEPENDS_ON_PRICE": (
        "Of een thuisbatterij zich bij u terugverdient, hangt af van wat u ervoor "
        "betaalt. Wij rekenen met een prijs tussen 450 en 900 euro per kWh, en dat is "
        "het verschil tussen wel en niet binnen twaalf jaar terugverdiend. Vraag "
        "offertes op en reken de prijs per kWh uit door het totaalbedrag te delen door "
        "de capaciteit. Hierboven staat geen enkel bedrag maar een marge, omdat wij de "
        "tarieven van 2027 niet kennen. Blijft u onder de onderkant van die marge, dan "
        "verdient de batterij zichzelf op tijd terug bij alle tarieven die wij "
        "doorrekenen. Zit u erboven, dan hangt het ervan af welke kant die tarieven op "
        "gaan. Doe eerst wat hierboven staat, want dat kost niets en verlaagt meteen "
        "wat u nodig heeft."
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

#: Why the recommended capacity carries no band, keyed by the id the response
#: sends. Every other amount in a battery advice is a band; this one is a choice
#: out of the sizes that were simulated, and the reader is told that in words
#: rather than left to wonder whether the band went missing.
#:
#: The second entry is not a variant of the first. It says the search reached
#: the largest size we simulate without the curve ever flattening, so the number
#: is a floor and not an answer.
SIZING_BASIS_TEXTS: dict[str, str] = {
    "CHOSEN_FROM_SIMULATED_CAPACITIES": (
        "Deze maat is een keuze uit vijf doorgerekende maten en geen schatting, dus er "
        "staat geen marge omheen. Het is de maat waarboven elke extra kWh opslag minder "
        "dan de helft oplevert van wat de eerste kWh oplevert."
    ),
    "LIMITED_BY_LARGEST_SIMULATED_CAPACITY": (
        "Deze maat is de grootste die wij doorrekenen. Bij u vlakt de opbrengst tot en "
        "met die maat nog niet af, dus lees hem als een ondergrens: een grotere batterij "
        "zou bij u mogelijk nog meer opleveren. Wij rekenen niet verder door, omdat wij "
        "geen maat willen aanraden die wij niet gemeten hebben."
    ),
}

#: Why the consumption the model used has no band, and what a reader should
#: check when it does not look like their year.
#:
#: The figure is an echo of an input rather than an estimate of anything, so a
#: band around it would be decoration. It is in the response at all because of
#: what the question repair in decision 26 cannot do by itself: that repair asks
#: for consumption WITHOUT the car and the heat pump, and its one failure mode
#: is a visitor who reads the total off their annual bill anyway. That visitor
#: is otherwise indistinguishable from a correct one. They lose between 26,5 and
#: 59,2 percent of their answer and nothing reports a problem.
#:
#: Two entries and not one with the numbers substituted. Keeping them static
#: keeps every Dutch sentence in this file whole and greppable, and the split
#: says the thing the numbers would: with no assets the figure IS what was
#: typed, so there is nothing to have gone wrong, and the sentence that warns
#: about the bill total would be noise on the household it cannot happen to.
MODELLED_CONSUMPTION_BASIS_TEXTS: dict[str, str] = {
    # This text is shown whenever the modelled year came back equal to the
    # figure entered, and `rendering.py` decides that by comparing the series
    # rather than by reading the request's flags. That is deliberate and right,
    # and it means this sentence cannot know which round the reader is in.
    #
    # It used to say "want u gaf aan geen elektrische auto en geen warmtepomp te
    # hebben". In round two that is true. In round one nobody is asked: the four
    # questions are postcode, wattpiek, roof and consumption, and the model
    # assumes no car and no heat pump, which chapter 19 of the methodology says
    # in as many words. So the product told most of its readers that they had
    # said something they were never asked. On a product whose whole promise is
    # that its reasoning can be checked, that is the worst sentence to get
    # wrong. It now states what the model did, which is true in both rounds and
    # is the thing the comparison actually establishes.
    "ENTERED_UNCHANGED": (
        "Dit is het verbruik waarmee wij gerekend hebben. Het is precies het getal dat u "
        "opgaf: wij telden er zelf niets bij op voor een elektrische auto of een "
        "warmtepomp. Heeft u die wel, dan ligt uw verbruik hoger en valt het bedrag "
        "bovenaan te laag uit. Er staat geen marge omheen: het is uw eigen opgave en "
        "geen schatting van ons."
    ),
    "ENTERED_PLUS_ASSETS": (
        "Dit is het verbruik waarmee wij gerekend hebben: het getal dat u opgaf, plus wat "
        "wij er zelf bij optelden voor uw auto of uw warmtepomp. Herkent u dit niet als "
        "uw jaarverbruik, kijk dan of u het totaal van uw jaarnota invulde. Daar zit het "
        "laden of de pomp al in, en dan telt het bij ons een tweede keer mee en valt het "
        "bedrag bovenaan te laag uit."
    ),
}

#: How complete the input was. This label says nothing about the width of the
#: band, and the two are shown next to each other so nobody has to guess.
CONFIDENCE_LABELS: dict[Confidence, str] = {
    Confidence.INDICATIVE: "Indicatief",
    Confidence.GOOD: "Goed",
    Confidence.PRECISE: "Precies",
}


#: The same advice in one line, for the top of the page.
#:
#: WHY THIS EXISTS. ``RULE_TEXTS`` is written to be read, and it earns its
#: length: it says what to do, why it is worth doing, and what it costs. On a
#: phone the first of them is seven lines, and a household that opened the page
#: to find out what to do reads a paragraph before it finds out. So each rule
#: also carries the instruction on its own, and the paragraph stays directly
#: underneath it.
#:
#: NOT A SUMMARY AND NOT A SECOND OPINION. Every line here is the first
#: sentence of its own text said shorter, and a test asserts each one stays
#: under ``ACTION_MAX_CHARS``. If the two ever disagree, the long one is the
#: advice and this one is the defect: it is the one a reader acts on before
#: they have read the reasoning.
#:
#: The house rules from the top of this file hold here and bite harder, because
#: a short line has nowhere to put a caveat. No recommendation to buy dressed
#: as an observation: ``CONSIDER_BATTERY`` says to consider and to read on, not
#: to order, and ``BATTERY_DOES_NOT_PAY_BACK`` says no in as many words,
#: because "nu geen batterij" is a valid and required outcome.
RULE_ACTIONS: dict[str, str] = {
    "SHIFT_FLEXIBLE_LOAD": "Zet de wasmachine, de droger en de vaatwasser midden op de dag aan.",
    "CHARGE_EV_ON_SURPLUS": "Laad uw auto overdag in plaats van 's avonds.",
    "CONSIDER_DYNAMIC_CONTRACT": "Kijk of een dynamisch contract bij u beter uitpakt.",
    "CONSIDER_BATTERY": "Een thuisbatterij is het overwegen waard. Lees eerst de terugverdientijd.",
    "BATTERY_DEPENDS_ON_PRICE": "Een batterij kan uit, maar alleen onder een bepaalde prijs per kWh.",
    "BATTERY_DOES_NOT_PAY_BACK": "Koop nu geen thuisbatterij.",
    "REVIEW_EXISTING_BATTERY": "Controleer of uw batterij op uw eigen overschot laadt.",
}

#: What "one line" means, measured rather than felt: at 430 CSS pixels, the
#: width of the phone this was drawn on, the page's body type fits roughly this
#: many characters on two lines. Three lines is a paragraph again.
ACTION_MAX_CHARS = 80


def action_for(rule_id: str) -> str:
    """Return the one line version of a rule's advice.

    Raises ``KeyError`` for an unknown id, like ``text_for`` and for the same
    reason.
    """
    return RULE_ACTIONS[rule_id]


def text_for(rule_id: str) -> str:
    """Return the Dutch text for a rule id.

    Raises ``KeyError`` for an unknown id on purpose. A rule that fires without
    text is a defect, and returning an empty string would ship that defect to
    the reader as a blank advice instead of failing here.
    """
    return RULE_TEXTS[rule_id]


#: What each varied or pinned model input is called in words.
#:
#: A scenario band sends `varied` and `pinned` so it can admit it is narrower
#: than the headline band. Those are English identifiers from the simulation
#: core, and a Dutch reader was being shown "supply_price" verbatim. The
#: frontend cannot translate them: a Dutch copy of the model's vocabulary
#: living there is a second copy that drifts the first time an input is added,
#: and it is the same language-boundary violation this file exists to prevent.
#: So the translation lives here, beside the advice text, keyed by the id.
#:
#: A test asserts that every name any variation can emit has an entry, so a new
#: assumption without a Dutch name fails the build rather than reaching a reader
#: as an identifier.
INPUT_LABELS: dict[str, str] = {
    "supply_price": "de stroomprijs",
    "feed_in_price": "de terugleververgoeding",
    "feed_in_cost_per_kwh": "de terugleverkosten",
    "battery_cost_per_kwh": "de prijs van de batterij",
    "annual_consumption_kwh": "uw jaarverbruik",
    "shiftable_block_kwh": "hoeveel verbruik u kunt verschuiven",
    "system_loss_fraction": "het verlies in uw installatie",
}


def label_for(input_id: str) -> str:
    """The Dutch name of one model input.

    Raises rather than falling back to the identifier. A fallback would put an
    English name in front of a reader and nothing would say so; the test that
    pairs this table with the variations is what should catch it, and it can
    only catch it if this refuses.
    """
    try:
        return INPUT_LABELS[input_id]
    except KeyError:  # pragma: no cover - the pairing test makes this unreachable
        raise KeyError(f"no Dutch name for model input {input_id!r}") from None


#: Where the production series came from, in words a reader can act on.
#:
#: The response also sends the enum name, which is English and is for a machine.
#: A reader who is told "FALLBACK" learns nothing; a reader told the sun figures
#: came from an offline table rather than from a live measurement knows exactly
#: how much weight to put on the answer, and that is the kind of thing this
#: product exists to say out loud.
#:
#: Keyed by the enum name rather than by the member, so this file keeps its
#: promise of importing nothing from the simulation core. A test pairs the two.
PRODUCTION_SOURCE_TEXTS: dict[str, str] = {
    "PVGIS": (
        "De opbrengst van uw dak is opgevraagd bij PVGIS, de rekentool van de Europese "
        "Commissie, op basis van echte instralingsmetingen voor uw postcodegebied."
    ),
    "FALLBACK": (
        "PVGIS was niet bereikbaar, dus wij hebben gerekend met onze eigen tabel: het "
        "gemiddelde van negen weerjaren voor Nederland. Dat is nauwkeurig genoeg om u "
        "een antwoord te geven en minder nauwkeurig dan een berekening voor uw eigen "
        "postcodegebied. Vraag het advies later nog eens op voor een scherper getal."
    ),
}


def production_source_text(source_name: str) -> str:
    """The Dutch sentence for one production source.

    Raises rather than falling back, for the same reason ``label_for`` does: a
    fallback would put an English enum name in front of a reader and nothing
    would say so.
    """
    try:
        return PRODUCTION_SOURCE_TEXTS[source_name]
    except KeyError:  # pragma: no cover - the pairing test makes this unreachable
        raise KeyError(f"no Dutch text for production source {source_name!r}") from None
