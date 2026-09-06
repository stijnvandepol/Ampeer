# Ontwerp: wachtwoordherstel en e-mailbevestiging (fase 1, deel 3)

Datum: 2026-09-06
Status: vastgesteld, klaar voor implementatieplan
Betreft: `backend/accounts/`, het eerste uitgaande mailkanaal van dit project, twee nieuwe
weergaven op `/account/`, en de documenten die daar iets van moeten vinden

## 1. Doel en afbakening

Wie zijn wachtwoord kwijt is, moet een nieuw kunnen kiezen. Wie een account aanmaakt, moet
kunnen aantonen dat het adres van hem is. Meer niet.

Dit is het derde deel van fase 1. Het auth-ontwerp
(`docs/superpowers/specs/2026-09-04-accounts-auth-design.md`, hoofdstuk 10) liet beide
weg en noemde dat de zwakste plek van dat ontwerp: wie zijn wachtwoord kwijt is, bereikt ook
het verwijderendpoint niet meer, en dat is aanvaardbaar "zolang fase 1 en fase 2 dicht op
elkaar zitten en het aantal accounts klein is". Beslissing 31 in `docs/decisions.md` legde het
vast als een beslissing met een eigen omkeerclausule: een `EMAIL_BACKEND`, twee routes, en
hoofdstuk 7 van de DPIA bijwerken. Dit document is die omkering, met één afwijking die
hoofdstuk 2 verantwoordt: het token wordt geen handtekening maar een rij.

Waarom nu. Fase 2 is de meterkoppeling, en die vraagt om een adres waarvan vaststaat dat het
bij de persoon hoort die kwartierdata gaat aanleveren. Bevestiging van het adres hoort dus
vóór fase 2 te bestaan, en wachtwoordherstel vraagt hetzelfde kanaal. Twee stromen, één
kanaal, één cyclus.

Binnen scope:

- `OneTimeToken`, één tabel voor beide stromen, en het veld `email_verified_at` op `User`
- Vier routes onder `/api/auth/`, waarmee het er dertien worden
- Het mailkanaal: een outbox-tabel, een management command op een timer, en één module die
  Resend bereikt
- Twee nieuwe uitgelogde weergaven op `/account/`, en een statusregel in de accountweergave
- De labels van de twee toestemmingen uit de API, onder dezelfde versie als de teksten, wat
  beslissing 38 sluit
- De documenten: DPIA, beslissingen, de twee eerdere ontwerpen, en de allowlist-zin in
  CLAUDE.md, die de eigenaar op 2026-09-06 heeft laten bijwerken

Buiten scope, en hoofdstuk 10 zegt per punt waarom:

- Geen HTML-mail
- Geen wijziging aan `frontend/src/lib/api.ts`
- Geen Celery en geen Redis in het verzoekpad
- Geen nieuw pad in de frontend: de link landt op `/account/`
- Geen inloggen na een geslaagd herstel

De keuzes in dit document zijn op 2026-09-06 met de eigenaar doorgenomen in vijf secties,
en hij nam vijf besluiten: bevestiging is een tijdstip dat de meterkoppeling straks eist en
dat niets anders blokkeert; de afzender is `noreply@ampeer.nl`; de mail verlaat het systeem
via een outbox en een timer; de link draagt zijn token in het fragment; en Resend is het
kanaal, omdat hij daar al een account heeft.

## 2. Het token

### 2.1 Eén tabel, twee soorten

`OneTimeToken` in `backend/accounts/models.py`:

| Veld | Type | Betekenis |
|---|---|---|
| `user` | FK naar `accounts.User`, `CASCADE`, `related_name="one_time_tokens"` | Van wie |
| `kind` | `CharField(16)`, `PASSWORD_RESET` of `EMAIL_VERIFY` | Waarvoor |
| `token_sha256` | `CharField(64)`, `unique=True`, `db_index=True` | De enige vorm waarin het token ooit wordt opgeschreven |
| `issued_at` | `DateTimeField` | Wanneer het token is aangemaakt, en dat is het moment van verzenden (hoofdstuk 4) |
| `expires_at` | `DateTimeField`, `db_index=True` | Eén uur na `issued_at` voor herstel, zeven dagen voor bevestiging |
| `spent_at` | `DateTimeField`, `null=True` | Wanneer hij gebruikt is |
| `superseded_at` | `DateTimeField`, `null=True` | Wanneer een nieuwer token van dezelfde soort hem verving |

Het ruwe token is `secrets.token_urlsafe(32)`: 256 bits, 43 tekens. Dat is twee keer zo
lang als het advies-token, en met reden: een advies-token opent een advies dat over negentig
dagen toch verdwijnt, dit token zet een wachtwoord. De digest is `token_digest` uit
`backend/advice/models.py`, dezelfde ongezouten sha256 die `RefreshSession.jti_sha256` en
`StoredAdvice` gebruiken, met hetzelfde argument: de invoer komt uit een cryptografische
bron met genoeg entropie, dus er is geen woordenboek om te draaien en geen zout dat iets
toevoegt.

`is_usable` is waar als `spent_at` en `superseded_at` leeg zijn en `expires_at` in de
toekomst ligt. Dat is één property, en de drie routes die een token lezen stellen alle drie
dezelfde vraag.

### 2.2 Eén keer, onder een lock

Het gebruiken van een token volgt `tokens.rotate` in `backend/accounts/tokens.py`, en dan
in het bijzonder de volgorde die de docstring daar dragend noemt. Binnen
`transaction.atomic()` wordt de rij met `select_for_update()` op zijn digest opgehaald.
Bestaat hij niet, is hij verlopen, gebruikt of vervangen, dan is het antwoord één en dezelfde
weigering. Is hij bruikbaar, dan gebeurt binnen hetzelfde blok alles wat de soort vraagt (het
wachtwoord zetten, de sessies intrekken, het tijdstip van bevestiging schrijven) en wordt
`spent_at` gezet. Twee gelijktijdige bevestigingen met hetzelfde token zien elkaar op de
lock: de tweede leest een rij met `spent_at` gevuld en wordt geweigerd. Er is hier geen
`revoke_all`-tak zoals bij een hergebruikt refresh-token: een hergebruikte herstellink is een
geweigerde link, niet een bewijs dat iemand anders de sessie heeft.

### 2.3 Een nieuw token vervangt het vorige

Vraagt iemand twee keer herstel aan, dan zet het aanmaken van het tweede token
`superseded_at` op elk ouder ongebruikt token van dezelfde soort voor dezelfde gebruiker.
Er is dus per persoon per soort altijd hoogstens één bruikbaar token. De outbox in
hoofdstuk 4 ontdubbelt daarnaast op dezelfde sleutel, zodat er ook hoogstens één mail
klaarligt.

### 2.4 Waarom niet `PasswordResetTokenGenerator`

Beslissing 31 en hoofdstuk 10 van het auth-ontwerp wezen op
`django.contrib.auth.tokens.PasswordResetTokenGenerator`: al geïnstalleerd, getekend met
`SECRET_KEY`, verloopt vanzelf, bewaart niets. Drie dingen doorbreken dat hier.

De generator neemt `last_login` op in zijn hash. Voor herstel is dat een verdienste, want
het token sterft zodra er is ingelogd. Voor bevestiging is het een fout: iemand die
registreert wordt meteen ingelogd, en de bevestigingslink die een minuut later aankomt zou al
dood zijn.

De generator kent geen "gebruikt". Een herstellink blijft geldig tot het wachtwoord
verandert of de tijd verstrijkt, en een bevestigingslink verandert niets aan de hash, dus die
zou zeven dagen lang opnieuw bruikbaar zijn. `spent_at` beantwoordt die vraag in één kolom.

En dit project heeft de vorm al. `RefreshSession` is een tabel die geen credential draagt
en toch precies zegt welk token wanneer gebruikt is; `OneTimeToken` is dezelfde vorm voor
een tweede vocabulaire. Eén patroon met twee toepassingen leest beter dan twee patronen.

### 2.5 `User.email_verified_at`

Eén veld erbij op `User`: `email_verified_at = DateTimeField(null=True, blank=True)`. Een
tijdstip en geen vlag, want de vraag die een DPIA stelt is "wanneer", en een vlag kan die niet
beantwoorden. Leeg betekent nooit bevestigd.

Het wordt gezet door een geslaagde bevestiging en door een geslaagd herstel. Het tweede is
geen gemak maar een gevolg: wie een link uit zijn mailbox kon openen, bezit dat adres, en dat
is precies wat bevestiging vaststelt. Niets in fase 1 leest het veld. Fase 2 eist het voor de
meterkoppeling, en dat is de enige plek waar het straks iets blokkeert. Inloggen,
toestemmingen, export en verwijderen werken zonder.

Dit is een migratie op `AUTH_USER_MODEL`, de tweede na de eerste, en hij voegt één nullable
kolom toe. Bestaande rijen krijgen `NULL`, wat waar is: van geen enkel bestaand account is het
adres bevestigd.

## 3. De routes

### 3.1 Vier routes, allemaal POST

