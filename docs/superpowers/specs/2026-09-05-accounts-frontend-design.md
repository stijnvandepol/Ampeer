# Ontwerp: frontend accounts (fase 1, deel 2)

Datum: 2026-09-05
Status: vastgesteld, klaar voor implementatieplan
Betreft: `frontend/`, de ene nieuwe route `/account/`, een tweede API-client ernaast, en de
enige wijziging die dit deelproject in `backend/accounts/` aanbrengt

## 1. Doel en afbakening

Iemand die een account wil, moet er een kunnen aanmaken, kunnen inloggen, zijn twee
toestemmingen kunnen zien en omzetten, zijn gegevens kunnen downloaden, en zijn account kunnen
verwijderen. Meer niet.

Dit is de schermkant van `docs/superpowers/specs/2026-09-04-accounts-auth-design.md`. Dat
ontwerp bouwde acht routes onder `/api/auth/` en zei er in hoofdstuk 11 bij dat er geen
dashboard komt, geen adviesgeschiedenis en geen overzichtspagina. Die zin geldt hier
onverkort: dit deelproject bouwt de bediening van die acht routes en geen product eromheen.

Binnen scope:

- Eén route, `/account/`, met drie weergaven op één pagina
- `frontend/src/lib/accounts.ts`, een tweede client naast `api.ts`
- De ene backend-wijziging die de toestemmingstekst uit de API haalt in plaats van uit de
  frontend, plus het veld dat die tekst aan de vastgelegde rij knoopt
- Toegankelijkheid en de taalgrens, allebei als poort en niet als voornemen

Buiten scope, eigen deelproject:

- De meterkoppeling, de P1-ingest en alles wat kwartierdata aanraakt (fase 2 en 3)
- Wachtwoordherstel en e-mailverificatie, om de reden in hoofdstuk 10 van het
  auth-ontwerp: dat is een SMTP-beslissing met een klein staartje code, en niet andersom
- Een ingelogd-indicator in de kop van de site, zie hoofdstuk 10

De rekenmachine en de adviseur blijven volledig anoniem. Niets in dit deelproject raakt
`estimate/`, `refine/` of de tokenroute aan, en niets erin vraagt een bezoeker om een account
voordat hij een antwoord krijgt.

## 2. De architectuurbeslissing: statisch, cookie-blind, en `me/` als enige waarheid

Deze drie eigenschappen zijn geen voorkeur. Ze volgen uit wat er al staat, en samen bepalen ze
de hele vorm van dit deelproject.

**De site wordt statisch geëxporteerd.** Er draait in productie geen Node-proces, dus er is
per verzoek geen server die iets kan afschermen. Een `middleware.ts` die een route achter een
login zet bestaat hier niet en kan hier niet bestaan: `out/account/index.html` is een bestand
dat nginx uitlevert aan iedereen die erom vraagt. Elke pagina laadt dus voor iedereen, en
vraagt daarna aan de API wie er is.

**De cookies zijn httpOnly.** `ampeer_access` en `ampeer_refresh` zijn met opzet onleesbaar
voor JavaScript (hoofdstuk 5.2 van het auth-ontwerp). De frontend kan dus niet zelf vaststellen
of er iemand is ingelogd. Er is geen vlag in `localStorage` en geen vlag in `sessionStorage`,
en dat is geen zuinigheid: een lokale vlag die zegt "ingelogd" terwijl het access-token
verlopen is, is een scherm dat iets belooft wat de volgende aanroep weerspreekt.

**Dus is `GET /api/auth/me/` de enige waarheid.** 200 betekent de accountweergave, 401 de
inlogweergave. Bij elke lading opnieuw, en nergens anders vandaan.

Dat die aanroep er toch al stond is bovendien de voorwaarde voor iets anders. `_AuthAPIView`
zet in `finalize_response` het CSRF-token, ook op een 401 en een 403, precies omdat een
frontend met httpOnly cookies geen andere manier heeft om te weten of er iemand is ingelogd.
De 401 op `me/` is dus tegelijk de aanroep die de `csrftoken`-cookie ophaalt waarmee de
inlogpost verstuurd kan worden. **De volgorde is daarmee dwingend: er wordt nooit gepost naar
`register/`, `login/` of `refresh/` voordat de eerste `me/` is teruggekomen.** Andersom is het
een 403 met `csrf_failed`, op de eerste handeling van elke nieuwe bezoeker.

### 2.1 De ene uitzondering op "geen retry"

`api.ts` opent met een blok in kapitalen: er wordt hier op geen enkele status opnieuw
geprobeerd. Die regel blijft staan en `accounts.ts` neemt hem letterlijk over, met één
uitzondering die geen retry is.

Een 401 op `me/` **bij het laden van de pagina** probeert éénmaal `POST refresh/` en daarna
éénmaal `GET me/`. Dat is geen herhaling van hetzelfde verzoek: het access-token leeft vijftien
minuten en het refresh-token veertien dagen, dus zonder deze wissel is een refresh-token van
veertien dagen zinloos vanaf minuut zestien. Het tweede verzoek stelt bovendien een andere
vraag dan het eerste, want er ligt een ander credential onder.

Waarom een tweede 401 het einde is, en niet een derde poging: na een geslaagde rotatie heeft de
server zojuist een nieuw access-cookie gezet. Antwoordt `me/` dan alsnog 401, dan wordt dat
cookie niet aanvaard, en dat is een fout in de configuratie of in de server en niet iets wat
een volgende poging oplost. Doorgaan zou bovendien per paginalading opnieuw roteren, wat de
`auth-refresh`-emmer van 60 per uur leegtrekt en, zodra een al ingewisseld token nog eens wordt
aangeboden, hoofdstuk 5.3 van het auth-ontwerp in werking zet: dat is hergebruik, en het
antwoord daarop is dat alle sessies van die gebruiker worden ingetrokken. Een client die blijft
proberen logt de gebruiker dus overal uit.

Een 401 **later in de sessie**, op welke route dan ook, wisselt niets in en toont gewoon de
inlogweergave. Er is precies één plek in de code waar de wissel staat, en het is de
laadfunctie.

Alleen een 401 zet de wissel in gang. Een verzoek dat helemaal niet aankomt is geen 401: er is
dan geen antwoord, dus ook geen uitspraak over wie er is ingelogd. Zie 6.5.

### 2.2 `SameSite=Strict` werkt hier, en waarom dat niet vanzelf spreekt

