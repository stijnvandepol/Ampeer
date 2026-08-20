# Ontwerp: advieslaag Ampeer (deelproject 3, onderdeel B)

Datum: 2026-08-20
Status: vastgesteld, klaar voor implementatieplan
Betreft: het pakket `ampeer_advice`, de regeltabel die van een simulatie-uitkomst een advies maakt

## 1. Doel en afbakening

De simulatiekern zegt hoeveel energie waarheen gaat en wat dat kost. Dit onderdeel
zegt wat het huishouden daaraan moet doen, in welke volgorde, en waarom.

Binnen scope:

- Een expliciete, geordende regeltabel met de zes regels uit het fase 0.5-document
- De drie routes in vaste volgorde, met de gratis routes altijd eerst
- Betrouwbaarheidsniveau op basis van welke velden ingevuld zijn
- Landelijke tariefwaarden met een gemeten bandbreedte, gedateerd en met bron
- Batterijdimensionering: de knik in de capaciteitscurve zoeken
- Nederlandse adviesteksten, in een aparte laag, gekoppeld aan Engelse regel-ids
- Een correctie op onderdeel A: terugleverkosten per kWh in plaats van per jaar

Buiten scope, eigen deelproject:

- De Django-API, opslag met token en rate limiting (onderdeel C)
- De frontend (onderdeel D)
- Tarieven per leverancier. Zie hoofdstuk 4 voor waarom niet

## 2. De correctie op de simulatiekern

`TariffSet` modelleert terugleverkosten nu als `feed_in_fixed_cost_year`, een vast
bedrag per jaar. Dat is onjuist. De gepubliceerde tarieven voor 2027 rekenen
terugleverkosten **per teruggeleverde kWh**, en de spreiding is groot.

Dat is niet alleen een ander getal maar ook ander gedrag: een bedrag per kWh straft
juist het huishouden met veel teruglevering, wat precies de doelgroep is. Een vast
jaarbedrag verdeelt de pijn gelijk en onderschat daardoor systematisch wat een groot
dak kost.

`TariffSet` krijgt daarom `feed_in_cost_per_kwh`. Het bestaande
`feed_in_fixed_cost_year` blijft bestaan, want sommige leveranciers hanteren wel een
vaste staffel, maar de standaardwaarden gebruiken de variant per kWh.

## 3. Wat het hoofdgetal is, en waarom dat het aanvalsoppervlak verkleint

Het getoonde bedrag is een verschil: dezelfde energiestromen onder de regels van nu
tegenover de regels van 2027.

Alles wat in beide scenario's identiek is, valt weg. Vastrecht, netbeheerkosten en
vaste leveringskosten zitten in beide en verdwijnen dus uit het antwoord. Ze worden
op nul gezet in beide `TariffSet`s, met die reden erbij.

Dat is geen truc maar een echte eigenschap: een model dat een verschil berekent,
heeft een kleiner aanvalsoppervlak voor foute aannames dan een model dat een absoluut
bedrag berekent. Wat overblijft zijn de drie grootheden die tussen nu en 2027 echt
veranderen: leveringstarief, terugleververgoeding en terugleverkosten.

Gevolg voor de presentatie: het bedrag mag nooit gepresenteerd worden als "uw
energierekening wordt X". Het is "dit kost het einde van saldering u extra".

## 4. Tarieven

Geen tabel per leverancier. Landelijke waarden met een expliciete bandbreedte, die
meevarieert in de gevoeligheidsanalyse, plus de mogelijkheid dat de gebruiker zijn
eigen tarieven invult.

Reden: een handmatig bijgehouden tarieftabel per leverancier geeft geen foutmelding
als hij veroudert, alleen een zelfverzekerd verkeerd bedrag. Dat is exact de
faalvorm waar dit hele project op jaagt. Daar komt bij dat de spreiding tussen
leveranciers zo groot is dat een gemiddelde met band eerlijker informeert dan een
puntschatting die toevallig van de verkeerde leverancier komt.

### Vastgestelde waarden, geraadpleegd op 2026-08-20

| Grootheid | Laag | Midden | Hoog | Bron |
|---|---|---|---|---|
| Leveringstarief all-in (euro/kWh) | 0,22 | 0,26 | 0,30 | energievergelijk, pure-energie, augustus 2026 |
| Terugleververgoeding bruto, vast contract (euro/kWh) | 0,050 | 0,065 | 0,077 | wettelijk minimum 50 procent van het kale leveringstarief tot 2030; Eneco publiceert 0,0766 |
| Terugleverkosten (euro/kWh) | 0,0446 | 0,075 | 0,115 | keuze.nl overzicht per leverancier |
| Terugleververgoeding netto, dynamisch contract (euro/kWh) | 0,05 | 0,06 | 0,07 | historisch gemiddelde uurprijs |
| Batterij geinstalleerd (euro/kWh capaciteit) | 450 | 675 | 900 | HuisAssist, 1KOMMA5, thuisbatterijmagazine, augustus 2026 |