Alle vier op `_AuthAPIView` in `backend/accounts/views.py`, zodat ze erven wat elke
`/api/auth/`-route heeft: `Cache-Control: private, no-store`, de CSRF-cookie op elk antwoord
via `finalize_response`, de Nederlandse 429 uit `throttled()`, en de 401 in plaats van een
403 op een publieke route via `get_authenticate_header`. De drie publieke routes roepen
`enforce_csrf(request)` zelf aan, precies zoals `RegisterView`, `LoginView` en `RefreshView`
dat doen, want de authenticatieklasse die het anders zou doen draait daar niet.

| Methode en pad | Toegang | Scope | Body | Antwoord |
|---|---|---|---|---|
| `POST /api/auth/reset/request/` | publiek | `auth-reset` | `{"email"}` | 202 met `{}` |
| `POST /api/auth/reset/confirm/` | publiek | `auth-reset` | `{"token", "password"}` | 204 |
| `POST /api/auth/verify/request/` | ingelogd | `auth-write` | geen | 202 met `{}` |
| `POST /api/auth/verify/confirm/` | publiek | `auth-reset` | `{"token"}` | 204 |

Dertien routes in totaal, en `docs/dpia.md` gaat van "negen routes" naar "dertien routes".
`tests/test_backend_settings.py` loopt de resolver af en eist van elke view een scope met een
tarief, dus een route zonder scope komt niet door de suite.

### 3.2 `reset/request/`

De body draagt één veld, `email`, gevalideerd als adres. Het antwoord is altijd 202 met een
leeg object, of het adres nu bekend is of niet, of het account nu actief is of niet. Dat is
de regel die maakt dat deze route niet kan vertellen wie een account heeft: een 202 en een
404 zouden een adresboek zijn dat vijf verzoeken per uur kan doorbladeren.

Achter dat antwoord gebeurt bij een bekend adres drie dingen, in `recovery.py`
(hoofdstuk 3.6): het adres wordt verlaagd zoals `_normalize_email` dat doet, want het staat
verlaagd in de tabel en een opzoeking met hoofdletters zou de rij missen; er komt een
outbox-rij van soort `PASSWORD_RESET` als er nog geen onverzonden ligt; en het auditlog krijgt
`PASSWORD_RESET_REQUESTED` met alleen `user_id`. Bij een onbekend adres gebeurt niets en wordt
niets gelogd: een auditregel "onbekend adres vroeg herstel" zou het adres zelf moeten dragen
om iets te betekenen, en dat is precies wat hoofdstuk 2 van de DPIA verbiedt.

De antwoordtijd hoort niet te verschillen. Er wordt geen mail verstuurd in dit verzoek en
geen token gemaakt; een bekend adres kost één `INSERT` meer dan een onbekend, en dat is
onder de ruis van één databaseronde. Dat is de tweede reden voor de outbox, naast de reden
in hoofdstuk 4.

### 3.3 `reset/confirm/`

De body draagt `token` en `password`. De volgorde is dwingend: eerst het token, dan het
wachtwoord. Een ongeldig token is een 400 onder `token` met één zin, `token_invalid`, voor
verlopen, gebruikt, vervangen en nooit bestaan tegelijk. Het verschil tussen die vier is
alleen interessant voor wie tokens probeert, en die krijgt het niet.

Is het token bruikbaar, dan gaan de wachtwoordvalidators erover heen, dezelfde
`validate_password` die `RegisterSerializer.validate_password` in
`backend/accounts/serializers.py` aanroept, mét de gebruiker erbij, want
`UserAttributeSimilarityValidator` vergelijkt met het adres. Zonder die stap zou deze route
de ene manier zijn om een wachtwoord te zetten dat `register/` zou weigeren. Een afgekeurd
wachtwoord is een 400 onder `password` met dezelfde zinnen als bij registratie, inclusief
`password_too_short` met zijn placeholder.

Dan, binnen de lock van hoofdstuk 2.2: `user.set_password`, `tokens.revoke_all(user)` zodat
elke sessie die met het oude wachtwoord begon eindigt, `email_verified_at` als het leeg was,
`spent_at`, en de auditregel `PASSWORD_RESET_COMPLETED` met `user_id`. Het antwoord is 204
zonder cookies. Het huishouden logt daarna in met het nieuwe wachtwoord. Dat is met opzet: de
login-route is de enige plek waar een sessie begint en `LOGIN_SUCCEEDED` wordt geschreven, en
een tweede plek zou de DPIA-zin dat elke inlog een regel is stilletjes onwaar maken. Het kost
het huishouden één formulier dat het toch al kent.

Axes telt hier niet mee, want er gaat geen `authenticate()` overheen. De bescherming tegen
raden is het token zelf (256 bits) en de scope `auth-reset` uit 3.5.

### 3.4 `verify/request/` en `verify/confirm/`

`verify/request/` is de enige van de vier die inloggen eist, en daarmee de enige die weet
voor wie hij werkt zonder body. Hij schrijft een outbox-rij van soort `EMAIL_VERIFY` als er
nog geen onverzonden ligt en antwoordt 202. Is het adres al bevestigd, dan antwoordt hij ook
202 en schrijft niets; een 400 zou een tweede weg zijn om die toestand te lezen, en `me/`
zegt het al.

Registratie doet hetzelfde zonder dat iemand erom vraagt: `RegisterView.post` schrijft na
`create_user` een outbox-rij van soort `EMAIL_VERIFY`. Elk nieuw account krijgt dus één mail,
binnen de minuut na aanmaken.

`verify/confirm/` is publiek, want de link wordt vaak geopend op een apparaat waar niemand
ingelogd is, en een 401 op een bevestigingslink zou een huishouden naar een inlogformulier
sturen om iets te bewijzen dat de link al bewijst. Body `{"token"}`, dezelfde lock, dezelfde
ene zin bij een ongeldig token, en bij succes `email_verified_at`, `spent_at`, en
`EMAIL_VERIFIED` met `user_id`. Antwoord 204.

`me/` krijgt er één veld bij: `email_verified_at`, een ISO-tijdstip of `null`. De fixture
`frontend/tests/fixtures/me-response.json` wordt daarop opnieuw vastgezet.

### 3.5 De scope `auth-reset`, en de som van beslissing 33

Eén nieuwe scope in `DEFAULT_THROTTLE_RATES` in `backend/ampeer/settings/base.py`:
`auth-reset` op 10 per uur per beller, voor `reset/request/`, `reset/confirm/` en
`verify/confirm/`. Tien, omdat `auth-login` ook tien is: wie een link probeert krijgt evenveel
pogingen als wie een wachtwoord probeert, en niet meer. `verify/request/` valt onder
`auth-write`, net als de andere handelingen van een ingelogd account.

Beslissing 33 eist dat het plafond van nginx, 10 verzoeken per seconde, de som van alle
scopes per bezoeker minstens vijftig keer overtreft, en
`test_something_ahead_of_django_limits_the_rate` in `tests/test_nginx_config.py` rekent dat
na. De som vandaag is 20 + 120 + 120 + 5 + 10 + 60 + 120 + 20 + 5 = 480 per uur, dus
0,1333 per seconde, en 10 per seconde overtreft dat 75 keer. Met `auth-reset` erbij is de som
490 per uur, 0,1361 per seconde, en het plafond overtreft dat 73,5 keer. Ruim boven de
vijftig, en het plafond hoeft niet te bewegen.

### 3.6 `backend/accounts/recovery.py`

De vier handelingen staan in een nieuwe module en niet in `service.py`, om een reden die
niets met smaak te maken heeft: `_audit_context_keys` in `tests/test_dpia.py` gaat ervan uit
dat `service.py` precies één `record()`-aanroep bevat, en zegt in zijn eigen assertiebericht
dat de test herschreven moet worden als dat niet meer zo is. Een tweede module houdt die
aanname waar, en `_accounts_audit_context_keys` loopt sowieso elk bestand onder
`backend/accounts/` af, dus de nieuwe sleutelwoorden worden gezien.

De module exporteert:

- `request_password_reset(email: str) -> None`, die nooit iets zegt over het adres
- `confirm_password_reset(raw_token: str, password: str) -> User`
- `request_email_verification(user: User) -> None`
- `confirm_email_verification(raw_token: str) -> User`
- `mint(user: User, kind: str) -> str`, die het ruwe token teruggeeft en de rij met de
  digest schrijft, en die alleen het command uit hoofdstuk 4 aanroept
- `TokenInvalid(Exception)`, één klasse voor verlopen, gebruikt, vervangen en onbekend

### 3.7 De labels reizen mee met de teksten

Beslissing 38 plande een versieveld voor de labels "bij de eerstvolgende backend-aanraking
van `backend/accounts/`". Dit is die aanraking. `GET /api/auth/consent-texts/` levert:

```json
{
  "text_version": "2026-09-04",
  "texts": {
    "LEAD_GENERATION": "Ik geef Ampeer toestemming om mijn gegevens door te geven aan een installateur als ik daar zelf om vraag. Dit is niet nodig om Ampeer te gebruiken en het verandert niets aan het advies dat ik krijg.",
    "METER_LINK": "Ik geef Ampeer toestemming om de kwartiergegevens van mijn slimme meter te verwerken om mijn advies nauwkeuriger te maken. Ik kan deze toestemming op elk moment intrekken."
  },
  "labels": {
    "LEAD_GENERATION": "Doorgeven aan een installateur",
    "METER_LINK": "Kwartiergegevens van uw slimme meter"
  }
}
```