In productie serveert `infra/nginx/nginx.conf` de statische export en proxyt hij `/api/` binnen
hetzelfde serverblok, en `.github/workflows/deploy.yml` bouwt met een lege
`NEXT_PUBLIC_API_BASE` zodat de client relatieve paden gebruikt. Eén oorsprong, dus `Strict`
kost niets en levert de sterkste CSRF-verdediging die er is.

Op een ontwikkelmachine is `localhost:3000` naar `127.0.0.1:8000` cross-site en stuurt de
browser de cookies niet mee. Daarvoor bestaat de uitzondering in `dev.py`
(`CORS_ALLOW_CREDENTIALS = True`, alleen voor de drie oorsprongen die daar al staan), met de
test die `prod.CORS_ALLOW_CREDENTIALS is False` afdwingt. Dit deelproject verandert daar niets
aan en leunt erop; wie lokaal inlogt en het niet ziet werken, moet die instelling nagaan
voordat hij de client verdenkt.

## 3. Routes en ingang

| Pad | Wat het is |
|---|---|
| `/account/` | Inloggen, registreren, of het account. Eén route, drie weergaven. |

Eén route en niet drie. `/account/inloggen/` en `/account/registreren/` zouden twee statisch
geëxporteerde pagina's zijn die allebei precies dezelfde vraag aan `me/` stellen om te weten
welke van de twee ze mogen tonen, plus een derde die dat ook doet. De keuze tussen de drie
weergaven is toestand en geen adres.

**De ingang is één stille link in de voettekst,** naast "Hoe Ampeer rekent", "Over ons" en
"Privacy". De kop van de site verandert niet en op `/advies/` komt niets.

Dat is regel 5 uit `docs/superpowers/specs/2026-08-21-frontend-design.md`: er zijn precies twee
soorten oproep tot actie, "verfijn uw antwoord" en "bewaar deze link", en er is geen derde.
"Maak een account aan" op de adviespagina zou de derde zijn. De voettekst is bovendien waar een
bezoeker een account zoekt, en een account is in fase 1 geen aanbod maar een voorziening: er
hangt nog niets aan wat het advies beter maakt.

`/account/` komt **niet** in `SITEMAP_ROUTES`. Een inlogformulier is geen antwoord op een
zoekvraag, en de sitemap is de lijst waarvan dit product zegt dat hij hem geïndexeerd wil
hebben. De twee tests die de sitemaplengte vergelijken lezen die constante, dus ze blijven
groen zonder wijziging.

De statisch geëxporteerde `/account/index.html` draagt wél een `<h1>` en één alinea die zeggen
wat deze pagina is. Op 2026-09-02 bleek `/berekenen/` zonder JavaScript nul koppen en 32
woorden te bevatten, allemaal kop en voettekst, en `e2e/form.spec.ts` bewaakt dat sindsdien.
Dezelfde fout hier zou goedkoper zijn (deze pagina hoeft door niemand gevonden te worden), maar
een blanco `main` is ook voor een bezoeker met een trage verbinding het verkeerde antwoord. De
laadtoestand is een zichtbare zin en niet een leeg element.

## 4. De client: `frontend/src/lib/accounts.ts`

`api.ts` blijft ongewijzigd, met zijn `credentials: "omit"` die daar met opzet ná de spread
staat zodat geen aanroeper hem per ongeluk aanzet. Die belofte is waar over de adviesAPI en
moet waar blijven: er is daar geen sessie, dus er is niets te sturen en niets te stelen.

De accountclient is het tegenovergestelde en staat daarom apart:

- `credentials: "include"` op **elke** aanroep, ook op de GET's. Zonder dat reist de
  access-cookie niet mee en is elk antwoord een 401.
- Bij elke onveilige methode wordt de `csrftoken`-cookie gelezen en als `X-CSRFToken`
  meegestuurd. Die cookie is met opzet niet httpOnly (`CSRF_COOKIE_HTTPONLY = False`): een
  double-submit-token dat JavaScript niet kan lezen kan JavaScript ook niet meesturen.
- Geen retry, op geen enkele status, met de ene uitzondering uit 2.1 die niet in deze module
  staat maar in de laadfunctie die haar aanroept.
- Elk antwoord wordt op vorm gecontroleerd voordat het een waarde wordt, zoals `isAdvice` dat
  doet en om dezelfde reden: er staat geen error boundary boven deze pagina, dus een veld dat
  hernoemd is levert geen melding op maar een leeg scherm.

### 4.1 Eén `ApiError`, en één gedupliceerde reductie

`ApiError` wordt geïmporteerd uit `@/lib/api` en niet opnieuw gedefinieerd. Twee klassen met
dezelfde naam maken `error instanceof ApiError` afhankelijk van welke module de aanroeper
importeerde, en dan geeft `fieldMessages` uit `_flow/messages.ts` stilzwijgend niets terug voor
een fout die er wel een heeft.

`readErrorBody` is in `api.ts` niet geëxporteerd. Er komt dus een tweede exemplaar in
`accounts.ts`, en dat is een bewuste kopie met een prijs. De alternatieven zijn allebei
slechter: `api.ts` aanpassen om de functie te exporteren raakt het bestand dat
`frontend/CLAUDE.md` juist op slot zet, en een derde module waar beide uit lezen doet dat ook.
De kopie wordt daarom niet met een belofte bijgehouden maar met een test: één tabel met
foutlichamen wordt door beide reducties gehaald en de uitkomsten moeten gelijk zijn. Verschuift
er een, dan is dat rood in `tests/lib/accounts.test.ts`. Komt er ooit een derde client, dan is
dat het moment om de gedeelde module alsnog te maken.

`fieldMessages` zelf wordt uit `_flow/messages.ts` geïmporteerd en niet nog eens geschreven, want
dat is precies de functie waar de redenering hierboven over één `ApiError` over gaat: alleen
`readErrorBody` bestaat twee keer.

### 4.2 De negen aanroepen, met hun antwoordvorm

Dit is wat de vormcontrole per route moet vaststellen. `void` betekent dat het antwoord geen
lichaam heeft en dat de status plus de cookies het hele resultaat zijn; die antwoorden worden
**niet** door `response.json()` gehaald, want dat werpt op een 204.