De netto vergoeding op een vast contract volgt uit bruto min kosten en ligt daarmee
tussen ongeveer min 6,5 en plus 3,2 cent per kWh. Dat strookt met de gepubliceerde
netto cijfers, die lopen van min 7,43 cent (Innova, GewoonEnergie) tot plus 1,19 cent
(Eneco), met de meeste grote leveranciers rond plus 0,25 cent.

**Dit corrigeert het projectplan.** Dat gaat uit van 3 tot 8 cent per teruggeleverde
kWh. Dat is de bruto vergoeding. Netto, na terugleverkosten, is het op een vast
contract rond nul of negatief. Voor een huishouden dat 3.000 kWh teruglevert scheelt
dat het verschil tussen ongeveer 7 euro en 200 euro per jaar. De schok is dus groter
dan het plan aannam, en het verschil tussen een vast en een dynamisch contract is
veel groter dan het plan aannam.

Elke waarde hierboven staat in `ampeer_advice/tariffs.py` met de datum en de bron in
een comment, en met een test die faalt als een waarde verandert zonder dat de datum
mee verandert.

## 5. Architectuur

`ampeer_advice` is een los pakket, puur Python, importeert Django niet en doet geen
I/O. Dezelfde grens en dezelfde reden als bij `ampeer_sim`: een verkeerd advies geeft
geen foutmelding.

```
ampeer_advice/
  types.py        AdviceContext, Rule, FiredRule, Route, Confidence, Advice
  facts.py        leidt uit EnergyFlows de grootheden af waar regels op oordelen
  tariffs.py      landelijke waarden met bandbreedte, gedateerd en met bron
  rules.py        de geordende regeltabel
  battery.py      capaciteitscurve doorrekenen en de knik zoeken
  confidence.py   betrouwbaarheidsniveau uit ingevulde velden
  nl.py           Nederlandse teksten, gekoppeld aan regel-id
  advise.py       compositiewortel: simulatie-uitkomst in, Advice uit
```

### Regels zijn data, geen code-paden

Een `Rule` is een dataclass met `rule_id`, een conditie over `AdviceContext`, een
`route`, een `priority` en een functie die de geschatte besparing uitrekent. De
regeltabel is een geordende tuple. Vuren levert `FiredRule`-objecten op met het
regel-id en de berekende besparing, **nooit tekst**.

Dat is de scheiding uit CLAUDE.md: de regeltabel is taalvrij. Nederlandse zinnen
staan in `nl.py` en worden pas aan de rand toegevoegd. Daardoor breken tekstwijziging
en gedragswijziging niet dezelfde test, en is een tweede taal later een extra bestand
in plaats van een herschrijving.

### Regels oordelen op feiten, niet op arrays

`facts.py` leidt uit de energiestromen af waar de regels op oordelen:
zelfconsumptiegraad, jaarlijkse teruglevering in kWh, aandeel van het verbruik in de
avond, aandeel in het middagvenster, aanwezigheid van een EV en zijn laadgedrag.

Een conditie leest dus `context.self_consumption_rate < 0.35` en niet een numpy-array.
Dat maakt een regel leesbaar voor iemand die geen simulatie begrijpt, en dat is de
eis: als iemand op een forum vraagt waarom hij dit advies krijgt, moet je de regel
kunnen aanwijzen.

## 6. De regeltabel

| id | Conditie | Route | Levert Ampeer op |
|---|---|---|---|
| `SHIFT_FLEXIBLE_LOAD` | zelfconsumptie < 35 procent en niemand overdag thuis | 1 | niets |
| `CHARGE_EV_ON_SURPLUS` | EV aanwezig, laadt niet op zon, en er is overdag overschot | 2 | niets |
| `CONSIDER_DYNAMIC_CONTRACT` | vast contract en teruglevering > 40 procent van de opwek | 2 | affiliate, later |
| `CONSIDER_BATTERY` | na route 1 en 2 nog > 1500 kWh teruglevering en gemiddeld > 3,0 kWh verbruik tussen 17:00 en 07:00 | 3 | lead |
| `BATTERY_DOES_NOT_PAY_BACK` | terugverdientijd > 12 jaar in het middenscenario | 3 | niets |
| `REVIEW_EXISTING_BATTERY` | batterij aanwezig | 3 | niets |

