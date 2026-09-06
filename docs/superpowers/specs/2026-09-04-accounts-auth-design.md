# Ontwerp: accounts en authenticatie Ampeer (fase 1)

Datum: 2026-09-04
Status: vastgesteld, klaar voor implementatieplan
Betreft: een nieuwe Django-app `backend/accounts/`, de instellingenketen eromheen, en de enige
wijziging die deze fase in `backend/advice/` aanbrengt

## 1. Doel en afbakening

Een huishouden moet een account kunnen aanmaken op het moment dat het aan een meterkoppeling
begint, daarna kunnen inloggen, zijn toestemmingen kunnen geven en intrekken, zijn gegevens
kunnen opvragen en zijn account kunnen verwijderen. Meer niet.

Het account is in deze fase geen product. Het is de duurzame identiteit waar fase 2 aan hangt,
en verder niets. Er komt geen dashboard, geen adviesgeschiedenis en geen overzichtspagina, en
dat is een beslissing en geen restpost.

`estimate/` en `refine/` blijven volledig anoniem. Niemand wordt gevraagd zich te registreren om
de rekenmachine of de adviseur te gebruiken. `CLAUDE.md` geeft daar de reden voor die zwaarder
weegt dan gemak: de grootste gebruikersgroep wil niets installeren.

Binnen scope:

- Een eigen gebruikersmodel met een e-mailadres als sleutel, Argon2id-hashing en `django-axes`
- JWT in httpOnly `SameSite=Strict` cookies, met rotatie van het refresh-token
- Twee losse toestemmingen, elk met een eigen tijdstempel en een intrekking die vastligt
- Uitbreiding van het bestaande `AuditEvent` met de gebeurtenissen die deze fase toevoegt
- Een export- en een verwijderroute, allebei werkend, want `CLAUDE.md` zet die bij de fase
  waarin accounts bestaan en dat is deze fase
- Snelheidslimieten op elke nieuwe route

Buiten scope, eigen deelproject:

- De meterkoppeling zelf, de P1-ingest en de ingest-tokens (fase 2)
- Alles wat kwartierdata uit een echte meter aanraakt (fase 3)
- Leads, dagplan en white-label (later)

De grondslag is voorlopig **toestemming**. Dat is de aanname waarop dit ontwerp staat, en
hoofdstuk 14 zegt wat er verandert als die aanname omgaat.

## 2. Waar het komt te staan

Een nieuwe app, `backend/accounts/`, naast `backend/advice/`. Niet in `advice` erbij.

De reden staat in het bestand zelf. `backend/advice/models.py` opent met "None of them holds a
personal detail", en `docs/dpia.md` hoofdstuk 2 leunt op die zin. Een e-mailadres en een
wachtwoordhash in datzelfde bestand maken hem onwaar. Drie controles in `tests/test_dpia.py`
parsen dat bestand bovendien op naam, dus de zin is er niet alleen, hij wordt bewaakt. De
scheiding houdt een belofte per bestand controleerbaar in plaats van hem te vervangen door een
langere uitzondering.

`AuditEvent` blijft staan waar hij staat, in `advice/models.py`. Een tabel tussen apps
verplaatsen vraagt `SeparateDatabaseAndState` over precies de tabel die met opzet append-only is
en nooit wordt opgeruimd. Dat is risico zonder opbrengst, en hoofdstuk 7 legt uit waarom
hergebruik hier beter is dan een tweede logboek.

Bestandenlijst, zodat het implementatieplan er niets bij hoeft te verzinnen:

| Bestand | Inhoud |
|---|---|
| `backend/accounts/__init__.py` | leeg |
| `backend/accounts/apps.py` | `AccountsConfig`, naar het model van `advice/apps.py` |
| `backend/accounts/models.py` | `User`, `UserManager`, `Consent`, `RefreshSession` |
| `backend/accounts/serializers.py` | de request- en responsvormen |
| `backend/accounts/authentication.py` | `CookieJWTAuthentication` |
| `backend/accounts/cookies.py` | het zetten en wissen van de twee cookies, op één plek |
| `backend/accounts/tokens.py` | uitgeven, roteren en intrekken van refresh-tokens |
| `backend/accounts/service.py` | export en verwijdering, de twee handelingen met gevolgen |
| `backend/accounts/views.py` | `_AuthAPIView` plus de acht routes |
| `backend/accounts/urls.py` | gemonteerd onder `/api/auth/` |
| `backend/accounts/nl.py` | Nederlandse teksten, gekoppeld aan Engelse ids |
| `backend/accounts/lockout.py` | de twee callables die axes een gehashte identiteit geven |
| `backend/accounts/management/commands/purge_expired_sessions.py` | het opruimen uit 4.4, naast de bestaande advies-opruiming |
| `backend/accounts/migrations/0001_initial.py` | `User`, met de `Lower("email")`-constraint |
| `backend/accounts/migrations/0002_consent.py` | `Consent` |
| `backend/accounts/migrations/0003_refreshsession.py` | `RefreshSession` |
| `backend/advice/migrations/0005_storedadvice_owner.py` | de enige wijziging in `advice` |

## 3. Drie vondsten die dit ontwerp sturen

Deze staan vooraan omdat ze de rest dwingend maken. Alle drie zijn uit de boom of uit de
installatie-instructies van een pakket gelezen, niet onthouden.

### 3.1 Er staat al een valstrik klaar voor deze fase

`tests/test_backend_settings.py` bevat `test_authentication_never_arrives_without_its_defences`.
Die test wordt rood op de dag dat `django.contrib.auth` in `INSTALLED_APPS` komt, tenzij axes,
de volgorde van `AUTHENTICATION_BACKENDS` en een Argon2-hasher in dezelfde commit meekomen. De
bijbehorende `test_the_rule_about_login_defences_recognises_a_setup_that_lacks_them` toont aan
dat de regel rood kán worden, in vier gevallen, en dat een axes-backend achter `ModelBackend`
als fout wordt gemeld.

De docstring erbij zegt waarom dat nodig was: Django levert `AUTHENTICATION_BACKENDS` en
`PASSWORD_HASHERS` ook zonder dat iemand ze invult, en de standaardwaarden zijn `ModelBackend`
alleen en `PBKDF2PasswordHasher` eerst. Argon2 vervangt dus geen leegte maar een werkende
standaard, en dat is de moeilijkere soort om aan te denken.

Deze fase is die dag. Dat is geen probleem dat opgelost moet worden maar de poort die gepasseerd
hoort te worden, en het is de reden dat hoofdstuk 9 er precies vier dingen in dezelfde commit
naast zet.

De docstring van `test_nothing_authenticates_because_there_is_nothing_to_log_in_to` moet in
dezelfde commit herschreven worden. Die test blijft groen, want
`DEFAULT_AUTHENTICATION_CLASSES` blijft `[]` (zie 5.4), maar zijn titel klopt dan niet meer.

### 3.2 django-axes schrijft standaard IP-adressen weg

De standaard van `django-axes` is `AXES_HANDLER = "axes.handlers.database.AxesDatabaseHandler"`,
en die maakt `AccessAttempt`, `AccessLog` en `AccessFailureLog` aan, alle drie met een
`ip_address`-kolom. `docs/dpia.md` hoofdstuk 2 zegt letterlijk "Geen IP-adres in enige tabel",
en `backend/advice/throttling.py` bestaat in zijn geheel om dat waar te maken: het adres wordt
met een HMAC onder `SECRET_KEY` gehasht voordat het een teller wordt, omdat een teller op een
adres een bezoekerslogboek is.

Niets in deze repository zou de terugval merken.
`tests/test_dpia.py::test_no_table_has_a_column_for_an_address` leest via AST alleen
`backend/advice/models.py`, dus de modellen van een derde partij komen er niet in voor. De zin
in de DPIA zou stilzwijgend onwaar worden, en dat is exact de faalvorm waar deze repository
tegen gebouwd is.

