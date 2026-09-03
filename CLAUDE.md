# Ampeer

Ampeer is een neutrale energie-adviseur voor Nederlandse huishoudens met zonnepanelen.
Domein: ampeer.nl

## Het probleem
De salderingsregeling stopt op 1 januari 2027, in een keer en niet in stappen
(Wet van 18 december 2024, Staatsblad 2025 nr. 17, artikel V; het eerdere
afbouwplan 35594 is op 13 februari 2024 door de Eerste Kamer verworpen).
Bijna 3 miljoen woningen hebben zonnepanelen (CBS, cijfer voor 2024, StatLine
85005NED; dat telt installaties op en rond woningen en niet huishoudens, en de
twee zijn niet hetzelfde). Zij krijgen dan nog 3 tot 8 cent per teruggeleverde
kWh in plaats van de circa 26 cent die ze besparen door die kWh zelf te
gebruiken. Die 26 is `SUPPLY_PRICE.mid` in `ampeer_advice/tariffs.py`: dit
document en de code horen hetzelfde middenscenario te noemen. Vanaf 1 januari
2029 komt daar een tijdsafhankelijk nettarief bij met vijf wegingsfactoren en
vijf tijdsblokken, waarvan er per dag maximaal vier tegelijk gelden en in de
winter drie (Netbeheer Nederland BR-2026-2242, 1 mei 2026, bijlage 5). Die
datum is een verzoek en geen feit: er staan twee uitwijkmogelijkheden naar
1 januari 2030 in, en de ACM had het voorstel op 2 september 2026 nog niet
beoordeeld.

Alle drie de correcties hierboven komen uit de bronnenronde van 2026-09-02.
Dit document zei ruim 3 miljoen huishoudens waar CBS bijna 3 miljoen woningen
zegt, circa 27 cent waar de constante 0,26 is, en vier prijsniveaus waar de
codetekst er vijf vastlegt. De volledige lezing staat in
`docs/analysis/2026-08-24-tou-tariff-2029.md` en de bronnen bij elke claim in
`docs/methodologie.md`.

## Wat Ampeer doet
Berekenen wat het einde van saldering een specifiek huishouden kost, en welke van
drie routes het beste past: gedrag verschuiven, slim sturen zonder opslag, of een
thuisbatterij.

Dat gebeurt in eerste instantie op een synthetisch kwartierprofiel, opgebouwd uit
NEDU-standaardprofielen en een PVGIS-opwekreeks, dus zonder dat de gebruiker iets
hoeft te koppelen. Echte kwartierdata uit de P1-poort is een upgrade die het antwoord
scherper maakt, geen voorwaarde om een antwoord te krijgen.

Deze volgorde is een ontwerpbeslissing, geen tijdelijke workaround. De grootste
gebruikersgroep wil niets installeren.

## Wat Ampeer NIET doet
- Geen hardware verkopen
- Geen batterijen of panelen verkopen
- Geen eigen energiecontract
- Geen advertenties
- Geen apparaten aansturen (adviseren, niet ingrijpen)

De neutraliteit is het product, en op 2026-09-02 is vastgelegd waar die precies
op rust. Niet op de afwezigheid van inkomsten: dat is een feit over een
bankrekening en het overleeft geen verdienmodel. Wel op de afwezigheid van een
belanghebbende. Niemand betaalt voor de uitkomst die een huishouden krijgt.
Geen installateur, geen leverancier en geen fabrikant wordt er beter van als er
"wel een batterij" uit komt.

Elk stuk code dat het advies laat afhangen van een commerciele relatie is een
bug. Dat is de regel die de zin hierboven waar houdt, en hij geldt onverkort
als er wel geld binnenkomt.

Hoe Ampeer betaald gaat worden is een open vraag. De vier bovenstaande regels
gaan over producten en blijven staan; ze zeggen niets over een betaald rapport,
een abonnement of een white-label licentie, en die zijn geen van drieen in
strijd met de zin hierboven omdat de betaler daarbij geen belang heeft bij de
uitkomst. Doorverwijzing tegen vergoeding is dat wel, en dat is precies waarom
het onder "Later" staat en niet onder "Wat Ampeer doet": het kan eerlijk, maar
alleen als de site het zelf benoemt in plaats van het weg te laten.

De website mag daarom niet beweren dat er nooit geld verdiend wordt. Tot
2026-09-02 deed hij dat op vijf plaatsen. Wat er nu staat is wat vandaag waar
is, plus de belofte dat een verandering er eerst komt te staan.

## Fasering
- Fase 0: publieke rekenmachine, valideren of de vraag bestaat
- Fase 0.5: de adviseur op zelf-ingevoerde gegevens. Dit is de product-launch
- Fase 1 en 2: accounts en meterkoppeling, als upgrade
- Fase 3: uitbreiding van dezelfde simulatiemotor met echte data als invoer
- Later: dagplan, leads, white-label, 2029-module

De simulatiemotor uit fase 0.5 en fase 3 is een en dezelfde motor met andere invoer.
Bouw geen tweede.

De simulatiekern is een los Python-pakket `ampeer_sim/` dat Django niet importeert.
De CI dwingt dat af. Data komt binnen via ingespoten providers, de kern doet zelf
geen I/O. Reden: dit is het enige onderdeel waar een fout geen foutmelding geeft
maar een plausibel verkeerd getal, dus het moet zonder database en zonder server
te testen en te valideren zijn.