De twee labels verhuizen van `CONSENT_LABELS` in `frontend/src/app/_account/ConsentRow.tsx`
naar `nl.py`, als `CONSENT_LABEL_METER_LINK` en `CONSENT_LABEL_LEAD_GENERATION` in de derde
categorie, naast de teksten. Ze staan onder dezelfde `CONSENT_TEXT_VERSION`: de docstring
bij die constante zegt dan dat hij ook bij een gewijzigd label omhoog gaat, en de
herzieningsregel uit beslissing 38 (een label mag versmallen tot waar de tekst nog dekt, en
nooit minder claimen dan de rij vastlegt) staat erbij als commentaar. Een aparte
`label_version` is overwogen en afgewezen: label en tekst worden samen gelezen en samen
vastgelegd, dus één versie voor het paar is de eerlijke vorm.

`tests/helpers/consent_texts_fixture.py` schrijft de fixture met de labels erbij, en
`test_no_consent_text_lives_in_the_frontend` in `tests/test_frontend_contract.py` gaat ook
over de twee labels: ze mogen nergens in `frontend/src/**` staan.

## 4. Het mailkanaal

### 4.1 Waarom een outbox

Drie manieren zijn gewogen. Verzenden in het verzoek zelf laat een view wachten op een
externe dienst, maakt een storing bij Resend een 500 of een stille fout, en laat de
antwoordtijd verschillen tussen een bekend en een onbekend adres. Celery brengt Redis, een
worker en een derde container voor twee mails per dag, en elk ontwerp in deze repository
weigert dat al met dezelfde reden. Een outbox met een timer is de vorm die er al is: de twee
opruimopdrachten draaien als management command onder een systemd-timer, en dit wordt de
derde.

Het gevolg dat het meest telt: geen enkel verzoek raakt het netwerk. De regel uit CLAUDE.md
dat de backend nooit naar buiten belt behalve naar een vaste lijst, blijft daarmee
categorisch waar op het pad dat een bezoeker kan bereiken. De ene module die wel naar buiten
gaat, draait alleen onder het command.

### 4.2 `OutboundMail`

| Veld | Type | Betekenis |
|---|---|---|
| `user` | FK naar `accounts.User`, `CASCADE`, `related_name="outbound_mails"` | Aan wie, via het adres op `User` |
| `kind` | `CharField(16)`, `PASSWORD_RESET` of `EMAIL_VERIFY` | Welke mail |
| `created_at` | `DateTimeField` | Wanneer gevraagd |
| `attempts` | `PositiveSmallIntegerField`, default 0 | Hoe vaak geprobeerd |
| `next_attempt_at` | `DateTimeField`, `db_index=True` | Vanaf wanneer het command hem weer oppakt |
| `last_status` | `PositiveSmallIntegerField`, `null=True` | De HTTP-status van de laatste poging, 0 bij een netwerkfout |
| `failed_at` | `DateTimeField`, `null=True` | Wanneer opgegeven |

Geen adres, geen token, geen onderwerp en geen body. Het adres staat op `User` en wordt op
het moment van verzenden gelezen; `test_no_table_has_a_column_for_an_address` in
`tests/test_dpia.py` blijft daarmee waar over elke tabel. Het token bestaat nog niet als de
rij wordt geschreven, en dat is de kern van 4.3. Wordt het account verwijderd voordat de mail
weg is, dan neemt `CASCADE` de rij mee en gaat er niets meer uit naar een adres dat niet meer
bij een account hoort.

Eén onverzonden rij per gebruiker per soort: `request_*` schrijft geen tweede als er een ligt
met `failed_at` leeg. Dat is de ontdubbeling uit 2.3, aan de kant van de mail.

### 4.3 Het token ontstaat bij het versturen

Het command leest een rij, roept `recovery.mint(user, kind)` aan, krijgt het ruwe token,
zet het in de link, verstuurt, en vergeet het. De digest staat vanaf dat moment in
`OneTimeToken`, met `issued_at` op het moment van verzenden, dus de looptijd van één uur of
zeven dagen telt vanaf het moment dat de mail de deur uit is en niet vanaf een verzoek dat
een uur in een wachtrij kan hebben gestaan.

Het ruwe token bestaat daarmee op precies twee plaatsen: in het geheugen van het command
gedurende één verzending, en in de mail. Geen kolom, geen log, geen journal.

### 4.4 `send_outbound_mail`

`backend/accounts/management/commands/send_outbound_mail.py`, elke minuut aangeroepen
door `ampeer-mail.timer`. Per run:

1. Claim met `SELECT ... FOR UPDATE SKIP LOCKED` elke rij met `failed_at` leeg en
   `next_attempt_at` in het verleden, in een eigen transactie per rij, zodat twee runs die
   elkaar overlappen nooit dezelfde rij versturen.
2. Bouw het bericht uit `nl.py` (hoofdstuk 7), met de link
   `{AMPEER_SITE_ORIGIN}/account/#herstel={token}` of `#verificatie={token}`.
3. Verstuur via het transport uit 4.6.
4. Bij succes: verwijder de rij en schrijf `MAIL_SENT` in het auditlog met `user_id`, `kind`
   en `provider_id`, het bericht-id dat Resend teruggeeft. Dat id is geen persoonsgegeven en
   is wel het enige spoor waarmee een verzending bij Resend teruggevonden kan worden.
5. Bij een netwerkfout, een timeout, een 429 of een 5xx: `attempts` één hoger,
   `last_status`, en `next_attempt_at` op 1, 5, 15 of 60 minuten verder, afhankelijk van de
   poging. Na 24 uur `failed_at`. Een mislukte poging laat geen bruikbaar token achter; de
   alinea onder deze lijst zegt hoe.
6. Bij een 4xx anders dan 429: `failed_at` meteen. Een verkeerde sleutel of een adres dat
   Resend weigert, wordt niet beter van wachten.

De volgorde van mint en verzending is precies. Het token wordt gemaakt vóór het versturen,
want het moet in de mail, en de mint en de verzending staan samen in één `atomic()`. Een
transportfout verlaat dat blok met een exception, en die draait de mint terug: er staat dan
geen digest in `OneTimeToken` van een token dat niemand heeft ontvangen. De outbox-rij wordt
daarna in een tweede, eigen transactie bijgewerkt met de poging en de wachttijd. Twee
transacties, in die volgorde, en de eerste committeert alleen als het transport het bericht
heeft aangenomen.

Het command eindigt met exitcode 1 als er na zijn eigen ronde nog een rij ligt met
`failed_at` leeg en `created_at` meer dan vijftien minuten geleden. Dat is de helft die
opmerkt, in de vorm die `purge_expired_advice --check` al heeft: een command dat elke minuut
draait en altijd nul teruggeeft, zegt niets als het stilletjes niets meer verstuurt. Met
`--check` doet het command alleen die controle en verstuurt niets, en dat is de aanroep voor
de deploy-job.

De opruiming van `OneTimeToken`-rijen na `expires_at` en van `OutboundMail`-rijen zeven dagen
na `failed_at` komt in `purge_expired_sessions`, dat daarmee drie tabellen opruimt en drie
tellingen afdrukt. Geen vierde command en geen derde timer: de docstring daar zegt al dat dit
één dagelijkse `DELETE` over een geïndexeerde kolom is, en dat blijft het.

### 4.5 `backend/accounts/mailer.py`

Eén module die naar buiten mag, en hij mag maar naar één plek. De bestemming is een
literal, `RESEND_ENDPOINT: Final = "https://api.resend.com/emails"`, op de plek waar een
reviewer hem ziet. De client is `requests`, de ene die `tests/test_boundaries.py` toestaat,
met `timeout=10`. Het verzoek: `POST` met `Authorization: Bearer {RESEND_API_KEY}`,
`Idempotency-Key: outbox-{id}`, en een JSON-body met `from`, `to`, `subject` en `text`.
Resend antwoordt met een JSON-object met één sleutel, `id`, een UUID; dat is `provider_id`.

De idempotentiesleutel is de reden dat een herhaling na een timeout veilig is: Resend bewaart
hem 24 uur, en een tweede `POST` met dezelfde sleutel binnen die tijd wordt niet een tweede
mail. De naam is het rijnummer van de outbox, dat nooit hergebruikt wordt.

Geen Resend-SDK. Het is één endpoint met vier velden, en een SDK zou verbindingen openen
vanuit een pakket dat de grenstest niet leest. `requests` staat al in `uv.lock`; er komt
geen afhankelijkheid bij.

### 4.6 Drie transporten

`AMPEER_MAIL_TRANSPORT` kiest:

| Waarde | Waar | Wat het doet |
|---|---|---|
| `resend` | productie | `mailer.py`, het echte verzoek |
| `file` | de lokale stack, en `dev.py` | schrijft elk bericht als één tekstbestand (onderwerp, ontvanger, body) in `AMPEER_MAIL_FILE_DIR`, en geeft een `provider_id` van de vorm `file-{id}` terug |
| `memory` | de testsuite | houdt de berichten in een lijst die een test leest |

`prod.py` leest `AMPEER_MAIL_TRANSPORT` met `_required` en accepteert `resend` en `file`, en
weigert `memory` bij het opstarten: dat transport bestaat om een test iets te laten lezen en
hoort nooit in een container. `file` is toegestaan in `prod.py` om één reden: de lokale
stack draait onder `ampeer.settings.prod`, en de live check uit hoofdstuk 8 leest de mail uit
een bestand. Dat maakt `file` op een echte host tot een stille storing: elke mail zou netjes
naar schijf gaan en niemand zou er een ontvangen. Daarom weigert `scripts/preflight_env.sh`,
dat op de host draait en `/srv/ampeer/.env` leest, elke waarde anders dan `resend`, en de
deploy stopt voordat er een container start. De env-fixture van de lokale stack is de enige
plek in de repository waar `file` geschreven wordt, en `tests/test_deploy_workflow.py` leest
de preflight om vast te houden dat die weigering er staat. `RESEND_API_KEY` is verplicht bij `resend`; `AMPEER_MAIL_FROM` en
`AMPEER_SITE_ORIGIN` zijn altijd verplicht, zonder standaardwaarde, zoals elke waarde in dat
bestand die een veiligheidseigenschap bepaalt. Een ontbrekende sleutel stopt het proces.

`infra/docker-compose.yml` geeft de `api`-service de vier variabelen door, en
`infra/compose.test.yml` mount `infra/fixtures/mail/` op `AMPEER_MAIL_FILE_DIR`, zodat de
live check op de host kan lezen wat het command in de container schreef. De env-fixture die
`tests/test_stack_smoke.py` schrijft, krijgt de vier namen erbij, want
`test_the_environment_fixture_names_every_variable_the_stack_reads` eist dat elke variabele
die compose interpoleert in de fixture staat. De placeholder voor `RESEND_API_KEY` is
`smoke-check-placeholder-not-a-secret`, dezelfde vorm als het databasewachtwoord daar, en met
opzet niet beginnend met `re_`, het voorvoegsel van een echte Resend-sleutel:
`test_the_environment_fixture_holds_no_value_that_could_be_mistaken_for_real` gaat die regel
ook lezen. `AMPEER_MAIL_FROM` is daar `noreply@ampeer.smoke.invalid`, op het gereserveerde
achtervoegsel dat nooit ergens aankomt. `infra/.env.example` krijgt de vier namen met `resend` als
transport, en `tests/test_infra.py` houdt dat bestand al gelijk met compose.

### 4.7 De grenstest wordt strenger

Het contextonderzoek voor dit ontwerp vond een gat in `tests/test_boundaries.py` dat er
sinds de eerste dag zit: `_imported_module_names` bewaart alleen het eerste deel van een
importnaam, dus `from django.core.mail import send_mail` telt als `django`, en `django` staat
niet in `NETWORK_CLIENTS`. Django's eigen SMTP-backend importeert `smtplib` in `.venv/`, waar
de scan nooit komt. De categorische regel tegen uitgaande verbindingen zag uitgaande mail via
Django's eigen API dus niet.

Dit ontwerp gebruikt die API niet, en sluit het gat toch, want een gat dat bekend is en
openblijft is een besluit. Drie wijzigingen:

1. `_imported_module_names` levert naast de eerste naam ook de volledige gepunte naam, en
   `NETWORK_CLIENTS` krijgt `django.core.mail` erbij. Het rood-bewijs is een tijdelijk
   bestand onder `backend/` met precies die import.
2. `OUTBOUND_MODULES` krijgt `"backend/accounts/mailer.py": frozenset({"api.resend.com"})`.
   De vergelijking in `test_only_these_modules_can_reach_outside_this_machine` is een
   gelijkheid over de hele mapping, dus `mailer.py` moet `requests` importeren en geen andere
   client, en geen ander bestand onder `backend/` mag dat.
3. `STRICT_DESTINATION_MODULE` wordt een tuple van twee: `pvgis.py` en `mailer.py`. De regel
   "de module stelt zijn URL nooit samen" geldt voor beide, want beide worden bereikt vanuit
   een proces dat de eigenaar niet ziet: de een vanuit een webverzoek, de ander vanuit een
   timer.

Het commentaar boven `OUTBOUND_MODULES`, dat zegt dat CLAUDE.md drie bronnen noemt terwijl de
repository er vier bereikt, wordt herschreven: CLAUDE.md noemt sinds 2026-09-06 de
bestemmingen die de repository werkelijk bereikt, en het item onder "What was not decided
here" in `docs/decisions.md` dat daarover ging, wordt in de documententaak beantwoord in
plaats van geschrapt, zoals dat document dat zelf doet met een beantwoord punt.

### 4.8 De units en de README

`infra/systemd/ampeer-mail.service` en `ampeer-mail.timer`, naar het model van
`ampeer-purge.*`: dezelfde kop die zegt dat niets in de repository ze installeert, dezelfde
`docker compose ... run --rm --entrypoint python api backend/manage.py send_outbound_mail`,
`Type=oneshot`. De timer: `OnCalendar=*-*-* *:*:00`, `AccuracySec=10s`, en geen
`Persistent=true`, want een gemiste minuut heeft geen inhaalslag nodig; de volgende run
verstuurt wat er ligt. Sectie 3 van `infra/README.md` krijgt de drie commando's om de tweede
timer te installeren, en de deploy-job krijgt `send_outbound_mail --check` na `migrate`,
naast `purge_expired_advice --check`.

## 5. Audit en privacy

### 5.1 Vier nieuwe soorten in het auditlog

`AuditEvent` in `backend/advice/models.py` krijgt vier constanten, en het commentaar boven de
lijst zegt bij elk dat het een handeling is die bestaat:

| Soort | Wanneer | Context |
|---|---|---|
| `PASSWORD_RESET_REQUESTED` | `reset/request/` voor een bekend adres | `user_id` |
| `PASSWORD_RESET_COMPLETED` | `reset/confirm/` geslaagd | `user_id` |
| `EMAIL_VERIFIED` | `verify/confirm/` geslaagd, of een herstel dat het adres bevestigde | `user_id` |
| `MAIL_SENT` | het command heeft een bericht afgeleverd bij het transport | `user_id`, `kind`, `provider_id` |

Nooit het adres, nooit het token, nooit de digest. `provider_id` is nieuw en komt in
`AUDIT_CONTEXT_PHRASES` in `tests/test_dpia.py` met een Nederlandse omschrijving die
hoofdstuk 2 van de DPIA moet dragen, want
`test_the_document_names_everything_the_audit_line_carries` leest elk sleutelwoord uit elke
`AuditEvent.record(`-aanroep onder `backend/accounts/`.
`test_the_audit_log_records_exactly_what_the_document_says_it_does` vergelijkt de verzameling
soorten met de lijst in de DPIA, dus de vier komen daar in dezelfde commit bij.

Een geweigerde herstel- of bevestigingspoging wordt niet gelogd. Bij een onbekend token is er
geen gebruiker om aan te wijzen, en bij een gebruikt of verlopen token is de weigering het
antwoord zelf. Hoofdstuk 10 noemt dit als bewuste weglating.

### 5.2 Wat Resend ziet en bewaart

Resend is vanaf deze cyclus de tweede verwerker, naast Cloudflare. Hij ziet per bericht het
adres, het feit dat er bij dat adres een account bestaat of om herstel is gevraagd, en de
inhoud van de mail, waarvan de link één uur of zeven dagen een credential is. Hij bewaart
een eigen verzendlog met adres, onderwerp en inhoud. Dat log staat in de Verenigde Staten,
ongeacht de verzendregio: Resend zegt zelf dat regio-keuze bepaalt waar een mail vandaan
wordt verstuurd en niet waar accountdata, metadata en logs staan. De doorgifte rust op de
Standard Contractual Clauses in zijn Data Processing Addendum en op zijn certificering onder
het EU-US Data Privacy Framework. De DPA is voorgetekend bij elk account en te downloaden uit
het dashboard; er is geen aparte ondertekening.

Dit ontwerp kiest de EU-verzendregio (Ierland), zodat de mail zelf niet via een Amerikaans
datacenter loopt, en zegt in de DPIA eerlijk dat het log wel daar staat.

### 5.3 De DPIA, per hoofdstuk

- **Hoofdstuk 2, Wat wij verwerken:** `email_verified_at` als nieuw gegeven op het account
  met zijn betekenis; de twee nieuwe tabellen en wat ze niet bevatten; de vier auditsoorten en
  `provider_id`; en de bewaartermijnen: een outbox-rij verdwijnt bij verzending en zeven
  dagen na mislukking, een tokenrij bij verloop, en `spent_at` blijft tot dat verloop, want
  een gebruikt token dat nog bestaat is wat hergebruik zichtbaar maakt.