| Methode en pad | Verzoek | Goed | Vorm die gecontroleerd wordt |
|---|---|---|---|
| `GET /api/auth/consent-texts/` | geen | 200 | `{ text_version: string, texts: { METER_LINK: string, LEAD_GENERATION: string } }`, alle drie niet leeg |
| `POST /api/auth/register/` | `{ email, password, consent_meter_link: boolean, consent_lead_generation: boolean, text_version }` | 201 | `void` |
| `POST /api/auth/login/` | `{ email, password }` | 200 | `void` |
| `POST /api/auth/refresh/` | geen | 200 | `void` |
| `GET /api/auth/me/` | geen | 200 | `{ email: string, consents: { METER_LINK: boolean, LEAD_GENERATION: boolean } }` |
| `POST /api/auth/consent/` | `{ kind, action, text_version? }` | 200 | `{ kind: string, granted: boolean }`, waarbij `kind` de verstuurde `kind` is |
| `POST /api/auth/export/` | geen | 200 | `{ email: string, date_joined: string, consents: Array<{ kind, action, occurred_at, text_version }>, advices: Array<{ inputs, advice }> }` |
| `POST /api/auth/logout/` | geen | 204 | `void` |
| `POST /api/auth/delete/` | `{ password }` | 204 | `void` |

Drie dingen die deze tabel vastlegt en die anders geraden zouden worden:

**`consents` is een object met precies de twee soorten die de pagina toont.** De namen zijn de
waarden van `Consent.KINDS` in `backend/accounts/models.py`, en `MeView` bouwt het antwoord met
`sorted(Consent.KINDS)`. De vormcontrole eist dat beide sleutels bestaan en booleans zijn, en
weigert een derde sleutel niet: een derde soort toestemming die de frontend nergens toont is
drift die aan de kant hoort te vallen waar hij ontstaat, en daarvoor staat de contracttest in
hoofdstuk 9 punt 4.

**`advices` wordt niet dieper gecontroleerd dan "een object met `inputs` en `advice`".** De
inhoud is de opgeslagen advies-JSON die de export ongewijzigd doorgeeft. Een tweede exemplaar
van `isAdvice` daarop loslaten zou een geldige export kunnen weigeren omdat de frontend nog
niet weet van een veld dat de motor is gaan sturen, en dat is precies de verkeerde kant om die
fout te laten vallen.

**Het exportlichaam wordt één keer als tekst gelezen.** De download krijgt die tekst
ongewijzigd, en de vormcontrole draait op `JSON.parse` daarvan. Niet parsen en opnieuw
serialiseren: elk bedrag in een advies is een string omdat JSON alleen floats kent, en een
extra rondje door een parser is precies de fout die dit project overal elders vermijdt. Er
staat een semgrep-regel op `parseFloat` over een bedrag, en die zou hier niets zien, want het
zou een `JSON.stringify` van een geparste boom zijn die het stilletjes doet.

Fouten worden gereduceerd zoals `api.ts` dat doet: `{ veld: [melding] }` uit DRF wordt
`fields`, een `{"detail": "..."}` wordt de boodschap. Een 429 draagt een `detail` en die wordt
letterlijk getoond, want de API weet hoe lang het duurt en de frontend niet.

Een `ApiError` uit `accounts.ts` draagt een lege `message` als de API geen `detail` stuurde, zodat
`describeAuthError` de Engelse standaardboodschap van `ApiError` zelf (`api.ts`'s eigen
`` advice API returned ${status} ``) nooit aan een huishouden toont.

## 5. De ene backend-wijziging

De toestemmingstekst is Nederlands, staat in `backend/accounts/nl.py`, en wordt met
`CONSENT_TEXT_VERSION` op elke `Consent`-rij vastgelegd. Die kolom bestaat om artikel 7 lid 1
AVG te kunnen beantwoorden: aantonen waarvoor toestemming is gegeven.

Zou de frontend die zin overschrijven, dan bewijst die kolom niets. Er zouden twee teksten
zijn, de rij zou naar de ene wijzen en het scherm de andere hebben getoond, en niets zou dat
verschil kunnen zien. Dat is ook precies wat de taalgrens uit `CLAUDE.md` verbiedt: een zin die
een huishouden toespreekt hoort niet in de logica.

### 5.1 `GET /api/auth/consent-texts/`

Een negende route onder `/api/auth/`, publiek, zonder authenticatieklasse en met
`permission_classes = (AllowAny,)`, op `throttle_scope = "auth-read"`. Dezelfde scope als
`me/`, om dezelfde reden: dit is een aanroep aan het begin van een paginalading en 120 per uur
is daar de maat voor. Een eigen scope zou een zevende `auth`-tarief in
`DEFAULT_THROTTLE_RATES` zijn voor een antwoord dat geen database raakt en voor iedereen
hetzelfde is.

Het antwoord:

```json
{
  "text_version": "2026-09-04",
  "texts": {
    "LEAD_GENERATION": "Ik geef Ampeer toestemming om mijn gegevens door te geven ...",
    "METER_LINK": "Ik geef Ampeer toestemming om de kwartiergegevens van mijn slimme meter ..."
  }
}
```

`text_version` en niet `version`: het veld heet zo in de kolom, in het verzoeklichaam en hier,
en één naam voor één ding op drie plaatsen is wat een vergelijking mogelijk maakt. De sleutels
onder `texts` zijn `sorted(Consent.KINDS)`, en de waarden zijn `NL["CONSENT_" + kind]` uit
`nl.py`, letterlijk. De view stelt niets samen en formatteert niets.

De route erft van `_AuthAPIView`, dus hij draagt `Cache-Control: private, no-store` en zet het
CSRF-token in `finalize_response`. Dat eerste is hier strikt genomen te streng, want dit
antwoord beschrijft geen huishouden; het staat er omdat een uitzondering op de basisklasse voor
één route de basisklasse zwakker maakt dan hij nu is, en een cache die dit niet bewaart kost
niets.

Dit blijft een API die uitsluitend `get` en `post` beantwoordt, dus
`tests/test_dpia.py::test_the_api_answers_only_the_verbs_the_document_describes` blijft groen
op een ware zin. Wat wél moet veranderen is de prosa: `docs/dpia.md` regel 358 zegt "acht
routes" en dat worden er negen, in dezelfde commit.

### 5.2 `text_version` in het verzoek, en de 400 die de garantie sluit

`RegisterSerializer` en `ConsentSerializer` krijgen een veld `text_version`. Is de waarde niet
`CONSENT_TEXT_VERSION`, dan is het antwoord een 400 met een melding onder de veldnaam
`text_version`.

