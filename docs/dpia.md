# Gegevensbeschermingseffectbeoordeling

Over de rekenmachine, de adviseur en de accountlaag zoals die vandaag draaien, fase 1.

## 0. Wat dit document is, en wat het niet is

Dit is de technische helft van een DPIA: een beschrijving van wat de dienst
werkelijk verwerkt, hoe lang, waar de kopieën staan, wie erbij kan en wat de
machine verlaat. Elk feit hierin is uit de code gelezen of gemeten, niet
onthouden, en `tests/test_dpia.py` houdt de getallen hieronder naast de plek in
de code waar ze vandaan komen. Verandert er een, dan valt die test om.

Dit is geen juridisch advies en het is niet ondertekend. Vijf dingen zijn
beslissingen van de verwerkingsverantwoordelijke en staan in hoofdstuk 10 met
de informatie die nodig is om ze te nemen.

## 1. Is een DPIA hier verplicht

Artikel 35 AVG eist een beoordeling bij verwerkingen die waarschijnlijk een hoog
risico opleveren. Voor fase 0.5 is dat waarschijnlijk niet zo, en het is de
moeite waard om op te schrijven waarom, want de reden verdwijnt bij de volgende
fase.

Wat een hoog risico zou opleveren is kwartierdata uit de meter. Daaruit is af te
leiden wanneer iemand thuis is, wanneer iemand op vakantie gaat en wanneer een
huishouden van samenstelling verandert. Die data is er niet. De rekenmachine
vraagt vier dingen en leidt de rest af uit een landelijk standaardprofiel dat
niets over dit huishouden weet.

Wat er wel is, is een viercijferige postcode naast een jaarverbruik en een
dakopstelling. Dat is een persoonsgegeven, want een postcodegebied plus een
verbruik plus een dakrichting is in een dunbevolkt gebied herleidbaar, en het
wordt bewaard achter een deelbare link. Het is geen bijzondere categorie, het is
geen stelselmatige observatie en het is geen grootschalige monitoring van een
openbare ruimte.

De afweging was dus: waarschijnlijk niet verplicht in fase 0.5, wel verstandig,
en verplicht zodra fase 1 begint.

Fase 1 is nu het geval. Er bestaat een account, een e-mailadres, een
wachtwoordhash en een bijgehouden inlogpoging, en dat is niet de kwartierdata
die hierboven het hoge risico beschrijft: een inlogformulier op zichzelf is
geen artikel 35-geval. Maar de afweging hierboven zei zelf dat de reden om te
wachten bij deze fase zou verdwijnen, en dat is precies wat er gebeurd is: een
beoordeling is nu waarschijnlijk wel verplicht. Hoofdstuk 9 zet uiteen wat er
bij fase 1 is bijgekomen en wat fase 2 nog brengt. Hoofdstuk 10 laat de
conclusie zelf aan de verwerkingsverantwoordelijke.

## 2. Wat wij verwerken

Alles hieronder komt uit `backend/advice/models.py`,
`backend/advice/serializers.py` en, sinds fase 1, `backend/accounts/models.py`
en de axes-instellingen.

### Wat de bezoeker invult

De eerste ronde stelt vier vragen en levert vijf antwoorden op: viercijferige
postcode, jaarverbruik in kWh, vermogen aan panelen in wattpiek, en dakrichting
en hellingshoek, die samen een vraag zijn en apart worden opgeslagen. Een
tweede ronde stelt vijf vragen erbij en levert acht antwoorden: overdag thuis,
elektrische auto en het laadmoment, warmtepomp en warmtevraag, contractvorm,
thuisbatterij en de omvang daarvan. Negen vragen in totaal, en dat getal
bepaalt ook het betrouwbaarheidsniveau in hoofdstuk 17 van de methodologie.

**De postcode wordt op vier cijfers gevalideerd en er is geen veld waar meer in
past.** Dat is niet een afspraak maar een reguliere expressie in de serializer:
zes tekens worden geweigerd, niet afgekapt. Een afgekapte waarde zou betekenen
dat de volledige postcode ooit de applicatie bereikte.

### Wat de dienst zelf toevoegt

Bij elk antwoord hoort een token van 22 tekens uit `secrets.token_urlsafe(16)`.
Dat is de sleutel in de deelbare link. Hij is niet af te leiden uit de inhoud en
niet te raden.

### Wat er niet is

Geen naam, geen telefoonnummer, geen huisnummer. Wel, sinds fase 1, een account:
wie er een aanmaakt geeft een e-mailadres op en een wachtwoord, en het
wachtwoord staat nergens in leesbare vorm. `backend/accounts/models.py` hasht
het met Argon2id voor het de database raakt, en wat er staat is de hash en
`last_login`, het tijdstip van de laatste geslaagde aanmelding dat
`AbstractBaseUser` zelf meebrengt.

Sinds het derde deel van fase 1 staat er ook `email_verified_at` bij: het
tijdstip waarop het adres is bevestigd via een link uit een mail, of leeg als
dat nooit is gebeurd. Een tijdstip en geen vlag, omdat "wanneer" de vraag is
die dit document stelt. Twee tabellen kwamen erbij en geen van beide draagt
een adres: `OneTimeToken` houdt de sha256 van een herstel- of
bevestigingslink met de tijdstippen van uitgifte, verloop en gebruik, en
`OutboundMail` houdt alleen wie een mail moet krijgen, van welke soort en
sinds wanneer; het adres wordt op het moment van verzenden van het account
gelezen en het token bestaat dan nog niet. Een tokenrij verdwijnt bij
verloop (`spent_at` blijft tot dan staan, want een gebruikt token dat nog
bestaat is wat hergebruik zichtbaar maakt), een outbox-rij bij verzending en
zeven dagen na een mislukking.