Wat dit ontwerp daarom doet staat in 9.3. De drie tabellen laten zich niet wegnemen: `axes` in
`INSTALLED_APPS` draait tien migraties en maakt ze aan ongeacht welke handler ingesteld staat.
Wat wel kan is dat er nooit een rij in komt, en dat is de vorm die 9.3 kiest: niet "de tabel
niet laten bestaan" maar "de tabel laten bestaan en leeg laten blijven".

### 3.3 simplejwt bewaart het refresh-token in platte tekst

`djangorestframework-simplejwt` biedt `ROTATE_REFRESH_TOKENS` en `BLACKLIST_AFTER_ROTATION`,
maar die tweede vraagt de app `token_blacklist`, en die schrijft in `OutstandingToken.token` het
volledige refresh-JWT. Dat is een werkend credential in een databasekolom.

Twee regels verbieden dat hier. `CLAUDE.md` zegt "Ingest-tokens gehasht opslaan, nooit in
plaintext". En `docs/dpia.md` hoofdstuk 2 heeft dezelfde afweging al gemaakt voor het
advies-token, met de zin die hier woord voor woord van toepassing is: het token is geen
verwijzing naar het record, het is de enige sleutel die het opent.

Daarom komt er in plaats van `token_blacklist` een eigen `RefreshSession`, die alleen de
sha256-digest van de `jti` bewaart. Zie 4.4. De prijs is ongeveer veertig regels die anders van
een pakket kwamen. De opbrengst is dat er geen bruikbaar credential in de database staat, en dat
`advice.models.token_digest` met zijn uitleg wordt hergebruikt in plaats van nagebouwd.

## 4. Het datamodel

### 4.1 `User`

Een eigen model op `AbstractBaseUser`, met `AUTH_USER_MODEL = "accounts.User"`.

Dit is de duurste beslissing van dit ontwerp om terug te draaien. `AUTH_USER_MODEL` omzetten
nadat er rijen bestaan is in Django praktisch een handmatige operatie, dus het moet in de eerste
migratie van deze fase goed staan.

| Veld | Waarom |
|---|---|
| `email` | `EmailField(unique=True)`, tevens `USERNAME_FIELD`. De enige identificatie |
| `password` | Argon2id, via `PASSWORD_HASHERS` |
| `is_active` | De enige vlag. Een geblokkeerd account moet kunnen bestaan zonder verwijderd te zijn |
| `date_joined` | UTC, zoals alles in dit project |

Geen `username`, geen `first_name`, geen `last_name`. Django's standaardmodel dwingt die drie af
en dit product vult ze nooit. Twee ervan heten een naam in een beoordeling die zegt dat er geen
naam is.

Geen postcode op de gebruiker. De postcode blijft waar hij hoort, in `StoredAdvice.inputs`, op
vier cijfers, geweigerd in plaats van afgekapt.

`PermissionsMixin` bewust niet. Er is geen admin, `backend/ampeer/settings/base.py` sluit die
expliciet uit, en er zijn geen rollen. Dat scheelt twee koppeltabellen. Als het later toch moet,
kost het één migratie met twee many-to-many-velden en een boolean, en dat is goedkoop. Dit is
dus de omkeerbare helft van deze paragraaf, in tegenstelling tot `AUTH_USER_MODEL` zelf.

**Het e-mailadres wordt volledig in kleine letters opgeslagen**, en dat is geen detail.
`BaseUserManager.normalize_email` maakt alleen het domein klein en laat het deel voor de apenstaart
staan. Daarmee zijn `A@voorbeeld.nl` en `a@voorbeeld.nl` twee accounts, en in 9.3 ook twee
verschillende lockout-sleutels, wat de brute-force-verdediging halveert zonder dat iemand het
ziet. `UserManager` verlaagt daarom het hele adres, en een test controleert dat een tweede
registratie met andere hoofdletters een 400 is en geen tweede rij.

### 4.2 `Consent`

Append-only, hetzelfde idee als `AuditEvent` en om dezelfde reden.

| Veld | Waarom |
|---|---|
| `user` | `ForeignKey`, `on_delete=CASCADE` |
| `kind` | `METER_LINK` of `LEAD_GENERATION`, uit een vaste lijst zoals `DailyCounter.CLIENT_NAMES` dat doet |
| `action` | `GRANTED` of `WITHDRAWN` |
| `occurred_at` | De eigen tijdstempel per opt-in die `CLAUDE.md` eist |
| `text_version` | Welke Nederlandse toestemmingstekst is aanvaard |

Een gebeurtenistabel en niet twee nullable datetime-kolommen op `User`. Intrekken en opnieuw
geven moet een geschiedenis opleveren, geen overschreven veld, en een kolom die twee keer
gevuld kan worden kan niet zeggen wat er tussenin gebeurde.

`text_version` is de kolom die dit verdedigbaar maakt in plaats van alleen aanwezig. Artikel 7
lid 1 AVG vraagt te kunnen aantonen waarvoor toestemming is gegeven, en dat is niet aan te tonen
als de tekst sindsdien herschreven is. De versie is een constante in `accounts/nl.py`, naast de
tekst zelf, zodat een reword en een versiebump één bewerking zijn.

`Consent.current(user, kind) -> bool` leest de laatste rij. Afwezigheid betekent nooit gegeven.
Een geweigerde vraag schrijft dus **niets**: `WITHDRAWN` voor iets dat nooit gegeven was zou een
onwaarheid zijn in een tabel die als bewijs bedoeld is.

### 4.3 `StoredAdvice.owner`

De enige wijziging die deze fase in `backend/advice/` aanbrengt:

```python
owner = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    null=True,
    blank=True,
    on_delete=models.CASCADE,
    related_name="advices",
)
```

`StoredAdvice.get_live(token)` verandert niet en filtert niet op `owner`. Elk bestaand advies
heeft `owner IS NULL`, en elk advies dat na deze fase anoniem gemaakt wordt ook. De deelbare
link blijft dus werken voor iedereen zonder account. **Eigendom voegt toe, het neemt de
tokenroute niets af**, en dat is een eigenschap waar een test op staat en geen zin waar op
vertrouwd wordt.

`CASCADE` en niet `SET_NULL`, en dat volgt rechtstreeks uit hoofdstuk 8. Een verwijderd account
moet zijn adviezen meenemen, want die adviezen zijn het enige wat dit product over dat huishouden
bewaart. `SET_NULL` zou de rijen laten staan als adviezen zonder eigenaar, die dan alsnog
negentig dagen op hun token opvraagbaar blijven, en dat maakt van een verwijderverzoek een
naamsverandering. Dat er in deze fase een verwijderroute komt is precies de reden dat deze keuze
nu genomen kan worden in plaats van geraden.

Dat de kolom er komt zonder dat er in v1 een route achter zit, is een bewuste uitzondering op
YAGNI met een precedent in deze repository. `docs/dpia.md` hoofdstuk 6 legt uit waarom
`shareable_token=False` gebouwd is voordat er een gemeten reeks bestond: vandaag kost het drie
regels, op het moment van gebruik kost het een migratie over elk opgeslagen advies, en tussen
die twee momenten zit een periode waarin de regel in een document staat en nergens wordt
afgedwongen. Hier geldt hetzelfde, met een tweede opbrengst: de verwijderroute uit hoofdstuk 8
heeft de kolom nodig om te weten wat ze moet verwijderen.

### 4.4 `RefreshSession`

| Veld | Waarom |
|---|---|
| `user` | `ForeignKey`, `on_delete=CASCADE` |
| `jti_sha256` | De digest van de `jti` van het refresh-token, via `advice.models.token_digest`. Nooit het token zelf, en nooit de `jti` zelf |
| `issued_at`, `expires_at` | `expires_at` heeft een index, zodat opruimen een `DELETE` op een index is, net als bij `StoredAdvice` |
| `rotated_at` | Nullable. Gevuld zodra dit token is ingewisseld |
| `revoked_at` | Nullable. Gevuld bij uitloggen of bij vermoed hergebruik |

Opruimen gaat met een management command naast de bestaande
`backend/advice/management/commands/purge_expired_advice.py`, aangeroepen door dezelfde cron, en
niet met Celery. Een dagelijkse `DELETE` over een geïndexeerde kolom heeft geen takenwachtrij
nodig, en dat is dezelfde afweging als in hoofdstuk 5 van het adviesAPI-ontwerp.