Daarmee kan een gebruiker nooit instemmen met tekst N terwijl de rij N+1 vastlegt. Het gat is
klein en echt: een tabblad dat een uur openstaat terwijl de tekst wordt herschreven en opnieuw
uitgerold, en dan schrijft `Consent.record` de nieuwe versie op een rij waarvan de gebruiker de
oude zin heeft gelezen. Het model verandert niet: `Consent.record` stempelt
`CONSENT_TEXT_VERSION` zoals het dat al deed. Het verzoekveld is uitsluitend een grendel.

**Bij `action = "WITHDRAWN"` is het veld niet verplicht en wordt het genegeerd.** Artikel 7 lid
3 AVG zegt dat intrekken net zo eenvoudig moet zijn als geven, en een intrekking weigeren omdat
de tekst inmiddels anders luidt is precies dat niet. Bij `action = "GRANTED"` en bij
`register/` is het veld verplicht, en ontbreken is een 400 zoals elk ander ontbrekend veld op
die serializers.

De melding komt uit `nl.py` als een nieuwe sleutel `consent_text_stale`. Die valt in de eerste
categorie die de docstring van dat bestand beschrijft, naast `csrf_failed`: die sleutel staat
daar al, ook al benoemt hij net als `consent_text_stale` geen veld en spreekt hij de lezer toch
aan over een pagina die te oud is. De tekst zegt dat de toestemmingstekst is gewijzigd en dat
de pagina opnieuw geladen moet worden.

Een versiebump blijft daarmee wat hij was, plus één gevolg dat erbij hoort: elke openstaande
pagina krijgt bij de volgende toestemming een 400 die zichzelf uitlegt, in plaats van een rij
die iets anders beweert dan er op het scherm stond.

## 6. De drie weergaven

Eén pagina, drie weergaven, en de toestand komt uit `me/`. Alleen een 200 daarop levert de
accountweergave op; elke andere afloop, ook een uitgebleven antwoord, levert de inlogweergave.

| Toestand | Wanneer | Wat er staat |
|---|---|---|
| `loading` | tot het eerste antwoord | Eén zin dat de gegevens worden opgehaald |
| `signed_out` | `me/` gaf 401, ook na de ene wissel, of er kwam geen antwoord (6.5) | Inloggen, met een schakelaar naar registreren |
| `signed_in` | `me/` gaf 200 | Het account |

### 6.1 Inloggen

E-mailadres (`type="email"`, `autocomplete="email"`), wachtwoord (`type="password"`,
`autocomplete="current-password"`), knop "Inloggen". Daaronder een schakelaar naar de
registratieweergave.

En één eerlijke zin: er is geen wachtwoordherstel. Hoofdstuk 10 van het auth-ontwerp noemt dat
de zwakste plek van dat ontwerp en beschrijft het gevolg, namelijk dat wie zijn wachtwoord
kwijt is ook het verwijderendpoint niet meer bereikt. Die zin hoort op het scherm te staan
waar iemand hem nodig heeft, en niet in een document. Het is formuliertekst, dus hij mag in de
frontend staan en hij staat in `ui-strings.txt`.

Na een 200 volgt `GET me/`, want `login/` heeft geen antwoordlichaam. Dat is geen retry: het is
de vraag die de accountweergave vult.

Fouten: een 401 draagt `credentials_invalid` en dat is met opzet hetzelfde antwoord voor een
onbekend adres en een fout wachtwoord. Een 403 draagt `csrf_failed`. Een 429 draagt zijn eigen
`detail`. Alle drie worden letterlijk getoond. Omdat ze letterlijk getoond worden, beantwoordt
de API een 429 zelf in het Nederlands, via een `throttled()`-overschrijving op `_AuthAPIView` die
de zin uit `nl.py` haalt in plaats van op DRF's eigen, onvertaalde Engelse tekst te vertrouwen.

### 6.2 Registreren

E-mailadres, wachtwoord (`autocomplete="new-password"`), en twee toestemmingen als losse
selectievakjes, allebei uit en allebei optioneel. Naast elk vakje staat de zin uit
`consent-texts/`, letterlijk.

`consent-texts/` wordt opgehaald zodra een weergave opengaat die die zinnen toont, dus bij het
registreren en bij de accountweergave, en niet bij elke paginalading. `auth-read` is één emmer
van 120 per uur voor `me/` en deze route samen, en wie alleen inlogt ziet geen van beide
weergaven en betaalt er dus ook niet voor.

**Zolang `consent-texts/` niet is teruggekomen worden de vakjes niet getoond en kan er niet
worden verzonden.** Anders zou er een `true` verstuurd kunnen worden voor een tekst die niemand
heeft gelezen, en dat is geen toestemming. Faalde die aanroep, dan zegt de weergave dat, en de
knop blijft onbereikbaar.

Beide antwoorden mogen nee zijn. Een `false` op `METER_LINK` weigert de registratie niet: dat
is hoofdstuk 6 van het auth-ontwerp, met artikel 7 lid 4 AVG als reden. De frontend mag dat dus
ook niet alsnog afdwingen met een `required` op het vakje, en er staat een test op dat hij dat
niet doet.

Het lichaam draagt `text_version` uit hetzelfde antwoord waaruit de getoonde zinnen komen. Niet
uit een constante hier: dan zou de frontend een tweede plek zijn waar de versie staat, en
precies dat is wat 5.2 sluit.

Na een 201 zijn beide cookies gezet. Dan volgt `GET me/` en daarna de accountweergave.

### 6.3 Account

- **Het e-mailadres**, uit `me/`. Verder geen profiel, want er is niets anders.
- **Twee toestemmingsrijen, `METER_LINK` eerst.** Elke rij draagt een Nederlands label dat zegt
  waar de rij over gaat (interfacetekst, in `ui-strings.txt`), de zin uit `consent-texts/`
  (API-tekst), de huidige stand uit `me/`, en een schakelaar. De renderorde is `METER_LINK` vóór
  `LEAD_GENERATION`, op beide plekken waar toestemmingen getoond worden (hier en in 6.2), via een
  `CONSENT_RENDER_ORDER`-constante op de renderplek en niet door `CONSENT_KINDS` zelf te
  herschikken: dat laatste is alfabetisch, wat de toestemming die betaalt boven de toestemming
  zet die het advies beter maakt, op het scherm waar de neutraliteit van dit product zichtbaar
  is.
  Elk label staat naast zijn eigen zin en is een strikte inperking daarvan: een label mag nooit
  meer beloven dan de zin waarnaast het staat, en elke toekomstige wijziging van een label wordt
  daartegen nagelopen. Een gedateerd `label`-veld in `consent-texts/`, zodat een labelwijziging
  net zo vastligt als een tekstwijziging via `text_version`, staat gepland voor de eerstvolgende
  wijziging aan `backend/accounts/`.
  Omzetten is `POST consent/` met `kind`, `action` en, bij `GRANTED`, `text_version`. Het
  antwoord `{ kind, granted }` is de nieuwe stand van die rij. Er wordt geen tweede `me/`
  gedaan: de API heeft de vraag net beantwoord, en een tweede aanroep zou de rij kunnen vullen
  met een antwoord dat een gelijktijdige wijziging elders inhaalt.
  Kwam `consent-texts/` hier niet terug, dan toont de rij zijn stand en kan er alleen worden
  ingetrokken. Aanzetten kan niet, want dan zou er ingestemd worden met een zin die niet op het
  scherm staat, en intrekken kan wel, om de reden in 5.2: dat mag nooit moeilijker zijn dan
  geven.