Een mislukte aanmelding wordt niet op het account bijgehouden maar in het
auditlogboek hieronder.

De rekenmachine zelf blijft anoniem. Een account bestaat naast een advies, niet
ervoor: `StoredAdvice.owner` in `backend/advice/models.py` staat op elke rij op
`NULL` totdat een latere fase hem vult, en de tokenroute kijkt er niet naar. Wie
nooit een account aanmaakt, merkt dus niets van dit hoofdstuk.

**Geen IP-adres in enige tabel die deze dienst zelf ontwerpt, en een lege tabel
bij de tabellen die een derde partij meebrengt.** Het IP-adres wordt gebruikt,
want het tempolimiet moet ergens op tellen, maar het wordt daarvoor eerst
gehasht (`advice/throttling.py`) en de teller staat in een cache met een
vervaltijd. Geen model van deze dienst heeft een adresveld en geen logregel van
deze dienst bewaart er een. `django-axes` is anders: die app brengt zelf drie
tabellen mee met een `ip_address`-kolom (`AccessAttempt`, `AccessLog`,
`AccessFailureLog`), en die tabellen bestaan zodra `axes` in `INSTALLED_APPS`
staat, ongeacht welke handler ingesteld is. Wat hier telt is dat ze leeg
blijven: `AXES_HANDLER` staat op de cachehandler en niet op de databasehandler,
dus een mislukte aanmelding telt op tegen een sleutel in een cache met een
vervaltijd, en niets schrijft ooit een rij in die drie tabellen. Gemeten: na
zes mislukte aanmeldingen staan alle drie op nul rijen.

### Het auditlogboek

`AuditEvent` is append-only en kent sinds fase 1 dertien soorten gebeurtenissen
in plaats van een: dat er een advies is gegenereerd (`ADVICE_GENERATED`), dat een
account is aangemaakt (`ACCOUNT_CREATED`), dat een aanmelding lukte of mislukte
(`LOGIN_SUCCEEDED`, `LOGIN_FAILED`), dat iemand uitlogde (`LOGOUT`), dat een
toestemming is gegeven of ingetrokken (`CONSENT_GRANTED`,
`CONSENT_WITHDRAWN`), dat gegevens zijn geexporteerd (`DATA_EXPORTED`) en dat
een account is verwijderd (`ACCOUNT_DELETED`), en sinds het derde deel van fase 1
ook dat om wachtwoordherstel is gevraagd voor een adres dat bij een account
hoort (`PASSWORD_RESET_REQUESTED`), dat een herstel is voltooid
(`PASSWORD_RESET_COMPLETED`), dat een e-mailadres is bevestigd
(`EMAIL_VERIFIED`) en dat een bericht bij de mailverwerker is afgeleverd
(`MAIL_SENT`). Bij de eerste regel staat een
sha256 van het token, het viercijferige postcodegebied, het
betrouwbaarheidsniveau en de twee versienummers van de motor en de regeltabel.
De twaalf andere dragen geen vaste vorm, en dat is opzettelijk beschreven in
plaats van vereenvoudigd tot een: de meeste dragen een `user_id`, een geheel
getal of `null`, en nooit een e-mailadres. `null` betekent dat een mislukte
aanmelding een adres probeerde dat bij geen account hoort; er is dan niets om
naar te verwijzen, en dat is het punt, niet een omissie. Een toestemmingsregel
draagt daarnaast een `kind` (`METER_LINK` of `LEAD_GENERATION`), want anders
staat er een toestemming zonder te zeggen waarvoor. En een mislukte
tokenvernieuwing draagt geen `user_id` maar alleen `reused`, een boolean die
onderscheidt of het ging om een hergebruikt token of om een andere fout: op dat
moment is de sessie al ontkoppeld van de aanvraag, en een `user_id` verzinnen
zou een koppeling suggereren die er niet is.

Een regel over een verzonden mail draagt naast `user_id` en `kind` een
`provider_id`: het bericht-id dat de mailverwerker teruggeeft. Dat id is geen
persoonsgegeven en het is wel het enige waarmee een verzending bij die
verwerker teruggevonden kan worden.

In alle gevallen geldt: deze tabel wordt nooit opgeruimd, dus wat erin staat
overleeft het account dat het beschrijft, en een getal dat naar een
verwijderde rij wijst is een lege verwijzing waar een e-mailadres een
blijvend persoonsgegeven zou zijn in een tabel zonder bewaartermijn. Een
herstelverzoek voor een adres dat bij geen account hoort, wordt niet gelogd:
een regel daarover zou het adres zelf moeten dragen om iets te betekenen.

**Niet het token zelf.** Het token is geen verwijzing naar een advies, het is
de enige sleutel die het opent, en deze tabel wordt nooit opgeruimd. Een token
in platte tekst zou hier dus als permanente regel blijven staan met een
werkende link naar een advies dat na negentig dagen weg had moeten zijn. De
hash houdt waar het logboek voor is: wie de link legitiem heeft kan hem hashen
en zijn eigen regel terugvinden.

Twee gebeurtenissen uit de lijst in `CLAUDE.md` staan hier nog niet: een
meterkoppeling die tot stand komt en een verstuurde lead. Die ontbreken omdat de
handelingen zelf nog niet bestaan. Een logboek dat ze nu al noemde zou een
verwerking beschrijven die er niet is.