### 4.5 Wat er bewust niet in het datamodel zit

Geen `AccessAttempt` van axes, zie 9.3. Geen `OutstandingToken` van simplejwt, zie 3.3. Geen
sessietabel, want er zijn geen sessies. Geen `Permission`-koppeltabellen, zie 4.1.

`AuditEvent` krijgt **geen** foreign key naar `User`, en dat is een keuze met een reden.
`PROTECT` zou een verwijderverzoek blokkeren op het logboek dat het verzoek vastlegt, en
`CASCADE` zou het logboek wissen op het moment dat het het meest nodig is. Beide zijn fout voor
een append-only tabel. Er staat dus een `user_id` als gewoon geheel getal in `context`, dat na
verwijdering nergens meer naar wijst. Dat is dezelfde constructie als `token_sha256` in
`advice/service.py`, en `docs/dpia.md` hoofdstuk 2 beschrijft het effect al: wat overblijft
verliest zijn zeggingskracht, en dat is de bedoeling.

## 5. De auth-flow

### 5.1 De endpoints

`backend/accounts/urls.py`, gemonteerd in `backend/ampeer/urls.py` als
`path("api/auth/", include("accounts.urls"))`.

| Methode en pad | Doet | Scope |
|---|---|---|
| `POST /api/auth/register/` | Maakt het account, zet beide cookies, schrijft de toestemmingsrijen | `auth-register` |
| `POST /api/auth/login/` | Zet beide cookies | `auth-login` |
| `POST /api/auth/refresh/` | Roteert het refresh-token en zet beide cookies opnieuw | `auth-refresh` |
| `POST /api/auth/logout/` | Wist beide cookies, zet `revoked_at` op de aangeboden sessie | `auth-write` |
| `GET /api/auth/me/` | Het e-mailadres en de stand van beide toestemmingen | `auth-read` |
| `POST /api/auth/consent/` | Geeft of trekt één toestemming in | `auth-write` |
| `POST /api/auth/export/` | Geeft alles terug wat dit account betreft | `auth-export` |
| `POST /api/auth/delete/` | Verwijdert het account en alles wat eraan hangt | `auth-write` |

Acht routes, en uitsluitend `get` en `post`. Dat is geen toeval en ook geen omweg om een test te
plezieren. `tests/test_dpia.py::test_the_api_answers_only_the_verbs_the_document_describes`
weigert een `delete`, `put` of `patch` ergens in deze API omdat hoofdstuk 7 van de DPIA zegt dat
rectificatie een rij toevoegt in plaats van er een te wijzigen. Dit ontwerp houdt zich daaraan
en `/api/auth/consent/` is er het bewijs van: intrekken is een nieuwe rij.

Voor `/api/auth/delete/` komt daar een tweede, technische reden bij, en die staat in 8.2.

Alle acht erven van `_AuthAPIView`, dat op zijn beurt van `_NoStoreAPIView` uit
`backend/advice/views.py` erft. Daarmee dragen ze `Cache-Control: private, no-store`, want elk
van deze antwoorden beschrijft één huishouden. `_AuthAPIView` voegt daar één ding aan toe, zie
5.5. De throttleklasse komt uit `DEFAULT_THROTTLE_CLASSES` in `base.py` en is dus
`advice.throttling.HashedIdentScopedRateThrottle`, dezelfde die de adviesendpoints gebruiken en
om dezelfde reden: hij telt per bezoeker zonder een adres neer te zetten.

`logout/` leest het refresh-token uit zijn eigen cookie, die onder `/api/auth/` ook op deze route
meereist, en zet `revoked_at` op de bijbehorende rij. Uitloggen op één apparaat laat de andere
apparaten dus met rust; het intrekken van alles gebeurt alleen bij vermoed hergebruik (5.3) en bij
verwijdering (8.2).

### 5.2 De cookies

| Cookie | httpOnly | SameSite | Path | Levensduur |
|---|---|---|---|---|
| `ampeer_access` | ja | Strict | `/api/` | 15 minuten |
| `ampeer_refresh` | ja | Strict | `/api/auth/` | 14 dagen |
| `csrftoken` | nee | Strict | `/` | sessie |

`Secure` staat aan in `prod.py` en uit in `dev.py`, langs dezelfde lijn als `SECURE_SSL_REDIRECT`
en `CSRF_COOKIE_SECURE` daar al lopen. De namen en de levensduren staan als constanten in
`base.py`, want een cookienaam die op twee plaatsen wordt uitgeschreven is een cookienaam die een
keer uiteen gaat lopen.

Dat `SameSite=Strict` hier werkt is niet vanzelfsprekend en is nagegaan.
`infra/nginx/nginx.conf` serveert de statische export en proxyt `/api/` naar gunicorn binnen één
serverblok, `.github/workflows/deploy.yml` bouwt met een lege `NEXT_PUBLIC_API_BASE` zodat
`frontend/src/lib/api.ts` relatieve paden gebruikt, en de CSP op datzelfde blok staat op
`connect-src 'self'`. In productie is er dus één oorsprong, en dan is `Strict` geen belemmering
maar de sterkste beschikbare CSRF-verdediging. Op een ontwikkelmachine ligt dat anders; zie 9.5.

De paden zijn verschillend en dat is opzet. Het refresh-token hoort niet mee te reizen op elk
verzoek dat het access-token draagt, dus het staat onder `/api/auth/`. Smaller kan niet: het
moet zowel `refresh/` als `logout/` bereiken en één cookie heeft één pad. Het access-token staat
onder `/api/` en niet onder `/api/auth/`, omdat de endpoints van fase 2 daarbuiten komen te
liggen.

### 5.3 Rotatie

Elke `POST /api/auth/refresh/` levert een nieuw refresh-token op en merkt het oude als
ingewisseld. De controle is vier stappen: digest van de aangeboden `jti` opzoeken, weigeren als
de rij niet bestaat, weigeren als `rotated_at` of `revoked_at` gevuld is, anders `rotated_at`
stempelen en een nieuwe rij schrijven.

Een aangeboden token waarvan `rotated_at` al gevuld is, is hergebruik van iets wat is ingeleverd.
Dat is de enige betrouwbare aanwijzing dat een token is ontvreemd, en het antwoord erop is niet
alleen dit verzoek weigeren maar **alle** rijen van die gebruiker intrekken. Er gaat een
`LOGIN_FAILED` naar het auditlogboek met de reden als vaste code, niet als vrije tekst.

### 5.4 `DEFAULT_AUTHENTICATION_CLASSES` blijft leeg

De authenticatieklasse wordt per view gezet, alleen op de acht routes hierboven.
`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` blijft `[]` in `base.py`.

Gevolg: de drie adviesendpoints blijven letterlijk anoniem en kunnen niet per ongeluk een
cookie-identiteit gaan accepteren. `tests/test_backend_settings.py` controleert die lege lijst al
en blijft groen omdat de zin waar is, niet omdat de assertie is weggehaald.

`CookieJWTAuthentication` in `backend/accounts/authentication.py` leest het access-token
**uitsluitend** uit de cookie en nooit uit een `Authorization`-header. Dat is dezelfde
redenering als in hoofdstuk 8 van `docs/dpia.md` over het advies-token in het pad: een tweede
aanvaarde plaats voor een credential is een tweede plaats waar het kan uitlekken, en een header
belandt makkelijker in een proxy-log dan een cookie. De klasse implementeert
`authenticate_header`, zodat een niet-ingelogde aanroep 401 krijgt en niet 403.

### 5.5 CSRF

`backend/ampeer/settings/base.py` beschrijft `CsrfViewMiddleware` vandaag als "here for the first
view that is neither of those", waarbij "those" een anonieme POST en een DRF-view zonder sessie
zijn. Dit is die view.

`SameSite=Strict` is de eerste verdediging en in dit deployment vrijwel volledig. De tweede komt
er goedkoop bij: `CookieJWTAuthentication` roept op onveilige methodes `enforce_csrf()` aan,
precies zoals DRF's eigen `SessionAuthentication` dat doet. Dat hergebruikt Django's beproefde
machinerie in plaats van een eigen double-submit te schrijven.

