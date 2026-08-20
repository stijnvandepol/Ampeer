# Ontwerp: simulatiekern Ampeer (fase 0.5, onderdeel A)

Datum: 2026-08-20
Status: vastgesteld, klaar voor implementatieplan
Betreft: het pakket `ampeer_sim`, de rekenkern onder de adviseur

## 1. Doel en afbakening

De simulatiekern berekent, op basis van vier tot negen zelf-ingevoerde antwoorden,
wat het einde van de salderingsregeling een specifiek huishouden kost, en wat drie
mogelijke ingrepen daaraan veranderen. Er is geen meterkoppeling nodig.

Binnen scope:

- Opbouw van een synthetische bruto verbruiksreeks op kwartierbasis
- Opbouw van een opwekreeks op dezelfde tijdbasis
- Deterministische simulatie van energiestromen per kwartier, met en zonder batterij
- Omzetting van energiestromen naar bedragen
- Een berekende bandbreedte en een betrouwbaarheidsniveau

Buiten scope, andere onderdelen van fase 0.5 met een eigen ontwerp:

- De adviesregels en hun Nederlandse teksten (onderdeel B)
- De API, opslag en rate limiting (onderdeel C)
- De frontend (onderdeel D)

Buiten scope van fase 0.5 als geheel:

- Echte meterdata als invoer. Fase 3 voegt een provider toe, niet een tweede motor
- Live prijs-ingest, aansturing van apparaten, accounts

## 2. Uitgangspunten uit de databronverificatie

Deze bevindingen zijn op 2026-08-20 geverifieerd tegen de echte bestanden en de echte API.

### NEDU standaardprofielen

- Per kalenderjaar een ZIP op Energiedatawijzer, vrij te downloaden zonder account
- Inhoud: een CSV met puntkomma als scheidingsteken en een punt als decimaalteken
- 35.040 datarijen voor 2025, dus kwartierwaarden. In een schrikkeljaar 35.136
- Zes kopregels: versienummer, toepassingsjaar, categoriecode, type, richting, tijdzone
- Kolom A is doorlopende wintertijd (UTC+1, geen zomertijdsprong) en geeft het einde
  van de profielperiode. Kolommen B en C geven lokale kloktijd (van, tot)
- Per categorie vier reeksen: type AZI (aansluiting zonder invoeding) of AMI
  (aansluiting met invoeding), richting A (afname) of I (invoeding)

Correcties op eerdere aannames in het projectplan:

- E1A is "niet op afstand uitleesbare meetinrichting", niet "zonder schakeltijden".
  E1B en E1C zijn slimme meters met respectievelijk nacht- en avondtariefregime
- Alleen E1A en E2A sommeren naar 1. E1B en E1C sommeren naar 2, omdat de reeks
  fracties bevat van twee tariefregisters die elk naar 1 sommeren
- In een schrikkeljaar liggen die sommen daarboven
- De praktische tolerantie is ongeveer 1e-6, niet 1e-9. Gemeten voor 2025:
  E1A_AZI_A = 1,00000057; E1B_AZI_A = 2,00000028; E1C_AZI_A = 2,00000013

### PVGIS

- Endpoint `https://re.jrc.ec.europa.eu/api/v5_3/seriescalc`, alleen GET, JSON of CSV
- Limiet 30 calls per seconde per IP, HTTP 429 bij overschrijding
- Levert per uur: `P` in watt, `G(i)` instraling, `H_sun`, `T2m` buitentemperatuur,
  `WS10m` en `Int`. Tijdstempels in UTC op het midden van het meetinterval
- 8.760 uurwaarden per jaar, 8.784 in een schrikkeljaar
- Geverifieerde testcall (51.66, 5.61, 3,5 kWp, zuid, 35 graden, verlies 14 procent,
  jaar 2020) gaf 3.766 kWh

Herziene beslissing, gemeten op 2026-08-20 tijdens de bouw: wij rekenen de opwek NIET
zelf uit de instraling. Een eigen model met `G(i)/1000 x kWp x (1 - verlies)` kwam
9,8 procent te hoog uit tegenover PVGIS zelf, omdat moduletemperatuur, reflectie en
spectrale respons ontbreken. De standaard temperatuurcorrectie bracht dat naar 5,3
procent, nog steeds structureel en altijd dezelfde kant op.