- **Hoofdstuk 5, Wie erbij kan:** Resend als tweede verwerker, met 5.2 in het Nederlands. De
  zin "Verder wordt niets uitbesteed" wordt herschreven tot wat waar is: twee verwerkers, elk
  met wat hij ziet.
- **Hoofdstuk 6, Wat de machine verlaat:** de vaste lijst krijgt `api.resend.com` erbij,
  met erbij dat alleen een timer die bestemming bereikt en geen enkel verzoek van een bezoeker.
- **Hoofdstuk 7, Wat een bezoeker kan uitoefenen:** de alinea die zegt dat wie zijn
  wachtwoord kwijt is zijn account niet meer kan verwijderen, wordt vervangen door de
  herstelroute, en de dertien routes worden beschreven zoals de negen dat al zijn.
- **Hoofdstuk 10, Wat bij Stijn ligt:** een vijfde punt. Het openingswoord wordt "Vijf",
  want `test_the_chapter_of_open_decisions_states_how_many_there_are` telt de punten en eist
  het telwoord. Het punt: Resend als verwerker, met drie deelvragen. Of de voorgetekende DPA
  volstaat als de verwerkersovereenkomst die artikel 28 vraagt. Of de EU-verzendregio in het
  dashboard staat ingesteld. En of opslag van het verzendlog in de Verenigde Staten onder
  SCC's en DPF aanvaardbaar is voor deze dienst, of dat een Europese aanbieder de volgende
  backend-aanraking wordt.
- **De rechtsgrond van bevestiging.** Het bevestigen van een adres is geen van de twee
  toestemmingen. Dit document zet hem voorlopig op noodzaak voor de dienst: zonder bevestigd
  adres kan de dienst geen wachtwoord herstellen en straks geen meter koppelen. Dat is een
  voorlopige keuze van dezelfde soort als de rechtsgrond in punt 2 van hoofdstuk 10, en hij
  wordt daar bij dat punt genoemd in plaats van als zesde punt, omdat het dezelfde vraag is.

### 5.4 Wat de eigenaar in zijn eigen stukken zet

De privacyverklaring en het verwerkersregister bestaan nog niet; dit ontwerp maakt ze niet,
en zegt wel welke regel Resend erin moet krijgen. Voor het register: Resend, Inc., voor het
versturen van herstel- en bevestigingsmails, ziet e-mailadres en berichtinhoud, bewaart een
verzendlog in de Verenigde Staten, grondslag voor doorgifte SCC's en DPF, overeenkomst de
voorgetekende DPA. Voor de privacyverklaring: dat een account een adres heeft, dat er mails
naar dat adres gaan voor herstel en bevestiging en nergens anders voor, en dat een derde
partij die mails aflevert.

## 6. De frontend

### 6.1 Het token reist in het fragment

De link in de mail is `https://ampeer.nl/account/#herstel={token}` of
`#verificatie={token}`. Een fragment verlaat de browser nooit. nginx ziet het niet, dus het
toegangslog ook niet en Cloudflare ook niet; een `Referer` draagt het niet. Daarmee vervalt
alles wat `/advies/<token>/` nodig had: de `location` met `try_files`, de regel in
`serve.json`, de logredactie-`map`, en de zin in hoofdstuk 5 van de DPIA dat Cloudflare een
tweede geheim pad ziet.

`AccountPage.tsx` leest `window.location.hash` één keer, bij het laden, en haalt het
fragment meteen uit de adresbalk met `history.replaceState`, zodat het niet in de
geschiedenis, in een tabtitel of in een gedeelde URL blijft hangen. Dat lezen en wissen staat
in één functie, `readRecoveryFragment()` in `frontend/src/app/_account/fragment.ts`, die
`{ kind: "reset" | "verify", token: string } | null` teruggeeft en niets anders doet.

Het principe uit hoofdstuk 2 van het frontend-ontwerp, dat de weergave toestand is en geen
adres, blijft staan. Het fragment noemt geen weergave. Het draagt een token, en wat de
pagina daarmee doet hangt af van wat `me/` zegt en wat de API met het token antwoordt.

### 6.2 Twee nieuwe uitgelogde weergaven

`SignedOutView` in `AccountPage.tsx` krijgt twee waarden erbij: `reset_request` en
`reset_confirm`. Beide zijn een formulier in dezelfde `role="group"` als inloggen en
registreren, met een eigen `<h2>` en `aria-labelledby`.

**Herstel aanvragen.** Bereikbaar via een knop "Wachtwoord vergeten?" in `SignInForm.tsx`,
op de plek van de zin die nu zegt dat herstel er niet is. Eén e-mailveld, één knop. Na de 202
toont het formulier één zin, altijd dezelfde, en het veld verdwijnt: dat er binnen enkele
minuten een mail klaarstaat als het adres bekend is, en dat de link één uur werkt. De zin
zegt niet of het adres bekend is, want de API weet het wel en zegt het ook niet. Een knop
"Terug naar inloggen" eronder.

**Nieuw wachtwoord.** Bereikt door `#herstel=`. Eén wachtwoordveld, één knop. Het token
staat in de toestand van de pagina en nergens in het formulier. Na de 204 wisselt de pagina
naar inloggen met de melding dat het wachtwoord gewijzigd is. Een 400 onder `token` toont de
zin van de API bij het formulier, met een knop naar "Herstel aanvragen", want dat is het
enige dat dan nog helpt. Een 400 onder `password` toont de zin bij het veld, zoals bij
registratie.

Beide weergaven zijn onbereikbaar voor wie ingelogd is: is `me/` een 200 en staat er
`#herstel=` in de URL, dan toont de pagina de accountweergave en negeert het token. Een
ingelogd huishouden hoeft geen wachtwoord te herstellen, en een herstellink die op een
ingelogde sessie werkt, zou een tweede manier zijn om het wachtwoord te wijzigen zonder het
oude te kennen.

### 6.3 Bevestiging is één klik

`#verificatie=` vraagt niets aan het huishouden. Na de eerste `me/`, en die volgorde blijft
de wet van deze pagina, post `AccountPage.tsx` het token naar `verify/confirm/`. Bij 204 staat
er één regel in een `role="status"`: dat het adres bevestigd is. Was `me/` een 200, dan wordt
`me/` daarna één keer opnieuw gevraagd, zodat de statusregel uit 6.4 klopt zonder dat de
pagina zelf raadt; dat is geen retry maar een tweede vraag na een verandering, dezelfde vorm
als na een toestemmingswissel. Bij een 400 staat de zin van de API in diezelfde regel, en de
rest van de pagina is wat `me/` zei.

### 6.4 De accountweergave

Eén regel over het adres, boven de twee toestemmingsrijen: "E-mailadres bevestigd" of
"E-mailadres nog niet bevestigd". Geen datum op het scherm. De datum staat in de export, en
een datum op het scherm zou datumopmaak in de frontend brengen, wat de klokregel van semgrep
en de taalgrens allebei raken. Bij "nog niet bevestigd" staan er twee dingen bij: de knop
"Verstuur de bevestigingsmail opnieuw", die `verify/request/` post en na de 202 één regel
toont, en de staande mededeling dat voor het koppelen van een slimme meter een bevestigd
adres nodig is. Direct na registratie staat er dat er een mail onderweg is om het adres te
bevestigen.

### 6.5 `accounts.ts`

Vier aanroepen erbij, dertien in totaal, elk met de vormcontrole die de andere negen hebben:

| Functie | Verzoek | Antwoord |
|---|---|---|
| `requestPasswordReset({ email })` | `POST reset/request/` | `void` op 202 |
| `confirmPasswordReset({ token, password })` | `POST reset/confirm/` | `void` op 204 |
| `requestEmailVerification()` | `POST verify/request/` | `void` op 202 |
| `confirmEmailVerification({ token })` | `POST verify/confirm/` | `void` op 204 |

`Me` krijgt `email_verified_at: string | null`, en `isMe` weigert een antwoord zonder dat
veld. `ConsentTexts` krijgt `labels`, en `isConsentTexts` eist beide sleutels.
`ConsentCheckbox` en `ConsentRow` krijgen het label als prop uit het `consent-texts/`-antwoord,
en `CONSENT_LABELS` verdwijnt. `AccountField` in `messages.ts` krijgt `token` erbij, anders
laat `fieldErrors` de ene zin van `reset/confirm/` stilletjes vallen.
`test_every_path_the_frontend_calls_is_one_the_backend_serves` in
`tests/test_frontend_contract.py` leest `urls.py` en `accounts.ts` naast elkaar, dus de vier
paden en de vier routes landen in dezelfde commit.

### 6.6 `ui-strings.txt`

De zin op regel 120, dat er geen wachtwoordherstel is, verdwijnt uit `SignInForm.tsx` en
daarmee uit het bestand. De kop van het bestand noemt die zin als voorbeeld van een staande
mededeling; dat voorbeeld wordt de verwijderzin en de zin over de meterkoppeling uit 6.4.
Elke nieuwe zin uit hoofdstuk 7 komt erin via de regeneratie, en de diff wordt gelezen.

### 6.7 Toegankelijkheid