Dat logboek heeft geen bewaartermijn, met opzet. Een auditlogboek dat verloopt
is geen auditlogboek. Wat het draagt verliest wel zijn zeggingskracht: zodra het
advies na negentig dagen weg is, wijst de hash in het logboek nergens meer
naar, en wat overblijft is een postcodegebied, een tijdstip en twee
versienummers. Voor een account geldt hetzelfde: zodra het account verwijderd
is, wijst een `user_id` in het logboek naar niets meer.

## 3. Waarom, en waarom niet meer

De vier vragen zijn precies wat de simulatie nodig heeft. De postcode kiest de
instralingsreeks, het jaarverbruik schaalt het profiel, en wattpiek en
dakopstelling bepalen de opwek. Er is geen vraag die alleen voor de statistiek
gesteld wordt.

De grondslag hoort bij de verwerkingsverantwoordelijke en staat in hoofdstuk 10.
Feitelijk relevant is dat de bezoeker de gegevens zelf invult om er een antwoord
voor terug te krijgen, dat er niets gebeurt zonder die invoer, en dat er geen
tweede doel is: geen advertenties, geen profielopbouw, geen doorverkoop, en geen
commerciele relatie die het advies kan sturen.

## 4. Hoe lang, en waar de kopieen staan

**Negentig dagen** (`AMPEER_ADVICE_TTL_DAYS`). Een dagelijkse taak verwijdert
wat over datum is, en de deploy weigert door te gaan als die taak gestopt blijkt.

Wat die negentig dagen beloven is nauwkeuriger dan het klinkt, en
`infra/README.md` legt het uit: `DELETE` markeert een rij als dood en overschrijft
hem niet. De belofte is dat de dienst het advies na negentig dagen niet meer
teruggeeft en niet meer kan vinden. Dat is de belofte waar een deelbare link,
een inzageverzoek en een verwijderverzoek alle drie over gaan.

**Sinds 21 augustus 2026 is er een tweede kopie**, en dat is een bewuste ruil.
Er wordt dagelijks een dump gemaakt en `KEEP_DAYS` staat op zeven, dus
een advies dat de dienst niet meer teruggeeft kan nog ten hoogste acht dagen in
een back-upbestand staan. Acht en niet zeven, en dat is geen afronding maar hoe
het opruimen telt: `find -mtime +7` verwijdert pas vanaf acht volle dagen, dus
naast de dump van vandaag blijven die van dag een tot en met zeven staan. Op
schijf staan er daarmee ten hoogste acht. Drie dingen begrenzen dat, en het zijn eigenschappen van
het script en de timer en geen beloften:

1. de dump draait een uur na de opruiming, dus een dump bevat nooit advies dat
   op het moment van maken al over datum was
2. dumps ouder dan zeven dagen worden bij elke run verwijderd
3. terugzetten verlengt niets blijvend, want de opruiming draait dagelijks en
   haalt herleefde rijen binnen een cyclus weg

Waarom die ruil is aangegaan staat in hoofdstuk 8 van `infra/README.md`: het
auditlogboek is de enige tabel die niets kan herbouwen, en append-only
beschermt hem tegen herschrijven en niet tegen het verdwijnen van een schijf.
Een back-up die alleen dat logboek zou dumpen vermijdt de ruil en kan de dienst
niet terugbrengen.

**Hetzelfde geldt sinds fase 1 voor een verwijderd account.** Verwijderen
gebeurt op verzoek en niet op een vervaldatum, dus er is geen dagelijkse taak
voor nodig: `delete_account` in `backend/accounts/service.py` haalt de rij in
een en dezelfde transactie weg, en `CASCADE` neemt `Consent`, elke
`RefreshSession` en elk eigen `StoredAdvice` in die transactie mee. Wat
blijft staan is een regel in het auditlogboek, zoals hoofdstuk 2 al
beschrijft. De back-upruil hierboven maakt geen uitzondering voor een
verwijderd account: het kan net als een vervallen advies nog ten hoogste acht
dagen in een dump staan, om precies dezelfde reden.

De vraag die de back-up daarmee oproept is niet hoe lang de cijfers in de dienst
leven, maar wie de bestanden kan lezen. Ze worden `0600` geschreven in een map
die het script `0700` aanmaakt, en de controle die de deploy draait weigert een
back-up gezond te noemen als een van beide ruimer staat.

## 5. Wie erbij kan

De database luistert niet naar buiten. Er is geen enkele gepubliceerde poort in
de stack; de tunnelverbinding wordt van binnenuit opgezet. De enige weg naar de
gegevens loopt via de API, en die geeft op een token precies een advies terug.

Op de host kan root bij alles, en dat is de verwerkingsverantwoordelijke.
Toegang tot de host is geen onderwerp van dit document en hoort bij hoofdstuk 10.

**Cloudflare Inc. is een verwerker.** De tunnelverbinding geeft het verkeer niet
alleen door. Cloudflare beeindigt TLS aan de rand en de connector spreekt daarna
gewoon HTTP tegen deze machine. Dat staat zo in `infra/nginx/nginx.conf`, als de
reden dat `X-Forwarded-Proto` daar een constante mag zijn: `$scheme` is op elk
verzoek `http`, ook op de verzoeken die over https binnenkwamen. De versleuteling
loopt dus tot Cloudflare en niet tot hier.

Cloudflare ziet daarmee op elk verzoek twee dingen in leesbare vorm:

- **Het pad.** Dat is `GET /advies/<token>/` en `GET /api/advice/<token>/`. Dat
  token is niet een verwijzing naar een advies, het is de enige sleutel die het
  opent, en het is precies wat vier voorzieningen in deze stack uit de logboeken
  houden: het `map`-blok in `infra/nginx/nginx.conf` dat een pad met een token
  door een label vervangt, `error_log crit` op de twee locaties die tokens
  dragen, `RedactedFormatter` in `backend/ampeer/settings/base.py` en
  `server_side_binding` in `backend/ampeer/settings/prod.py`. Die vier houden het
  token uit de logboeken van deze machine. Ze zeggen niets over de rand.
- **Het IP-adres van de bezoeker.** Hoofdstuk 2 zegt dat er geen tabel is met een
  adresveld, en dat klopt: `backend/advice/throttling.py` hasht het adres met een
  HMAC onder `SECRET_KEY` voordat het een teller wordt. Die moeite gaat over deze
  machine. Bij Cloudflare komt het adres onvermijdelijk binnen, want het is de
  partij die de verbinding aanneemt.

Dat maakt Cloudflare een verwerker in de zin van artikel 4 lid 8 AVG, en artikel
28 eist voor een verwerker een schriftelijke verwerkersovereenkomst. Cloudflare
publiceert een standaardovereenkomst die bij het account hoort. Of die is
aanvaard en of hij deze verwerking dekt, is niet nagegaan en nergens vastgelegd,
en dat is wat hier ontbreekt. Hoofdstuk 10 zet het bij de
verwerkingsverantwoordelijke, naast de privacyverklaring en het
verwerkersregister.

**Resend, Inc. is sinds het derde deel van fase 1 de tweede verwerker.** Hij
verstuurt de mails voor wachtwoordherstel en adresbevestiging, en ziet per
bericht het e-mailadres, het feit dat bij dat adres een account bestaat of om
herstel is gevraagd, en de inhoud van de mail, waarvan de link een uur of zeven
dagen een werkende sleutel is. Hij bewaart een eigen verzendlog met adres,
onderwerp en inhoud, en dat log staat in de Verenigde Staten, ongeacht de
verzendregio: Resend zegt zelf dat de regio bepaalt waar een mail vandaan
wordt verstuurd en niet waar accountdata, metadata en logs staan. De doorgifte
rust op de Standard Contractual Clauses in zijn Data Processing Addendum en op
zijn certificering onder het EU-US Data Privacy Framework; die DPA is
voorgetekend bij elk account en te downloaden uit het dashboard. De
verzendregio is de EU-regio (Ierland), zodat de mail zelf niet via een
Amerikaans datacenter loopt. Wat Resend niet ziet: de reden voor een
herstelverzoek, een wachtwoord, een toestemming of een advies. Alleen het
command `send_outbound_mail` bereikt Resend, onder een timer; geen enkel
verzoek van een bezoeker doet dat.

Verder wordt niets uitbesteed. Er gaat geen gegeven naar een advertentie- of
analysepartij.

## 6. Wat de machine verlaat

**Voor de bezoeker: niets.** Het laden van een pagina veroorzaakt geen enkel
verzoek aan een host buiten de machine die de site serveert. Er is geen Google
Analytics, geen tag manager, geen CDN en geen extern lettertype: de twee
lettertypen worden bij het bouwen opgehaald en daarna vanaf de eigen oorsprong
geserveerd. Gemeten op 21 augustus 2026 in de gebouwde site, en sindsdien
afgedwongen door `frontend/e2e/privacy.spec.ts`, die elk verzoek meeleest en
valt op elke host die deze machine niet is.

**Voor de dienst: naar een vaste lijst.** De backend haalt instralingsgegevens
op bij PVGIS. Die URL wordt nooit uit gebruikersinvoer opgebouwd; de invoer
levert alleen gevalideerde parameters, en de postcode gaat als tweecijferig
gebied naar een middelpunt. Er is geen enkele plek waar de backend een door de
gebruiker aangeleverde URL ophaalt.

Sinds het derde deel van fase 1 staat `api.resend.com` op die lijst, als
bestemming van het command dat de outbox leegt. Alleen dat command bereikt
die host, elke minuut onder een timer, en geen verzoek van een bezoeker; de
lijst zelf staat als `OUTBOUND_MODULES` in `tests/test_boundaries.py` en die
test valt om zodra een tweede module dezelfde host aanraakt of Django's eigen
mail-API ergens wordt geïmporteerd.

### Het jaar in kwartieren, en waarom dat hier staat

Het antwoord draagt sinds 27 augustus 2026 een veld `year`: uw hele jaar in
kwartieren, zodat het scherm het als een plaat kan tekenen. Dat zijn twee
reeksen van 35040 bytes, base64 gecodeerd, met drie plafonds in kWh per
kwartier erbij en een telling van het aantal kwartieren. De eerste byte per
kwartier zegt hoeveel van de eigen opwek u in dat kwartier zelf hebt gebruikt,
de tweede is de meter, met de richting in de hoogste bit.

Wat dat kost om te versturen, gemeten op 27 augustus 2026 op het
referentiehuishouden van `tests/test_advice_series.py`: het veld is 93.608
bytes aan JSON, en 45.242 bytes zodra nginx het inpakt op compressieniveau 1,
de standaard die `infra/nginx/` niet overschrijft.

Het eerste getal ligt vast in de vorm: 35040 bytes per reeks worden 46720
tekens base64, en verder varieren alleen de drie plafonds. Het tweede hangt af
van uw gegevens en beweegt dus mee met elke correctie aan het opwekmodel.
Daarom houdt `tests/test_dpia.py` beide binnen twee procent van een verse
meting in plaats van op de letter. Een eerdere versie van dit hoofdstuk noemde
ongeveer 43 kB voor het ingepakte veld. Dat getal hoorde bij de gepakte bytes
voordat er base64 overheen ging, dus bij iets wat niemand ontvangt.

