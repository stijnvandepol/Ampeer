# Ontwerp: de juridische pagina's, het register en de restschuld (fase 1, afronding)

Datum: 2026-09-07
Status: vastgesteld, klaar voor implementatieplan
Betreft: `/privacy/` herschreven voor fase 1, een nieuwe pagina `/voorwaarden/`, het
verwerkingsregister van artikel 30 AVG als document, de open vragen in de DPIA en in
`docs/decisions.md` die nu een antwoord hebben, en de vijf punten code-schuld die de drie
accountcycli hebben opgetekend

## 1. Doel en afbakening

Fase 1 staat op `dev`: een huishouden kan een account aanmaken, inloggen, twee toestemmingen
geven en intrekken, zijn gegevens exporteren, zijn account verwijderen, zijn wachtwoord
herstellen en zijn adres bevestigen. De pagina's die zeggen wat dat allemaal betekent zijn
daar niet in meegegaan. `/privacy/` zegt nog "Er is geen account en er is geen wachtwoord",
"Wij plaatsen geen cookies" en "Er is nog geen knop waarmee u uw advies zelf weggooit", en
sluit af met de belofte dat de pagina opnieuw geschreven wordt zodra er accounts zijn. Die
belofte is verlopen op het moment dat PR #49 werd gemerged.

Dit ontwerp doet vier dingen, en niets daarbuiten.

1. **De privacyverklaring wordt waar tegen fase 1.** Zelfde pagina, zelfde principe, zelfde
   toon; de inhoud volgt de DPIA zoals die nu is.
2. **Er komt een pagina `/voorwaarden/`** met de gebruiksvoorwaarden en de disclaimer over
   het advies. De eigenaar koos een eigen pagina boven een sectie elders, omdat een
   disclaimer die op een methodologiepagina staat er een is die niemand vindt op het moment
   dat hij ertoe doet.
3. **Er komt een verwerkingsregister** als document, `docs/verwerkersregister.md`, met een
   test die het aan de DPIA en de code bindt zoals `tests/test_dpia.py` de DPIA bindt.
4. **De opgetekende code-schuld wordt betaald:** de 401 die DRF's zin geeft in plaats van
   die uit `nl.py`, de begrensde batch voor het mailcommand, drie verouderde zinnen in
   gesloten documenten, branch-dekking met een eigen vloer, en de enumeratie via `register/`
   als vastgelegde beslissing.

Drie feiten van de eigenaar liggen vast en zijn niet opnieuw ter discussie:

- De verwerkingsverantwoordelijke is **Stijn IT, eenmanszaak**, KvK 42015984, met het
  postadres dat `frontend/src/app/privacy/identity.ts` al draagt en `info@ampeer.nl` als
  contactadres. Voor verzoeken over persoonsgegevens komt daar `privacy@ampeer.nl` bij.
- De grondslag voor de accountverwerking is **toestemming**. `identity.ts` zegt sinds
  2026-09-02 "overeenkomst"; de DPIA zegt sinds fase 1 voorlopig toestemming; de code voert
  toestemming uit. De eigenaar heeft op 2026-09-07 voor toestemming gekozen, en daarmee
  vervalt de keuze van 2026-09-02.
- Registreren met een adres dat al een account heeft blijft een 400 met de zin uit `nl.py`.
  De eigenaar heeft gekozen de enumeratie die dat oplevert niet te sluiten; hoofdstuk 7.5
  legt vast waarom, en dat is een beslissing zonder code.

Wat dit ontwerp niet is: geen fase 2, geen werk aan het Resend-account of de host (dat is
van de eigenaar, hoofdstuk 9 van het herstelontwerp), geen nieuwe afhankelijkheid in een van
beide bomen, geen wijziging aan het advies of aan de vragenstroom, en geen wijziging aan
`frontend/src/lib/api.ts`.

## 2. De identiteit

### 2.1 Twee adressen, een grondslag

`frontend/src/app/privacy/identity.ts` is de enige plek waar de site weet wie erachter zit;
`/privacy/` en `/over-ons/` lezen het allebei, zodat de twee pagina's nooit twee entiteiten
kunnen noemen. Het bestand verandert op drie punten.

**`privacyEmail` komt erbij**, verplicht, met dezelfde bewaking als de andere velden. De AVG
geeft een maand om een inzage- of verwijderverzoek te beantwoorden, en het commentaar bij
`contactEmail` zegt zelf wat een algemeen adres kost: een verzoek dat in een gewone inbox
aankomt is er een dat als gewone post gelezen en gelaten wordt. Een eigen adres is de
goedkope oplossing die dat commentaar al noemde. `contactEmail` blijft `info@ampeer.nl` voor
al het andere. Het `Identity`-type, `CompleteIdentity`, `IDENTITY_FIELDS` en
`IDENTITY_FIELD_HELP` krijgen het veld; `IDENTITY_FIELDS` is een geschreven lijst met
`satisfies`, dus een veld dat wel in het type staat en niet in de lijst is een typefout, en
dat blijft zo.

**`legalBasis` wordt `"toestemming"`.** Het commentaar erboven van 2026-09-02 verdedigt
"overeenkomst" met artikel 6 lid 1 sub b en zegt waarom toestemming daar slechter zou zijn.
Dat commentaar wordt vervangen, niet aangevuld, want een pagina die twee redeneringen naast
elkaar draagt zegt niets. De nieuwe tekst zegt: de DPIA kiest in hoofdstuk 10 punt 2 voor
toestemming met het argument van artikel 7 lid 4, namelijk dat `RegisterSerializer` een
aanmelding accepteert met of zonder `METER_LINK` en dat de dienst dus niet afhangt van een
toestemming die hij zelf niet nodig heeft; de code voert dat uit met twee losse, niet
voorgevinkte toestemmingen met eigen tijdstip en eigen tekstversie; de eigenaar heeft de
keuze op 2026-09-07 bevestigd. Wat het kost staat er ook: toestemming moet even makkelijk in
te trekken zijn als te geven, en voor het account is intrekken gelijk aan verwijderen, wat de
knop op `/account/` doet.

**De bewaking verandert niet van vorm.** `missingIdentityFields` en `requireCompleteIdentity`
blijven wat ze zijn; het nieuwe veld doet mee in `isUnfilled` op dezelfde manier als
`contactEmail`. De bouw blijft de poort: een pagina die een leeg veld zou tonen, bouwt niet.

### 2.2 De test die nu niets test

`frontend/tests/app/LegalPages.test.tsx` opent met "ships with every fact still unfilled, and
says which", een lus over `missingIdentityFields(IDENTITY)` die asserteert dat elk ontbrekend
veld de sentinel draagt. Sinds 2026-09-03 is die lijst leeg en draait de test nul asserties.
Dat is de vorm die de rode-proefregel verbiedt: een controle die groen leest omdat hij niets
leest.

Hij wordt omgedraaid naar wat vandaag waar is: `missingIdentityFields(IDENTITY)` is leeg, en
`IDENTITY` noemt beide adressen, `info@ampeer.nl` en `privacy@ampeer.nl`, met de grondslag
`toestemming`. Rood bewijs: zet `privacyEmail` tijdelijk op `NOG_IN_TE_VULLEN`; de test
noemt het veld; zet terug. De test op `:171-205` die `out/` afloopt op de sentinel blijft
staan.

