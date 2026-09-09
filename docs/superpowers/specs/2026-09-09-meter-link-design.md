# Meterkoppeling: ontwerp

Fase 2 uit `CLAUDE.md`. Een huishouden koppelt zijn slimme meter, zijn P1-poort duwt
kwartierstanden naar Ampeer, die bewaart ze negentig dagen ruw en daarna alleen als
uurtotalen, en het huishouden kan de koppeling met een druk op de knop weer weghalen.

## 1. Doel en afbakening

Wat deze cyclus levert: een koppeling, een duwroute waarop metingen binnenkomen, opslag,
opruiming, intrekking, en de knoppen en zinnen die daarbij horen.

Wat deze cyclus niet levert, en dat is geen bezuiniging maar de fasering van `CLAUDE.md`
zelf: het advies blijft op het synthetische profiel draaien. Daar staat "Fase 3:
uitbreiding van dezelfde simulatiemotor met echte data als invoer", en dat is een aparte
cyclus met een eigen ontwerp. De weigering die daarvoor klaarligt, `refuse_unless_shareable`
in `backend/advice/series.py` met `year_field(..., shareable_token=False)` in
`backend/advice/serializers.py`, blijft dus onaangeraakt en ongebruikt.

Ook niet in deze cyclus: TimescaleDB. `CLAUDE.md` noemt het in de stack, de repository
gebruikt het nergens, en `infra/docker-compose.yml` draait `postgres:16-alpine`. Een
hypertable toevoegen is een wijziging aan de database van een draaiende dienst en die
hoort niet in dezelfde cyclus als de eerste tabel die hem zou vullen. Een gewone tabel met
een index op de twee kolommen waarop gezocht wordt is voor honderdduizenden rijen per
huishouden ruim genoeg; wanneer dat niet meer waar is, is dat een meting en een eigen
beslissing.

## 2. Wat een huishouden doet

1. Het geeft toestemming `METER_LINK` en bevestigt zijn e-mailadres. Beide bestaan al, en
   `frontend/src/app/_account/AccountPage.tsx` zegt vandaag al dat het tweede nodig is voor
   het eerste.
2. Het drukt op "Koppel uw meter". Ampeer maakt een koppeling en toont eenmalig een
   sleutel plus het adres waar zijn apparaat naartoe moet duwen.
3. Het zet die twee in zijn eigen apparaat. Elk apparaat dat kan POST'en voldoet: een
   HomeWizard P1-meter, een dongle, Home Assistant, een script. Ampeer schrijft geen
   merk voor en haalt zelf nooit iets op.
4. Het ziet op zijn accountpagina wanneer er voor het laatst iets binnenkwam.
5. Het drukt op "Ontkoppel", of trekt `METER_LINK` in. Beide doen hetzelfde: de sleutel
   werkt niet meer en de metingen zijn weg.

## 3. De koppeling

`MeterLink`, in `backend/accounts/models.py` naast de andere tabellen die een account
beschrijven:

- `user`, een `ForeignKey` met `on_delete=CASCADE`.
- `token_sha256`, `CharField(max_length=64, unique=True, db_index=True)`. De sleutel zelf
  wordt nooit opgeslagen, precies zoals `RefreshSession` en `OneTimeToken` het doen, met
  dezelfde `token_digest` uit `backend/advice/models.py`.
- `created_at`, `revoked_at` (nullable), `last_seen_at` (nullable).
- `is_active`, een property: `revoked_at is None`.

Er staat geen EAN-code, geen meternummer en geen adres in. Ampeer heeft ze niet nodig om
een reeks getallen bij een account te leggen, en een identificerend gegeven dat nergens
voor dient is een gegeven dat niet verzameld hoort te worden.

De sleutel is `secrets.token_urlsafe(32)`, drieënveertig tekens, en wordt precies één keer
getoond: in het antwoord op de aanmaak. Daarna kent Ampeer alleen de afdruk. Wie hem
kwijtraakt ontkoppelt en koppelt opnieuw; dat is één druk op de knop en het is eerlijker
dan een sleutel die te heropvragen is.

Eén actieve koppeling per account. Een tweede aanmaak trekt de eerste in, in dezelfde
transactie, en dat is ook wat een huishouden verwacht dat "opnieuw koppelen" doet.

## 4. De routes

Drie routes horen bij de sessie en staan onder `/api/auth/`, naast de dertien die er al zijn:

- `GET /api/auth/meter/` geeft de toestand: of koppelen mag, of er een koppeling is,
  wanneer die is gemaakt en wanneer er voor het laatst iets binnenkwam.
- `POST /api/auth/meter/link/` maakt er een en geeft de sleutel eenmalig terug.
- `POST /api/auth/meter/unlink/` trekt hem in en verwijdert de metingen.

De vierde route hoort niet bij een sessie en staat er dus buiten.