- **"Gegevens exporteren"** doet `POST export/` en biedt het antwoord aan als bestand
  (`ampeer-gegevens.json`), gebouwd uit de ruwe tekst van het antwoord. `auth-export` staat op
  5 per uur; een 429 daarop toont de `detail` van de API.
  Dat de lijst `advices` in fase 1 leeg is, is geen fout van deze knop. De weergave zegt niets
  over die lijst en verzint er geen zin bij.
- **"Uitloggen"** doet `POST logout/`. Na de 204 is de weergave `signed_out`.
- **"Account verwijderen"** klapt uit naar één zin die zegt wat verwijderen wegneemt en wat
  blijft staan, dan één wachtwoordveld en een bevestigknop. Ingeklapt staat er een knop en geen
  waarschuwing: dit is de zwaarste handeling op de pagina en ze hoort niet als aanbod te lezen,
  maar ook niet als dreiging. De zin staat er wel zodra het blok openklapt, vóór het
  wachtwoordveld, en zonder aandrang:

  > "Hiermee verdwijnen uw e-mailadres, uw twee toestemmingen, uw opgeslagen adviezen en uw
  > sessies. In ons logboek blijft alleen de regel staan dat een account is verwijderd, met een
  > nummer dat nergens meer heen wijst."

  Dat is `delete_account` in `backend/accounts/service.py` in gewone taal: de CASCADE neemt het
  e-mailadres, beide toestemmingen en elk opgeslagen advies mee, en het logboek houdt alleen de
  regel dat er iets verwijderd is. Zonder deze zin vraagt het scherm alleen om een wachtwoord en
  een klik, en dat is een bevestiging die niets bevestigt. Dit is het spiegelbeeld van
  toestemming: de zin moet gelezen zijn voordat het vinkje gezet wordt, dus moet het gevolg
  gelezen zijn voordat de knop wordt ingedrukt.

### 6.4 Wat er na de 204 op `delete/` gebeurt

De backend wist beide tokencookies in datzelfde antwoord (`cookies.clear_tokens`), dus de
browser draagt ze daarna niet meer. De `csrftoken`-cookie blijft staan en blijft geldig, en dat
is precies wat iemand nodig heeft die meteen daarna een nieuw account aanmaakt.

De weergave gaat naar `signed_out` met één regel bevestiging erboven. Er wordt **geen** `me/`
gedaan om dat te controleren, en er wordt **geen** `refresh/` geprobeerd. De 204 is het bewijs;
een `me/` erna zou een `auth-read` uitgeven aan een vraag die al beantwoord is, en een 401 daar
is niet te onderscheiden van een sessie die gewoon verlopen is. De wissel uit 2.1 hoort bij het
laden van de pagina en nergens anders, en na een verwijdering is er ook niets meer om in te
wisselen: de `RefreshSession`-rijen zijn met het account meegegaan.

Dezelfde regel geldt voor `logout/`: 204, weergave `signed_out`, geen controlevraag erachteraan.

### 6.5 Wat er gebeurt als de API onbereikbaar is

`fetch` werpt bij een netwerkfout, en dat is iets anders dan een 401. De pagina toont dan de
inlogweergave met een melding erboven dat de verbinding mislukte, en probeert geen tokenwissel:
er is niets teruggekomen om op te reageren. De accountweergave verschijnt in dit geval nooit,
want er is niets bekend over wie er is ingelogd.

Dit is geen randgeval dat alleen op papier bestaat. `e2e/privacy.spec.ts` opent elke pagina die
een bezoeker zonder advies kan bereiken en mockt de API niet, dus dit is precies de toestand
waarin `/account/` daar geopend wordt. Een weergave die daar leeg blijft, of die de
accountweergave laat zien, valt in die test om op iets anders dan waar die test over gaat.

## 7. Tekst en de taalgrens

De grens loopt hier anders dan op de adviespagina, en het is de moeite waard om precies te
zeggen hoe.

**Uit de frontend:** labels, knoppen, koppen, de zin over wachtwoordherstel, de zin die zegt
dat de gegevens worden opgehaald, de regel na een verwijdering, en de labels die de twee
toestemmingsrijen benoemen. Dat is navigatie en formuliertekst, en dat is precies wat de
frontend volgens `frontend/CLAUDE.md` zelf schrijft.

**Uit de API:** de twee toestemmingsteksten, en elke validatiemelding. Die eerste omdat
hoofdstuk 5 dat afdwingt. Die tweede omdat ze in `accounts/nl.py` staan, gekoppeld aan Engelse
ids, en omdat een frontend die ze overschrijft een tweede tabel is die uiteen kan lopen met de
eerste.

Elke nieuwe zin uit de eerste categorie is één regel in `frontend/tests/ui-strings.txt`.
`e2e/language.spec.ts` haalt met de TypeScript-compiler elke string uit `src/**` die een
DOM-tekstknoop of een toegankelijke naam kan worden, en vergelijkt die verzameling byte voor
byte in beide richtingen met dat bestand. Er is geen filter dat betekenis leest, en dat is de
opzet: een zin die een huishouden vertelt wat het moet doen kan er niet in komen zonder in een
diff te verschijnen, onder een kop die zegt wat een regel daar mag zijn.

De toestemmingsteksten staan er dus **niet** in, want ze staan niet in `src/**`. Dat is
controleerbaar en wordt gecontroleerd: hoofdstuk 9 punt 4 leest `nl.py` en zoekt die zinnen in
de frontend-broncode.