## 3. De privacyverklaring, herschreven

### 3.1 Wat blijft

Drie principes uit de docstring van `frontend/src/app/privacy/page.tsx` blijven de wet van
de pagina, en de herschrijving mag er niet van afwijken.

- **Gebouwd uit `docs/dpia.md` en nergens anders uit.** Elk getal op de pagina is er een dat
  de DPIA uit de code heeft gemeten. De pagina noemt geen bewaartermijn, geen aantal en geen
  partij die niet in de DPIA staat.
- **Tien tot vijftien woorden per zin.** De rest van de site zit op negentien tot
  drieëntwintig; dit is de pagina met de breedste lezerskring en de minst gemotiveerde lezer.
  Elke zin die een bijzin nodig had, wordt gesplitst.
- **Wat de pagina niet zegt, zegt hij niet.** Geen doorgiftemechanisme voor Cloudflare, geen
  functionaris gegevensbescherming en geen verwerkersovereenkomst met Cloudflare, want deze
  repository weet van geen van de drie. Voor Resend ligt dat anders, en hoofdstuk 3.3 zegt
  precies wat er wel bekend is.

De sectievolgorde blijft: wie verantwoordelijk is, wat wij vragen, de postcode, waarom,
de grondslag, wat wij bewaren en hoe lang, het logboek, het IP-adres, de verwerkers, wat er
niet naar buiten gaat, cookies, uw rechten, de toezichthouder, over deze verklaring. Wat
verandert is de inhoud van acht secties, hieronder per sectie, en er komt één sectie bij
over het account.

### 3.2 Per sectie, wat er anders komt te staan

**Wie verantwoordelijk is.** De `<dl>` krijgt een tweede e-mailrij: het adres voor vragen
over uw gegevens (`privacyEmail`) naast het algemene adres (`contactEmail`). De inleidende
zin wijst naar het eerste. Naam, KvK-nummer en postadres blijven uit `identity`.

**Wat wij van u vragen.** De alinea "Wij vragen geen naam, geen e-mailadres en geen
telefoonnummer. Wij vragen ook geen huisnummer. Er is geen account en er is geen wachtwoord."
wordt: voor het advies vragen wij nog steeds geen van die dingen, en de rekenmachine werkt
zonder account. Wie een account aanmaakt, geeft een e-mailadres en kiest een wachtwoord, en
meer niet. Geen naam, geen telefoonnummer, geen huisnummer.

**Nieuw: uw account.** Een eigen sectie, tussen de grondslag en de bewaartermijnen. Uit
DPIA hoofdstuk 2: het wachtwoord wordt met Argon2id onleesbaar gemaakt voordat het de
database bereikt, wij kunnen het niet lezen en niet teruggeven; wij bewaren het tijdstip van
uw laatste inlog; wij bewaren het tijdstip waarop u uw adres bevestigde, en dat veld is leeg
zolang u dat niet deed. Een bevestigd adres is straks nodig om een slimme meter te koppelen;
vandaag is het nergens voor nodig. De twee toestemmingen op uw accountpagina zijn losse
keuzes; wij zetten er nooit een vooraf aan; elke keuze bewaren wij met tijdstip en de versie
van de tekst die u toen las, en intrekken kost één klik. Herstel en bevestiging gaan per
mail met een link die één uur (herstel) of zeven dagen (bevestiging) werkt en één keer.

**Op welke grondslag wij dit doen.** `<LegalBasisParagraphs>` blijft de plek en de tak
`toestemming` wordt de tak die rendert. De twee bestaande alinea's van die tak gaan over het
advies (toestemming door de vragen in te vullen en op berekenen te klikken; intrekken met de
link erbij) en blijven staan. Er komen twee alinea's bij over het account: uw account
verwerken wij met uw toestemming, en die geeft u door het aan te maken; intrekken doet u
door het te verwijderen, en dat kan altijd, zonder ons iets te vragen. Voor doorgeven aan
een installateur en voor het koppelen van uw meter vragen wij elk apart toestemming. De tak
`overeenkomst` blijft in de code staan, want `identity.legalBasis` kan die waarde dragen en
de test rendert beide takken één keer; er verandert niets aan die tekst.

**Wat wij bewaren, en hoe lang.** De bestaande alinea's over de link en de 90 dagen (uit
`AMPEER_ADVICE_TTL_DAYS`, gelezen door de test) en de reservekopie van zeven dagen blijven.
Erbij, uit DPIA hoofdstuk 2 en 4, in gewone woorden: uw account bewaren wij tot u het
verwijdert; een herstel- of bevestigingslink bewaren wij als onomkeerbare afdruk tot hij
verloopt; een mail die wij nog moeten versturen staat in een wachtrij zonder uw adres erin
en verdwijnt zodra hij weg is, of zeven dagen nadat het versturen definitief mislukte. Een
verwijderd account kan net als een verwijderd advies nog hoogstens acht dagen in een
reservekopie staan.

**Wat er in ons logboek komt.** De alinea over de ene regel per advies blijft. Erbij: sinds
er accounts zijn schrijven wij ook een regel bij het aanmaken, inloggen, mislukt inloggen,
uitloggen, geven of intrekken van een toestemming, exporteren, verwijderen, aanvragen en
afronden van een herstel, bevestigen van een adres en versturen van een mail. Dertien
soorten. In die regels staat een nummer dat naar uw account wijst en nooit uw e-mailadres;
na verwijdering wijst dat nummer nergens meer naar. Bij een herstelverzoek voor een adres
dat wij niet kennen schrijven wij niets. De DPIA-zin dat dit logboek nooit wordt opgeruimd
blijft staan.

**Uw IP-adres bewaren wij niet.** De tekst blijft, met één toevoeging die de DPIA op
hoofdstuk 2 heeft gemeten: een hulpprogramma tegen inbrekers brengt drie tabellen mee die
een IP-adres zouden kunnen bevatten, en die blijven leeg omdat wij het tellen in het
geheugen doen. Gemeten: na zes mislukte inlogpogingen staan alle drie op nul rijen.

**Cloudflare ziet uw verzoek langskomen.** De sectie blijft. De laatste alinea, dat de link
in het webadres bij Cloudflare zichtbaar is en dat de oplossing nog niet gebouwd is, blijft
waar voor de advieslink en wordt zo gelaten.

**Nieuw: Resend verstuurt onze mail.** Direct na Cloudflare, uit DPIA hoofdstuk 5. Wij
sturen alleen mail om een wachtwoord te herstellen of een adres te bevestigen, nergens
anders voor. Die mail vertrekt via Resend, Inc., onze tweede verwerker. Resend ziet uw
adres, dat er een account bij hoort of dat er herstel is gevraagd, en de tekst van de mail
met de link erin. Resend bewaart een eigen verzendlog met adres, onderwerp en tekst, en dat
log staat in de Verenigde Staten, ook al versturen wij vanuit de Europese regio. Die
doorgifte rust op de standaardbepalingen van de Europese Commissie in Resends
verwerkersovereenkomst en op Resends certificering onder het Data Privacy Framework. Wat
Resend niet ziet: waarom u herstel vroeg, uw wachtwoord, uw toestemmingen of uw advies.

**Verder gaat er niets naar buiten.** De lijst blijft; de zin "Dit is geen belofte maar een
test" blijft, en de test die hem waarmaakt gaat vanaf deze cyclus ook over deze pagina
(hoofdstuk 4.4).