Daarom vraagt de provider `pvcalculation=1` met `peakpower=1` en `loss=0`, en levert
een opwekreeks in watt per kWp waar de fysica al in verwerkt zit. Wij passen daarna
alleen lineaire factoren toe: arraygrootte, systeemverlies en degradatie. Dat geeft
0,00 procent afwijking, geverifieerd tegen een live call, en het houdt de
gevoeligheidsanalyse op een enkele API-call, want alleen lineaire factoren varieren.

`T2m` komt in dezelfde respons mee, dus KNMI blijft onnodig.

Gevolg: KNMI is niet nodig. De temperatuurreeks voor het warmtepompmodel komt uit
dezelfde call als de opwek, op dezelfde locatie en dezelfde uren, en is daarmee per
constructie consistent met de instraling.

### Openstaand

Noch Energiedatawijzer noch PVGIS vermeldt expliciete licentie- of
hergebruikvoorwaarden op de pagina. Gebruik is onproblematisch, herdistributie niet
bevestigd. Daarom worden de profielbestanden niet in de repository gecommit, maar bij
build of deploy opgehaald door een ingest-script. Dat is los daarvan ook wenselijk,
want de CSV is 13 MB.

Actie: bevestiging vragen bij energiedatawijzer@hetnormo.nl en bij de JRC.

## 3. Architectuur

### Grens

`ampeer_sim` is een los installeerbaar Python-pakket dat Django niet importeert. De CI
dwingt dat af met een controle die faalt op elke django-import binnen het pakket.
Reden: dit is het enige onderdeel waar een fout geen foutmelding geeft maar een
plausibel verkeerd getal, dus het moet zonder database en zonder server testbaar en
valideerbaar zijn.

De kern doet zelf geen I/O. Alle externe data komt binnen via providers die als
Protocol gedefinieerd zijn: `ProfileProvider`, `ProductionProvider`, `PriceProvider`.
In tests worden die vervangen door handgeschreven reeksen.

### Modules

```
ampeer_sim/
  types.py          Household, PVSystem, BatterySpec, TariffSet, Scenario, Result
  timebase.py       het jaarrooster en alle tijdzonelogica
  providers.py      Protocols voor profiel-, productie- en prijsdata
  simulate.py       compositiewortel: antwoorden in, Result uit
  validate.py       CLI om het model tegen een echte jaarafrekening te leggen
  profiles/
    nedu.py         fracties inlezen, valideren en schalen naar kWh
    assets.py       ev_profile, heatpump_profile
    presence.py     verplaatsbaar blok verschuiven
    compose.py      bouwt de bruto verbruiksreeks
  production/
    pvgis.py        de enige plek met uitgaand HTTP-verkeer
    model.py        systeemverlies, degradatie, uur naar kwartier
  engine/
    battery.py      laadtoestand, vermogens, rendement, ontlaaddiepte
    strategies.py   SELF_CONSUMPTION, ARBITRAGE, HYBRID
    run.py          de tijdstaplus
  economics/
    tariffs.py      de enige plek waar kWh euro's worden
    sensitivity.py  variatie, p10, midden, p90
```

### Dataflow

Eenrichtingsverkeer, zonder terugkoppeling:

```
antwoorden (4 of 9)
  -> profiles/compose.py    bruto verbruik, kWh per kwartier
  -> production/            opwek, kWh per kwartier, zelfde rooster
  -> engine/run.py          per scenario energiestromen in kWh
  -> economics/             dezelfde stromen in euro's, als Decimal
  -> Result                 bedrag, bandbreedte, betrouwbaarheid, scenario's
```

### Getaltypen

Energie in kWh is float in numpy-arrays. Bedragen in euro's zijn Decimal. De omzetting
gebeurt uitsluitend in `economics/tariffs.py`. Nergens anders staat een prijs naast een
energiereeks.

### Versionering

`ampeer_sim.ENGINE_VERSION` is een expliciete constante. Elk `Result` bevat hem, zodat
een later antwoord altijd te herleiden is naar de motor die het gaf.

## 4. Tijdbasis

Drie roosters komen samen en zijn het onderling oneens:

- NEDU: 35.040 of 35.136 kwartieren, doorlopende wintertijd, tijdstempel op het einde
- PVGIS: 8.760 of 8.784 uurwaarden, UTC, tijdstempel op het midden
- De gebruiker: Nederlandse kloktijd, met een nacht van 23 uur in maart en 25 in oktober

`timebase.py` definieert het jaarrooster eenmalig. Elke reeks die de kern binnenkomt
wordt daar eerst op gezet. Alles daarna is index-op-index zonder tijdzonelogica.

Beslissingen:

- Het rooster volgt het NEDU-profieljaar: kwartierresolutie, doorlopende wintertijd
- Opwek wordt van uur naar kwartier gebracht door lineair te interpoleren op de
  opwekreeks per kWp. Deze beslissing luidde eerder: interpoleer op de instraling en
  reken pas daarna naar vermogen, omdat die omzetting niet-lineair is en interpoleren
  en omrekenen dus niet verwisselbaar zijn. Die redenering klopte, maar de premisse is
  vervallen: wij doen die omzetting niet meer zelf, PVGIS doet hem. Alles wat wij nog
  toepassen is lineair, dus de volgorde maakt niet meer uit
- Profieljaar en PVGIS-weerjaar mogen verschillen. Ze worden uitgelijnd op
  kalenderdatum, niet op weekdag. Opwek is niet weekdagafhankelijk, verbruik wel, en
  het profieljaar bepaalt de weekdagstructuur

## 5. Profielmodel

### Stap 1: basisvorm

`E1A_AZI_A` van het nieuwste beschikbare profieljaar, geschaald op het opgegeven
jaarverbruik. Eén getal invoer, geen registersplitsing.

Onderbouwing van deze keuze, gemeten op 2026-08-20 voor 3.500 kWh en 3,5 kWp zuid:

| Basisprofiel | Aanname | Zelfconsumptie |
|---|---|---|
| E1A | geen | 33,95 % |
| E1B (nacht) | 50 % laag | 33,36 % |
| E1B | 55 % laag | 32,41 % |
| E1B | 60 % laag | 31,34 % |
| E1C (avond) | 55 % laag | 33,95 % |
| E1C | 60 % laag | 32,66 % |

De keuze tussen E1A en E1B of E1C is bij realistische aannames ongeveer anderhalve
procentpunt waard, terwijl de benodigde aanname over de laag/normaal-verhouding zelf al
twee tot zes procentpunt beweegt. Bij een bandbreedte van plus of min 30 procent is dat
de verkeerde plek voor complexiteit. E1B en E1C blijven als parameter beschikbaar voor
als kalibratie later laat zien dat het loont.

AZI en niet AMI, omdat AMI de netto afname is van huizen die al terugleveren. Daar zit
de zon al in verwerkt; die gebruiken zou de opwek dubbel tellen.

Genoemde beperking voor `docs/methodologie.md`: AZI is het gemiddelde van huishoudens
zonder teruglevering, terwijl de gebruiker juist panelen heeft. Paneelbezitters zijn
geen willekeurige steekproef. Het basisprofiel is dus systematisch net niet het profiel
van de gebruiker. Kalibratie in fase 2 corrigeert dit.

### Stap 2: assets optellen

EV en warmtepomp worden opgeteld bij de basisvorm, niet ingemengd.

`ev_profile(behaviour, annual_km, kwh_per_100km)` met drie gedragingen:

- `NIGHT`: laden in het laagtariefvenster
- `ARRIVAL`: laden direct bij thuiskomst
- `SOLAR`: laden op overschot. Deze heeft de opwekreeks nodig en wordt daarom pas in
  stap 4 toegepast

`heatpump_profile(t2m_series, building_type, build_year, cop_curve)`: warmtevraag
evenredig met graaduren boven een stookgrens, elektriciteitsvraag is warmtevraag
gedeeld door een COP die daalt bij lagere buitentemperatuur. Een vaste COP zou het
winterverbruik onderschatten, precies in de maanden zonder opwek.

### Stap 3: aanwezigheid

Model: verplaatsbaar blok. Een vaste hoeveelheid verplaatsbaar verbruik per dag (was,
vaatwas, droger, boiler; default 1,0 kWh per dag, in de gevoeligheidsanalyse
gevarieerd tussen 0,5 en 2,0 kWh) verhuist tussen de avondpiek en het
middaguur, afhankelijk van het antwoord op "is er doordeweeks overdag iemand thuis".