Drie van de zes leveren Ampeer niets op en twee daarvan raden actief iets af. Dat is
geen nobelheid maar het product: de gebruiker die bij `CONSIDER_BATTERY` uitkomt, is
door de gratis routes heen gefilterd, en daarom is dat een waardevollere lead dan een
die er niet doorheen is.

`BATTERY_DOES_NOT_PAY_BACK` en `CONSIDER_BATTERY` sluiten elkaar uit: als de
terugverdientijd te lang is, vuurt alleen de eerste. "Nu geen batterij" is een geldige
en verplichte uitkomst.

De routes worden altijd in volgorde 1, 2, 3 getoond, ook als route 1 niets oplevert.
De volgorde is een eigenschap van de uitvoer, geen sorteerkeuze van de frontend.

## 7. Batterijdimensionering

`battery.py` draait de simulatie voor 3, 5, 7, 10 en 15 kWh en zoekt de knik.

De knik is expliciet gedefinieerd, niet met het oog geschat: neem de marginale
besparing per extra kWh van de eerste stap als referentie, en adviseer de grootste
capaciteit waarvan de marginale besparing nog minstens de helft van die referentie
is. Alles daarboven koopt capaciteit die zichzelf steeds slechter terugverdient.

De drempel van 3,0 kWh avondverbruik bij `CONSIDER_BATTERY` volgt dezelfde logica:
een batterij levert alleen iets op als er vraag is wanneer de zon weg is. Onder die
waarde staat hij 's avonds vol en 's ochtends nog steeds vol.

Kosten volgen uit de tabel in hoofdstuk 4, met de bandbreedte. Terugverdientijd is
investering gedeeld door jaarlijkse besparing, en levert daardoor zelf ook een p10,
midden en p90.

**Beperking, expliciet:** deze vijf runs gebeuren alleen op het middenscenario, niet
op alle 81 combinaties van de gevoeligheidsanalyse. Vijf capaciteiten maal 81
varianten is 405 doorrekeningen en dat past niet in het tijdbudget van twee seconden.
Het gevolg is dat het batterijadvies een grovere band heeft dan het hoofdgetal. Dat
hoort in `docs/methodologie.md` en in de uitvoer.

## 8. Betrouwbaarheid

`confidence.py` bepaalt INDICATIEF, GOED of PRECIES uit welke invoervelden gevuld
zijn: vier velden, negen velden, of eigen meterdata.

Label en bandbreedte zijn twee verschillende dingen en blijven gescheiden, zoals in de
spec van onderdeel A al vastgelegd. De band komt gemeten uit de simulatie. Het label
zegt alleen hoe compleet de invoer is. Een gebruiker kan dus een smalle band hebben
bij het label INDICATIEF, en dat is geen tegenstrijdigheid maar informatie.

## 9. Testregime

1. **Golden files**: dezelfde vijf tot zes huishoudens als de simulatiekern, nu met
   de verwachte gevuurde regel-ids en de verwachte route. Regel-ids, geen teksten
2. **Snapshot op de teksten**, apart, zodat een tekstwijziging zichtbaar is in de
   diff zonder een gedragstest te breken
3. **Property tests**
   - de gratis routes staan altijd voor route 3, ongeacht de invoer
   - `CONSIDER_BATTERY` en `BATTERY_DOES_NOT_PAY_BACK` vuren nooit samen
   - meer teruglevering verlaagt nooit de aanbevolen batterijcapaciteit onder gelijke
     omstandigheden. Meer overschot kan een grotere batterij rechtvaardigen, nooit een
     kleinere
   - elke gevuurde regel heeft een tekst in `nl.py`, en elke tekst hoort bij een regel
4. **Tariefwaarden**: een test die faalt als een waarde verandert zonder dat de
   `SOURCED_ON`-datum mee verandert
5. **Neutraliteitstest**: geen regel leest een veld dat met een commerciele relatie te
   maken heeft. Afgedwongen doordat `AdviceContext` zo'n veld niet heeft, en getest
   doordat de regeltabel alleen velden van `AdviceContext` mag aanraken

## 10. Definition of done

- Een advies uit een simulatie-uitkomst in onder de 500 milliseconden, exclusief de
  batterijcurve
- `ampeer_advice` importeert Django niet, afgedwongen in CI door dezelfde test die dat
  voor `ampeer_sim` doet
- Geen Nederlandse tekst buiten `nl.py`, afgedwongen door een test
- Elke tariefwaarde heeft een bron en een datum in een comment
- `docs/methodologie.md` uitgebreid met hoofdstuk 4, 6 en 7 in gewone taal, inclusief
  de correctie op de 3 tot 8 cent
- De dekkingsdrempel blijft 98 of hoger