Dat dekt de zes routes achter een login, maar niet `register/` en `login/`, want daar is nog geen
cookie en draait de authenticatieklasse dus niet. Die twee krijgen daarom `csrf_protect`
expliciet, tegen login-CSRF, waarbij een aanvaller het slachtoffer in het account van de
aanvaller laat inloggen.

Daarvoor moet de browser al een `csrftoken` hebben voordat hij post, en die moet dus ook gezet
worden op een antwoord aan iemand die nog niet is ingelogd. `_AuthAPIView` doet dat in
`finalize_response` door `django.middleware.csrf.get_token(request)` aan te roepen, waarna
`CsrfViewMiddleware` de cookie meestuurt. Dat is bewust dezelfde plaats waar `_NoStoreAPIView` in
`backend/advice/views.py` zijn `Cache-Control` zet, en het is de enige plaats die werkt: DRF roept
`finalize_response` ook aan voor het antwoord dat uit `handle_exception` komt, dus de cookie komt
mee op een 401 en op een 403.

De eerste aanroep is in de praktijk `GET /api/auth/me/`, en dat is geen extra stap. Een frontend
met httpOnly cookies heeft geen andere manier om te weten of er iemand is ingelogd, dus die
aanroep stond er toch al.

Een aanpak die niet werkt en daarom hier staat: de cookie zetten in de view van `me/` zelf.
`me/` staat op `IsAuthenticated`, dus voor een uitgelogde bezoeker antwoordt DRF met 401 voordat
de view draait, en dan wordt er nooit een token gezet. Precies degene die moet gaan inloggen zou
de cookie dus niet krijgen, en `login/` zou onbereikbaar zijn.

`CSRF_COOKIE_SAMESITE = "Strict"` en `CSRF_COOKIE_HTTPONLY = False` komen in `base.py`. Die
tweede is geen verzwakking maar de voorwaarde: een double-submit-token dat JavaScript niet kan
lezen kan JavaScript ook niet meesturen.

## 6. Het toestemmingsmodel

Twee soorten, apart, geen van beide voorgevinkt, elk met een eigen tijdstempel, en intrekking
vastgelegd. Dat zijn de vier eisen uit `CLAUDE.md` en ze worden alle vier afzonderlijk getest.

`METER_LINK` wordt gevraagd in dezelfde stap als het account, want dat is de enige reden dat het
account bestaat. `LEAD_GENERATION` wordt **ook** gevraagd, en het antwoord mag nee zijn zonder
dat er iets stukgaat.

Dat tweede is de plek waar de neutraliteitsregel uit `CLAUDE.md` technisch afdwingbaar wordt.
Die regel zegt dat elk stuk code dat het advies laat afhangen van een commerciële relatie een bug
is. Dit hoofdstuk vroeg om een test die een advies berekent met `LEAD_GENERATION` op `False` en op
`True` en eist dat het antwoord byte voor byte gelijk is. Wat er ligt is een andere toets, met
opzet: `tests/test_accounts_consent.py::test_nothing_that_computes_an_advice_can_see_a_consent`
scant de adviescode op het woordenboek van een toestemming (`Consent`, `LEAD_GENERATION`,
`consent_lead`) in plaats van twee adviezen te berekenen en te vergelijken. De byte-voor-byte
versie is een test van een negatief: hij slaagt zolang niemand de koppeling geschreven heeft, en
zegt daarna niets meer. De scan faalt zodra iemand die koppeling schrijft, in dezelfde diff, en is
bovendien niet traag. Dat is de vervanging die hoofdstuk 13, punt 4, hieronder ook noemt.

Niet-voorgevinkt is een eigenschap van de serializer en niet van de tekst op het scherm: het veld
heeft geen `default`, dus een ontbrekend veld is een 400 en niet een stilzwijgende `True`. Een
frontend die het vakje vergeet te tonen krijgt een foutmelding in plaats van een toestemming.

**Een `False` op `METER_LINK` weigert de registratie niet.** Het account wordt aangemaakt en er
wordt geen toestemmingsrij geschreven. Dat is contra-intuïtief, want de meterkoppeling is de enige
reden dat het account bestaat, en het is precies daarom belangrijk: artikel 7 lid 4 AVG zegt dat
bij de beoordeling of toestemming vrijelijk is gegeven rekening wordt gehouden met de vraag of
een dienst afhankelijk is gemaakt van toestemming die daarvoor niet nodig is. Een registratie die
zonder `METER_LINK` weigert, maakt de toestemming tot een voorwaarde, en een toestemming die de
enige weg naar de dienst is, is als grondslag zwak. Wat er dan gebeurt is dat het account bestaat
en de koppeling niet start, en dat is een gevolg van de keuze van het huishouden en niet een straf
van de dienst. Fase 2 controleert `Consent.current(user, METER_LINK)` voordat er ook maar één
meting binnenkomt, en dat is de plek waar de toestemming werk doet.

De Nederlandse teksten staan in `backend/accounts/nl.py`, gekoppeld aan Engelse ids, exact het
patroon van `backend/advice/nl.py`. Dat bestand legt in zijn eigen docstring een regel vast die
hier overgenomen wordt: een validatiemelding benoemt een veld en spreekt de lezer niet aan, want
zodra er "vul uw e-mailadres in" staat is het een zin waarin iemand wordt toegesproken en gelden
de registerafspraken uit `docs/decisions.md`. De toestemmingsteksten zelf zijn wel zinnen aan een
huishouden en volgen die afspraken dus wel.

Wachtwoordvalidatie gebruikt Django's eigen `AUTH_PASSWORD_VALIDATORS`, met
`MinimumLengthValidator` op 12 in plaats van 8. Die meldingen komen Nederlands binnen via
Django's eigen vertalingen bij `LANGUAGE_CODE = "nl-nl"`, dus daar hoeft geen Nederlands in de
logica te staan. Alleen wat Ampeer zelf schrijft gaat naar `accounts/nl.py`.

## 7. Het auditlog

`advice.models.AuditEvent` wordt hergebruikt waar hij staat. `AppendOnlyQuerySet` levert de eis
al: `save()` weigert een update van een bestaande rij, en `delete()` werpt op zowel instantie- als
querysetniveau.

Nieuwe gebeurtenistypen, precies de gebeurtenissen die deze fase toevoegt:

`ACCOUNT_CREATED`, `LOGIN_SUCCEEDED`, `LOGIN_FAILED`, `LOGOUT`, `CONSENT_GRANTED`,
`CONSENT_WITHDRAWN`, `DATA_EXPORTED`, `ACCOUNT_DELETED`.

Wat er niet bij komt: `koppeling aangemaakt` en `lead verstuurd` uit de lijst in `CLAUDE.md`.
Beide horen bij een handeling die nog niet bestaat, en `docs/dpia.md` hoofdstuk 2 geeft de reden
die hier woordelijk geldt: een logboek dat ze nu al noemde zou een verwerking beschrijven die er
niet is.

Wat er per regel in `context` staat is `user_id` als geheel getal, en **nooit het e-mailadres**.
Dat is dezelfde beslissing als `token_sha256` in plaats van `token` in `advice/service.py`. Het
logboek wordt nooit opgeruimd, dus alles wat erin staat blijft staan nadat het account weg is.
Een geheel getal dat naar een verwijderde rij wijst is een lege verwijzing; een e-mailadres is een
permanent persoonsgegeven in een tabel zonder bewaartermijn.

Bij `LOGIN_FAILED` staat het `user_id` erin als het account bestaat, en anders niets
identificerends. **Niet het geprobeerde e-mailadres.** Dat zou het adres van iemand zijn die
misschien geen klant is, permanent bewaard, en het is precies wat een aanvaller die adressen
uitprobeert erin zou schrijven.

Dit breekt met opzet `tests/test_dpia.py::test_the_audit_log_records_exactly_what_the_document_says_it_does`,
die `kinds == ["ADVICE_GENERATED"]` afdwingt. Dat is de hele functie van die test: hij dwingt af
dat `docs/dpia.md` in dezelfde commit wordt herschreven in plaats van erna. Hoofdstuk 9 van dat
document is met het oog hierop geschreven.