**Cookies.** De sectie "Cookies zetten wij niet" wordt "Drie cookies, en geen enkele om u
te volgen". Uit DPIA hoofdstuk 2 en `backend/accounts/cookies.py`: zonder account zetten wij
geen cookie. Logt u in, dan zetten wij twee cookies die uw sessie zijn, een voor een
kwartier en een voor veertien dagen, en een derde die de pagina beschermt tegen verzoeken
die niet van u komen. Alle drie zijn ze nodig om ingelogd te zijn en voor niets anders. Ze
volgen u niet, ze meten niets en ze gaan naar geen ander bedrijf. Daarom is er geen
cookiemelding: de wet vraagt geen toestemming voor cookies die alleen doen wat u zelf vroeg.
Uw antwoorden op de vragen staan in de opslag van uw eigen browser en verlaten die niet; uw
keuze voor licht of donker ook.

**Wat u met uw gegevens kunt.** De vier kopjes blijven en krijgen elk een tweede alinea voor
het account, uit DPIA hoofdstuk 7. *Inzien:* op uw accountpagina staat uw adres en de stand
van beide toestemmingen; de knop exporteren geeft alles wat wij over uw account hebben, als
bestand dat een computer kan lezen. *Meenemen:* dat bestand is de overdracht. *Corrigeren:*
een verkeerd antwoord kunt u niet wijzigen, wel opnieuw rekenen; een toestemming kunt u
altijd omzetten, en wij bewaren de oude keuze naast de nieuwe. *Laten verwijderen:* "Er is
nog geen knop" verdwijnt. Op uw accountpagina staat een knop die uw account verwijdert; hij
vraagt uw wachtwoord opnieuw. Weg zijn dan uw adres, uw wachtwoord, beide toestemmingen en
alle adviezen die aan uw account hingen; wat blijft is een logregel met een nummer dat
nergens meer naar wijst. Bent u uw wachtwoord kwijt, dan herstelt u het eerst via de mail
en verwijdert u daarna. *Bezwaar maken* blijft, met `privacyEmail` als adres.

**Klagen kan bij de toezichthouder.** Blijft, met de link naar
`https://www.autoriteitpersoonsgegevens.nl/`, de enige externe link op de pagina.

**Over deze verklaring.** De slotalinea wordt herschreven: deze verklaring hoort bij de
dienst met accounts, herstel en bevestiging, zoals die vandaag draait. Komt er een koppeling
met uw meter, dan verandert er veel en schrijven wij deze pagina opnieuw voordat dat
gebeurt. De verwijzing naar `/over-ons/` en `/methodologie/` blijft; er komt een verwijzing
naar `/voorwaarden/` bij. "Laatst gewijzigd op 7 september 2026."

### 3.3 Wat de pagina over Resend mag zeggen, en waar dat vandaan komt

Drie feiten over Resend staan in de DPIA en komen uit Resends eigen documentatie, gelezen
op 2026-09-06: de regiokeuze bepaalt waar mail vandaan vertrekt en niet waar accountdata,
metadata en logs staan, want die staan in de Verenigde Staten; de doorgifte rust op de
SCC's in Resends DPA en op de certificering onder het EU-US Data Privacy Framework; de DPA
is voorgetekend bij elk account en te downloaden uit het dashboard. De pagina zegt die drie
dingen en niets meer. Of de voorgetekende DPA volstaat als de overeenkomst die artikel 28
vraagt, is punt 5 van DPIA hoofdstuk 10 en blijft bij de eigenaar; de pagina beweert dat
niet.

### 3.4 De tests op de pagina

`frontend/tests/app/LegalPages.test.tsx:222-326` blijft de bewaking, en dit is wat
verandert.

- **Blijft, ongewijzigd:** één `<h1>` "Privacyverklaring", de metadata, de canonical als
  string; de artikel 13-woordenlijst (`verantwoordelijk`, `vier cijfers`, `jaarverbruik`,
  `grondslag`, `werkt de link niet meer`, `Cloudflare`, `verwerker`, `advertenties`,
  `cookies`, `profiel`, `Autoriteit Persoonsgegevens`); de regulatorlink als enige externe
  link; de bewaartermijn gelezen uit `backend/ampeer/settings/base.py`; geen em-dash; geen
  eurobedrag.
- **Verandert van tak:** de test op `:274-281` rendert beide grondslagtakken al; met
  `IDENTITY.legalBasis = "toestemming"` wordt de toestemmingstak de tak die in productie
  rendert. De asserties blijven: de toestemmingstak bevat `uw toestemming intrekken` en niet
  `uitvoering van de overeenkomst`, de andere tak omgekeerd.
- **Komt erbij:** de tekst noemt `Resend`; de tekst noemt `Argon2id`; de tekst noemt de twee
  sessiecookies bij hun functie en zegt `geen cookiemelding`; de tekst bevat het
  privacyadres van de identiteit (`privacyEmail` uit `FILLED`, een tweede sentinel
  `privacy@example.invalid`); de tekst noemt `verwijdert` bij een knop en niet meer `Er is
  nog geen knop`; de tekst noemt `dertien` bij het logboek; de tekst zegt `7 september
  2026`. Elke nieuwe assertie krijgt een rood bewijs door de zin tijdelijk uit de pagina te
  halen.
- **Gaat weg:** niets in de testsuite; de zin "Wij plaatsen geen cookies" verdwijnt uit
  `ui-strings.txt` bij de regeneratie, en de test die `cookies` als woord eist blijft waar
  omdat de nieuwe sectie het woord draagt.

## 4. `/voorwaarden/`

### 4.1 De route

`frontend/src/app/voorwaarden/page.tsx`, een servercomponent zoals `/privacy/` en
`/over-ons/`, met `metadata`: `title: "Gebruiksvoorwaarden"`, een `description` van meer dan
vijftig tekens, `alternates: { canonical: "/voorwaarden/" }`, geen `openGraph` om de reden
die `privacy/page.tsx` geeft (de samenvoeging is ondiep). De pagina wordt geïndexeerd en
komt in `SITEMAP_ROUTES` in `frontend/src/app/_shell/site.ts` met `changeFrequency:
"yearly"` en `priority: 0.3`, dezelfde waarden als `/privacy/`. Hij importeert
`legal.module.css` uit `../privacy/` zoals `/over-ons/` dat doet, en roept
`requireCompleteIdentity(IDENTITY)` aan, want hij noemt de entiteit en de twee adressen. De
identiteitstest op `:141-157` die de twee pagina's op die aanroep leest, gaat over drie
pagina's.

### 4.2 De secties, in deze volgorde

De volgorde volgt het principe van `/over-ons/`: eerst wat de lezer moet weten voordat hij
op het advies vertrouwt, dan wie wij zijn, dan de regels. Een pagina die met de regels
begint heeft de disclaimer begraven.

1. **Wat Ampeer is.** Een rekenmachine die met uw antwoorden en met standaardprofielen
   uitrekent wat het einde van de salderingsregeling u kost en welke van drie routes het
   beste past. Elk bedrag komt met een bandbreedte, want wij rekenen de hele berekening
   243 keer door met de aannames die wij niet zeker weten; het woord bij het advies
   ("indicatief", "goed", "precies") zegt hoeveel u ons verteld hebt. "Precies" kunt u
   vandaag niet krijgen. Dit is de samenvatting van `docs/methodologie.md` hoofdstuk 9 en
   18, en de pagina verwijst ernaar in plaats van het na te vertellen.