Het veld is optioneel. Een advies dat voor 27 augustus 2026 is opgeslagen draagt
het niet, en de tokenroute geeft terug wat er staat, dus in de negentig dagen
daarna komen beide vormen voor. Datzelfde antwoord wordt ook opgeslagen, dus
een advies van vandaag beslaat in de database ongeveer 91 kB in plaats van
enkele kilobytes. Dat is dezelfde reeks achter dezelfde link en geen tweede
verwerking, maar het is wel een grotere kopie, en hoofdstuk 4 beschrijft hoe
lang die blijft staan.

**Waarom dit vandaag geen nieuw persoonsgegeven is.** De reeks is synthetisch.
Hij wordt opgebouwd uit een landelijk NEDU-standaardprofiel, geschaald naar het
jaarverbruik dat u zelf hebt ingevuld, plus wat het model voor een auto of een
warmtepomp optelt, en een opwekreeks voor het tweecijferige postcodegebied. Er
staat niets in over dit huishouden dat dit huishouden niet zelf heeft
ingetypt. Wie de reeks terugrekent, komt uit bij de antwoorden uit hoofdstuk 2
en niet bij een dag thuis. Het is dus geen nieuwe verwerking maar een andere
weergave van wat al achter dezelfde link stond.

**De zin waarmee dat verandert.** Zodra hetzelfde veld een reeks draagt die van
de meter van dit huishouden zelf komt, is het wel een persoonsgegeven. Het is
bovendien precies het persoonsgegeven waarover hoofdstuk 1 zegt dat het de hele
afweging omdraait: uit kwartierdata over verbruik is af te leiden wanneer
iemand thuis is, wanneer iemand op vakantie gaat en wanneer een huishouden van
samenstelling verandert. De vorm van het veld is dan gelijk, de resolutie is
gelijk, en de gevoeligheid is dat niet.

**Wat ertussen staat.** Het veld draagt zelf waar zijn getallen vandaan komen,
in `provenance`, met twee mogelijke waarden: `SYNTHETIC` of `MEASURED`. De API
weigert een antwoord samen te stellen dat een gemeten reeks combineert met een
deelbaar token. Dat is de combinatie waar het om gaat, want een token is een
sleutel zonder account erachter, negentig dagen geldig, en iedereen aan wie de
link ooit is doorgestuurd kan lezen wat erachter staat.

De weigering staat in `backend/advice/serializers.py`, in de enige functie die
dit veld kan opbouwen, en `tests/test_advice_series.py` valt om zodra een
gemeten reeks over de tokenroute te halen zou zijn. Voor fase 2 is er een
uitgang, `shareable_token=False`, bedoeld voor een advies dat achter een
account wordt opgehaald in plaats van achter een doorstuurbare link. Niets
gebruikt die uitgang vandaag, en een test valt om zodra iets dat wel doet.

Die weigering staat bij het schrijven en niet bij het lezen, en dat is een
eigenschap om te kennen in plaats van een detail. De tokenroute zoekt een rij
op en geeft terug wat erin staat; hij kijkt niet naar `provenance` en filtert
niets. Wat er dus eenmaal in staat, is negentig dagen lang leesbaar voor
iedereen aan wie de link is doorgestuurd, en een controle die later aan de
leeskant wordt toegevoegd laat elke rij van daarvoor ongemoeid. Daarom zit de
deur voor het opslaan.
`tests/test_advice_api.py` doet dat na op de echte route: met een gemeten reeks
mislukt het verzoek, de rij die al was aangemaakt blijft leeg, en er is dus
niets om op te halen. `tests/test_advice_series.py` legt de andere helft vast,
namelijk dat de tokenroute een gemeten reeks die iemand er rechtstreeks in zou
schrijven wel degelijk zou uitleveren.

Dat dit nu is gebouwd en niet in fase 2 is een keuze met een reden. Vandaag
kost het drie regels. Op het moment dat de eerste gemeten reeks bestaat kost
het een migratie over elk opgeslagen advies, en tussen die twee momenten zit
een periode waarin deze regel in dit document staat en nergens wordt
afgedwongen. Hoofdstuk 9 telt op wat er in die fase verder verandert.

## 7. Wat een bezoeker kan uitoefenen, en wat vandaag niet kan

Een beoordeling die opsomt wat een dienst bewaart en niet zegt wat de betrokkene
daarmee kan, is de helft van een beoordeling. Dit hoofdstuk ontbrak in de eerste
versie van dit document.

De tokenroute kent nog steeds drie handelingen: twee die rekenen en opslaan, en
een die op een token teruggeeft wat er staat. Sinds fase 1 komt daar een tweede,
apart bediende API bij, onder `/api/auth/`, met dertien routes die geen van alle
meer dan `get` of `post` beantwoorden. Vier daarvan zijn publiek zonder een
persoonsgegeven terug te geven: de toestemmingsteksten met hun labels en versie,
voor iedereen hetzelfde, en de drie routes waarmee een herstellink wordt
aangevraagd, een herstellink wordt gebruikt en een bevestigingslink wordt
gebruikt. De aanvraag antwoordt voor elk adres hetzelfde en zegt dus niet of er
een account bij hoort. `tests/test_dpia.py` leest beide bestanden en valt om
zodra een van beide dat niet meer doet.

Inzage, overdraagbaarheid en verwijdering veranderen hieronder alle drie voor
wie een account heeft, en geen van drieen voor de tokenroute: die blijft precies
wat hij was.