De regels uit hoofdstuk 8 van het frontend-ontwerp gelden onveranderd, en dit zijn de vier
die hier iets doen. Geen focusverplaatsing bij het laden, ook niet als de pagina via een link
met fragment is bereikt: aankomst is geen handeling. `role="alert"` alleen voor een melding
over het formulier dat iemand net verstuurde; de regel over bevestiging en de regel na een
202 zijn `role="status"`. Een veldfout hangt aan zijn veld met `aria-describedby`, ook de
`token`-zin, die aan het wachtwoordveld hangt omdat er geen tokenveld is. axe draait op de
twee nieuwe weergaven, in beide paletten.

## 7. Tekst en de taalgrens

Elke zin die een huishouden leest heeft één thuis. De zinnen die de API zegt staan in
`backend/accounts/nl.py`; de zinnen die de pagina zegt staan in `frontend/src/**` en daarmee
in `frontend/tests/ui-strings.txt`. Geen Engelse standaardtekst is bereikbaar: de vier
aanroepen bouwen bij een 202 en 204 niets, en bij een fout dezelfde `ApiError` met een lege
`message` als de andere negen.

### 7.1 `nl.py`, eerste categorie

Eén sleutel, die een veld benoemt en niemand aanspreekt:

- `token_invalid`: "deze link is verlopen of al gebruikt; vraag een nieuwe aan"

### 7.2 `nl.py`, derde categorie

De twee labels, naast de twee teksten en onder dezelfde versie:

- `CONSENT_LABEL_METER_LINK`: "Kwartiergegevens van uw slimme meter"
- `CONSENT_LABEL_LEAD_GENERATION`: "Doorgeven aan een installateur"

### 7.3 `nl.py`, vierde categorie: de mails

Een nieuwe categorie, en de docstring zegt waarom: dit zijn brieven aan een huishouden, dus
ze spreken aan met "u", en ze dragen geen versie, want er wordt niets mee vastgelegd. Twee
onderwerpen en twee bodies, platte tekst, met `%(link)s` als enige placeholder.

`MAIL_RESET_SUBJECT`: "Uw wachtwoord bij Ampeer herstellen"

`MAIL_RESET_BODY`:

```text
U heeft gevraagd om een nieuw wachtwoord voor uw account bij Ampeer.

Open deze link om een nieuw wachtwoord te kiezen. De link werkt een uur en kan een keer
gebruikt worden:

%(link)s

Heeft u dit niet gevraagd, dan hoeft u niets te doen. Uw wachtwoord blijft zoals het was.

Op dit bericht kunt u niet antwoorden.
```

`MAIL_VERIFY_SUBJECT`: "Bevestig uw e-mailadres bij Ampeer"

`MAIL_VERIFY_BODY`:

```text
Met dit e-mailadres is een account bij Ampeer aangemaakt.

Open deze link om te bevestigen dat dit adres van u is. De link werkt zeven dagen:

%(link)s

Heeft u geen account aangemaakt, dan heeft iemand anders uw adres ingevuld. U hoeft niets te
doen: zonder bevestiging kan dat account geen slimme meter koppelen.

Op dit bericht kunt u niet antwoorden.
```

"Een uur" en "een keer" staan er zonder accenten, want de eerste categorie schrijft ze ook
zo en een mailclient toont een platte tekst zoals hij binnenkomt.

### 7.4 De pagina

Navigatie en formulier:

- "Wachtwoord vergeten?"
- "Wachtwoord herstellen" (kop)
- "Stuur een herstellink"
- "Terug naar inloggen"
- "Nieuw wachtwoord" (kop en veldlabel)
- "Wachtwoord opslaan"
- "Verstuur de bevestigingsmail opnieuw"

Meldingen over het verzoek dat iemand net deed:

- "Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar.
  De link daarin werkt een uur."
- "Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord."
- "Uw e-mailadres is bevestigd."
- "De bevestigingsmail is onderweg."
- "Er is een e-mail onderweg om uw adres te bevestigen."

Staande mededelingen:

- "E-mailadres bevestigd"
- "E-mailadres nog niet bevestigd"
- "Voor het koppelen van een slimme meter is een bevestigd e-mailadres nodig."

De eerste zin onder meldingen is de enige die een adres noemt zonder te zeggen of het
bestaat, en dat is de bedoeling. Geen em-dash, nergens.

## 8. Testregime

Vijf lagen, dezelfde als in het frontend-ontwerp. Van elke nieuwe controle wordt aangetoond
dat hij rood kan worden, en het plan zegt per controle hoe.

### 8.1 Laag 1: Python, de kern

In `tests/test_accounts_recovery.py`:

- `test_a_reset_request_answers_the_same_for_a_known_and_an_unknown_address`: twee
  verzoeken, byte-identieke status en body, en na het onbekende adres geen enkele nieuwe
  auditregel en geen outbox-rij. Rood-bewijs: laat de view een 404 antwoorden op onbekend.
- `test_a_reset_request_for_a_known_address_enqueues_exactly_once`: twee verzoeken, één
  outbox-rij, één `PASSWORD_RESET_REQUESTED`.
- `test_a_reset_token_can_be_used_exactly_once_under_contention`: dezelfde vorm als de
  hergebruikstest van `rotate`, met twee gelijktijdige `confirm_password_reset` op één
  token; één slaagt, één krijgt `TokenInvalid`, en het wachtwoord is één keer gezet.
- `test_expired_spent_superseded_and_unknown_tokens_all_read_the_same_sentence`: vier
  gevallen, één status, één zin, byte-identiek.
- `test_a_completed_reset_revokes_every_session_and_verifies_the_address`: `revoke_all` is
  gebeurd, `email_verified_at` gevuld, het oude wachtwoord geweigerd op `login/`, het nieuwe
  aanvaard, en geen cookie op het 204-antwoord.
- `test_the_password_validators_apply_on_a_reset`: een te kort wachtwoord is een 400 onder
  `password` met `password_too_short`, en het token is niet verbruikt.
- `test_a_verification_confirms_once_and_answers_204_without_a_session`.
- `test_registration_enqueues_a_verification_mail`.
- `test_resending_a_verification_requires_a_session_and_dedupes`.
- `test_no_column_anywhere_holds_a_raw_token`: waarde-gebaseerd zoals
  `test_no_session_row_carries_anything_that_opens_a_session`: het ruwe token uit een
  verzonden mail komt in geen enkele kolom van `OneTimeToken`, `OutboundMail` en
  `AuditEvent` voor.

In `tests/test_accounts_mail.py`:

- `test_the_command_mints_sends_deletes_and_logs`: met het `memory`-transport, één rij,
  daarna nul rijen, één `MAIL_SENT` met `provider_id`, één `OneTimeToken` waarvan de digest
  het token in de mail is, en `issued_at` op het moment van verzenden.
- `test_a_transport_failure_leaves_no_token_behind`: het transport werpt; na afloop geen
  tokenrij, `attempts` één, `next_attempt_at` een minuut verder.
- `test_the_backoff_is_one_five_fifteen_sixty_and_then_failed`: onder een nepklok.
- `test_a_four_hundred_other_than_429_fails_at_once`.
- `test_the_command_exits_nonzero_when_something_is_overdue`, en `--check` verstuurt niets.
- `test_the_mailer_posts_one_literal_url_with_the_bearer_the_key_and_the_timeout`: met
  `requests` gemockt op de aanroep, en de idempotentiesleutel `outbox-<id>`.
- `test_the_file_transport_writes_one_readable_file_per_message`.
- `test_prod_settings_refuse_the_memory_transport`.
- `test_the_host_preflight_refuses_any_transport_but_resend`, in
  `tests/test_deploy_workflow.py`, dat `scripts/preflight_env.sh` leest zoals de andere
  tests daar de deploy-scripts lezen: rood zodra de weigering uit 4.6 uit het script verdwijnt.

In `tests/test_boundaries.py`, uitgebreid:

- `django.core.mail` in `NETWORK_CLIENTS`, en het rood-bewijs is een tijdelijk bestand
  onder `backend/` met die import.
- `mailer.py` in `OUTBOUND_MODULES`, en de strikte-bestemmingsregel over beide modules.

In `tests/test_dpia.py`, `tests/test_accounts_privacy.py` en `tests/test_backend_settings.py`
verandert niets aan de tests zelf, en dat is het punt: ze lezen de code en gaan rood totdat
de documenten en de instellingen kloppen. Hoofdstuk 4.6 en 5.3 zeggen wat ze zullen eisen.

### 8.2 Laag 2: Vitest

- `frontend/tests/lib/accounts.test.ts`: de vier aanroepen sturen `credentials: "include"`
  en de CSRF-header, precies één fetch per aanroep op elke status, en de vormcontroles
  weigeren een `me/` zonder `email_verified_at` en een `consent-texts/` zonder `labels`.
- `frontend/tests/account/fragment.test.ts`: `readRecoveryFragment` leest beide vormen,
  geeft `null` op alles anders, en de adresbalk is daarna leeg van het fragment.
- `frontend/tests/account/ResetRequestForm.test.tsx` en
  `frontend/tests/account/ResetConfirmForm.test.tsx`: de velden, de zinnen na 202 en 204, de
  `token`-zin bij het wachtwoordveld, en dat geen Engels bereikbaar is.