## 8. Vormgeving en toegankelijkheid

Geen nieuwe bibliotheek, geen nieuw ontwerpsysteem. De bestaande tokens uit
`src/design/tokens.ts` en de bestaande formuliercomponenten uit `src/components/form/`. Wat
deze pagina nodig heeft en nog niet bestaat is een selectievakje met een zin ernaast en een
rij met een schakelaar; dat zijn twee kleine componenten en geen ontwerpsysteem.

Licht en donker allebei, langs `prefers-color-scheme` met de expliciete keuze die voorgaat,
zoals elke andere route.

**Rustig.** Regel 4 uit het frontend-ontwerp verbiedt aftelklokken, schaarste en sociale
bewijsvoering op de adviespagina, en die regel geldt hier in geest net zo goed. Er staat geen
zin die aanspoort een account te maken, geen "nog even" bij het tweede selectievakje, en geen
enkele visuele voorkeur voor "ja" boven "nee". De twee vakjes zien er hetzelfde uit, staan
allebei uit, en de tweede is niet kleiner dan de eerste.

Toegankelijkheid, in de poort en niet in een controle achteraf:

- WCAG 2.2 AA, met axe over `/account/` in beide toestanden en beide paletten
- Elke fout wordt aangekondigd in een `role="alert"` binnen `main`, zoals de vragenstroom dat
  doet, en elke veldfout is met `aria-describedby` aan zijn eigen veld gekoppeld. Veldfouten
  komen via een eigen, per-veld toegang op `fieldMessages` (`fieldErrors` in
  `_account/messages.ts`), zodat elk veld zijn eigen meldingen krijgt in plaats van dat ze worden
  samengevoegd in de ene alinea met `role="alert"`, die alleen overblijft voor meldingen die geen
  veld noemen
- Op beide toestemmingsschermen (6.2 en 6.3) rendert `METER_LINK` als eerste en
  `LEAD_GENERATION` als tweede, op de renderplek zelf en niet door `CONSENT_KINDS` te herschikken
- Het uitklappen van het verwijderblok is een `<button>` met `aria-expanded`, en de focus gaat
  naar het wachtwoordveld dat verschijnt
- De hele pagina is met het toetsenbord te bedienen, inclusief de twee schakelaars en het
  uitklapblok
- `prefers-reduced-motion` wordt gerespecteerd, en de betekenis zit nooit alleen in beweging

## 9. Testregime

Vijf lagen. Bij elke staat wat hij bewijst, en bij de eerste drie ook wat hij niet kan bewijzen,
want dat is de reden dat de vijfde bestaat.

1. **`frontend/tests/lib/accounts.test.ts` (Vitest).** Dat elke aanroep
   `credentials: "include"` meegeeft; dat elke POST een `X-CSRFToken` draagt met de waarde uit
   de `csrftoken`-cookie en dat een GET dat niet doet; dat een 500 precies één `fetch`
   oplevert; dat elke vormcontrole uit 4.2 een plausibel verkeerd lichaam weigert; en dat de
   twee foutreducties op dezelfde tabel hetzelfde teruggeven. Bewijst het contract van de
   module tegen een gemockte `fetch`. Bewijst niet dat een browser die cookie ook echt stuurt.
2. **`frontend/tests/account/*` (Vitest + Testing Library).** De drie weergaven: dat `loading`
   een zin toont en geen leeg element; dat beide selectievakjes uit staan bij de eerste
   rendering en geen van beide `required` is; dat het registratieformulier niet verzendt
   zolang `consent-texts/` niet is teruggekomen; dat de getoonde toestemmingszin **byte voor
   byte** de string is die de client teruggaf; en dat een 200 op `consent/` de rij bijwerkt
   zonder een tweede `me/`.
3. **`frontend/e2e/account.spec.ts` (Playwright, API gemockt met `page.route`).** De schakeling
   op `me/`: 200 toont het account, 401 toont inloggen. De ene wissel: een 401 gevolgd door een
   geslaagde `refresh/` en een 200 toont het account, en een 401 die ná de wissel opnieuw 401
   is beëindigt het, geteld op het aantal verzoeken en niet op wat er op het scherm staat.
   Registreren met beide toestemmingen geweigerd, een toestemming aanzetten, exporteren (met
   `waitForEvent("download")`), verwijderen. Een verzoek dat afgebroken wordt in plaats van
   beantwoord toont de inlogweergave met een melding en zet geen wissel in gang, zie 6.5. axe
   in beide toestanden en beide paletten, en de hele stroom met het toetsenbord. Bewijst de
   stroom. **Bewijst niets over `credentials` of
   over de CSRF-header:** `page.route` antwoordt wat er gevraagd wordt, dus een frontend die
   allebei vergeet komt hier groen doorheen en werkt in productie niet.
4. **De Python-contractlaag: `tests/test_frontend_contract.py` en `tests/test_accounts_api.py`
   (allebei uitgebreid).** De kant waar de vorm wordt geproduceerd. Het eerste bestand draait
   zonder database en houdt de fixtures en de paden tegen de broncode aan; het tweede heeft een
   testdatabase en is daarom de plek voor alles wat een gebruikersrij nodig heeft:
   - de `consent-texts`-fixture wordt gegenereerd uit `nl.py` en byte voor byte vergeleken,
     precies zoals `advice_fixture.py` dat doet. Dat kan, want dat antwoord raakt geen
     database
   - de `me`- en `export`-fixtures kunnen niet zo gegenereerd worden: die antwoorden vragen
     een gebruikersrij. Ze worden met de hand geschreven en in `tests/test_accounts_api.py`
     vastgezet, waar een testdatabase wel bestaat: de test bouwt de rij met de ORM, roept de
     view aan, en vergelijkt de **vorm** van het antwoord met de fixture, langs dezelfde
     `_shape`-functie die de adviesfixture al gebruikt. Waarden verschillen dan (een e-mailadres,
     een tijdstempel) en de sleutels niet, en het zijn de sleutels waar de frontend op bouwt
   - dat de sleutels onder `texts` gelijk zijn aan `Consent.KINDS`, en dat de frontend precies
     die twee soorten kent. Een derde soort valt daarmee om aan de kant waar hij is toegevoegd
   - dat de teksten in de fixture byte voor byte `NL["CONSENT_METER_LINK"]` en
     `NL["CONSENT_LEAD_GENERATION"]` zijn, en `text_version` gelijk is aan
     `CONSENT_TEXT_VERSION`
   - `test_no_consent_text_lives_in_the_frontend`: geen van beide zinnen komt voor in
     `frontend/src/**`
   - dat elk pad dat `accounts.ts` aanroept een pad is dat `accounts/urls.py` bedient. De
     bestaande `test_every_path_the_frontend_calls_is_one_the_backend_serves` leest vandaag
     `advice.urls` en `api.ts`; die wordt een geparametriseerd paar, zodat de tweede client
     dezelfde controle krijgt als de eerste