`GET /api/auth/meter/` staat op de bestaande scope `auth-read`, de twee POST-routes op
`auth-write`. Er komt geen nieuwe scope voor deze drie bij; ze doen wat de bestaande
scopes beschrijven en een aparte scope zou het plafond onnodig verschuiven.

De toestand komt met een eigen route terug en niet als veld op `me/`, zodat het
antwoord op `me/` en zijn vormcontrole in `accounts.ts` blijven zoals ze zijn.

### De duwroute

`POST /api/meter/readings/`, buiten `/api/auth/` omdat er geen sessie aan te pas komt.

**Authenticatie.** Een `MeterTokenAuthentication` leest de sleutel uit de header
`Authorization: Meter <sleutel>`, hasht hem en zoekt de actieve koppeling. Geen cookie,
geen CSRF: een apparaat heeft geen browser, en de route verandert niets aan een sessie.
Onbekend, ingetrokken of ontbrekend levert 401 met de zin uit `nl.py`.

**Het lichaam** is JSON:

```text
{"readings": [{"measured_at": "2026-09-09T10:15:00Z", "consumption_kwh": "0.243", "feed_in_kwh": "0.000"}, ...]}
```

Ten hoogste honderd metingen per verzoek. `measured_at` staat in UTC en op een kwartier;
iets ertussenin is een 400 onder dat veld. De twee hoeveelheden zijn kilowattuur over dat
kwartier, niet een meterstand, en niet negatief.

**Idempotent.** Een `UniqueConstraint` op `(link, measured_at)` en een schrijfactie die
bestaande rijen overslaat. Een apparaat dat na een storing zijn buffer opnieuw stuurt,
stuurt dus geen dubbele werkelijkheid. Het antwoord is 202 met het aantal opgeslagen en
het aantal overgeslagen metingen, zodat een apparaat kan zien dat het aankwam.

**Tempo.** Een nieuwe scope `meter-ingest` op `120/hour`. Een apparaat dat elk kwartier
duwt doet vier verzoeken per uur; honderdtwintig laat een dagbuffer en een reeks
herhalingen toe zonder dat de limiet in de weg zit. De som van alle scopes gaat daarmee
van 490 naar 610 per uur, oftewel 0,16944 verzoeken per seconde, en het plafond van tien
per seconde in `infra/nginx/nginx.conf` blijft daar 59 keer boven. `tests/test_nginx_config.py`
eist vijftig keer, dus dat houdt, en de test rekent het zelf uit in plaats van het te
geloven.

## 5. De metingen

`QuarterReading`: `link` (CASCADE), `measured_at`, `consumption_kwh`, `feed_in_kwh`. Twee
floats, want dit is energie en geen geld. Index op `(link, measured_at)`, en die dubbele
kolom is ook de unieke sleutel.

`HourAggregate`: `link` (CASCADE), `hour_start`, `consumption_kwh`, `feed_in_kwh`,
`quarters` (hoeveel kwartieren erin zaten, één tot vier). Uniek op `(link, hour_start)`.

De opruiming is een management command `purge_meter_readings`, naast de twee die er al
zijn en met dezelfde vorm: het telt de kwartieren ouder dan negentig dagen op tot uren,
schrijft die uren weg, verwijdert daarna de kwartieren, en zegt in één regel hoeveel van
elk. `--check` verstuurt niets en geeft een exitcode die rood is zodra er kwartieren
liggen die ouder zijn dan negentig dagen en één, want dan draait de timer niet meer. Een
uur waarvan niet alle vier de kwartieren aankwamen wordt bewaard met `quarters` op wat er
was; weggooien zou een gat maken waar een gedeeltelijke waarheid past.

Een systemd-timer draait hem dagelijks, zoals `ampeer-purge` dat doet.

## 6. Intrekken en verwijderen

Ontkoppelen zet `revoked_at` en verwijdert in dezelfde transactie elke `QuarterReading` en
elke `HourAggregate` van die koppeling. Het intrekken van `METER_LINK` doet precies
hetzelfde, want een toestemming intrekken moet even makkelijk zijn als hem geven en het
zou raar zijn als de gegevens daarna bleven staan.

`export_account` in `backend/accounts/service.py` krijgt de koppeling erbij: wanneer ze is
gemaakt, wanneer voor het laatst iets binnenkwam, de uurtotalen en de kwartieren. Het is
hun data en artikel 15 vraagt erom; de sleutel staat er niet in, want die kent Ampeer niet.

`delete_account` hoeft niets nieuws te doen: `CASCADE` neemt de koppeling en daarmee de
metingen mee, en `tests/test_accounts_privacy.py` controleert dat door de rijen te tellen.

## 7. Het logboek

Twee nieuwe soorten in `AuditEvent`: `METER_LINKED` en `METER_UNLINKED`, allebei met
`user_id` en niets anders. Dat is wat `CLAUDE.md` vraagt ("koppeling aangemaakt").