- `frontend/tests/account/AccountPage.test.tsx`: de wissel naar `reset_confirm` op een
  fragment bij een 401, het negeren van het fragment bij een 200, de bevestigingspost pas na
  de eerste `me/` (geteld op verzoeken), de tweede `me/` na een 204, de statusregel en de
  herstuurknop.
- `frontend/tests/account/ConsentRow.test.tsx`: de labels komen als prop en staan nergens
  als constante.

### 8.3 Laag 3: Playwright

In `frontend/e2e/account.spec.ts`, met dezelfde `serveAuth`:

- De herstelronde: `/account/#herstel=<token>` laden, het fragment is weg uit de URL, het
  formulier staat er, na 204 de inlogweergave met de melding.
- De aanvraagronde: dezelfde zin na een 202, of de mock nu een bekend adres speelt of niet.
- De bevestigingsronde: `#verificatie=`, de post gebeurt na `me/`, de regel staat er.
- Geen Engels op alle drie, en axe op beide nieuwe weergaven in beide paletten.

### 8.4 Laag 4: het contract

`tests/test_frontend_contract.py`: de dertien paden tegen de dertien routes; de fixtures
`me-response.json` en `consent-texts.json` opnieuw vastgezet, de tweede gegenereerd met de
labels; en de twee labels nergens in `frontend/src/**`.

### 8.5 Laag 5: over de echte stack

`test_live_a_reset_link_closes_the_loop` in `tests/test_stack_smoke.py`, onder dezelfde
`needs_stack`:

1. Registreer een vers adres, log uit.
2. `POST reset/request/` met dat adres; 202.
3. Draai het command in de container:
   `docker compose -f infra/docker-compose.yml -f infra/compose.test.yml --env-file
   infra/fixtures/env.smoke run --rm --entrypoint python api backend/manage.py
   send_outbound_mail`, exit 0.
4. Lees het nieuwste bestand in `infra/fixtures/mail/`, haal de link eruit, lees het token
   uit het fragment.
5. `POST reset/confirm/` met het token en een nieuw wachtwoord; 204, geen `Set-Cookie`.
6. `POST login/` met het oude wachtwoord: 401. Met het nieuwe: 200, en de cookie-attributen
   zoals de bestaande live check ze leest.
7. `GET me/`: `email_verified_at` is gevuld.
8. Verwijder het account.

Hetzelfde voor de bevestiging in `test_live_a_verification_link_sets_the_timestamp`, met
de mail die de registratie zelf al in de outbox zette. De uitvoer van de handmatige run gaat
in de commit, zoals bij de vier live checks die er al zijn, en de twee mailbestanden worden
na de run verwijderd. `infra/fixtures/mail/` is git-ignored, met een `.gitkeep`.

### 8.6 De vloeren

`fail_under` staat op 99,05 en de vier Vitest-vloeren op 97/94/96/98. Ze mogen omhoog en
nooit omlaag, en de meting die telt is die van de runner: een lokale run met `data/` erbij
dekt één regel meer dan de CI en heeft de vloer op 2026-09-06 al één keer rood laten worden.
Elke fouttak van vier views, één command en één client wordt getest, of de vloer wordt rood.

## 9. Deploy en omgeving

Wat op de host verandert, en wie het doet:

- **Eigenaar, bij Resend:** het domein `ampeer.nl` toevoegen en verifiëren met de SPF- en
  DKIM-records die Resend geeft; de verzendregio op `eu-west-1` (Ierland) zetten; een
  API-sleutel aanmaken met alleen verzendrecht, voor alleen dat domein; de DPA downloaden en
  bij de stukken leggen.
- **Eigenaar, in `/srv/ampeer/.env`:** `AMPEER_MAIL_TRANSPORT=resend`, `RESEND_API_KEY`,
  `AMPEER_MAIL_FROM=noreply@ampeer.nl`, `AMPEER_SITE_ORIGIN=https://ampeer.nl`.
  `scripts/preflight_env.sh` en `tests/test_infra.py` houden `infra/.env.example` en compose
  gelijk, dus een vergeten naam valt in de deploy. Dezelfde preflight weigert op de host
  elke `AMPEER_MAIL_TRANSPORT` anders dan `resend` (4.6), zodat een host nooit stil naar
  schijf mailt.
- **Eigenaar, op de host:** `cp infra/systemd/ampeer-mail.* /etc/systemd/system/`,
  `systemctl daemon-reload`, `systemctl enable --now ampeer-mail.timer`, en
  `systemctl list-timers ampeer-mail.timer` als controle. Zoals bij de purge-timer installeert
  niets in de repository dit, en de README zegt dat met dezelfde woorden.
- **De deploy-job:** `send_outbound_mail --check` na `migrate`, naast
  `purge_expired_advice --check`. Een stack waarin sinds een kwartier een mail ligt te wachten
  is een rode deploy.
- **`docker compose config --no-interpolate`** blijft de manier om het samengevoegde bestand
  te lezen: `RESEND_API_KEY` is de vierde waarde in deze stack die anders in klare tekst op een
  terminal komt.

## 10. Wat expliciet niet in v1 zit

- **Geen HTML-mail.** Platte tekst heeft één laag om te vertrouwen, de link is dezelfde, en
  een mailclient toont hem zonder afbeeldingen te laden of stijlen te strippen. Een
  opgemaakte variant zou een tweede tekstlaag zijn die gelijk moet blijven met de eerste.
- **Geen inloggen na herstel.** Hoofdstuk 3.3: de login-route blijft de enige plek waar een
  sessie begint.
- **Geen blokkade op een onbevestigd adres.** De eigenaar koos een tijdstip dat fase 2 eist
  en dat niets in fase 1 blokkeert. Een account werkt vanaf de registratie.
- **Geen opruiming van onbevestigde accounts.** Een account waarvan het adres na zeven dagen
  niet bevestigd is, blijft bestaan; wie het aanmaakte kan het verwijderen, wie het adres
  bezit kan via herstel het wachtwoord zetten en het dan verwijderen. Een automatische
  opruiming is een bewaartermijn op een `User`-rij, en dat is een DPIA-beslissing die hier
  niet genomen wordt. Hoofdstuk 10 van de DPIA noemt het niet als zesde punt, omdat het pas
  een vraag wordt als er accounts zijn die niemand bevestigt; het staat in
  `docs/decisions.md` onder wat hier niet besloten is.
- **Geen auditregel voor een geweigerde link.** Hoofdstuk 5.1.
- **Geen wijziging van het adres.** Een huishouden dat een ander adres wil, verwijdert zijn
  account en maakt een nieuw. Adreswijziging vraagt om een bevestiging van het nieuwe adres
  vóór de wissel, en dat is een derde stroom die dit kanaal wel mogelijk maakt en dit
  document niet bouwt.
- **Geen Celery, geen Redis in het verzoekpad, geen SDK, geen SMTP.** Hoofdstuk 4.
- **Geen nieuw pad, geen `layout.tsx`, geen wijziging aan `api.ts`, aan de vragenstroom of aan
  de adviespagina.** De enige bestaande frontend-bronbestanden die veranderen staan in
  hoofdstuk 11.
- **Geen tweede aanbieder.** Resend, omdat de eigenaar daar al een account heeft; het vijfde
  punt in hoofdstuk 10 van de DPIA houdt de vraag naar een Europese aanbieder open.

## 11. Bestanden die veranderen

Nieuw, backend:

| Bestand | Inhoud |
|---|---|
| `backend/accounts/recovery.py` | Hoofdstuk 3.6 |
| `backend/accounts/mailer.py` | Hoofdstuk 4.5 en de drie transporten uit 4.6 |
| `backend/accounts/management/commands/send_outbound_mail.py` | Hoofdstuk 4.4 |
| `backend/accounts/migrations/0002_*.py` | `email_verified_at`, `OneTimeToken`, `OutboundMail`; het nummer volgt op de bestaande migratie |

Gewijzigd, backend:

| Bestand | Wat |
|---|---|
| `backend/accounts/models.py` | `email_verified_at`; `OneTimeToken`; `OutboundMail` |
| `backend/accounts/views.py` | Vier views; `RegisterView.post` zet de bevestigingsmail klaar; `MeView` levert `email_verified_at`; `ConsentTextsView` levert `labels` |
| `backend/accounts/urls.py` | Vier paden, namen `auth-reset-request`, `auth-reset-confirm`, `auth-verify-request`, `auth-verify-confirm` |
| `backend/accounts/serializers.py` | `ResetRequestSerializer`, `ResetConfirmSerializer`, `VerifyConfirmSerializer`; `MeSerializer` met het nieuwe veld |
| `backend/accounts/nl.py` | `token_invalid`; de twee labels; de vierde categorie met vier mailsleutels; de docstring bij `CONSENT_TEXT_VERSION` |
| `backend/accounts/management/commands/purge_expired_sessions.py` | Ook `OneTimeToken` na `expires_at` en `OutboundMail` zeven dagen na `failed_at` |
| `backend/advice/models.py` | Vier constanten op `AuditEvent` |
| `backend/ampeer/settings/base.py` | `auth-reset` in `DEFAULT_THROTTLE_RATES`; `AMPEER_MAIL_TRANSPORT` met `memory` als basiswaarde voor de tests |
| `backend/ampeer/settings/dev.py` | `file`, naar `data/mail/` |
| `backend/ampeer/settings/prod.py` | De vier variabelen via `_required`, `memory` geweigerd |