5. **`tests/test_stack_smoke.py` (uitgebreid), tegen de draaiende compose-stack.** Dit is het
   enige wat een mock niet kan bewijzen, en het is daarom niet optioneel:
   - een echte inlogronde over HTTP, waarna de `Set-Cookie`-attributen stuk voor stuk uit het
     antwoord worden gelezen: `httponly`, `samesite=Strict`, en `path=/api/` respectievelijk
     `path=/api/auth/`. Niet "de aanroep gaf 200"
   - een POST zonder `X-CSRFToken` geeft 403. Deze aanroep stuurt wel een productie-vormige
     `Origin`-header (`https://127.0.0.1`, zonder poort, want nginx zet `Host` op `$host`) mee op
     elk onveilig verzoek, want `infra/nginx/nginx.conf` zet `X-Forwarded-Proto: https`
     onvoorwaardelijk en Django eist dan een `Origin` of `Referer` vóórdat het naar het token
     kijkt. Zonder die header zou de weigering om de verkeerde reden 403 geven; de controle laat
     daarom alleen het token weg en draagt een positieve controle in dezelfde test: dezelfde
     sessie mét het token komt wel langs de CSRF-check
   - `test_the_consent_text_shown_is_the_text_recorded`: `GET consent-texts/` levert versie V
     en de twee zinnen; `POST register/` met die V en `consent_meter_link: true`; `POST
     export/` geeft de `Consent`-rij terug en de `text_version` daarop is V. Dat is de lus die
     de garantie uit hoofdstuk 5 sluit, over de echte HTTP-route en zonder de database te
     openen

   Deze checks draaien niet in CI, want daar is geen Docker. Ze zijn opt-in via een
   omgevingsvariabele met het adres van de stack, ze slaan zichzelf over als die er niet is, en
   **een overgeslagen check is geen bewijs**: de uitvoer van de handmatige run gaat in de
   commit, precies zoals de zeven checks uit het deploy-ontwerp dat doen. Het bestand zelf zegt
   dat al over zichzelf in zijn eerste regels.

Welke test bewijst dat de getoonde toestemmingstekst gelijk is aan de vastgelegde: dat is
`test_the_consent_text_shown_is_the_text_recorded` in laag 5, en die is de enige die de hele
lus over één echte HTTP-route legt. De andere twee lagen dekken elk een helft ervan: laag 2
bewijst dat getoond gelijk is aan geleverd, en laag 4 dat geleverd gelijk is aan `nl.py`. De
400 uit 5.2 sluit het tijdvenster waarin die twee helften uit elkaar kunnen lopen.

Van elke nieuwe controle wordt aangetoond dat hij rood kan worden. Dat geldt hier het zwaarst
voor punt 5: een smoke die stilzwijgend overslaat leest als groen en is niets.

## 10. Wat expliciet niet in v1 zit

- **Geen ingelogd-indicator in de kop.** Die zou op elke route een `me/` vragen, dus op elke
  paginalading van elke bezoeker, ingelogd of niet. `auth-read` staat op 120 per uur en de
  vraag heeft alleen op `/account/` een antwoord dat iets doet.
- **Geen wachtwoordherstel-UI.** De backend heeft het niet, en een scherm dat het aanbiedt zou
  een knop zijn die niets doet. Wat er wel is, is de zin uit 6.1 die het zegt.
- **Geen e-mailverificatie.** Zelfde reden, en zie hoofdstuk 10 van het auth-ontwerp.
- **Geen "onthoud mij".** De refresh-cookie leeft veertien dagen en dat is het antwoord op die
  vraag. Een vakje dat suggereert dat het iets omzet zou over niets gaan.
- **Geen sessieoverzicht en geen "log overal uit".** `RefreshSession` maakt dat later
  goedkoop; er is nu geen scherm met een vraag erachter.
- **Geen dashboard, geen adviesgeschiedenis, geen claim-route.** Dat is de beslissing uit
  hoofdstuk 11 van het auth-ontwerp en dit deelproject verandert er niets aan.
- **Geen wijziging aan `api.ts`, aan de vragenstroom of aan de adviespagina.** De enige
  wijziging in een bestaand frontend-bronbestand is de vierde link in de voettekst.

## 11. Bestanden die veranderen

Nieuw, frontend:

| Bestand | Inhoud |
|---|---|
| `frontend/src/lib/accounts.ts` | De client uit hoofdstuk 4 |
| `frontend/src/app/account/page.tsx` | De route: een servercomponent die `metadata`, de `<h1>` en de alinea draagt, met `<AccountPage />` eronder. Geen `account/layout.tsx`: alleen `AccountPage.tsx` is een clientcomponent, dus `page.tsx` kan `metadata` gewoon zelf exporteren. Anders dan `berekenen/`, waar `page.tsx` zelf een clientcomponent is en daarom wel een `layout.tsx` nodig heeft |
| `frontend/src/app/_account/AccountPage.tsx` | De drie weergaven en de toestand ertussen |
| `frontend/src/app/_account/SignInForm.tsx` | 6.1 |
| `frontend/src/app/_account/RegisterForm.tsx` | 6.2 |
| `frontend/src/app/_account/ConsentRow.tsx` | Twee componenten, niet één: `ConsentCheckbox` voor 6.2 en `ConsentRow` voor 6.3, de twee kleine componenten uit hoofdstuk 8. Ze delen het label per soort en de regel dat de zin uit de API komt, en verschillen in wat er gebeurt als je erop drukt |
| `frontend/src/app/_account/session.ts` | De laadvolgorde en de ene wissel uit 2.1 |
| `frontend/src/app/_account/messages.ts` | `describeAuthError`, naar het model van `_flow/messages.ts`, plus `fieldErrors`, de per-veld toegang uit hoofdstuk 8 |
| `frontend/src/app/_account/download.ts` | Het exportbestand uit de ruwe antwoordtekst |
| `frontend/tests/lib/accounts.test.ts` | Laag 1 |
| `frontend/tests/account/AccountPage.test.tsx` | Laag 2 |
| `frontend/tests/account/SignInForm.test.tsx` | Laag 2 |
| `frontend/tests/account/RegisterForm.test.tsx` | Laag 2 |
| `frontend/tests/account/ConsentRow.test.tsx` | Laag 2, voor beide componenten uit `ConsentRow.tsx`; niet in `RegisterForm.test.tsx`, waar de eerste versie ze nog meetestte |
| `frontend/tests/account/session.test.ts` | Laag 2, de wissel en de toestand uit 6.5 |
| `frontend/tests/account/messages.test.ts` | Laag 2, wat er op het scherm komt bij een 400, 401, 403 en 429 |
| `frontend/tests/fixtures/consent-texts.json` | Gegenereerd uit `nl.py`, niet met de hand |
| `frontend/tests/fixtures/me-response.json` | Met de hand, vastgezet op vorm in `tests/test_accounts_api.py`, zie hoofdstuk 9 punt 4 |
| `frontend/tests/fixtures/export-response.json` | Idem, met een lege `advices` en één `Consent`-rij |
| `frontend/e2e/account.spec.ts` | Laag 3 |