2. **Wat Ampeer niet is.** Geen financieel advies, geen installatieadvies, geen advies
   over een energiecontract. De getallen zijn een schatting op een verzonnen jaar met
   standaardprofielen; uw dak, uw apparaten en het tarief van 2027 kennen wij niet
   (hoofdstuk 19 van de methodologie somt op wat wij niet weten). U beslist zelf, en een
   beslissing over een batterij of panelen is er een die u met een offerte in de hand neemt
   en niet met dit scherm.
3. **Waarvan Ampeer betaald wordt.** De alinea van `/over-ons/` in dezelfde woorden: wij
   verkopen geen panelen, geen batterijen en geen energiecontract en plaatsen geen
   advertenties; niemand betaalt ons voor de uitkomst die u krijgt; vandaag verdienen wij
   niets aan uw advies; verandert dat, dan staat het hier en op `/over-ons/` voordat het
   gebeurt; gaat Ampeer ooit doorverwijzen, dan vragen wij daar apart toestemming voor en
   uw advies verandert er niet door. De regel uit `CLAUDE.md` geldt: de pagina beweert niet
   dat er nooit geld verdiend wordt.
4. **Uw account.** Eén account per e-mailadres. U kiest en bewaart uw wachtwoord; wij kunnen
   het niet lezen en geven het niet terug; kwijt is herstellen via de mail. Verwijderen is
   definitief en doet u zelf, met uw wachtwoord erbij. Wat een account vandaag doet
   (toestemmingen bewaren, exporteren) en wat het straks kan (een meter koppelen, met een
   bevestigd adres) staat er in twee zinnen.
5. **Waarvoor wij niet instaan.** In gewone woorden en zonder juridisch register: de
   uitkomst is een schatting en geen belofte; wij zijn niet aansprakelijk voor een
   beslissing die u op die schatting neemt, voor zover de wet ons toestaat dat uit te
   sluiten; de dienst kan er even niet zijn en wij beloven geen beschikbaarheid. Geen
   bedrag, geen plafond, geen verwijzing naar een wetsartikel op het scherm.
6. **Wat wij van u vragen.** Gebruik de dienst voor uw eigen huishouden of voor iemand die
   u daarom vroeg; probeer niet in te breken, te overbelasten of om de tempolimieten heen te
   werken; maak geen account op een adres dat niet van u is. Meer regels zijn er niet.
7. **Recht en klachten.** Nederlands recht. Een klacht over de dienst gaat naar
   `contactEmail`; een vraag of klacht over uw gegevens naar `privacyEmail`; over uw
   gegevens kunt u ook bij de Autoriteit Persoonsgegevens terecht, met dezelfde link als op
   `/privacy/`, en dat is de enige externe link op deze pagina.
8. **Over deze voorwaarden.** Een wijziging komt op deze pagina te staan met een nieuwe
   datum, en een wijziging die u iets kost komt er te staan voordat hij ingaat. Verwijzing
   naar `/privacy/`, `/over-ons/` en `/methodologie/`. "Laatst gewijzigd op 7 september
   2026."

De vijf regels van `frontend/CLAUDE.md` gelden: geen aftelklok, geen schaarste, geen
sociale bewijsvoering, en geen oproep tot actie, want een derde oproep maakt van een
disclaimer een trechter. Register "u" (beslissing 1), geen em-dash, geen eurobedrag.

### 4.3 De voettekst, de sitemap en de twee routelijsten

`frontend/src/app/_shell/SiteFooter.tsx` krijgt een vijfde link, "Voorwaarden" naar
`/voorwaarden/`, tussen "Privacy" en "Account". `frontend/tests/app/LegalPages.test.tsx:454`
gaat van `toHaveLength(4)` naar `toHaveLength(5)` en het commentaar erboven zegt waarom
vijf: de vijfde is de pagina die zegt waarvoor wij niet instaan, en zij staat naast de
pagina die zegt wat wij bewaren omdat een lezer die de ene zoekt de andere ook nodig heeft.
De assertie dat er geen `https?:`-href in de voettekst staat blijft.

`/over-ons/` krijgt een verwijzing naar `/voorwaarden/` naast die naar `/privacy/` in de
slotsectie "Wat wij met uw gegevens doen"; de test op "at least one `/over-ons/` link" op de
privacypagina blijft, en de privacypagina krijgt de omgekeerde verwijzing.

De twee handgeschreven routelijsten in de e2e-specs zijn vandaag onvolledig, en dat is een
gat dat groter is dan deze pagina: `frontend/e2e/privacy.spec.ts` (`PAGES`, vijf routes,
`toHaveLength(5)`) mist `/privacy/` en `/over-ons/`, dus de sweep die belooft dat geen
pagina een verzoek naar een ander bedrijf doet laadt juist de twee pagina's niet die dat
beloven. `frontend/e2e/rules.spec.ts` (`ALL_PATHS`, "Every route the site has", vijf routes)
mist `/over-ons/`, `/privacy/` en `/account/`. Beide lijsten worden compleet: elke route die
`frontend/src/app/` heeft, plus de advieslink, en `/voorwaarden/`. De lengte-asserties gaan
mee met een commentaar dat zegt dat een route die ontbreekt een bevinding is. Een test die
de twee lijsten naast `SITEMAP_ROUTES` en de routeboom legt, zodat een zesde route nooit
stil ontbreekt, komt in `frontend/tests/app/LegalPages.test.tsx`: elke map onder
`src/app/` zonder onderstreep en met een `page.tsx` staat in `ALL_PATHS`, en `/advies/` en
`/account/` zijn de twee bewuste uitzonderingen op de sitemap die de test bij naam noemt.

`frontend/tests/ui-strings.txt` groeit met elke zin van de nieuwe pagina en de herschreven
secties, en verliest de zinnen die verdwijnen. De regel van ruling 73 uit de herstelcyclus
geldt: regenereren, de diff lezen, elke toegevoegde regel is een zin die deze cyclus schreef
of een element-id-kop, en de taalspec moet daarna op eigen kracht slagen.

### 4.4 Toegankelijkheid

Dezelfde regels als `/privacy/`: één `<h1>`, koppen in volgorde, de `<dl>` voor de
identiteit, geen tekst als afbeelding, axe schoon in beide paletten met `wcag2a`, `wcag2aa`
en `wcag22aa`. De e2e-spec die axe over de routes draait krijgt `/voorwaarden/` erbij.

## 5. Het verwerkingsregister

### 5.1 Waarom een document, en waarom nu

Artikel 30 AVG vraagt van elke verwerkingsverantwoordelijke een register van
verwerkingsactiviteiten. De DPIA beschrijft elke verwerking al, maar in de vorm van een
beoordeling en niet in de vorm van een register, en hoofdstuk 10 van de DPIA zegt sinds
fase 1 dat er geen register is. Alles wat een register moet bevatten staat in deze
repository; het document is dus te schrijven, en de belofte dat het buiten de repository
valt was te ruim.

`docs/verwerkersregister.md`, Nederlands, geen em-dash, genummerde hoofdstukken zoals de
DPIA, en een test die het bindt zoals `tests/test_dpia.py` de DPIA bindt.