Nieuw, frontend:

| Bestand | Inhoud |
|---|---|
| `frontend/src/app/_account/fragment.ts` | `readRecoveryFragment` |
| `frontend/src/app/_account/ResetRequestForm.tsx` | 6.2 |
| `frontend/src/app/_account/ResetConfirmForm.tsx` | 6.2 |
| `frontend/tests/account/fragment.test.ts` | Laag 2 |
| `frontend/tests/account/ResetRequestForm.test.tsx` | Laag 2 |
| `frontend/tests/account/ResetConfirmForm.test.tsx` | Laag 2 |

Gewijzigd, frontend:

| Bestand | Wat |
|---|---|
| `frontend/src/lib/accounts.ts` | Vier aanroepen; `Me.email_verified_at`; `ConsentTexts.labels`; de twee vormcontroles |
| `frontend/src/app/_account/AccountPage.tsx` | Twee weergaven; het fragment; de bevestigingspost na `me/`; de statusregel en de herstuurknop |
| `frontend/src/app/_account/SignInForm.tsx` | De knop "Wachtwoord vergeten?" op de plek van de zin over geen herstel |
| `frontend/src/app/_account/ConsentRow.tsx` | Label als prop; `CONSENT_LABELS` weg |
| `frontend/src/app/_account/RegisterForm.tsx` | Labels uit het `consent-texts/`-antwoord |
| `frontend/src/app/_account/messages.ts` | `token` in `AccountField` |
| `frontend/tests/lib/accounts.test.ts` | Laag 2 |
| `frontend/tests/account/AccountPage.test.tsx` | Laag 2 |
| `frontend/tests/account/ConsentRow.test.tsx` | Laag 2 |
| `frontend/tests/account/messages.test.ts` | De `token`-zin per veld |
| `frontend/tests/fixtures/me-response.json` | `email_verified_at: null` |
| `frontend/tests/fixtures/consent-texts.json` | Gegenereerd, met `labels` |
| `frontend/tests/ui-strings.txt` | Hoofdstuk 6.6 en 7.4, via de regeneratie |
| `frontend/e2e/account.spec.ts` | Laag 3 |

Nieuw en gewijzigd, tests, infra en documenten:

| Bestand | Wat |
|---|---|
| `tests/test_accounts_recovery.py` | Nieuw, laag 1 |
| `tests/test_accounts_mail.py` | Nieuw, laag 1 |
| `tests/test_accounts_api.py` | `me/` met het nieuwe veld; `consent-texts/` met de labels; de scope van elke nieuwe route |
| `tests/test_boundaries.py` | Hoofdstuk 4.7 |
| `tests/test_dpia.py` | `provider_id` in `AUDIT_CONTEXT_PHRASES` |
| `tests/test_frontend_contract.py` | Laag 4 |
| `tests/test_stack_smoke.py` | De twee live checks; de vier variabelen in de env-fixture; de placeholder-regel voor `RESEND_API_KEY` |
| `tests/helpers/consent_texts_fixture.py` | De labels in de fixture |
| `tests/test_deploy_workflow.py` | `test_the_host_preflight_refuses_any_transport_but_resend` (4.6) |
| `infra/docker-compose.yml` | De vier variabelen naar `api` |
| `infra/compose.test.yml` | De mount van `infra/fixtures/mail/` |
| `infra/fixtures/mail/.gitkeep` | Nieuw; de map is git-ignored op inhoud |
| `infra/systemd/ampeer-mail.service`, `infra/systemd/ampeer-mail.timer` | Nieuw, hoofdstuk 4.8 |
| `infra/README.md` | Sectie 3: de tweede timer; sectie 1: de vier variabelen |
| `infra/.env.example` | De vier namen |
| `.github/workflows/` | `send_outbound_mail --check` in de deploy-job, na `migrate`; geen jobnaam verandert |
| `scripts/preflight_env.sh` | Weigert op de host elke `AMPEER_MAIL_TRANSPORT` anders dan `resend` (4.6) |
| `docs/dpia.md` | Hoofdstuk 5.3 |
| `docs/decisions.md` | De zeven entries uit hoofdstuk 13; het beantwoorde punt over de vierde bron; het punt over onbevestigde accounts onder wat niet besloten is |
| `docs/superpowers/specs/2026-09-04-accounts-auth-design.md` | Hoofdstuk 10 daar krijgt de zin dat dit document het omkeert; de routetabel in 5.1 wordt dertien |
| `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md` | Hoofdstuk 10 daar: de twee punten over herstel en bevestiging verwijzen hierheen; hoofdstuk 6.1: de eerlijke zin is vervangen door de knop |
| `CLAUDE.md` | De allowlist-zin, al bijgewerkt in de commit die dit document toevoegt |

Geen nieuwe afhankelijkheid, in geen van beide bomen. `requests` staat er, en de frontend
heeft niets nodig dat er niet is.

## 12. Definition of done

- Een huishouden registreert, ontvangt binnen een minuut een bevestigingsmail, opent de link
  en ziet "E-mailadres bevestigd"; in de export staat het tijdstip
- Een huishouden dat zijn wachtwoord kwijt is, vraagt herstel aan, ontvangt een mail, kiest
  een nieuw wachtwoord, logt daarmee in, en kan daarna zijn account verwijderen: de
  zwakste plek uit hoofdstuk 10 van het auth-ontwerp is dicht
- Die twee rondes zijn met mocks in Playwright aangetoond, en over de echte stack met het
  `file`-transport, met de uitvoer in de commit
- `reset/request/` antwoordt byte-identiek voor een bekend en een onbekend adres, en logt
  niets voor een onbekend
- Een token werkt precies één keer, ook onder gelijktijdigheid, en verlopen, gebruikt,
  vervangen en onbekend geven dezelfde zin
- Een geslaagd herstel trekt elke sessie in, zet geen cookie, en bevestigt het adres
- Geen kolom in `OneTimeToken`, `OutboundMail` of `AuditEvent` bevat een ruw token of een
  adres, aangetoond op waarden
- Het command verstuurt, verwijdert, logt `MAIL_SENT`, wacht met backoff, geeft op na 24 uur,
  en laat na een mislukking geen token achter
- `mailer.py` is de enige module onder `backend/` die `requests` importeert, zijn URL is een
  literal, en `from django.core.mail import send_mail` maakt de grenstest rood
- De dertien routes hebben elk een scope met een tarief, en het plafond van nginx overtreft
  de som nog minstens vijftig keer
- `me/` draagt `email_verified_at`, `consent-texts/` draagt `labels`, en beide fixtures zijn
  opnieuw vastgezet
- De DPIA noemt de vier auditsoorten, `provider_id`, Resend als tweede verwerker, dertien
  routes, en opent hoofdstuk 10 met "Vijf"
- De zin over "geen wachtwoordherstel" staat nergens meer in `frontend/src/**`, en de kop
  van `ui-strings.txt` noemt een ander voorbeeld
- axe vindt geen overtredingen op de twee nieuwe weergaven, in beide paletten
- De units staan in `infra/systemd/`, de README zegt hoe ze geïnstalleerd worden, en de
  deploy-job draait `send_outbound_mail --check`
- Alle poorten zijn groen, de vloeren zijn gemeten op de runner, en van elke nieuwe controle
  is aangetoond dat hij rood kan worden

## 13. Beslissingen die dit ontwerp vastlegt

Zeven entries voor `docs/decisions.md`, te schrijven in de documententaak van het plan, elk
met Decided, Because, Lives in en To reverse:

1. **A password can be reset, and the token is a row rather than a signature.** Keert
   beslissing 31 om en zegt waarom `PasswordResetTokenGenerator` het niet werd (hoofdstuk 2.4).
2. **Mail leaves through an outbox and a timer, not through the request and not through
   Celery.** Hoofdstuk 4.1.
3. **Resend is reached from one module on the allowlist, and Django's mail API is forbidden
   by the boundary test.** Hoofdstuk 4.5 en 4.7.
4. **The recovery link carries its token in the fragment.** Hoofdstuk 6.1.
5. **Verification is a timestamp, set by a confirmation or a completed reset, and read by
   nothing before phase 2.** Hoofdstuk 2.5.
6. **The consent labels travel with the texts under one version.** Sluit beslissing 38,
   hoofdstuk 3.7.
7. **A reset request answers the same way for every address, and logs nothing for an
   unknown one.** Hoofdstuk 3.2.

Daarnaast beantwoordt die taak in hetzelfde document het punt onder "What was not decided
here" over de vierde bron, want CLAUDE.md noemt nu wat de repository bereikt, en voegt het
punt over onbevestigde accounts toe, met de reden uit hoofdstuk 10.
