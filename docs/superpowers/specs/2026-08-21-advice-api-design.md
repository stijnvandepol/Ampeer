# Ontwerp: adviesAPI Ampeer (deelproject 3, onderdeel C)

Datum: 2026-08-21
Status: vastgesteld, klaar voor implementatieplan
Betreft: het Django-project in `backend/`, de drie endpoints en de opslag eromheen

## 1. Doel en afbakening

Een browser moet een advies kunnen opvragen op basis van vier tot negen antwoorden,
zonder account, en het resultaat later kunnen terugvinden via een deelbare link.

Binnen scope:

- Django 5 met Django REST Framework, project `ampeer` in `backend/`
- Drie endpoints: schatten, verfijnen, ophalen
- Opslag van een resultaat onder een willekeurig token, negentig dagen houdbaar
- Een cache voor PVGIS-antwoorden, zodat een bezoeker geen externe call afwacht
- Rate limiting op alle publieke endpoints
- Een append-only auditlog voor "advies gegenereerd"
- Nederlandse adviesteksten, want de API is de grens waar taal binnenkomt

Buiten scope, eigen deelproject:

- De frontend (deelproject 4)
- De LXC, de runner en de deploy (deelproject 2)
- Accounts, meterkoppeling en alles uit fase 1 en 2

## 2. Waar het komt te staan

`backend/` met daarin het Django-project, zoals `CLAUDE.md` voorschrijft. De twee
pure pakketten blijven staan waar ze staan, in de wortel, en worden gewoon
geïmporteerd.

Eén `pyproject.toml`, één lockfile, één omgeving, met de Django-afhankelijkheden in
een aparte dependency group. Twee losse projecten met twee lockfiles zou de enige
winst opleveren dat `ampeer_sim` los te installeren is, en dat is een winst die
niemand nodig heeft zolang alles in één repository zit.

De grens die er wél toe doet, namelijk dat de pure pakketten Django niet importeren,
wordt al afgedwongen door `tests/test_boundaries.py` en verandert hier niet. Die test
krijgt er wel een tegenhanger bij: `backend/` mag `ampeer_sim` en `ampeer_advice`
importeren, maar nooit andersom.

## 3. Synchroon, geen Celery

Gemeten op 2026-08-21: de bandbreedte over 243 combinaties kost 0,30 seconde, het
advies zelf 0,23. Met een gecachet PVGIS-antwoord blijft een verzoek daarmee ruim
onder de seconde.

Celery zou daar Redis, een worker, een taakstatus en een pollprotocol in de frontend
aan toevoegen, voor een rekentijd die een gebruiker niet als wachten ervaart. Dat is
vier bewegende delen erbij voor nul winst.

Deze keuze is gemeten en niet aangenomen, en hij wordt herzien wanneer een meting
zegt dat het moet. De drempel daarvoor staat hier zodat hij niet later verzonnen
wordt: als het negentigste percentiel van de responstijd boven de twee seconden komt,
gaat het rekenwerk naar een worker.

## 4. De PVGIS-cache staat in de database

Een cache-entry is een uurreeks van 8.760 waarden plus een temperatuurreeks, per
combinatie van postcode4, azimut, helling en weerjaar. Die combinaties herhalen zich
enorm: een postcodegebied heeft duizenden huizen en de meeste daken staan op een
handvol oriëntaties.

De cache staat in Postgres en niet in Redis, om twee redenen. Hij moet een herstart
overleven, anders betaalt de eerste bezoeker na elke deploy een externe call van
ruim een seconde. En het houdt Redis volledig uit het verzoekpad, wat één ding
minder is dat plat kan liggen op het moment dat er iemand op de site is.

Sleutel: `(postcode4, azimuth_deg, tilt_deg, weather_year)`. Waarde: beide reeksen,
gecomprimeerd opgeslagen. Geen vervaldatum: PVGIS-data over een afgesloten weerjaar
verandert niet. Wel een `fetched_at`, zodat een latere opschoning mogelijk blijft.

Bij een cache-misser wordt PVGIS bevraagd via de bestaande
`ResilientProductionProvider`, dus met de offline tabel als terugval. Een advies mag
nooit falen omdat een externe partij traag is, en dat gedrag zit al in de kern.

## 5. Opslag van een resultaat

Eén model, `StoredAdvice`:

| Veld | Waarom |
|---|---|
| `token` | 22 tekens uit `secrets.token_urlsafe(16)`, de deelbare sleutel |
| `created_at`, `expires_at` | `expires_at` is `created_at` plus negentig dagen |
| `inputs` | de gevalideerde antwoorden, zodat een advies te reproduceren is |
| `advice` | de uitkomst als JSON, inclusief `engine_version` en `advice_version` |

Geen naam, geen e-mailadres, geen volledige postcode. Het serializer-contract weigert
onbekende velden, dus er kan niets binnenkomen wat hier niet hoort.

Opruimen gebeurt met een management command, aangeroepen door cron, en niet met
Celery. Een dagelijkse `DELETE` over een tabel met een index op `expires_at` heeft
geen takenwachtrij nodig.

Het token is de enige toegang tot een resultaat. Dat is bewust: er is geen account
om aan te koppelen. Zestien willekeurige bytes zijn niet te raden, en er staat geen
persoonsgegeven in dat het raden de moeite waard maakt.

## 6. De endpoints

| Methode en pad | Invoer | Uitvoer |
|---|---|---|
| `POST /api/advice/estimate/` | vier velden | advies op niveau INDICATIEF, met token |
| `POST /api/advice/refine/` | negen velden | advies op niveau GOED, met token |
| `GET /api/advice/{token}/` | niets | hetzelfde advies |

Ronde 1 stelt vier vrágen, wat vijf waarden oplevert, omdat oriëntatie en helling
samen één vraag zijn over hetzelfde dak:

1. postcode, vier cijfers
2. wattpiek
3. dakoriëntatie en hellingshoek
4. jaarverbruik in kWh

Ronde 2 stelt er vijf bij: overdag thuis, EV met laadgedrag, warmtepomp,
contracttype, bestaande batterij met capaciteit. Negen vragen in totaal, en dat
aantal is wat het betrouwbaarheidsniveau bepaalt.

Beide POST-endpoints geven het volledige advies terug én slaan het op. De gebruiker
krijgt dus meteen antwoord en houdt een link over. Een aparte "maak aan" en "haal op"
zou een extra rondgang kosten voor niets.

Antwoordvorm, voor elk advies gelijk:

```json
{
  "token": "…",
  "confidence": "INDICATIVE",
  "headline": {"p10": "561.11", "p50": "700.08", "p90": "846.90", "runs": 243},
  "routes": [
    {"route": "SHIFT_BEHAVIOUR", "title": "…", "rules": [
      {"rule_id": "SHIFT_FLEXIBLE_LOAD", "text": "…", "saving_eur": "143.56"}
    ]}
  ],
  "battery": {
    "verdict": "BATTERY_DEPENDS_ON_PRICE",
    "sized_capacity_kwh": 7.0,
    "break_even_cost_per_kwh": "696.82",
    "payback_years": {"p10": "7.74", "p50": "11.62", "p90": "15.49"},
    "annual_saving_eur": "422.31",
    "curve": [[3.0, "…"], [5.0, "…"], [7.0, "…"], [10.0, "…"], [15.0, "…"]]
  },
  "engine_version": "0.1.0",
  "advice_version": "0.1.0",
  "production_source": "PVGIS",
  "profile_year": 2025,
  "weather_year": 2023
}
```

Drie eigenschappen van die vorm zijn niet onderhandelbaar, want ze staan in
`CLAUDE.md`:

- Er staat nooit een enkel bedrag zonder band. `headline` heeft geen veld dat alleen
  `p50` bevat
- `confidence` staat op het hoogste niveau van het antwoord, niet weggestopt
- De routes staan altijd in dezelfde volgorde, met de gratis routes eerst, ook als ze
  leeg zijn. Een lege route wordt meegestuurd en niet weggelaten, want de frontend
  mag de volgorde niet hoeven kennen

Bedragen gaan als string over de lijn, niet als getal. JSON kent alleen floats, en
een bedrag dat als float door een parser gaat is precies de fout die dit project
elders vermijdt.

## 7. Rate limiting

DRF `ScopedRateThrottle`, anoniem, op IP.

| Scope | Limiet | Reden |
|---|---|---|
| `advice-compute` | 20 per uur | Een berekening kost 0,5 seconde CPU. Twintig per uur is ruim voor een echt bezoek en te weinig om de machine te bezetten |
| `advice-read` | 120 per uur | Een link openen en delen moet kunnen zonder na te denken |