Er komt geen regel per binnengekomen meting. Die tabel wordt nooit opgeruimd, en een regel
per kwartier zou hem met tienduizenden rijen per huishouden per jaar vullen zonder dat er
één vraag mee te beantwoorden is. Wanneer er voor het laatst iets binnenkwam staat op de
koppeling zelf, in `last_seen_at`, en dat verdwijnt met de koppeling.

`docs/dpia.md` hoofdstuk 2 beschrijft de twee soorten in dezelfde commit als de constanten,
want `tests/test_dpia.py` bindt die twee aan elkaar.

## 8. Het scherm

Op `/account/`, onder de toestemmingen, een blok "Uw slimme meter" met drie toestanden:

- **Niet gekoppeld en niet mogelijk.** De zin die er al staat, dat een bevestigd adres en
  toestemming nodig zijn, met daarbij wat er ontbreekt.
- **Niet gekoppeld en mogelijk.** Een knop "Koppel uw meter". Na het indrukken verschijnt
  de sleutel, het duwadres, en de zin dat de sleutel hierna niet meer te zien is.
- **Gekoppeld.** Wanneer er voor het laatst iets binnenkwam, of dat er nog niets binnenkwam,
  en een knop "Ontkoppel" die vraagt of het zeker is en erbij zegt dat de metingen dan weg
  zijn.

Geen grafiek, geen getal over het verbruik zelf. Deze cyclus koppelt; wat er met de data
gebeurt is Fase 3, en een grafiek zou beloven dat het advies er al iets mee doet.

## 9. Taal

Elke zin die een huishouden leest staat in `nl.py` als de API hem zegt, en in
`frontend/tests/ui-strings.txt` als de pagina hem zegt. De nieuwe sleutels in `nl.py`:
`meter_token_invalid`, `meter_not_allowed` (geen toestemming of geen bevestigd adres),
`meter_reading_invalid`, `meter_batch_too_large`. Geen em-dash, "u", en de meldingen
benoemen de situatie zonder iemand aan te spreken, zoals de eerste categorie daar voorschrijft.

## 10. Bewijs

- **Laag 1, Python.** De koppeling (aanmaken, tweede aanmaak trekt de eerste in, de sleutel
  komt één keer terug en staat nergens in een kolom), de authenticatie (onbekend,
  ingetrokken, ontbrekend, verkeerde vorm), het lichaam (te groot, geen kwartier, negatief,
  dubbel), de idempotentie, de opruiming onder een vaste klok, `--check`, het intrekken langs
  beide wegen, de export, en dat `CASCADE` alles meeneemt. Elke nieuwe controle krijgt een
  rood bewijs.
- **Laag 2, Vitest.** De vier aanroepen in `accounts.ts` met hun vormcontroles, en de drie
  toestanden van het blok.
- **Laag 3, Playwright.** De ronde in de browser met gemockte API, axe op de nieuwe toestand
  in beide paletten, en geen Engels op het scherm.
- **Laag 4, contract.** `tests/test_frontend_contract.py` legt de paden die `accounts.ts`
  aanroept naast `urls.py`; de nieuwe route hoort daar dus bij.
- **Laag 5, de echte stack.** Een live check die een koppeling maakt, met de sleutel duwt,
  de meting terugleest, ontkoppelt en ziet dat ze weg is.

## 11. Wat er expliciet niet in zit

Geen wijziging aan de simulatiemotor of aan het advies. Geen TimescaleDB. Geen grafiek.
Geen tweede koppeling per account. Geen sleutel die opnieuw te tonen is. Geen ophaalrichting:
Ampeer duwt niets en haalt niets, en `tests/test_boundaries.py` blijft daarom precies zoals
hij is, met dezelfde drie bestemmingen.

## 12. Definition of done

Een huishouden met een bevestigd adres en toestemming koppelt, duwt met de sleutel een
kwartier naar binnen, ziet op zijn accountpagina dat er iets binnenkwam, exporteert het,
ontkoppelt, en ziet dat het weg is. De opruiming maakt van kwartieren ouder dan negentig
dagen uurtotalen en verwijdert de kwartieren. Elke poort is groen, de dekkingsdrempels
staan waar ze stonden of hoger, en `docs/dpia.md`, `docs/verwerkersregister.md` en
`docs/decisions.md` beschrijven wat er nu draait.

## 13. Beslissingen die dit ontwerp vastlegt

1. De meterkoppeling koppelt, en het advies blijft synthetisch tot Fase 3.
2. Geen TimescaleDB in de cyclus die de eerste tijdreeks aanmaakt.
3. Metingen komen binnen op een eigen route met een eigen sleutel, buiten de sessie om.
4. De sleutel wordt één keer getoond en daarna alleen als afdruk bewaard.
5. Eén actieve koppeling per account, en opnieuw koppelen trekt de vorige in.
6. Het logboek krijgt twee soorten en geen regel per meting.
7. Intrekken van de toestemming verwijdert de metingen, niet alleen de toegang.