### 5.2 De inhoud

**Hoofdstuk 0, de verantwoordelijke.** Stijn IT, eenmanszaak; KvK 42015984; het postadres;
`info@ampeer.nl`; `privacy@ampeer.nl` voor verzoeken over persoonsgegevens; geen
functionaris gegevensbescherming en geen vertegenwoordiger, want geen van beide is
verplicht voor deze verwerking en er is er geen.

**Hoofdstuk 1 tot en met 7, één verwerking per hoofdstuk**, elk met dezelfde acht kopjes:
doel, betrokkenen, categorieën gegevens, grondslag, ontvangers, doorgifte buiten de EER,
bewaartermijn, maatregelen.

1. **Het advies.** Doel: uitrekenen wat het einde van saldering een huishouden kost.
   Betrokkenen: bezoekers. Gegevens: de vijf antwoorden uit de eerste ronde en de acht uit
   de tweede (DPIA hoofdstuk 2), het advies, een token van 22 tekens. Grondslag: toestemming
   door te rekenen. Ontvangers: Cloudflare Inc. als verwerker voor al het verkeer.
   Doorgifte: geen door Ampeer; Cloudflare beëindigt de verbinding aan zijn rand. Bewaring:
   90 dagen, dagelijks opgeruimd; reservekopie zeven dagen. Maatregelen: postcode op vier
   cijfers geweigerd in plaats van afgekapt, het token nooit in een log, tempolimiet per
   gehasht IP-adres.
2. **Het account.** Gegevens: e-mailadres, wachtwoord als Argon2id-hash, tijdstip laatste
   inlog, tijdstip bevestiging. Grondslag: toestemming, gegeven door registratie (DPIA
   hoofdstuk 10 punt 2). Bewaring: tot verwijdering; reservekopie zeven dagen.
   Maatregelen: Argon2id, httpOnly-cookies met SameSite=Strict, refresh-tokens als digest,
   inbraakbeveiliging in het geheugen zonder IP-tabel, wachtwoord opnieuw gevraagd bij
   verwijderen.
3. **De toestemmingen.** Gegevens: soort, handeling, tijdstip, tekstversie, per rij.
   Grondslag: toestemming (dit is de toestemming zelf). Bewaring: tot verwijdering van het
   account; elke rij blijft, intrekken is een nieuwe rij.
4. **Herstel en bevestiging per mail.** Gegevens: het e-mailadres, de soort mail, de
   afdruk van een link. Grondslag: noodzaak voor de dienst (DPIA hoofdstuk 10, bij punt 5:
   zonder bevestigd adres geen herstel en straks geen meter). Ontvangers: Resend, Inc. als
   verwerker. Doorgifte: Verenigde Staten, onder de SCC's in Resends DPA en het Data Privacy
   Framework; verzendregio EU. Bewaring: de afdruk tot de link verloopt (één uur of zeven
   dagen); de wachtrij-rij tot verzending of zeven dagen na definitief mislukken; Resends
   eigen verzendlog volgens Resends termijn. Maatregelen: het token alleen als sha256 in de
   database, aangemaakt op het moment van versturen, één keer bruikbaar; geen adres in de
   wachtrij; één module die naar buiten mag en een test die dat afdwingt.
5. **Het auditlogboek.** Gegevens: soort handeling, tijdstip, een accountnummer of niets,
   de afdruk van een advieslink, postcodegebied, versienummers; nooit een adres.
   Grondslag: gerechtvaardigd belang van de verantwoordelijke bij een controleerbaar
   systeem, en artikel 5 lid 2 (verantwoordingsplicht). Bewaring: geen opruiming; het
   nummer wijst na verwijdering nergens meer naar. Maatregelen: alleen toevoegen, nooit
   wijzigen of verwijderen; een test die de soorten aan de DPIA bindt.
6. **De tempolimiet.** Gegevens: een teller per gehasht IP-adres in het geheugen.
   Grondslag: gerechtvaardigd belang (misbruik tegengaan). Bewaring: een uur, in het
   geheugen, nooit in een tabel. Maatregelen: HMAC onder de geheime sleutel; de drie
   axes-tabellen blijven leeg, gemeten.
7. **De reservekopieën.** Gegevens: een dump van de hele database. Grondslag: dezelfde
   als de verwerkingen die erin staan. Bewaring: zeven dagen, dus een verwijderd gegeven
   hoogstens acht. Maatregelen: bestanden `0600` in een map `0700`, dagelijks, en de deploy
   weigert een kopie gezond te noemen die breder leesbaar is.

**Hoofdstuk 8, de verwerkers.** Twee rijen: Cloudflare Inc. (al het verkeer; ziet IP-adres
en pad; verwerkersovereenkomst: de standaardovereenkomst bij het account, aanvaarding niet
vastgelegd, bij de eigenaar) en Resend, Inc. (herstel- en bevestigingsmail; ziet adres en
inhoud; verwerkersovereenkomst: de voorgetekende DPA, beoordeling bij de eigenaar). Geen
derde.

**Hoofdstuk 9, wat er verandert bij fase 2.** Eén alinea: zodra kwartierdata binnenkomt is
er een achtste verwerking, met een eigen bewaartermijn van 90 dagen ruw en daarna alleen
uuraggregaten, en dan wordt dit register herschreven samen met de DPIA.

### 5.3 De test: `tests/test_verwerkersregister.py`

Dezelfde vorm als `tests/test_dpia.py`: het document wordt gelezen als tekst, en elke
bewering die aan de code te toetsen is, wordt getoetst.

- `test_the_register_names_every_table_the_service_has`: elke modelklasse in
  `backend/accounts/models.py` en `backend/advice/models.py` (gelezen met `ast`, zoals
  `test_no_table_has_a_column_for_an_address`) komt bij naam voor in het register.
  Rood bewijs: haal `OutboundMail` tijdelijk uit het document.
- `test_the_register_names_both_processors_and_no_third`: `Cloudflare` en `Resend` komen
  voor; de hosts in `OUTBOUND_MODULES` van `tests/test_boundaries.py` zijn de enige externe
  bestemmingen die het register mag noemen naast Cloudflare, en `energiedatawijzer.nl` is
  daar de bewuste uitzondering op (een handmatige ingest, geen verwerking van
  persoonsgegevens), bij naam in de test.
- `test_the_register_quotes_the_retention_the_service_applies`: `AMPEER_ADVICE_TTL_DAYS` uit
  `base.py` en `KEEP_DAYS` uit `scripts/backup_db.sh` staan als getal in het register, op
  de manier waarop `test_dpia.py` ze leest; de tokentermijnen uit `backend/accounts/recovery.py`
  ("een uur", "zeven dagen") en de outbox-termijn uit `purge_expired_sessions.py`.
- `test_the_register_counts_the_audit_kinds`: het Nederlandse telwoord bij het logboek is
  het aantal constanten op `AuditEvent`, met `_DUTCH_NUMERALS` uit `test_dpia.py`
  geïmporteerd en niet gekopieerd.
- `test_the_register_carries_no_em_dashes`, `test_every_section_is_numbered_consecutively`:
  dezelfde twee als de DPIA heeft.
- `test_the_register_names_the_controller_the_site_names`: de KvK `42015984` en beide
  adressen komen voor, en zijn gelijk aan wat `frontend/src/app/privacy/identity.ts` draagt
  (gelezen met een regex over de drie regels).