Dit is een verschuiving, geen schaling: het dagtotaal blijft gelijk. De omvang van het
blok is gekalibreerd op 2026-08-20 tegen de enige externe kennis die we erover hebben:
het projectplan zegt dat overdag thuis zijn tien tot vijftien procentpunt zelfconsumptie
scheelt. Bij 1,75 kWh gaf het model 22 procentpunt, bij 1,0 kWh 13,7. Vandaar 1,0. Het model sluit direct
aan op adviesregel 1, die de gebruiker vertelt datzelfde blok te verschuiven.

### Stap 4: opwek en terugkoppeling

Opwek uit PVGIS als watt per kWp, geschaald op wattpiek, met systeemverliesfactor
(standaard 14 procent, instelbaar) en paneeldegradatie op basis van bouwjaar. Alle drie
lineair. Daarna pas het `SOLAR`-laadgedrag van de EV.

### IJking zonder gebruikers

`E1A_AMI_I` is het gemeten gemiddelde terugleverprofiel van Nederlandse huishoudens met
panelen. Dat is geen invoer, maar een toetssteen: als de gemodelleerde terugleverreeks
qua vorm sterk afwijkt van die empirische reeks, klopt er iets niet in het opwek- of
verbruiksmodel. Deze vergelijking hoort in de testset.

## 6. Simulatiemotor

Deterministische tijdstaplus over het hele jaar, per kwartier.

Batterijmodel: laadtoestand, laad- en ontlaadvermogen, round-trip rendement, bruikbare
ontlaaddiepte, degradatie per cyclus.

Strategieën:

- `SELF_CONSUMPTION`: overschot naar batterij, tekort uit batterij. Geen prijsdata nodig
- `ARBITRAGE`: laden op goedkope uren, ontladen op dure. Vereist netladen en prijsdata
- `HYBRID`: zelfconsumptie als basis, arbitrage bij voldoende verwachte spread

Regel voor arbitrage: de strategie mag alleen vooruitkijken binnen het venster waarin
day-ahead-prijzen in werkelijkheid bekend zijn: vanaf 13:00 lokale tijd is de
prijsreeks tot en met 23:59 van de volgende dag bekend, daarvoor alleen tot en met
23:59 van de huidige dag. Vooruitkijken daarbuiten is perfecte voorkennis en levert een rendement op dat in
de praktijk niet bestaat. Deze grens staat in de code, niet in een comment, en wordt
getest.

### Uitval van externe bronnen

Het advies mag nooit falen omdat een externe API traag is. Omdat de kern zelf geen I/O
doet, hoort die afhandeling in de provider en niet in de motor.

`ProductionProvider` kent daarom twee implementaties: de PVGIS-implementatie, en een
fallback op een lokale tabel met maandelijkse opbrengstfactoren per oriëntatie en
helling, waaruit een uurreeks geïnterpoleerd wordt. Bij een timeout of een 429 valt de
provider terug op de tabel en markeert het resultaat als `production_source=FALLBACK`,
zodat de uitkomst zichtbaar minder scherp is in plaats van stilletjes minder juist.

Voor de kern zijn beide implementaties inwisselbaar; hij ziet alleen een reeks.
De fallback wordt getest met een gemockte timeout.

Prijsdata: één vast jaar day-ahead-prijzen als databestand naast de profielen. Geen
API-sleutel in productie, geen live afhankelijkheid. Later te vervangen door een
live-ingest zonder dat de kern verandert.

### Invariant

Op elke tijdstap moet gelden:

```
verbruik = zelfverbruik + afname_net + ontlading
opwek    = zelfverbruik + teruglevering + lading
```

Sluit dit niet binnen 1e-9, dan is er energie uit het niets ontstaan.

## 7. Economie en bandbreedte

### Definitie van het hoofdgetal

- Basislijn: de huidige situatie met saldering
- Scenario: dezelfde energiestromen onder de tarieven van 2027, zonder saldering,
  zonder ingreep
- Het getoonde bedrag is het verschil

De drie routes verlagen datzelfde bedrag, elk gemeten vanaf diezelfde basislijn, zodat
ze onderling vergelijkbaar zijn en niet ten onrechte stapelen.