## 8. Export en verwijderen

`CLAUDE.md` zet de export- en verwijderknop bij de fase waarin accounts bestaan. Dat is deze
fase, dus ze werken allebei in v1. `docs/dpia.md` hoofdstuk 10 punt 4 legde de vraag of
verwijderen mogelijk wordt bij de verwerkingsverantwoordelijke; die is op 2026-09-04 beantwoord
met ja, en dat hoofdstuk moet dat gaan zeggen.

### 8.1 Export

`POST /api/auth/export/` geeft in één JSON-antwoord terug: het e-mailadres, `date_joined`, alle
`Consent`-rijen met hun tijdstempel en tekstversie, en van elk `StoredAdvice` met deze eigenaar
zowel `inputs` als `advice`.

Een POST en geen GET, om twee redenen die allebei zwaarder wegen dan de gewoonte. De handeling
schrijft een `DATA_EXPORTED`-regel in het auditlogboek, en een GET met een bijwerking is een GET
die een browser of proxy mag herhalen. En het antwoord beschrijft één huishouden volledig, dus
het moet onder `Cache-Control: private, no-store` vallen, wat `_NoStoreAPIView` in
`advice/views.py` al doet en wat deze views overnemen.

**De adviezenlijst is in v1 altijd leeg, en dat moet erbij gezegd worden.** Niets in deze fase
vult `StoredAdvice.owner`: er is geen claim-route (hoofdstuk 11) en fase 2 bestaat nog niet. De
export levert dus in de praktijk het e-mailadres, `date_joined` en de toestemmingsrijen, met een
lege lijst ernaast. Dat is geen bug en ook geen dood veld: het is de vorm waar fase 2 in schrijft,
en het testregime vult hem rechtstreeks via de ORM zodat de vorm nu al vastligt.

Dat `inputs` erin zit lost daarmee structureel een tekortkoming op die `docs/dpia.md` hoofdstuk 7
zelf benoemt, namelijk dat de tokenroute het advies teruggeeft en niet de antwoorden waarmee het
gemaakt is, zodat een bezoeker de uitkomst ziet en niet de invoer. Structureel, en vandaag nog
niet materieel, want er is nog geen advies met een eigenaar. Voor de anonieme tokenroute verandert
er sowieso niets. Hoofdstuk 7 van dat document moet die drie dingen uit elkaar houden in plaats
van te beweren dat de tekortkoming verholpen is.

De opgeslagen JSON gaat **ongewijzigd** mee. Niet opnieuw renderen. Elk bedrag in een advies is
een string omdat JSON alleen floats kent, en een export die het antwoord opnieuw zou opbouwen is
een extra plek waar een bedrag door een parser gaat. Doorgeven wat er staat is hier zowel het
eenvoudigst als het enige veilige.

`auth-export` krijgt een eigen scope op 5 per uur. Een advies is volgens `docs/dpia.md` hoofdstuk
6 ongeveer 91 kB, dus een export van een account met tien adviezen is bijna een megabyte, en dat
is de duurste respons die deze API kent.

### 8.2 Verwijderen

`POST /api/auth/delete/`, met het huidige wachtwoord in de body als bevestiging.

Een POST en geen `DELETE`-werkwoord, om twee redenen. De eerste staat in 5.1: de DPIA beschrijft
een API die leest en rekent, en `test_the_api_answers_only_the_verbs_the_document_describes` pint
dat op `{get, post}`. De tweede is technisch en zou op zichzelf al genoeg zijn: deze route heeft
een body nodig, want zonder wachtwoordbevestiging is één gestolen sessie genoeg om iemands
gegevens te wissen, en een `DELETE` met een body is iets waar proxies en clients het onderling
niet over eens zijn.

Wat er verdwijnt, in één transactie:

- de `User`-rij
- elke `Consent`-rij, via `CASCADE`
- elke `RefreshSession`, via `CASCADE`
- elk `StoredAdvice` met deze eigenaar, via `CASCADE`, zie 4.3

Die laatste regel raakt in v1 nul rijen, om dezelfde reden als in 8.1: niets vult `owner` in deze
fase. De keuze voor `CASCADE` moet nu toch gemaakt worden, want ze zit in de migratie en niet in
een view, en het testregime dwingt het gedrag af op een rij die de test zelf koppelt.

Wat blijft staan is het auditlogboek, inclusief een nieuwe `ACCOUNT_DELETED`-regel met het
`user_id` erin. Dat is geen omissie maar de constructie uit 4.5: een append-only logboek dat een
verwijdering vastlegt en zichzelf daarbij wist, legt niets vast.

Die regel wordt binnen dezelfde transactie geschreven als de verwijdering, niet ervoor en niet
erna. Ervoor zou een mislukte verwijdering een logboekregel achterlaten die zegt dat er iets
gebeurd is wat niet gebeurd is; erna zou een mislukte schrijving een verwijdering achterlaten die
nergens staat. Dat is dezelfde afweging die `advice/service.py` maakt over de volgorde van de rij
en de payload, en ze wordt hier expliciet gemaakt omdat `AuditEvent` de enige tabel is die niets
kan herbouwen.

Wat een advies met `owner IS NULL` betreft gebeurt er niets, want dat is niet van dit account.
Iemand die eerst anoniem heeft gerekend en daarna een account heeft gemaakt houdt die anonieme
adviezen dus tot ze na negentig dagen vervallen. Dat is eerlijk om te zeggen en het volgt uit het
ontbreken van een claim-route, zie hoofdstuk 11.

Twee bestaande beloften blijven onverkort gelden en worden hier niet opnieuw uitgevonden.
`docs/dpia.md` hoofdstuk 4 legt uit dat `DELETE` een rij als dood markeert en niet overschrijft,
en dat de belofte is dat de dienst het niet meer teruggeeft en niet meer kan vinden. En een
verwijderd advies kan nog ten hoogste acht dagen in een back-upbestand staan, met de drie
begrenzingen die daar staan. Beide zinnen gelden woord voor woord voor een verwijderd account, en
hoofdstuk 4 van dat document moet dat gaan zeggen in plaats van het alleen over adviezen te
hebben.

## 9. Beveiliging en instellingen

### 9.1 Argon2id

`PASSWORD_HASHERS` met `django.contrib.auth.hashers.Argon2PasswordHasher` op de eerste plaats.
`CLAUDE.md` vraagt om Argon2**id**, en dat is een eigenschap van de hasher en niet van de naam:
een test leest het `type`-attribuut terug en eist `argon2.low_level.Type.ID`. Aannemen dat de
variant klopt omdat de klasse Argon2 heet is precies het soort controle dat niet rood kan worden.

### 9.2 De vier dingen die in één commit binnenkomen

Zodra `django.contrib.auth` in `INSTALLED_APPS` staat, moeten in dezelfde commit staan: de app
`axes`, `axes.backends.AxesStandaloneBackend` als **eerste** in `AUTHENTICATION_BACKENDS`,
`axes.middleware.AxesMiddleware` in `MIDDLEWARE`, en een Argon2-hasher vooraan in
`PASSWORD_HASHERS`. Dat is niet een lijstje uit dit document maar wat de test uit 3.1 afdwingt,
inclusief de volgorde: een lockout die als tweede draait is een lockout die de poging al is
gepasseerd.

### 9.3 axes zonder een adres en zonder een adresboek

Drie instellingen, en alle drie hebben ze een reden die uit deze repository komt.

`AXES_HANDLER = "axes.handlers.cache.AxesCacheHandler"`, zodat `AccessAttempt`, `AccessLog` en
`AccessFailureLog` (elk met een `ip_address`-kolom, meegebracht door `axes` zelf, en aanwezig
ongeacht deze instelling) nooit een rij krijgen. Zie 3.2. In productie is de cache `DatabaseCache` in Postgres,
dus de teller wordt gedeeld over de drie gunicorn-workers en overleeft een deploy, en dat is
precies wat een lockout nodig heeft. Dat is dezelfde afweging die `prod.py` al maakt voor de
teller van de snelheidslimiet, met dezelfde uitleg erbij.