- `test_the_dpia_no_longer_says_there_is_no_register`: `docs/dpia.md` bevat niet meer de
  zin "geen verwerkersregister" en verwijst naar het bestand.

Elke test met een rood bewijs door een tijdelijke bewerking van het document, met de hand
teruggezet.

## 6. DPIA en beslissingen

### 6.1 `docs/dpia.md`

**Hoofdstuk 10, punt 2**, wordt in de tekst beantwoord op de manier waarop het verwijderpunt
eerder is beantwoord: het punt blijft staan, opent met "Beantwoord op 2026-09-07:
toestemming.", en zegt in twee zinnen wat daaruit volgt (de privacyverklaring beschrijft het
zo; `identity.ts` draagt het; de keuze van 2026-09-02 voor overeenkomst is daarmee vervallen).
Het aantal genummerde punten blijft vijf en het openingswoord "Vijf" blijft, want
`tests/test_dpia.py` telt de punten en beantwoorde punten blijven op de lijst.

**De slotalinea van hoofdstuk 10** ("Er is verder geen privacyverklaring, geen
verwerkersregister en geen vastgelegde verwerkersovereenkomst...") wordt herschreven: er is
een privacyverklaring op `/privacy/`, herschreven op 2026-09-07 voor fase 1; er is een
register in `docs/verwerkersregister.md`, gebonden door `tests/test_verwerkersregister.py`;
wat er niet is en bij de eigenaar blijft, is de vastgelegde aanvaarding van Cloudflares
verwerkersovereenkomst en de beoordeling van Resends DPA (punt 5). De instructies "Voor het
register: ..." en "Voor de privacyverklaring: ..." verdwijnen, want ze zijn uitgevoerd.

**Hoofdstuk 5** krijgt één verwijzing naar het register bij de twee verwerkers.

`tests/test_dpia.py` krijgt één test erbij:
`test_the_document_points_at_the_register_and_the_statement`, die de twee verwijzingen
leest.

### 6.2 `docs/decisions.md`

Zeven entries, 49 tot en met 55, Engels, met **Decided / Because / Lives in / To reverse**:

49. The legal basis for the account is consent, and the 2026-09-02 choice for a contract is
    reversed.
50. The site has a terms page, and it carries the disclaimer the advice needs.
51. The article 30 register is a document in this repository, bound by a test.
52. A 401 on `/api/auth/` answers in Dutch from this project's own table, like the 429.
53. The outbox command sends at most fifty mails per run.
54. Branch coverage is on, with a floor measured under it.
55. Registration says when an address is taken, and the reset route does not; recorded as a
    choice.

**"What was not decided here"**: de openingsalinea noemt vijf punten bij de eigenaar en
"the legal basis" is er een van; die wordt beantwoord in de tekst zoals het verwijderpunt
("answered rather than dropped"), het aantal blijft vijf omdat punt 5 (Resend) er sinds de
herstelcyclus bij is en punt 2 als beantwoord blijft staan. Het punt `branch = true` wordt
beantwoord in de tekst (beslissing 54). De zin "Nine sit outside that document" wordt
opnieuw geteld nadat het `branch`-punt beantwoord is en het aantal wordt het getelde aantal.
`tests/test_decisions.py` eist dat elk pad achter "Lives in" bestaat en elk symbool in die
bestanden voorkomt; de zeven entries noemen alleen bestaande paden.

## 7. De code-restpunten

### 7.1 De 401 antwoordt uit `nl.py`

`_AuthAPIView` in `backend/accounts/views.py` overschrijft al `throttled` (beslissing 40) en
`get_authenticate_header`, allebei omdat DRF's Nederlandse catalogus niet zegt wat deze API
wil zeggen. De derde hook is `permission_denied`. DRF's eigen versie is:

```text
def permission_denied(self, request, message=None, code=None):
    if request.authenticators and not request.successful_authenticator:
        raise exceptions.NotAuthenticated()
    raise exceptions.PermissionDenied(detail=message, code=code)
```

Zonder cookie geeft dat `NotAuthenticated()` met DRF's standaardzin, in het Nederlands
"Authenticatiegegevens zijn niet opgegeven.", en een 403 zou "Je hebt geen toestemming om
deze actie uit te voeren." geven, in het informele register dat beslissing 1 uitsluit. Geen
test pint DRF's zin; elke stub in de frontend en elke e2e-mock gebruikt al `NL["not_signed_in"]`,
"u bent niet ingelogd". Elke stub is dus in tegenspraak met de echte server, en op de zes
ingelogde routes (`me/`, `consent/`, `logout/`, `export/`, `delete/`, `verify/request/`)
leest een huishouden na een verlopen sessie DRF's zin in het `role="alert"`, want
`describeAuthError` toont een 401 letterlijk (beslissing van het frontend-ontwerp,
hoofdstuk 6).

De override, in dezelfde stijl en op dezelfde plek als `throttled`:

```text
def permission_denied(self, request, message=None, code=None):
    if request.authenticators and not request.successful_authenticator:
        raise NotAuthenticated(NL["not_signed_in"])
    raise PermissionDenied(NL["forbidden"] if message is None else message, code=code)
```

`nl.py` krijgt in de tweede categorie (berichten over de lezer zelf) de sleutel
`"forbidden": "u mag dit niet doen"`. De tak `NotAuthenticated` is de tak die vandaag
bereikt wordt; de tak `PermissionDenied` zonder `message` wordt vandaag door geen route
bereikt (`DeleteView` geeft zijn eigen `PermissionDenied(NL["credentials_invalid"])`) en
krijgt een directe test, zoals de `wait is None`-tak van `throttled` er een kreeg.

Tests in `tests/test_accounts_api.py`: `test_a_stranger_reads_the_projects_own_sentence`
(GET `me/` zonder cookie: 401, body `{"detail": NL["not_signed_in"]}`, en de CSRF-cookie
nog steeds gezet); `test_permission_denied_without_a_message_reads_the_projects_own_sentence`
(directe aanroep op een view-instantie met een geauthenticeerd request); de bestaande
`test_me_answers_401_to_a_stranger_and_still_hands_out_a_csrf_token` blijft. Rood bewijs:
de override tijdelijk verwijderen; de eerste test faalt op DRF's zin. De e2e-mocks en de
Vitest-stubs veranderen niet, want ze droegen de goede zin al; wat verandert is dat ze nu
waar zijn.

### 7.2 Een grens op de batch

`send_outbound_mail` leegt de outbox met `while True` tot `row is None`. Met twee mails per
dag is dat theoretisch, en met een achterstand van honderden rijen houdt één run honderden
keer tien seconden een transactie open. `add_arguments` krijgt `--max`, standaard 50; de lus
in `_deliver` stopt na dat aantal rijen en `handle` schrijft dan
`sent N messages, deferred M, stopped at the cap of K` zodat het journaal het zegt.
`_report_what_is_stuck` blijft ongewijzigd: wat de grens laat liggen wordt na `OVERDUE_AFTER`
gewoon geteld, en dat is precies goed, want een timer die elke minuut vijftig verstuurt en
toch een kwartier achterloopt heeft een probleem dat de check moet zien.

Test in `tests/test_accounts_mail.py`: `test_the_cap_stops_the_run_and_leaves_the_rest_for_the_next_tick`
(drie rijen, `--max 2`, twee verzonden, één blijft met `attempts == 0`, de uitvoer noemt de
grens). De bestaande drierijentest voor de vergiftigde rij blijft groen omdat de standaard
50 is. Rood bewijs: de grens tijdelijk negeren in de lus; de test ziet drie verzonden.
`infra/README.md` sectie 3 krijgt één zin over de grens.

### 7.3 Drie verouderde zinnen

Drie gesloten documenten zeggen dat `localhost:3000` naar `127.0.0.1:8000` cross-site is en
dat `dev.py` daarom cookies toestaat voor drie oorsprongen:
`docs/superpowers/specs/2026-09-04-accounts-auth-design.md:656`,
`docs/superpowers/specs/2026-09-05-accounts-frontend-design.md:101` en
`docs/superpowers/plans/2026-09-04-accounts-auth.md:1138`. Sinds commit `2109901` zegt
`dev.py` het tegendeel: een cookie hoort bij een site, `localhost` en `127.0.0.1` zijn twee
sites, en `localhost:3000` is uit de lijst. Geen test leest de prosa van een spec of een
plan (`tests/test_plans.py` leest alleen Files-blokken; `tests/test_pipeline_contract.py`
alleen paden), dus de correctie kost niets.

De huisstijl voor een gesloten document is een gedateerde correctie en geen herschrijving:
direct onder elke zin komt een alinea "Gecorrigeerd op 2026-09-07: ..." die zegt wat er
fout was (het mechanisme, de oorsprong en het aantal) en waar de waarheid nu staat
(`backend/ampeer/settings/dev.py`, beslissing 104 in het logboek van de herstelcyclus, en
de test in `tests/test_backend_settings.py`). In het plan staat de zin in een codeblok; de
correctie komt als tekst onder het blok en het blok blijft, want een plan is een verslag van
wat er is voorgeschreven.

### 7.4 Branch-dekking, met een eigen vloer

Statement-dekking leest een ternary over meerdere regels als één statement, en dat is hoe
de `wait is None`-tak van `throttled` onzichtbaar bleef tot een reviewer hem met een
scratch-reproductie aanwees. Gemeten op 2026-09-07 met `--cov-branch` op deze machine:
1551 geslaagd, 2757 statements, 23 gemist, 398 branches, 21 deels, 98,61 procent gecombineerd
tegen 99,17 procent statement-only. Zeventien van de 21 halve branches hangen aan een
statement dat zelf niet gedekt is; slechts vier zijn echte branch-gaten waar het statement
draait en één uitgang nooit genomen wordt:

- `ampeer_sim/profiles/assets.py` `52->48`: de `break` op regel 53 als de dagbehoefte al
  gedekt is voordat het laadvenster op is. Test: een dag met een kleine behoefte en een
  grote capaciteit; de posities na de eerste blijven nul.
- `backend/accounts/lockout.py` `64->66`: `if isinstance(value, str)` onwaar, dus een
  `username` die geen string is. Test: `username(request, {"username": 123})` geeft de
  digest van de lege string.
- `backend/accounts/models.py` `102->104`: `if self.email:` onwaar in `User.save`. Test:
  een `User(email="")` die direct wordt opgeslagen normaliseert niets en laat de weigering
  aan `create_user`, die er al een test voor heeft.
- `backend/accounts/views.py` `347->352`: `if raw:` onwaar in `LogoutView.post`, dus
  uitloggen met alleen een access-cookie en geen refresh-cookie. Test: 204 en de auditregel
  `LOGOUT`, zonder dat `tokens.revoke` wordt aangeroepen.

Daarna gaat `branch = true` in `[tool.coverage.run]` in `pyproject.toml`, en de vloer wordt
opnieuw gemeten onder de conditie van de runner: zonder `data/nedu-profiles-2025.csv`, dat
op deze machine `nedu.py:87-95` dekt en op de runner niet (de zes statements die de
statement-vloer van 2751 op 2757 brengen). `fail_under` wordt één honderdste onder het
afgeronde gecombineerde cijfer van die meting, naar verwachting rond 98,5. Het commentaar
boven `fail_under` zegt dat dit een nieuwe maat is (statement plus branch), dat het getal
daarom onder 99,15 komt zonder dat er bescherming verdwijnt, en dat de statement-only
meting op dezelfde boom boven 99,15 blijft; de bestaande alinea in `[tool.coverage.run]` die
zegt dat branch-dekking alleen aan mag samen met een vloer die eronder is gemeten, wordt de
alinea die zegt dat dat op 2026-09-07 is gebeurd. `tests/test_pipeline_contract.py` houdt:
`test_the_coverage_floor_is_not_lowered` eist `fail_under >= 98` (`MINIMUM_COVERAGE_FLOOR`),
`test_the_coverage_comparison_is_not_rounded_away` eist `precision >= 2`, en de omit-lijst
verandert niet. Komt de meting op de runner onder 98 uit, dan stopt de taak en meldt dat:
de vloer gaat niet onder het minimum en de oplossing is dan meer dekking, geen ander
minimum.

### 7.5 Enumeratie via `register/`: een beslissing zonder code

`register/` antwoordt een 400 `{"email": ["er bestaat al een account met dit
e-mailadres"]}` voor een adres dat al een account heeft, en `reset/request/` antwoordt voor
elk adres hetzelfde (beslissing 48). Dat is niet consequent, en de eigenaar heeft gekozen het
zo te laten. De reden, vast te leggen in beslissing 55: registratie logt direct in en toont
de accountweergave, en een antwoord voor een bestaand adres is daar niet identiek aan te
maken zonder de directe inlog op te geven; het sluiten zou elk nieuw huishouden een extra
stap kosten (wachten op een mail voordat het account werkt) en een derde mailsoort vragen;
`auth-register` staat op vijf per uur per beller, wat een adresboek traag maakt; en herstel,
de route waar een aanvaller iets mee kan, is dicht. Wat de beslissing ook zegt: als fase 2
de directe inlog na registratie toch opgeeft (bijvoorbeeld omdat een meter alleen aan een
bevestigd adres mag hangen), is dit het moment om de twee routes gelijk te trekken.

## 8. Testregime

### 8.1 Laag 1: Python

- `tests/test_verwerkersregister.py`, nieuw, de zeven tests uit 5.3.
- `tests/test_dpia.py`: één test erbij (6.1).
- `tests/test_decisions.py`: ongewijzigd, leest de zeven nieuwe entries.
- `tests/test_accounts_api.py`: de twee tests uit 7.1.
- `tests/test_accounts_mail.py`: de test uit 7.2.
- De vier branch-tests uit 7.4: in `tests/test_assets.py` (of het bestand dat
  `ampeer_sim/profiles/assets.py` al test; het plan zoekt het op), `tests/test_accounts_lockout.py`
  (of waar `lockout.username` al getest wordt), `tests/test_accounts_models.py`,
  `tests/test_accounts_api.py`.
- Elke nieuwe test met een rood bewijs; de branch-tests bewijzen rood met de
  `--cov-branch`-uitvoer voor en na (de pijl verdwijnt uit `Missing`).

### 8.2 Laag 2: Vitest

- `frontend/tests/app/LegalPages.test.tsx`: de omgedraaide identiteitstest (2.2); de nieuwe
  asserties op de privacypagina (3.4); een suite voor `/voorwaarden/` naar het model van de
  privacy-suite (één `<h1>` "Gebruiksvoorwaarden", metadata, de woordenlijst `schatting`,
  `bandbreedte`, `geen financieel`, `verkoopt geen`, `Niemand betaalt ons`, `één account`,
  `Nederlands recht`, `Autoriteit Persoonsgegevens`, precies één externe link, geen em-dash,
  geen eurobedrag, `7 september 2026`); de voettekst op vijf; de sitemap met
  `/voorwaarden/`; de routelijsttest (4.3).
- Rood bewijs per nieuwe assertie: de zin tijdelijk uit de pagina; de link tijdelijk uit de
  voettekst.

### 8.3 Laag 3: Playwright

- `frontend/e2e/privacy.spec.ts`: `PAGES` compleet; de sweep laadt `/privacy/`,
  `/over-ons/` en `/voorwaarden/`.
- `frontend/e2e/rules.spec.ts`: `ALL_PATHS` compleet.
- axe op `/voorwaarden/` in beide paletten (de spec die axe over de pagina's draait; het
  plan noemt hem).
- `frontend/e2e/language.spec.ts` groen na de regeneratie.

### 8.4 De poorten

Alle groepen van `scripts/gates.sh` op de eindboom, op exitcode, in de laatste taak; de
Python-vloer gemeten zonder `data/`; de Vitest-vloeren mogen omhoog en niet omlaag.

## 9. Wat expliciet niet in deze cyclus zit

- Fase 2, de meterkoppeling, en alles wat de DPIA in hoofdstuk 9 daarover zegt.
- Het Resend-account, de DNS-records, de host-omgeving en de timer: van de eigenaar.
- De aanvaarding van Cloudflares verwerkersovereenkomst en de beoordeling van Resends DPA:
  DPIA hoofdstuk 10, punt 5 en de slotalinea; van de eigenaar.
- Een cookiemelding: er is geen cookie waarvoor die nodig is.
- Een wijziging aan `register/` (7.5).
- Een analyseprogramma (Umami of Plausible uit `CLAUDE.md`): er is er geen en deze cyclus
  voegt er geen toe; de privacypagina zegt dat er geen is.
- Een nieuwe afhankelijkheid in een van beide bomen.

## 10. Bestanden die veranderen

Nieuw:

| Bestand | Inhoud |
|---|---|
| `frontend/src/app/voorwaarden/page.tsx` | Hoofdstuk 4 |
| `docs/verwerkersregister.md` | Hoofdstuk 5 |
| `tests/test_verwerkersregister.py` | Hoofdstuk 5.3 |
| `docs/superpowers/specs/2026-09-07-legal-and-tidy-design.md` | Dit document |
| `docs/superpowers/plans/2026-09-07-legal-and-tidy.md` | Het plan |

Gewijzigd, frontend:

| Bestand | Wat |
|---|---|
| `frontend/src/app/privacy/identity.ts` | `privacyEmail`; `legalBasis` toestemming; het commentaar |
| `frontend/src/app/privacy/page.tsx` | Hoofdstuk 3 |
| `frontend/src/app/over-ons/page.tsx` | De verwijzing naar `/voorwaarden/` |
| `frontend/src/app/_shell/SiteFooter.tsx` | De vijfde link |
| `frontend/src/app/_shell/site.ts` | `/voorwaarden/` in `SITEMAP_ROUTES` |
| `frontend/tests/app/LegalPages.test.tsx` | Hoofdstuk 2.2, 3.4, 4.3, 8.2 |
| `frontend/tests/ui-strings.txt` | Via de regeneratie |
| `frontend/e2e/privacy.spec.ts` | `PAGES` compleet |
| `frontend/e2e/rules.spec.ts` | `ALL_PATHS` compleet |
| De e2e-spec met de axe-rondes over de pagina's | `/voorwaarden/` erbij |

Gewijzigd, backend en tests:

| Bestand | Wat |
|---|---|
| `backend/accounts/views.py` | `permission_denied` op `_AuthAPIView` |
| `backend/accounts/nl.py` | `forbidden` in de tweede categorie |
| `backend/accounts/management/commands/send_outbound_mail.py` | `--max` |
| `pyproject.toml` | `branch = true`; de vloer; de twee commentaren |
| `tests/test_accounts_api.py` | 7.1, 7.4 |
| `tests/test_accounts_mail.py` | 7.2 |
| `tests/test_accounts_models.py` | 7.4 |
| Het testbestand van `lockout.username` en dat van `assets.py` | 7.4 |
| `tests/test_dpia.py` | 6.1 |

Gewijzigd, documenten:

| Bestand | Wat |
|---|---|
| `docs/dpia.md` | Hoofdstuk 5 en 10 |
| `docs/decisions.md` | Entries 49 tot en met 55; de twee open lijsten |
| `docs/superpowers/specs/2026-09-04-accounts-auth-design.md` | De correctie bij :656 |
| `docs/superpowers/specs/2026-09-05-accounts-frontend-design.md` | De correctie bij :101 |
| `docs/superpowers/plans/2026-09-04-accounts-auth.md` | De correctie bij :1138 |
| `infra/README.md` | De zin over `--max` |

Geen nieuwe afhankelijkheid, in geen van beide bomen.

## 11. Definition of done

- `/privacy/` zegt niets meer dat sinds fase 1 onwaar is: geen "geen account", geen "geen
  cookies", geen "geen knop", Resend genoemd, dertien logsoorten, toestemming als grondslag,
  "7 september 2026"; de tests uit 3.4 zijn groen en elk had een rood.
- `/voorwaarden/` bestaat, staat in de voettekst, in de sitemap en in beide routelijsten,
  is axe-schoon in beide paletten en draagt geen oproep tot actie en geen eurobedrag.
- `docs/verwerkersregister.md` bestaat en `tests/test_verwerkersregister.py` is groen met
  zeven tests die elk rood konden.
- DPIA hoofdstuk 10 punt 2 is beantwoord, de slotalinea is waar, "Vijf" blijft en
  `tests/test_dpia.py` is groen.
- `docs/decisions.md` heeft entries 49 tot en met 55 en `tests/test_decisions.py` is groen.
- Een GET op `me/` zonder cookie antwoordt `{"detail": "u bent niet ingelogd"}`; de e2e-mocks
  zijn daarmee waar.
- `send_outbound_mail` stopt na vijftig rijen en zegt dat.
- De drie verouderde zinnen dragen een gedateerde correctie.
- `branch = true` staat aan, de vier branch-gaten hebben een test, `fail_under` is gemeten
  zonder `data/` en staat op of boven 98; `tests/test_pipeline_contract.py` is groen.
- `identity.ts` noemt beide adressen en toestemming; de omgedraaide test is groen.
- Elke poortgroep van `scripts/gates.sh` exit 0 op de eindboom.

## 12. Beslissingen die dit ontwerp vastlegt

49. The legal basis for the account is consent, and the 2026-09-02 choice for a contract is
    reversed.
50. The site has a terms page, and it carries the disclaimer the advice needs.
51. The article 30 register is a document in this repository, bound by a test.
52. A 401 on `/api/auth/` answers in Dutch from this project's own table, like the 429.
53. The outbox command sends at most fifty mails per run.
54. Branch coverage is on, with a floor measured under it.
55. Registration says when an address is taken, and the reset route does not; recorded as a
    choice.