### Inzage werkt, en voor een accountholder nu vollediger

Wie de link heeft, opent het advies zoals voorheen. Dat is inzage zonder
verzoek, zonder wachttijd en zonder dat iemand een identiteit hoeft aan te
tonen, en dat kan juist omdat het token het enige is dat de rij aanwijst.

Er is wel een verschil dat eerlijk benoemd hoort te worden, en dat verschil
geldt onveranderd voor de tokenroute. De dienst bewaart naast het advies ook de
antwoorden waarmee het gemaakt is, en de tokenroute geeft alleen het advies
terug. Wie wil weten wat er precies over hem is opgeslagen via de link alleen,
ziet dus de uitkomst en niet de invoer. Dat is te herleiden, want het advies is
uit die invoer gemaakt, maar het is niet hetzelfde als het tonen ervan.

Wie een account heeft, kan sinds fase 1 meer. `GET /api/auth/me/` toont het
e-mailadres en de actuele stand van beide toestemmingen. `POST
/api/auth/export/` gaat verder: het geeft het e-mailadres, de datum van
aanmaken, het tijdstip waarop het adres is bevestigd (leeg zolang dat niet is
gebeurd), de volledige geschiedenis van beide toestemmingen (elke rij, niet
alleen de laatste) en de lijst van eigen adviezen terug, met daarin zowel de
antwoorden als het advies zelf. Dat laatste repareert precies het gat dat de
vorige alinea beschrijft: de invoer wordt hier wel teruggegeven.

Die lijst van eigen adviezen is vandaag structureel aanwezig en materieel
altijd leeg. Niets in fase 1 zet `StoredAdvice.owner`, dus `advices` in de
export is een lege lijst totdat fase 2 een advies aan een account koppelt. Het
is dezelfde reden waarom die kolom nu al bestaat: hem later toevoegen is een
migratie over elk opgeslagen advies, en tussen die twee momenten in zou een
export iets beloven dat de kolom nog niet kan waarmaken.

### Overdraagbaarheid volgt daaruit

Het antwoord op de tokenroute is JSON en dus machineleesbaar. Er is geen knop
die het exporteert, maar er is ook geen tussenkomst nodig: de link teruggeeft
is het bestand. Dezelfde beperking geldt, namelijk dat de opgeslagen invoer er
niet in zit.

Voor een accountholder is de export hetzelfde antwoord machineleesbaar, en wel
achter een knop: `POST /api/auth/export/` in plaats van een link die toevallig
het bestand is.

### Rectificatie voegt toe in plaats van te wijzigen

Een antwoord dat verkeerd is ingevuld, is niet te corrigeren, voor geen van
beide routes. Opnieuw rekenen maakt een nieuw advies met een nieuw token, en
het oude blijft staan tot het verloopt. Een correctie voegt dus een rij toe
waar een lezer een vervanging zou verwachten. Dat geldt voor een advies met een
`owner` net zo goed als voor een anoniem advies: er is nergens een `put` of een
`patch`, en dit is de enige van de vier rechten die niet is beantwoord door
fase 1.

### Verwijderen kan voor een accountholder, en niet voor de tokenroute

Wie alleen de link van een advies heeft, kan dat advies nog steeds niet eerder
laten verdwijnen dan na negentig dagen: er is voor de tokenroute geen knop en
geen route die dat doet. Bezit van een token is geen bruikbare autorisatie voor
een verwijdering, want elke ontvanger van een doorgestuurde link zou hem dan
kunnen gebruiken, en wat er dan verdwijnt zou toch herberekenbaar zijn geweest
uit de eigen antwoorden.

Voor een accountholder is de vraag nu beantwoord. `POST /api/auth/delete/`
verwijdert het account, op een `post` en niet op een `delete`, want de API
onder `/api/auth/` beantwoordt uitsluitend `get` en `post`. De route vraagt het
wachtwoord opnieuw, dus bezit van de sessiecookie alleen is niet genoeg: wie de
cookie steelt maar het wachtwoord niet heeft, kan het account niet verwijderen.
Dat is precies de autorisatie die bij de tokenroute ontbrak en ontbreekt.

Diezelfde vraag om het wachtwoord had tot het derde deel van fase 1 een
keerzijde: er was geen route om een vergeten wachtwoord te herstellen, dus wie
het kwijt was bereikte `/api/auth/delete/` niet meer. Die route bestaat nu.
`POST /api/auth/reset/request/` zet een mail klaar naar het adres van het
account, `POST /api/auth/reset/confirm/` zet met de link uit die mail een nieuw
wachtwoord, trekt elke sessie in en bevestigt het adres, en daarna werkt
inloggen, en dus ook verwijderen, met het nieuwe wachtwoord. De link werkt een
uur en een keer. Wie zijn wachtwoord kwijt is heeft daarmee weer een
zelfbedieningsweg, en de zwakste plek van het auth-ontwerp is dicht. Wat er
nog niet kan: het adres zelf wijzigen; wie een ander adres wil, verwijdert zijn
account en maakt een nieuw.

Wat er dan gebeurt staat in `delete_account` in `backend/accounts/service.py`,
in een transactie. `CASCADE` neemt `Consent`, elke `RefreshSession` en elk
eigen `StoredAdvice` in een keer mee. Wat blijft staan is een regel in
`AuditEvent` met daarin een `user_id` die naar niets meer wijst: een geheel
getal zonder persoonsgegeven erbij, zoals hoofdstuk 2 al beschrijft.