`AXES_CLIENT_IP_CALLABLE` wijst naar een functie die dezelfde digest teruggeeft die
`advice/throttling.py` al berekent. Dat is een bewuste afwijking en geen eigen `KEY_SALT`: de
callable hergebruikt `HashedIdentScopedRateThrottle.get_ident` rechtstreeks in plaats van zelf
opnieuw te zouten. Twee definities van "dezelfde bezoeker" die met elkaar moeten kloppen zijn
anders een definitie die dat op termijn niet meer doet, en axes en de snelheidslimiet mogen hier
juist wel dezelfde teller delen: allebei zijn ze een digest van dezelfde bezoeker, dus een botsing
tussen de twee is de bedoeling en geen lek. Dan telt axes per bezoeker zonder ergens een adres neer
te zetten.

`AXES_USERNAME_CALLABLE` doet hetzelfde met het e-mailadres, en dat is de instelling die het
snelst over het hoofd gezien wordt. Zonder haar staat het geprobeerde e-mailadres in een
cachesleutel, en die cache is in productie een rij in de tabel `ampeer_cache`. Dan zou het
leeg laten blijven van de axes-tabellen alleen het adres hebben weggehaald en het adresboek
hebben laten staan.

Die callable raakt alleen wat axes telt en opslaat, niet waarmee wordt ingelogd. De view geeft het
echte e-mailadres aan de authenticatie door, want anders valt er niets op te zoeken; axes ziet
daarvan alleen de digest, en die is stabiel per account omdat het adres volgens 4.1 al in kleine
letters is genormaliseerd voordat er iets mee gebeurt.

Verder `AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]`, dus de combinatie van beide
digests, en `AXES_FAILURE_LIMIT = 5` met `AXES_COOLOFF_TIME` op een uur. Alleen op username
sluiten laat iedereen elk account op afstand blokkeren; alleen op adres sluiten laat een
aanvaller achter een grote NAT ongemoeid.

### 9.4 Snelheidslimieten

Zes nieuwe scopes in `DEFAULT_THROTTLE_RATES` in `base.py`:

| Scope | Limiet | Reden |
|---|---|---|
| `auth-register` | 5/uur | Een echt huishouden registreert één keer. Dit is er om massaal aanmaken te stoppen, niet om een vergissing te straffen |
| `auth-login` | 10/uur | Ruim voor iemand die zich vertypt, en axes doet de lockout. Deze limiet doet het volume, niet de verdediging |
| `auth-refresh` | 60/uur | Een access-token leeft 15 minuten, dus vier verversingen per uur per apparaat. Zestig laat meerdere apparaten toe |
| `auth-read` | 120/uur | `me/` is het beginpunt van elke paginalading. Dezelfde ruimte als `advice-read`, om dezelfde reden |
| `auth-write` | 20/uur | Toestemming, uitloggen en verwijderen. Handelingen die een mens een paar keer doet |
| `auth-export` | 5/uur | De duurste respons die deze API kent, zie 8.1 |

`tests/test_backend_settings.py::test_every_public_route_is_rate_limited` loopt de resolver af en
dekt de acht nieuwe routes automatisch, inclusief de valkuil die die test beschrijft: DRF
antwoordt een view zonder `throttle_scope` zonder enige limiet, en dat is één ontbrekend attribuut
dat niets logt en niets werpt. De globale limiet van 5r/s in `infra/nginx/nginx.conf` geldt er
ook voor, want die is gesleuteld op `$server_name`.

De routes onder `/api/auth/` dragen geen geheim in hun pad, dus het `map`-blok in
`infra/nginx/nginx.conf` mag ze gewoon loggen. Ze vallen op de laatste arm, die elk pad buiten
`/api/advice` en `/advies` als zichzelf doorlaat, en dat is het gewenste gedrag zonder wijziging.

### 9.5 De CORS-uitzondering in `dev.py`

In productie is alles één oorsprong, zie 5.2, dus `CORS_ALLOW_CREDENTIALS` blijft daar `False`.
Op een ontwikkelmachine is `localhost:3000` naar `127.0.0.1:8000` cross-site, en dan stuurt de
browser de cookies niet mee: inloggen werkt daar zonder uitzondering niet.

`dev.py` zet daarom `CORS_ALLOW_CREDENTIALS = True`, alleen voor de drie oorsprongen die daar al
in `CORS_ALLOWED_ORIGINS` staan. Er komt een comment bij dat uitlegt waarom `prod.py` hem niet
zet, en dat verwijst naar de belofte die `base.py` vandaag hardop doet, namelijk dat er geen
cookies over die grens gaan en dat dat uitgeschreven staat zodat een latere view er niet per
ongeluk op gaat leunen. Die belofte blijft waar in productie, en het comment in `base.py` moet
gaan zeggen dat de ontwikkelomgeving de uitzondering is en waarom.

Er komt een test die `prod.CORS_ALLOW_CREDENTIALS is False` afdwingt, naast de bestaande test die
`CORS_ALLOW_ALL_ORIGINS` in de gaten houdt. Zonder die test is de uitzondering in `dev.py` een
regel die iemand een keer naar boven kopieert.

### 9.6 Twee dingen die gemeten moeten worden en nu niet vaststaan

Dit zijn de enige twee open punten in dit ontwerp, en ze staan hier omdat ze niet uit documentatie
te beslissen zijn. Ze horen vooraan in het implementatieplan, niet achteraan, want bij een
negatieve uitkomst verandert er iets aan hoofdstuk 9 en niet aan een regel code.

**Meting 1: is `DatabaseCache.incr` bruikbaar voor een lockout-teller?** Django's `DatabaseCache`
hoogt op met een lezing gevolgd door een schrijving, en of dat onder drie gelijktijdige gunicorn
workers geen pogingen laat vallen is niet gedocumenteerd. Een ondertelling maakt de lockout
losser dan hij lijkt, en dat is stil falen van precies de soort waar deze repository tegen gebouwd
is. Meet het met gelijktijdige mislukte inlogpogingen tegen de draaiende stack en tel wat er
aankomt. Blijkt het niet te kloppen, dan is de terugval de databasehandler met de axes-tabellen,
en dan moet 3.2 opnieuw beantwoord worden in plaats van genegeerd.

**Meting 2: werkt `AxesMiddleware` zonder `AuthenticationMiddleware`?**
`django.contrib.auth.middleware.AuthenticationMiddleware` staat niet in `MIDDLEWARE` en kan er
ook niet in, want die vraagt sessies. Bovendien staat `REST_FRAMEWORK["UNAUTHENTICATED_USER"]` op
`None`, dus `request.user` is `None` en niet `AnonymousUser`. Of axes daartegen kan is een
empirische vraag. Toon aan dat een lockout daadwerkelijk optreedt, met een test die eerst rood is
zonder axes en daarna groen ermee, want een lockout die stil niets doet is de gevaarlijkste
uitkomst van deze twee.

Voor beide geldt de regel die deze repository al hanteert: een groene uitkomst is pas bewijs als
is aangetoond dat het instrument rood kan worden.

## 10. Wachtwoordherstel ontbreekt, en wat dat kost

Er komt in v1 geen wachtwoordherstel en geen e-mailverificatie. Beide vragen uitgaande e-mail, en
daarmee een SMTP-credential in `prod.py`, een afzender, en een tweede kanaal dat vertrouwd moet
worden. Dat is infrastructuur en geen app, en het hoort niet in dezelfde commit als de
accountlaag zelf.

Het gevolg wordt hier benoemd in plaats van later ontdekt. **Wie zijn wachtwoord kwijt is, kan
ook het verwijderendpoint niet meer bereiken**, want dat zit achter de login en vraagt bovendien
datzelfde wachtwoord als bevestiging. Het account blijft dan bestaan met de gegevens erin, en de
enige weg die overblijft is de bestaande opruiming: elk `StoredAdvice` vervalt na negentig dagen,
dus wat er materieel overblijft is een e-mailadres, een wachtwoordhash en een paar
toestemmingsrijen. Dat is de dunste vorm die dit account kan aannemen, en het is niet niets.