### Bandbreedte

De bandbreedte wordt berekend, niet vastgesteld. `economics/sensitivity.py` varieert de
invoer waarvan bekend is dat hij onzeker is:

- jaarverbruik
- omvang van het verplaatsbare blok
- systeemverlies
- terugleververgoeding en terugleverkosten
- de aanwezigheidsaanname

De variaties worden gecombineerd, niet een voor een toegepast. Een run die drie van de
vier aannames op hun middenwaarde houdt, bereikt de hoeken van de band nooit, en een band
die zijn eigen hoeken niet haalt is decoratie. Het raster is volledig factorieel over drie
niveaus van vier aannames, dus 81 doorrekeningen. Bij ongeveer zes milliseconden per
doorrekening past dat ruim binnen het tijdbudget.

De simulatie draait over die combinaties; p10, midden en p90 vormen de band.

Label en band zijn twee verschillende dingen en mogen niet door elkaar lopen. Het label
INDICATIEF, GOED of PRECIES volgt uit welke invoervelden ingevuld zijn en wordt bepaald
in onderdeel B. De band wordt hier gemeten. De kern levert dus altijd een band terug en
nooit een label; onderdeel B zet ze naast elkaar.

Een hardgecodeerde plus of min 30 procent bij het label is expliciet verboden. De
eerlijke bandbreedte is de kern van de positionering; een verzonnen band maakt er een
grafisch element van.

## 8. Testregime

1. **Energiebalans-invariant** over elke tijdstap van elk scenario. Vangt het meeste en
   veroudert niet als het model verfijnt
2. **Property tests**
   - meer opwek bij gelijk verbruik verlaagt altijd de zelfconsumptiegraad
   - een batterij verlaagt nooit de zelfconsumptie
   - de laadtoestand blijft binnen de grenzen
   - een groter verplaatsbaar blok verhoogt de zelfconsumptie monotoon
   - arbitrage met venstergrens levert nooit meer op dan arbitrage met perfecte
     voorkennis, als regressietest op de voorkennisgrens
3. **Profielvalidatie**: de som van de fracties klopt met de verwachting per categorie
   en per jaartype (1 voor E1A en E2A, 2 voor de rest, hoger in een schrikkeljaar), met
   een tolerantie van 1e-6
4. **Golden files**: vijf uitgeschreven huishoudens met verwachte uitkomst. Minstens één
   daarvan klein genoeg om met de hand na te rekenen
5. **Validatie tegen echte jaarafrekeningen**, als commandoregelscript:
   `python -m ampeer_sim.validate <bestand>`. Doelnorm: binnen 10 procent

De eerste vier testen of de code doet wat het ontwerp zegt. Alleen de vijfde test of het
ontwerp klopt.

## 9. Aannames die in de methodologie moeten

Deze lijst is de basis voor `docs/methodologie.md` en moet publiek zijn.

1. Standaardprofielen zijn gemiddelden over honderdduizenden aansluitingen en zijn
   daardoor glad. Een echt huishouden heeft pieken die het gemiddelde niet heeft.
   Acceptabel voor zelfconsumptie, minder geschikt voor advies over batterijvermogen
2. Het basisprofiel is dat van huishoudens zonder teruglevering
3. De laadgedragingen van de EV zijn drie stereotypen, geen gemeten verdeling
4. Het verplaatsbare blok is een aangenomen grootheid, nog niet gekalibreerd
5. Profieljaar en weerjaar kunnen verschillen en worden op kalenderdatum uitgelijnd
6. Er wordt gerekend op het verbruiks- en weerpatroon van een historisch jaar, met
   tarieven van een toekomstig jaar. Dat wordt in de uitkomst benoemd

## 10. Definition of done

- Een compleet resultaat vanaf vier antwoorden in onder de 2 seconden, inclusief de
  variatieruns voor de bandbreedte
- `ampeer_sim` importeert Django niet, afgedwongen in CI
- Alle vijf testlagen groen, met minstens drie echte jaarafrekeningen gevalideerd binnen
  10 procent
- `ENGINE_VERSION` in elk resultaat
- `docs/methodologie.md` bevat hoofdstuk 9 in gewone taal