## Werkwijze en poorten
- Werk op `dev` of op een `feat/**`-branch, nooit direct op `main`
- Naar `main` gaat alleen een pull request waarvan alle vereiste checks groen zijn
- Elke nieuwe afhankelijkheid gaat via `uv add`, en `uv.lock` wordt meegecommit
- Elke GitHub Action staat op een commit-SHA, met de versie als comment erachter
- De jobnamen `quality`, `test`, `dependencies`, `sast` en `secrets` zijn een
  interface met de rulesets. Hernoem er nooit een zonder
  `scripts/setup_rulesets.sh` in dezelfde commit mee te wijzigen
- Draai `scripts/gates.sh` voordat je pusht. Het draait wat CI draait en het
  zegt erbij welke poorten het hier niet kon draaien. Beoordeel een poort op
  de exitcode, nooit op een grep over de uitvoer van een tool: op 21 augustus
  2026 filterde zo'n grep op "High" terwijl de bevinding Medium was, en een
  rode `sast` zag er lokaal groen uit
- De dekkingsdrempel mag omhoog en nooit omlaag, en `precision = 2` blijft staan:
  zonder die instelling rondt pytest-cov af voordat het vergelijkt en kan de
  poort niet rood worden. Controleer een wijziging op de exitcode, niet op het
  getoonde percentage

## Stack
- Backend: Django 5 + Django REST Framework, Python 3.12
- Database: PostgreSQL 16 + TimescaleDB (hypertables voor tijdreeksen)
- Async: Celery + Redis
- Frontend: Next.js 15 (App Router), TypeScript, Tailwind
- Deploy: Docker Compose, Cloudflare Tunnel in de eerste fase
- CI: GitHub Actions

## Repo-structuur
ampeer/
  backend/          Django project "ampeer"
  frontend/         Next.js
  infra/            docker-compose, nginx, tunnel config
  docs/             methodologie, aannames, DPIA
  .github/workflows/

## Conventies
- Code is Engels, applicatie is Nederlands. Dit is een harde scheiding:
  - Engels: functienamen, klassen, variabelen, modules, bestandsnamen, docstrings,
    comments, commit messages, testnamen, API-veldnamen, enum-keys, log messages
  - Nederlands: alles wat een gebruiker leest, inclusief adviesteksten, labels,
    foutmeldingen in de UI, e-mails en de inhoud van docs/methodologie.md
  - Nederlandse tekst hoort nooit hardcoded in de logica. Adviesteksten staan in
    een aparte laag (nl.py of een vertaalcatalogus), gekoppeld aan een Engelse
    regel-id, zodat de regeltabel taalvrij blijft
- Geen em-dashes in gebruikersgerichte teksten
- Geld is Decimal, energie is float. Dit is een harde scheiding:
  - Bedragen in euro's altijd Decimal, nooit float
  - Energiehoeveelheden in kWh zijn float (numpy-arrays in de simulatiekern),
    want ze komen uit meetreeksen en modellen met een onzekerheid van procenten;
    Decimal zou daar schijnprecisie zijn
  - De omzetting van kWh naar euro's gebeurt op precies een plek, aan de rand van
    de simulatiekern. Nergens anders staat een prijs naast een energiereeks
- Alle tijdstempels in UTC opslaan, in Europe/Amsterdam tonen
- Elke berekening logt de engine-versie mee
- Type hints verplicht in Python, strict mode in TypeScript

## Regels voor elk advies
- Nooit een enkel getal zonder bandbreedte
- Het betrouwbaarheidsniveau (indicatief, goed, precies) is altijd direct zichtbaar,
  niet weggeklikt in een voetnoot
- Elk advies geeft terug welke regels gevuurd hebben, zodat het uitlegbaar is
- De gratis routes (gedrag verschuiven, bestaande assets slimmer inzetten) worden
  altijd eerst getoond, ook als ze niets opleveren voor Ampeer
- "Nu geen batterij" is een geldige en verplichte uitkomst

## Security-eisen (altijd, elke fase)
- Argon2id password hashing
- JWT in httpOnly SameSite=Strict cookies, refresh token rotation
- django-axes tegen brute force
- Rate limiting op alle publieke endpoints
- Object-level permissions: elk queryset filtert op request.user, nooit alleen op pk
- GEEN outbound HTTP naar door de gebruiker aangeleverde URLs. Meterdata komt binnen
  via push, nooit via een fetch door de backend. Dit sluit SSRF categorisch uit.
  Uitzondering: een vaste, in de config vastgelegde allowlist van externe bronnen
  (PVGIS, ENTSO-E, KNMI). Die URLs worden nooit uit gebruikersinvoer opgebouwd;
  gebruikersinvoer levert alleen gevalideerde parameters.
- Ingest-tokens gehasht opslaan, nooit in plaintext
- Append-only audit log voor: login, koppeling aangemaakt, toestemming gegeven of
  ingetrokken, advies gegenereerd, lead verstuurd, data geexporteerd of verwijderd

## Privacy-eisen (altijd)
Kwartierdata over energieverbruik is een persoonsgegeven waaruit af te leiden is
wanneer iemand thuis is. Behandel het als zodanig.
- Toestemming voor datakoppeling en toestemming voor leadgeneratie zijn twee
  aparte, niet-voorgevinkte opt-ins met eigen timestamp in de database
- Ruwe kwartierdata automatisch verwijderen na 90 dagen, alleen uur-aggregaten bewaren
- Export- en verwijderknop werkend vanaf de fase waarin accounts bestaan
- Postcode alleen op 4 cijfers opslaan, nooit volledig
- Geen Google Analytics. Self-hosted Umami of Plausible.