Dit is de zwakste plek van dit ontwerp. Ze is aanvaardbaar zolang fase 1 en fase 2 dicht op elkaar
zitten en het aantal accounts klein is, en ze is dat niet meer zodra er maanden tussen zitten met
echte gebruikers.

De goedkoopste latere reparatie is bekend en hoeft niet ontworpen te worden.
`django.contrib.auth.tokens.PasswordResetTokenGenerator` zit al in de app die deze fase
installeert, is ondertekend met `SECRET_KEY`, verloopt vanzelf via
`PASSWORD_RESET_TIMEOUT` en bewaart niets in de database. De codehelft is daarmee twee views en
een tekst in `accounts/nl.py`. Wat ontbreekt is uitsluitend het kanaal: een SMTP-instelling die
`prod.py` volgens zijn eigen regel zonder standaardwaarde uit de omgeving moet lezen, plus de
keuze van een afzender. Het is dus een infrastructuurbeslissing met een klein staartje code, en
niet andersom.

## 11. Wat expliciet niet in v1 zit

- **Geen dashboard, geen adviesgeschiedenis, geen overzichtspagina.** Beslissing van de
  verwerkingsverantwoordelijke. Het account is een voorwaarde voor fase 2 en geen scherm.
- **Geen claim-route voor anoniem gemaakt advies.** De `owner`-kolom komt er, de route niet. Er
  is in v1 geen scherm dat het resultaat zou tonen, en een route die op bezit van een token
  eigendom vestigt is precies de autorisatievraag die `docs/dpia.md` hoofdstuk 7 open laat:
  iedereen aan wie de link ooit is doorgestuurd zou hem kunnen claimen.
- **Geen wachtwoordherstel en geen e-mailverificatie.** Zie hoofdstuk 10, inclusief het gevolg.
- **Geen adminsite.** `base.py` sluit die uit met de reden dat een geïnstalleerde app
  aanvalsoppervlak is of er nu een URL naar wijst of niet, en dit ontwerp verandert dat niet.
- **Geen tweefactorauthenticatie, geen inloggen via derden, geen apparatenoverzicht.**
  `RefreshSession` maakt dat laatste later goedkoop, maar het is nu een scherm zonder vraag
  erachter.
- **Geen `token_blacklist`-app van simplejwt.** Vervangen door `RefreshSession`, zie 3.3.
- **Geen `PermissionsMixin`, geen groepen, geen rollen.** Zie 4.1.
- **Geen wijziging aan `estimate/`, `refine/` en de tokenroute.** Die blijven anoniem, zonder
  cookie en zonder authenticatieklasse, en er staat een test op dat ze dat blijven.

## 12. Afhankelijkheden

Drie pakketten, geen ervan staat vandaag in `uv.lock`. Alle drie via `uv add --group backend`,
met `uv.lock` meegecommit, zoals `CLAUDE.md` voorschrijft.

| Pakket | Waarvoor |
|---|---|
| `djangorestframework-simplejwt` | Het uitgeven en verifiëren van de tokens. Uitsluitend dat; de blacklist-app blijft ongebruikt |
| `django-axes` | De lockout die `CLAUDE.md` eist, met de instellingen uit 9.3 |
| `argon2-cffi` | Wat `Argon2PasswordHasher` nodig heeft om te kunnen werken |

`argon2-cffi` draagt een C-extensie, dus `infra/api.Dockerfile` moet nagelopen worden op de
bouwomgeving. De jobs `dependencies` en `sast` pakken de drie vanzelf op via `pip-audit` en
`cyclonedx-bom`.

Als `prod.py` een nieuwe verplichte omgevingsvariabele krijgt, moet die ook in de stap "Django
deployment checklist" in `.github/workflows/ci.yml`. `tests/test_backend_settings.py` bewaakt dat
al, met de uitleg erbij van de keer dat het misging toen CORS arriveerde: de instelling weigerde
terecht te starten en de job was er nooit over ingelicht.

## 13. Testregime

De dekkingsdrempel staat op 98,00 met `precision = 2`, mag omhoog en nooit omlaag, en `backend`
staat al in `[tool.coverage.run] source`. Elke regel die deze fase toevoegt telt dus vanaf de
eerste commit mee. De nieuwe bestanden volgen de naamgeving in `tests/`.

1. **`tests/test_accounts_models.py`** Normalisatie van het e-mailadres, inclusief dat een tweede
   registratie met andere hoofdletters een 400 is en geen tweede rij. Dat `Consent.current()` de
   laatste rij leest en niet de eerste, dat afwezigheid `False` oplevert, en dat een grant na een
   withdrawal weer `True` geeft. Dat `RefreshSession` de digest bewaart en de `jti` nergens
   letterlijk voorkomt.
2. **`tests/test_accounts_api.py`** Het contract per route: statuscode, antwoordvorm, en de
   cookie-attributen uit de echte respons. `httponly`, `samesite`, `path` en `secure` worden stuk
   voor stuk uit `response.cookies` gelezen. Een test die alleen 200 controleert zegt niets over
   `SameSite`.
3. **`tests/test_accounts_auth.py`** Rotatie in vier gevallen: een geldig token roteert, hetzelfde
   token een tweede keer wordt geweigerd, hergebruik trekt de hele keten van die gebruiker in, en
   een verlopen token geeft 401. Plus dat een access-token in een `Authorization`-header **niet**
   wordt aanvaard, en dat een onveilige methode zonder `X-CSRFToken` wordt geweigerd.
4. **`tests/test_accounts_consent.py`** De vier eisen uit `CLAUDE.md` afzonderlijk, plus de
   neutraliteitstest uit hoofdstuk 6. Niet de byte-voor-byte vergelijking die hoofdstuk 6 eerst
   voorstelde: `test_nothing_that_computes_an_advice_can_see_a_consent` scant `backend/advice`,
   `ampeer_advice` en `ampeer_sim` op het woordenboek van een toestemming in plaats van twee
   adviezen te berekenen, precies omdat een test van een negatief anders zwak en traag tegelijk
   zou zijn.
5. **`tests/test_accounts_privacy.py`** Dat geen enkel model in `backend/accounts/` een
   adresachtige kolom heeft, dat geen `AuditEvent`-context een e-mailadres bevat, en dat de export
   de opgeslagen JSON ongewijzigd doorgeeft in plaats van bedragen opnieuw op te bouwen.
6. **`tests/test_accounts_deletion.py`** Dat verwijderen de gebruiker, zijn toestemmingen, zijn
   sessies en zijn adviezen meeneemt; dat een advies met `owner IS NULL` blijft staan; en dat het
   auditlogboek de `ACCOUNT_DELETED`-regel houdt.
7. **Uitbreiding van `tests/test_backend_settings.py`** De hasher is Argon2**id** en niet alleen
   Argon2. De adviesendpoints hebben geen authenticatieklasse. `prod.CORS_ALLOW_CREDENTIALS` is
   `False`. En de twee metingen uit 9.6, elk met een aangetoond rood.
8. **Uitbreiding van `tests/test_advice_api.py`** Eén toevoeging die het meeste waard is: een
   advies met `owner IS NULL` blijft opvraagbaar op zijn token, en een advies met een `owner`
   **ook**. Eigendom voegt toe en neemt niets af.
9. **Uitbreiding van `tests/test_dpia.py`** De padconstanten `MODELS` en `VIEWS` worden lijsten,
   zie hoofdstuk 14, en de nieuwe gebeurtenistypen worden naast het herschreven document gelegd.

Van elke nieuwe controle wordt aangetoond dat hij rood kan worden. Dat is niet een extra stap maar
de werkwijze die dit project al hanteert, en 9.6 noemt de twee gevallen waar het het meest toe
doet.

## 14. Wat in dezelfde commit mee moet veranderen

Zonder deze lijst is de suite groen over een boom die hij niet meer helemaal leest, en dat is de
faalvorm die 3.2 beschrijft.