`CLAUDE.md` zette de export- en verwijderknop bij de fase waarin accounts
bestaan. Die fase is nu, en de knop bestaat.

### Een geautomatiseerd besluit is het niet

Het advies komt volledig geautomatiseerd tot stand. Het heeft geen rechtsgevolg
en het treft niemand in vergelijkbare mate: het is een berekening waar de
bezoeker zelf om vroeg, er wordt niets op geweigerd of toegekend, en er gaat
geen gegeven naar een partij die er iets mee doet.

Wat artikel 22 zou eisen als het wel zo was, doet de dienst overigens al. Elk
advies geeft terug welke regels gevuurd hebben, elk bedrag draagt een
bandbreedte, en het betrouwbaarheidsniveau staat in het eerste scherm in plaats
van in een voetnoot. Dat staat er niet omdat het moet maar omdat het het product
is, en het is de reden dat dit hoofdstuk kort kan zijn.

## 8. Risico's, en wat ertegen staat

| Risico | Wat ertegen staat |
|---|---|
| Iemand raadt of doorloopt tokens en leest andermans advies | 22 tekens uit een cryptografische bron, en een tempolimiet van 120 leesverzoeken per uur per gehashte identiteit |
| Een deelbare link belandt bij iemand anders, bijvoorbeeld in een doorgestuurd bericht | Dit is inherent aan een link zonder account. De link verloopt na negentig dagen. Wat erachter staat is een postcodegebied en een jaarverbruik, geen naam |
| Het IP-adres van een bezoeker wordt bewaard | Het wordt gehasht voordat het teller wordt, en er is geen tabel met een adresveld |
| De volledige postcode bereikt de dienst | De serializer weigert alles wat geen vier cijfers is, in plaats van af te kappen |
| Een back-upbestand lekt | `0600` in een map `0700`, ten hoogste acht bestanden, en de deploy weigert door te gaan als een van beide ruimer staat |
| Verwijderde gegevens leven voort in een back-up | Ten hoogste acht dagen, en de dagelijkse opruiming haalt herleefde rijen na een terugzetting weer weg |
| De opruiming stopt zonder dat iemand het merkt | De deploy draait een controle die rood wordt zodra er iets over datum is, en de timer zelf faalt zichtbaar |
| Een derde partij krijgt het surfgedrag van de bezoeker | Geen enkel verzoek buiten de eigen oorsprong, afgedwongen door een test |
| Een gemeten kwartierreeks bereikt iemand aan wie de link is doorgestuurd | Het veld `year` draagt zijn herkomst mee, en de enige functie die het kan opbouwen weigert een gemeten reeks achter een deelbaar token. Vandaag bestaat er nog geen gemeten reeks |
| Het token staat in het pad van elk verzoek en is dus leesbaar voor Cloudflare | Niets structureels. Het token hoort in het pad, en Cloudflare beeindigt TLS aan de rand, dus het pad is daar leesbaar. Wat het begrenst is dat de link na negentig dagen verloopt. De oplossing staat onder deze tabel en is niet gebouwd |
| Het advies wordt gestuurd door een commercieel belang | Geen advertenties, geen leads, geen eigen contract en geen hardwareverkoop. Elke regel die vuurt komt terug in het antwoord, dus een advies is na te lopen |

**Wat hier niet tegen staat.** Er is geen kopie buiten de host, dus een storing
die de machine meeneemt neemt de gegevens en de back-ups mee. Dat is een
beschikbaarheidsrisico en geen vertrouwelijkheidsrisico, en het is opgeschreven
in hoofdstuk 8 van `infra/README.md` in plaats van hier opgelost.

**De oplossing voor de regel over Cloudflare, en waarom die er nog niet is.** Het
token hoeft niet in het pad te staan. Een URL-fragment wordt door geen enkele
browser naar een server gestuurd, dus `/advies/#<token>` blijft in de browser, en
het token kan daarna in een `Authorization`-header naar de API. Dan leest
Cloudflare het niet meer. Dat is ook wat OWASP ASVS v5.0.0 in 14.2.1 op niveau 1
eist: "the URL and query string do not contain sensitive information, such as an
API key or session token". Het ontwerp van vandaag voldoet daar niet aan.

Dat is in deze wijziging niet gedaan, en de kosten zijn de reden om het apart te
doen. `frontend/src/lib/api.ts` bouwt vandaag `/api/advice/<token>/` en zou een
header moeten sturen; de route onder `frontend/src/app/advies/` leest het token
uit het pad en zou het uit het fragment moeten lezen; en de API zou de header
naast de padvorm moeten aannemen zolang er links van voor de wijziging rondgaan.
Die links leven negentig dagen, dus de padvorm kan niet in een keer weg. Zolang
dat niet is gebeurd, staat de regel hierboven in de tabel zonder iets ernaast.

## 9. Wat er is veranderd bij fase 1, en wat fase 2 nog brengt

Dit document beschreef fase 0.5 en is voor fase 1 herschreven: de hoofdstukken
2, 4, 7 en 10 hierboven beschrijven de accountlaag zoals hij nu draait, niet
zoals hij ooit zou gaan draaien. Op die vier punten is dit hoofdstuk dus geen
vooruitblik meer. Op een vijfde punt is het dat nog wel.

**Wat fase 1 heeft gebracht.**

- **Accounts.** Een e-mailadres, een wachtwoordhash, inlogpogingen, en de
  gebeurtenissen die het auditlogboek er sinds hoofdstuk 2 bij heeft. De
  rekenmachine zelf blijft anoniem: een account bestaat naast een advies, niet
  ervoor.