Bij een cache-misser kost een berekening bovendien een PVGIS-call, en die staat op
30 per seconde per IP aan hun kant. De limiet hierboven zit daar ruim onder, wat
tegelijk voorkomt dat Ampeer PVGIS overbelast.

## 8. Auditlog

`CLAUDE.md` eist een append-only auditlog voor onder meer "advies gegenereerd". Eén
model, `AuditEvent`, met een gebeurtenistype, een tijdstip en een JSON-veld met
context. Er staat geen persoonsgegeven in: wel het token en de postcode4, niet het
IP-adres.

Append-only wordt afgedwongen in de code: `save()` weigert een update van een
bestaande rij en `delete()` werpt een fout. Dat is geen bescherming tegen iemand met
databasetoegang en het is ook niet bedoeld om dat te zijn. Het is bescherming tegen
de gewone manier waarop een auditlog stukgaat, namelijk dat een latere ontwikkelaar
er een `update_or_create` op loslaat zonder er bij na te denken.

## 9. Instellingen en beveiliging

Gesplitst in `base`, `dev` en `prod`.

- `SECRET_KEY` uit de omgeving, zonder standaardwaarde in productie. Ontbreekt hij,
  dan start het proces niet
- `DEBUG` staat standaard uit en kan alleen in `dev` aan
- `ALLOWED_HOSTS` uit de omgeving, leeg is een fout
- In productie: HSTS, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS = DENY`
- Geen sessies of cookies op de adviesendpoints. Er is niets in te loggen, dus er is
  niets te stelen

De endpoints zijn anoniem en veranderen niets aan bestaande gegevens, dus CSRF is
hier geen risico. De middleware blijft wel staan voor de beheerinterface.

`django-axes` en Argon2 uit `CLAUDE.md` horen bij accounts en die bestaan hier nog
niet. Ze komen in fase 1, samen met het eerste wachtwoord. Ze nu installeren zou
beveiliging suggereren die niets bewaakt.

## 10. Database

PostgreSQL 16, ook in de tests, met een service container in CI.

Geen SQLite voor tests. Zodra het schema in de test anders is dan in productie wordt
een hele klasse fouten onzichtbaar, en dit project is er precies op gebouwd om geen
onzichtbare faalvormen te hebben.

TimescaleDB nog niet. Dat is er voor tijdreeksen per huishouden en die worden in fase
0.5 niet opgeslagen. De twee tabellen hier zijn gewone tabellen.

Gevolg voor de leverstraat: `ci.yml` krijgt een Postgres-service container in de
`test`-job. Zonder dat draaien deze tests nergens behalve op de machine van de
ontwikkelaar, en dan bewaakt de poort ze niet.

## 11. Testregime

1. **Contract per endpoint**: statuscode, vorm van het antwoord, en dat de drie
   routes altijd in dezelfde volgorde staan
2. **Validatie**: een onbekend veld wordt geweigerd, een postcode van zes cijfers
   wordt geweigerd, een negatief jaarverbruik wordt geweigerd
3. **Geen persoonsgegevens**: een test die het opgeslagen record doorloopt en faalt
   op elk veld dat op een naam, een e-mailadres of een volledige postcode lijkt
4. **Token**: twee verzoeken leveren verschillende tokens, een onbekend token geeft
   404, een verlopen token geeft 404 en niet 200 met oude inhoud
5. **Cache**: een tweede identiek verzoek doet geen tweede PVGIS-call, aangetoond met
   een provider die zijn aanroepen telt
6. **Rate limiting**: het eenentwintigste verzoek binnen een uur krijgt 429
7. **Auditlog**: elk gegenereerd advies levert precies één regel op, en een poging
   die regel te wijzigen of te verwijderen faalt
8. **De grens**: `ampeer_sim` en `ampeer_advice` importeren `backend` niet

## 12. Definition of done

- Een advies vanaf vier antwoorden binnen één seconde bij een gecachete opwekreeks
- Alle drie de endpoints werken zonder account en zonder cookie
- Een tweede identiek verzoek doet aantoonbaar geen tweede PVGIS-call
- Het opgeslagen record bevat geen persoonsgegeven, afgedwongen door een test
- Het eenentwintigste verzoek in een uur krijgt 429, aangetoond
- Dekking blijft 98 of hoger, `precision = 2` blijft staan
- `mypy --strict` blijft schoon over de twee pure pakketten en over `backend`

## 13. Blootstelling en privacy, ronde 2026-08-21

Elf punten uit een audit op de geïmplementeerde API. Alle elf zijn gemeten en
niet vermoed, en van elke nieuwe controle is aangetoond dat hij rood kan worden.
Wat hieronder staat is de reden, niet de wijziging: de wijziging staat in de
code en in de tests.

### 13.1 Het aantal proxies is verplicht, en ontbreken is fataal

`NUM_PROXIES` stond nergens. Zonder die instelling bouwt DRF de sleutel van zijn
snelheidslimiet uit de volledige `X-Forwarded-For` die de client zelf meestuurt,
dus elk verzoek met een andere header telde als een andere bezoeker. Gemeten op
2026-08-21: veertig verzoeken met een roterende header, nul keer een 429.

`prod.py` leest de waarde nu uit de omgeving zonder standaardwaarde, precies
zoals `SECRET_KEY`. Ontbreekt hij, dan start het proces niet. Dat is een
bewuste keuze tussen twee soorten falen: een proces dat weigert te starten
merkt iemand bij de eerste deploy, een snelheidslimiet die stilletjes uit staat
merkt niemand. `dev.py` zet de waarde op nul, want er staat geen proxy voor
`runserver` of voor de testclient, en `test.py` erft die nul. Nul is niet
hetzelfde als niet ingesteld: nul betekent negeer de header, niet ingesteld
betekent vertrouw de header.

De keuze om de waarde niet in `base.py` te zetten is dezelfde keuze: er bestaat
geen gedeelde standaard die klopt, want het getal is een eigenschap van de
proxyketen van één installatie.

### 13.2 Alleen JSON, en dus geen 500 voor een browser

De standaardlijst van DRF bevat `BrowsableAPIRenderer`, die een Django-template
rendert, en `TEMPLATES` is leeg. Elke browser die een gedeelde link opende
stuurde `Accept: text/html` en kreeg een `TemplateDoesNotExist`, dus een 500.
Dat is de kernstroom van dit product: iemand deelt een link.

`DEFAULT_RENDERER_CLASSES` staat nu vast op `JSONRenderer`. Dat lost het niet
alleen op, het voorkomt ook dat het ooit terugkomt als iets ergers: zodra
`TEMPLATES` wel ingevuld wordt, zou de standaardlijst een interactieve
API-console publiceren op drie anonieme publieke endpoints.

`DEFAULT_PARSER_CLASSES` is om dezelfde reden ingeperkt tot één parser. De
frontend stuurt JSON; een formulier-body is nooit een ondersteunde invoer
geweest, en `FormParser` en `MultiPartParser` zijn leesoppervlak dat geen enkele
aanroeper nodig heeft.

### 13.3 De teller van de snelheidslimiet staat in Postgres

`prod.py` had geen `CACHES`, dus gold Django's `LocMemCache`. Een teller in een
dictionary per proces is drie fouten tegelijk: de limiet geldt per worker in
plaats van per dienst, hij begint opnieuw bij elke deploy, en het geheugen is
begrensd op 300 ingangen, dus vanaf 400 verschillende sleutels wordt een derde
weggegooid op volgorde van sleutel, inclusief de geschiedenis van degene die ze
veroorzaakte.

Het wordt `DatabaseCache`. Postgres is er al, de teller moet gedeeld zijn en
moet een herstart overleven, en het besluit uit sectie 4 om Redis buiten het
verzoekpad te houden blijft staan. De prijs is eerlijk te noemen: een verzoek
kost nu een extra schrijfactie in de database.

Twee dingen zijn hierbij niet vanzelf goed gegaan en staan daarom expliciet in
de code. `MAX_ENTRIES` is bij Django op elke backend standaard 300, ook op
`DatabaseCache`, dus het verplaatsen van de teller naar Postgres zou het
weggooiprobleem gewoon hebben meegenomen. De waarde is opgehoogd tot een plafond
waarbij verval, en niet opruiming, de manier is waarop een ingang verdwijnt. En
de tabel wordt aangemaakt door een migratie in de `advice`-app en niet door een
handmatige `createcachetable`, want een stap in een draaiboek is een stap die
een deploy een keer overslaat.

### 13.4 Te diep geneste JSON is een 400 en geen 500

`json.load` werpt `RecursionError` bij invoer die welgevormd en te diep is, en
de `JSONParser` van DRF vangt alleen de fouten die het bij ongeldige invoer
werpt. `[` tweehonderdduizend keer is 200 kB en gaf onmiddellijk een 500, plus
een regel in het foutenlogboek voor wat een gewoon verkeerd verzoek is.

`advice/parsers.py` vangt het en antwoordt met een 400. De diepte zelf is niet
instelbaar gemaakt: de grens bestond al, in de vorm van de recursielimiet van de
interpreter. Wat ontbrak was het antwoord.

### 13.5 Een deploy met ontwikkelinstellingen kan niet meer onopgemerkt blijven

`wsgi.py` gebruikte `setdefault`, en daarmee wint een geëxporteerde
`DJANGO_SETTINGS_MODULE`. Eén regel in een unit-bestand of een compose-bestand
en het publieke verkeer wordt bediend met `DEBUG` aan, `ALLOWED_HOSTS` op
localhost en een `SECRET_KEY` die in deze repository staat uitgeschreven.

Twee wijzigingen, want ze dekken twee verschillende fouten. `wsgi.py` wijst de
module nu hard toe in plaats van met `setdefault`, wat de verkeerde module
categorisch uitsluit. En de `quality`-job draait `manage.py check --deploy
--fail-level WARNING` tegen diezelfde module, wat een fout in `prod.py` zelf
afvangt. Het faalniveau doet er evenveel toe als het commando: op het
standaardniveau drukt een waarschuwing over een ontbrekende beveiligingsheader
zichzelf af en eindigt de stap alsnog met nul.

Die controle vond er meteen een. `CsrfViewMiddleware` stond niet in `MIDDLEWARE`,
terwijl sectie 9 van dit document schrijft dat die middleware blijft staan. Het
document had gelijk en de code niet, dus de middleware staat er nu. Hij
beschermt vandaag niets, want DRF verpakt elke `APIView` in `csrf_exempt` en er
is geen sessie om op mee te liften, maar hij staat er voor de eerste view die
geen van beide is.

### 13.6 De bandit-onderdrukking is weer één onderdrukking

De uitleg stond achter de onderdrukkingsmarkering op dezelfde regel. Bandit
leest alles daarachter als een lijst met test-ids, dus de zin werd gelezen als
een reeks extra ids en de `sast`-job drukte voor elk woord een waarschuwing af.
Nagemeten op 2026-08-21 door de proza-versie terug te zetten: zeventien keer
"Test in comment: ... is not a test name or id". De audit meldde er zeven voor
de oorspronkelijke formulering; het aantal hangt af van de zin, de fout niet.
Dat de foutieve regel ook een onderdrukking met een lege id registreert is niet
zichtbaar in de uitvoer van bandit en is hier dus niet bevestigd. De uitleg
staat nu op eigen regels en achter de markering staat alleen nog `B105`. Bandit
draait schoon, met nul waarschuwingen en precies één onderdrukking.

Dat geldt ook voor het uitleggen van deze fout: geen enkele regel in dat bestand
schrijft de markering nog voluit in een zin, want dan begint het opnieuw. Dat is
tijdens deze ronde één keer gebeurd en door de controle zelf gevonden.

### 13.7 De poorten bewaken nu ook dat ze `backend/` lezen

`tests/test_pipeline_contract.py` controleerde dat `backend` in de bron van de
dekkingsmeting staat, maar niets controleerde de argumentlijsten van ruff, mypy
en bandit. `backend` van de bandit-regel halen zou de `sast`-check groen laten
over precies het deel van de boom dat al veilig was, terwijl de drie anonieme
publieke endpoints niet meer gescand worden, en niets zou dat melden.

De assertie staat nu naast die over de dekking, en leest de lijst met te dekken
mappen uit de boom in plaats van hem over te schrijven.

### 13.8 Het auditlogboek bewaart een hash en niet het token

`service.py` schreef `token=stored.token` in `AuditEvent.context`. Het token is
geen verwijzing naar het advies, het is de enige sleutel die het advies opent,
en `AuditEvent` is met opzet niet te verwijderen. Na de opschoning op negentig
dagen bleef er dus een permanente regel staan met een werkende link naar een
record dat weg had moeten zijn.

Er staat nu een SHA-256 in hex onder de naam `token_sha256`. Het doel van het
logboek overleeft dat volledig: er staat nog steeds wat de dienst gedaan heeft,
en wie de link legitiem heeft kan hem hashen en de regel terugvinden. De hash is
niet gezouten en niet gerekt, en dat is hier veilig om een reden die bij een
wachtwoord niet zou gelden: de invoer is 128 bits uit `secrets.token_urlsafe`,
dus er is geen woordenlijst om langs te lopen. Zouten zou juist de enige
eigenschap kapotmaken waar het om gaat.

### 13.9 De privacytest kijkt naar de waarden en niet naar de veldenlijst

De twee bestaande tests met "geen persoonsgegevens" in de naam lezen
`Model._meta.get_fields()`. Die lijst staat vast bij het importeren en kan dus
nooit `email` bevatten, wat er ook binnenkomt. Ze konden niet falen.

Sectie 11.3 vroeg om een test die het opgeslagen record dóórloopt. Die is er nu:
hij loopt recursief door `StoredAdvice.inputs`, `StoredAdvice.advice` en
`AuditEvent.context`, sleutels zowel als waarden, en faalt op iets dat op een
e-mailadres of op een volledige postcode lijkt.

De regels over lengte en witruimte gelden alleen voor `inputs` en voor de
auditcontext, en niet voor `advice`. Adviesteksten zijn met opzet proza, ze
staan in `ampeer_advice.nl` en komen niet van een aanroeper. In `inputs` en in
de auditcontext is niets proza: de langste legitieme waarde is de digest van 64
tekens en geen enkele waarde bevat een spatie. Dat is de grens, en hij is
uitgeschreven in plaats van geraden.

Aangetoond door een `email`-veld helemaal door de serializer heen toe te voegen.
De nieuwe test viel om; de twee oude bleven groen. Dat is precies de reden dat
ze vervangen moesten worden.

### 13.10 De PVGIS-cache heeft de sleutel die bij zijn data past

`postcode4_to_latlon` zoekt op `postcode4[:2]`, dus elke postcode binnen één
honderdtal krijgt een byte-identieke reeks. De cache stond op alle vier de
cijfers, en bewaarde die ene reeks van 60 kB dus opnieuw per buurt, voor altijd,
met een trefkans die twee ordes te laag lag.

De sleutel is nu het honderdtal. De kolom heet `postcode_area` en is twee tekens
breed, zodat niemand hem als een hele postcode4 kan lezen en niemand er een hele
postcode4 in kan zetten. De koppeling met `ampeer_sim` wordt niet aangenomen
maar getest: een test controleert dat drie postcodes uit één honderdtal
dezelfde coördinaten en dezelfde reeks opleveren, en wordt rood op het moment
dat `postcode4_to_latlon` ooit fijner gaat resolveren.

De migratie laat de tabel vallen en maakt hem opnieuw aan in plaats van de kolom
te hernoemen. De bestaande rijen zijn gesleuteld op iets dat niet meer betekent
wat het betekende en zouden onder de nieuwe sleutel met elkaar botsen. Het
verlies is één externe aanroep per honderdtal en oriëntatie die opnieuw gevraagd
wordt, en daar is een cache voor.

### 13.11 Twee kleinere

De foutmelding over onbekende velden gaf elke verkeerde sleutel terug. Een body
van een megabyte aan verschillende sleutels kwam terug als ruwweg twee en een
halve megabyte JSON, dus het endpoint versterkte wat een aanroeper er in stopte.
Er worden er nu tien genoemd, met daarachter een telling van de rest onder de
sleutel die DRF gebruikt voor een fout die niet bij één veld hoort. Tien, omdat
een formulier met negen velden er niet meer dan dat tegelijk fout kan hebben, en
omdat het noemen van het veld de hele reden is dat een onbekend veld geweigerd
wordt in plaats van genegeerd.

En elk antwoord van de drie endpoints draagt nu `Cache-Control: private,
no-store`. Elk van die antwoorden beschrijft één huishouden: het verbruik, het
dak en wat de energie kost. Een gedeelde proxy die er een kopie van bewaart geeft
de volgende bezoeker op dat adres de cijfers van iemand anders. Ook op de 400,
want die geeft de geweigerde antwoorden terug.