| Bestand | Wat er moet gebeuren |
|---|---|
| `tests/test_dpia.py` | `MODELS` en `VIEWS` wijzen op naam naar `backend/advice/models.py` en `backend/advice/views.py`. `VIEWS` wordt een lijst die `backend/accounts/` meeneemt; `MODELS` blijft één pad en krijgt een eigen `ACCOUNT_MODELS` ernaast, omdat twee bestaande tests `MODELS.read_text()` rechtstreeks aanroepen voor een eigenschap van alleen `advice/models.py`. Zonder deze wijziging ontsnappen precies de modellen met persoonsgegevens aan de adrescontrole en de nieuwe views aan de werkwoordcontrole |
| `tests/test_dpia.py` | `test_the_audit_log_records_exactly_what_the_document_says_it_does` krijgt de acht nieuwe gebeurtenistypen, samen met het herschreven document en niet los ervan |
| `tests/test_backend_settings.py` | `test_nothing_authenticates_because_there_is_nothing_to_log_in_to` beweert `"django.contrib.auth" not in settings.INSTALLED_APPS`, en die regel wordt onwaar zodra `AUTH_USER_MODEL` die app nodig heeft. Die ene assertie gaat eruit, de drie andere (geen sessies, geen admin, lege `DEFAULT_AUTHENTICATION_CLASSES`) blijven staan, en de docstring wordt herschreven naar die versmalde belofte |
| `docs/dpia.md` hoofdstuk 1 | De conclusie dat een beoordeling waarschijnlijk niet verplicht is, gold voor fase 0.5 en zegt zelf dat de reden bij de volgende fase verdwijnt |
| `docs/dpia.md` hoofdstuk 2 | Een e-mailadres, een wachtwoordhash, inlogpogingen en toestemmingsrijen bestaan nu. De zin "Er is niets om in te loggen" moet weg. De zin "Geen IP-adres in enige tabel" blijft staan, en 9.3 is de reden dat dat mag |
| `docs/dpia.md` hoofdstuk 4 | De bewaartermijnen en de back-upruil gelden nu ook voor een verwijderd account, niet alleen voor een vervallen advies |
| `docs/dpia.md` hoofdstuk 7 | Inzage, overdraagbaarheid en verwijdering veranderen alle drie voor een accounthouder en veranderen niet voor de anonieme tokenroute. Het onderscheid moet er in staan, inclusief dat de export de invoer structureel bereikbaar maakt en materieel pas in fase 2, zie 8.1. De zinnen "Er is geen vierde." en "Er is geen verwijderknop en geen verwijderendpoint." worden onwaar; `tests/test_dpia.py` controleert allebei letterlijk |
| `docs/dpia.md` hoofdstuk 9 | Dit hoofdstuk beschrijft wat er bij fase 1 verandert. Het is nu geen vooruitblik meer |
| `docs/dpia.md` hoofdstuk 10 | Punt 2 gaat over de grondslag en punt 4 over verwijderen op verzoek. Punt 4 is beantwoord met ja; punt 2 staat voorlopig op toestemming |
| `docs/decisions.md` | Een entry per beslissing in het bestaande formaat: het eigen gebruikersmodel, `CASCADE` op `owner`, `RefreshSession` in plaats van `token_blacklist`, de axes-cachehandler, en het ontbreken van wachtwoordherstel met het gevolg uit hoofdstuk 10 |
| `backend/advice/views.py` | De moduledocstring opent met "Three endpoints, anonymous, no cookie, no session." Dat blijft waar voor dat bestand en moet dat blijven, maar de zin verdient een verwijzing naar waar het wel gebeurt |
| `backend/advice/models.py` | De moduledocstring zegt dat geen van de tabellen een persoonsgegeven bevat. `StoredAdvice` krijgt een `owner`, en dat is een verwijzing naar een persoon. De zin moet nauwkeuriger worden in plaats van geschrapt |
| `backend/ampeer/settings/base.py` | Het comment bij `CORS_ALLOW_CREDENTIALS` moet zeggen dat de ontwikkelomgeving de uitzondering is, en waarom productie hem niet nodig heeft |
| `.github/workflows/ci.yml` | Alleen als `prod.py` een nieuwe verplichte omgevingsvariabele krijgt. Zie hoofdstuk 12 |

**Deze commit is groot, en dat is een gevolg en geen keuze.** Drie bestaande tests binden code en
document aan elkaar: de valstrik uit 3.1, de werkwoordcontrole uit 5.1 en de logboekcontrole uit
hoofdstuk 7. Elk van de drie is er om te voorkomen dat een verwerking eerder bestaat dan de
beschrijving ervan, dus ze doen precies hun werk.

Wat daaruit volgt voor de fasering van het implementatieplan: de accountlaag en de export- en
verwijderroute kunnen niet in twee pull requests. De zinnen "Er is geen vierde." en "Er is geen
verwijderknop en geen verwijderendpoint." in `docs/dpia.md` zouden dan twee keer herschreven
worden, en de tussenliggende toestand zou een dienst zijn met accounts en zonder de knoppen die
`CLAUDE.md` bij die fase eist. Wat wel kan, en wat de aanbevolen volgorde binnen één branch is:
eerst de twee metingen uit 9.6, dan het datamodel en de migraties, dan de auth-flow, dan export en
verwijderen, en de documenten als laatste, wanneer er niets meer verschuift.

## 15. Definition of done

- Registreren, inloggen, verversen en uitloggen werken over de echte HTTP-route, met cookies die
  `httponly`, `SameSite=Strict` en het juiste pad dragen, aangetoond uit de respons
- Een tweede inwisseling van hetzelfde refresh-token wordt geweigerd en trekt de keten in
- Er staat nergens een bruikbaar credential in de database: geen refresh-token, geen `jti`, geen
  ingest-token
- Er staat nergens een IP-adres of een e-mailadres in een tabel, een cachesleutel of een
  auditregel, aangetoond door een test die de nieuwe app meeleest
- Beide toestemmingen zijn apart, hebben elk een tijdstempel, kunnen los ingetrokken worden, en
  een ontbrekend veld is een 400
- Export geeft e-mailadres, `date_joined`, toestemmingen en de adviezenlijst terug, met bedragen
  als string. Die lijst is in v1 leeg voor elk echt account, en de vorm ervan is aangetoond op een
  advies dat de test zelf aan een gebruiker koppelt
- Verwijderen wist gebruiker, toestemmingen, sessies en eigen adviezen, laat anonieme adviezen
  staan, en laat het auditlogboek staan, aangetoond op datzelfde gekoppelde advies
- Elke nieuwe route heeft een scope met een tarief, afgedwongen door de bestaande resolverwalk
- De twee metingen uit 9.6 zijn uitgevoerd en het resultaat staat in `docs/decisions.md`
- Dekking blijft 98 of hoger en `precision = 2` blijft staan
- `mypy --strict` blijft schoon over `backend`, inclusief de nieuwe app
- Elke wijziging uit hoofdstuk 14 zit in dezelfde pull request

## 16. Wat dit ontwerp voor fase 2 openhoudt

Fase 2 is uitdrukkelijk buiten scope, en dit hoofdstuk bestaat om te zeggen dat er niets is
dichtgetimmerd.

`StoredAdvice.owner` bestaat al, dus een advies uit gemeten data heeft een eigenaar zonder
migratie over bestaande rijen. `year_field(..., shareable_token=False)` in
`backend/advice/serializers.py` bestaat al en is precies bedoeld voor een advies dat achter een
account wordt opgehaald in plaats van achter een doorstuurbare link; niets in deze fase gebruikt
die uitgang en niets erin verhindert hem. De route die zo'n advies teruggeeft moet een **andere**
route zijn dan de tokenroute en moet filteren op `owner`, nooit op `pk` alleen.

`advice.models.token_digest` en zijn uitleg zijn het patroon voor de ingest-tokens die fase 2
gehasht moet opslaan. `RefreshSession` laat zien hoe dat er voor een roterend credential uitziet.

`AuditEvent` heeft dan alleen nog `koppeling aangemaakt` en `lead verstuurd` nodig, en de reden
dat die er nu niet in staan is dezelfde reden waarom ze er dan wel in horen: de handeling bestaat
dan.