Gewijzigd, frontend:

| Bestand | Wat |
|---|---|
| `frontend/src/app/_shell/SiteFooter.tsx` | De vierde link, "Account" |
| `frontend/tests/app/LegalPages.test.tsx` | De footertest heet "reaches all three pages" en somt er drie op; dat worden er vier, en de assertie dat er geen externe href in staat blijft |
| `frontend/tests/ui-strings.txt` | Elke nieuwe zin uit hoofdstuk 7, geregenereerd met `UPDATE_UI_STRINGS=1 pnpm e2e language` en gelezen als diff |
| `frontend/e2e/theme.spec.ts` | `/account/` in `ALL_PATHS`, zodat het donkere palet ook hier langskomt. `serveFixture` mockt vandaag alleen `**/api/advice/**` en krijgt er een 401 op `**/api/auth/me/**` bij, zodat het contrast wordt gemeten op de inlogweergave en niet op een toestand die van een netwerkfout afhangt |
| `frontend/e2e/privacy.spec.ts` | `/account/` in `PAGES`: het is een pagina die een bezoeker zonder advies kan bereiken, en de controle op verzoeken naar derden hoort er dus over te gaan. Hier wordt met opzet niets gemockt, dus dit is meteen de toestand uit 6.5 |

Gewijzigd, backend:

| Bestand | Wat |
|---|---|
| `backend/accounts/views.py` | `ConsentTextsView`, publiek, `auth-read` |
| `backend/accounts/urls.py` | `path("consent-texts/", ..., name="auth-consent-texts")` |
| `backend/accounts/serializers.py` | `text_version` op `RegisterSerializer` en `ConsentSerializer`, met de regel voor `WITHDRAWN` uit 5.2 |
| `backend/accounts/nl.py` | Eén sleutel, `consent_text_stale`, in de eerste categorie die de docstring beschrijft |

Gewijzigd, tests en documenten:

| Bestand | Wat |
|---|---|
| `tests/test_accounts_api.py` | De negende route: statuscode, vorm, en dat de teksten uit `nl.py` komen. Plus de 400 op een verouderde `text_version` bij `register/` en bij `consent/` met `GRANTED`, en dat `WITHDRAWN` zonder het veld slaagt |
| `tests/test_frontend_contract.py` | Laag 4, inclusief het geparametriseerde padpaar |
| `tests/test_stack_smoke.py` | Laag 5 |
| `tests/helpers/consent_texts_fixture.py` | De generator voor de `consent-texts`-fixture, naast `advice_fixture.py` en langs hetzelfde patroon: gegenereerd, byte voor byte vergeleken, en niet met de hand bij te werken |
| `docs/dpia.md` | Regel 358: "acht routes" wordt "negen routes", met erbij dat de negende publiek is en geen persoonsgegeven teruggeeft |
| `docs/decisions.md` | Twee entries: `text_version` in het verzoek als grendel, en de ene tokenwissel bij het laden als uitzondering op de retry-regel |
| `docs/superpowers/specs/2026-09-04-accounts-auth-design.md` | De tabel in 5.1 en de zin "Acht routes" eronder krijgen de negende erbij, met een verwijzing naar dit document |

Geen nieuwe afhankelijkheid, in geen van beide bomen. Geen wijziging aan `.github/workflows/`,
want `frontend-quality`, `frontend-test`, `quality` en `test` dekken al wat hier bij komt, en
de jobnamen zijn een interface met de rulesets.

## 12. Definition of done

- Een bezoeker komt via de voettekst op `/account/`, registreert met beide toestemmingen
  geweigerd, ziet zijn account, zet één toestemming aan, exporteert, verwijdert, en staat
  daarna uitgelogd op dezelfde pagina met één regel bevestiging
- Diezelfde ronde is met mocks in Playwright aangetoond, en de delen ervan die alleen een echte
  verbinding kan bewijzen (inloggen, de cookie-attributen, de weigering zonder CSRF-header en de
  toestemmingslus) tegen de echte API over de compose-stack, met de uitvoer daarvan in de commit
- De `Set-Cookie`-attributen zijn uit een echt antwoord gelezen: `httponly`, `SameSite=Strict`,
  en de twee verschillende paden
- Een POST zonder `X-CSRFToken` geeft 403, aangetoond over de echte stack
- De getoonde toestemmingstekst is byte voor byte de tekst die de rij vastlegt, aangetoond
  via `consent-texts/`, `register/` en `export/` in één lus
- Een verouderde `text_version` is een 400 op `register/` en op een `GRANTED`, en een
  `WITHDRAWN` slaagt zonder het veld
- Een 401 op `me/` bij het laden wisselt precies één keer, en een tweede 401 toont de
  inlogweergave in plaats van opnieuw te wisselen, geteld op verzoeken
- axe vindt geen overtredingen op `/account/`, in beide toestanden en beide paletten
- `ui-strings.txt` is bijgewerkt via de regeneratie en de diff is gelezen; de twee
  toestemmingsteksten komen er niet in voor en staan nergens in `frontend/src/**`
- `api.ts` is niet gewijzigd, en `credentials: "omit"` staat er nog
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build` en `pnpm e2e` zijn groen, en de
  vijf bestaande poorten met hen
- Van elke nieuwe controle is aangetoond dat hij rood kan worden