- **Twee aparte toestemmingen**, voor datakoppeling en voor leadgeneratie, geen
  van beide voorgevinkt en elk met een eigen tijdstempel: `Consent` in
  `backend/accounts/models.py`.
- **Een export- en verwijderroute**, die nu werken. Hoofdstuk 7 beschrijft wat
  ze doen en voor wie.

**Wat fase 2 nog moet brengen.**

- **Kwartierdata uit de P1-poort.** Dat is de verwerking die hoofdstuk 1 als
  afwezig aanmerkt en die de afweging daar omdraait. Daaruit is af te leiden
  wanneer iemand thuis is. Het veld waarin die reeks het antwoord zou verlaten
  bestaat al, met de weigering erin die hoofdstuk 6 beschrijft, zodat er geen
  periode is waarin de eerste gemeten reeks bestaat en de regel erover nog
  niet.

Zodra die laatste verwerking bestaat, moet dit document opnieuw geschreven
worden, en dan is een beoordeling niet langer waarschijnlijk verplicht maar
zeker verplicht: de kwartierdata is precies wat hoofdstuk 1 als het hoge risico
beschrijft.

## 10. Wat bij Stijn ligt

Vijf dingen kan dit document niet voor de verwerkingsverantwoordelijke
beslissen. Een eerdere vraag, of verwijderen op verzoek mogelijk wordt voor fase
1, is inmiddels beantwoord: ja. `POST /api/auth/delete/` bestaat, hoofdstuk 7
beschrijft wat hij doet, en de vier feiten die deze paragraaf eerder opsomde
zijn opgelost door een account te eisen en het wachtwoord opnieuw te vragen, in
plaats van bezit van het token als autorisatie te accepteren.

1. **Of de conclusie in hoofdstuk 1 wordt overgenomen.** De feiten staan er; de
   afweging of artikel 35 van toepassing is, is zijn oordeel.
2. **De grondslag.** Voorlopig gekozen: **toestemming**, niet uitvoering van
   een overeenkomst. Dat is geen slag om de arm maar een keuze die de code al
   uitvoert: de twee toestemmingen in `Consent` bestaan met een eigen
   tijdstempel en een eigen tekstversie, wat een grondslag van toestemming
   vraagt en een grondslag van overeenkomst niet nodig heeft. Wat daarbij hoort
   staat ook al in de code: registratie wordt niet geweigerd als `METER_LINK`
   wordt onthouden, `RegisterSerializer` accepteert de aanmelding met of zonder
   die toestemming. Dat is precies wat artikel 7 lid 4 AVG eist zodra de
   grondslag toestemming is, namelijk dat een dienst niet afhankelijk mag zijn
   van een toestemming die voor die dienst zelf niet nodig is. Als de
   verwerkingsverantwoordelijke hier alsnog voor overeenkomst kiest, is dat een
   wijziging van dit document en van de privacyverklaring en geen migratie: er
   verandert niets aan `Consent`, aan wat er gevraagd wordt of aan wanneer een
   account werkt. Wat wel verandert is dat artikel 7 lid 4 niet meer van
   toepassing is, want er is dan geen toestemming meer om aan te toetsen.
3. **De back-upruil uit hoofdstuk 4.** Zeven dagen is een keuze die ik heb
   gemaakt en verantwoord; korter maakt de kopie kleiner en het herstel
   krapper, en alleen het auditlogboek dumpen laat de dienst onherstelbaar. Die
   ruil geldt sinds fase 1 net zo goed voor een verwijderd account als voor een
   vervallen advies.
4. **Toegang tot de host**, en of `web2` ephemeer wordt. Die staat los van dit
   document en is elders opgeschreven.
5. **Resend als verwerker.** Drie deelvragen. Of de voorgetekende DPA van
   Resend volstaat als de verwerkersovereenkomst die artikel 28 vraagt, of dat
   er iets naast moet. Of de verzendregio in het dashboard van Resend op de
   EU-regio staat, wat een instelling is die dit document veronderstelt en
   niet kan controleren. En of opslag van het verzendlog in de Verenigde
   Staten, onder SCC's en het Data Privacy Framework, aanvaardbaar is voor deze
   dienst, of dat een Europese aanbieder de volgende backend-aanraking wordt.
   Wat daarbij hoort en niet als zesde punt staat, omdat het dezelfde vraag is
   als punt 2: de grondslag voor het bevestigen van een adres is geen van de
   twee toestemmingen. Dit document zet hem voorlopig op noodzaak voor de
   dienst, want zonder bevestigd adres kan de dienst geen wachtwoord herstellen
   en straks geen meter koppelen.

Er is verder geen privacyverklaring, geen verwerkersregister en geen vastgelegde
verwerkersovereenkomst met Cloudflare en geen beoordeelde met Resend. Alle drie
zijn ze nodig voordat de dienst publiek gaat, en alle drie vallen ze buiten wat
uit deze repository te schrijven is. De verwerkersovereenkomst is wel de enige
van de drie die over een verwerking gaat die vandaag al draait: hoofdstuk 5
beschrijft wat Cloudflare op elk verzoek te zien krijgt en wat Resend per mail
te zien krijgt. Voor het register: Resend, Inc., voor het versturen van
herstel- en bevestigingsmails, ziet e-mailadres en berichtinhoud, bewaart een
verzendlog in de Verenigde Staten, grondslag voor doorgifte SCC's en DPF,
overeenkomst de voorgetekende DPA. Voor de privacyverklaring: dat een account
een adres heeft, dat er mails naar dat adres gaan voor herstel en bevestiging
en nergens anders voor, en dat een derde partij die mails aflevert.
