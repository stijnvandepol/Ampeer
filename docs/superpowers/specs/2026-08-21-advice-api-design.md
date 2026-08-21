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
