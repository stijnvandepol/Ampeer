# Ontwerp: frontend Ampeer (deelproject 4)

Datum: 2026-08-21
Status: vastgesteld, klaar voor implementatieplan
Betreft: `frontend/`, het ontwerpsysteem, en de manier waarop de browser met de adviesAPI praat

## 1. Doel en afbakening

Een bezoeker moet in vier vragen kunnen zien wat het einde van de saldering hem kost,
begrijpen hoe zeker dat antwoord is, en het resultaat kunnen delen.

Binnen scope:

- `frontend/`, Next.js met de App Router, TypeScript in strict mode, Tailwind
- Het ontwerpsysteem: kleur, typografie, ruimte, beweging, en de componenten die het advies tonen
- De vragenstroom van ronde 1 en ronde 2
- De adviespagina en de deelbare link
- Toegankelijkheid en prestatiebudgetten, allebei als poort en niet als voornemen

Buiten scope, eigen deelproject:

- De LXC, de reverse proxy en de deploy (deelproject 2)
- Accounts en meterkoppeling (fase 1 en 2)
- Een dagplan, leads of white-label (later)

## 2. De spanning die dit deelproject moet oplossen

Stijn heeft gevraagd om een UI die "echt over de top" is, aan de nieuwste trends voldoet,
en "visueel en marketing gericht over de top" is. `CLAUDE.md` zegt dat de neutraliteit het
product is, dat er nooit een enkel getal zonder bandbreedte getoond wordt, en dat het
betrouwbaarheidsniveau altijd direct zichtbaar is en niet weggeklikt in een voetnoot.

Die twee lijken tegenover elkaar te staan en dat doen ze ook, als je "marketing" leest
zoals een energieadviseur het meestal doet: een groot vet getal, een gevoel van urgentie,
en een knop die naar een offerte leidt. Dat kan hier niet, en niet omdat het smakeloos is.
Het kan niet omdat het **onwaar** is. Het antwoord van deze motor is een band van 1.395 tot
1.980 euro over 243 doorrekeningen. Eén getal daaruit groot afdrukken is niet een
stijlkeuze, het is de band weggooien, en de band is wat het antwoord eerlijk maakt.

De oplossing is niet een compromis tussen de twee. Het is een herdefinitie van waar het
vakmanschap heen gaat.

**De onzekerheid wordt het hoofdonderwerp van het beeld, niet de voetnoot eronder.**

Elke rekenmachine in deze markt toont één getal en verstopt de marge. Een interface die de
marge tot het centrale visuele object maakt is daarmee vanzelf onderscheidend, want niemand
anders doet het, en hij is tegelijk het eerlijkst mogelijke beeld van wat het model weet.
Dat is waar "over the top" naartoe gaat: naar typografie, beweging, datavisualisatie,
laadsnelheid en toegankelijkheid, en niet naar overreding.

Dat is geen mooie zin maar een lijst regels waaraan de implementatie zich houdt, en vijf
ervan zijn te testen:

1. **Geen enkel getal wordt groter afgebeeld dan zijn eigen band.** Waar een band bestaat,
   is de band het object en het middelpunt een markering daarin.
2. **Het betrouwbaarheidsniveau staat in het eerste scherm**, niet onder de vouw en niet
   achter een uitklapper.
3. **De drie routes staan altijd alle drie op de pagina, in vaste volgorde, gratis eerst.**
   Een route waarin niets gevonden is toont "hier is niets meer te halen" en wordt niet
   verborgen. Een lege sectie is zelf een antwoord.
4. **Geen aftelklok, geen schaarste, geen sociale bewijsvoering.** Geen "nog 14 maanden",
   geen "3.412 huishoudens gingen u voor". Het einde van de saldering heeft geen
   aangeprate urgentie nodig en zou die niet mogen krijgen.
5. **De enige twee oproepen tot actie zijn "verfijn uw antwoord" en "bewaar deze link".**
   Er is geen derde. Er komt nooit een knop die naar een verkopende partij leidt.
6. **De betaalde route krijgt nooit meer ruimte dan de gratis routes samen.** Toegevoegd op
   2026-08-21, nadat een audit mat dat het batterijblok 38,5 procent van de pagina besloeg
   bij een huishouden dat te horen kreeg er geen te kopen. Regel 3 was geimplementeerd als
   volgorde in het document, en volgorde is de zwakste vorm van voorrang die er is: de
   gratis routes stonden bovenaan en verloren op hoogte, op detail en op het aantal getallen
   dat een lezer kreeg aangeboden. Zie hoofdstuk 7.

Regels 1, 2, 3, 5 en 6 zijn met Playwright te controleren en worden dat ook. Regel 4 wordt
bewaakt door een test die de gebouwde pagina's afzoekt op de patronen die erbij horen, en
dat is bewust de zwakste van de zes: een audit heeft drie plausibele manieren beschreven om
er langs te komen, waaronder urgentie die uit een datumberekening komt in plaats van uit een
woord. Wie die test uitbreidt, breidt de lijst uit en niet de belofte.

Beweging mag de aandacht naar de onzekerheid trekken en nooit naar een aankoop.

## 3. Stack en versies

| Pakket | Versie | Reden |
|---|---|---|
| Next.js | 16.x | `CLAUDE.md` zegt 15, en dat is achterhaald. Next kent geen LTS-spoor: de actuele hoofdversie krijgt actieve ondersteuning en de vorige alleen nog kritieke fixes. De actuele major kiezen is hier dus juist de langst ondersteunde keuze. Dat is de omgekeerde redenering van de Django-keuze eerder vandaag, en dat komt doordat Django wel een LTS-spoor heeft en Next niet. |
| React | 19.x | Wat Next 16 meebrengt. |
| TypeScript | 5.9.3 | **Niet 7.** TypeScript 7, de herschrijving in Go, staat op `latest`, maar `create-next-app` van Next 16.3.1 kiest zelf `^5` en installeert 5.9.3. Het nieuwste nemen zou hier het nemen van iets zijn waar de toolchain eromheen nog niet op gebouwd is. |
| ESLint | 9.39.5 | **Niet 10.** npm meldt 9.x als deprecated en 10.8.1 als beschikbaar, maar `eslint-config-next@16.3.1` eist `^9`. Dit is de combinatie die Next zelf ondersteunt; 10 nemen betekent de Next-configuratie weggooien. Opnieuw beoordelen zodra `eslint-config-next` 10 accepteert. |
| Tailwind | 4.3.3 | |
| pnpm | 10.33.0, via `packageManager` in `package.json` | Strikte `node_modules`, dus een pakket dat niet gedeclareerd is kan ook niet geimporteerd worden. Dat is dezelfde soort grens als de importgrens in `ampeer_sim`: afgedwongen in plaats van afgesproken. `create-next-app` zet het veld zelf. |
| Node | 24, vastgelegd in `.nvmrc` | Active LTS, en wat er op de ontwikkelmachine staat. Next 16 eist minimaal 20.9. |
| Vitest + Testing Library | actueel | Eenheden en componenten. |
| Playwright | actueel | De stromen, en de vijf regels uit hoofdstuk 2. |

Wat de foundation daadwerkelijk installeerde, op 2026-08-21: next 16.3.1, react en
react-dom 19.2.8, typescript 5.9.3, eslint 9.39.5, eslint-config-next 16.3.1, tailwindcss
en @tailwindcss/postcss 4.3.3, vitest en @vitest/coverage-v8 4.1.11, @vitejs/plugin-react
6.1.0, jsdom 30.0.1, @testing-library/react 16.3.2, @testing-library/user-event 14.6.5,
@testing-library/jest-dom 7.0.1, @playwright/test 1.62.1, @axe-core/playwright 4.13.0,
serve 14.2.6. `@vitest/coverage-v8` stond niet in de tabel hierboven en is nodig: zonder
dat pakket kan `vitest run --coverage` niet starten.

`actions/setup-node` staat op v7.0.0, niet op v5. Het plan schreef v5 en dat was een gok:
v7 is de actuele hoofdversie en de rest van deze repository pint `actions/checkout` op
v7.0.1. Twee hoofdversies achterlopen op een actie die in een vereiste poort draait, is
geen keuze die iemand gemaakt heeft.

`sast` dekt de TypeScript-boom met semgrep, met een regelset die in deze repository staat
(`.semgrep/frontend.yml`) en niet uit semgrep's registry komt. Een vereiste poort die
afhangt van de bereikbaarheid van een derde partij gaat rood om redenen die niets met de
code te maken hebben, en de regels die een poort afdwingt horen niet te kunnen veranderen
zonder een commit hier. De set is smal en zegt dat zelf: hij dekt de manieren waarop een
statische site die API-tekst rendert en formulierinvoer aanneemt daadwerkelijk stukgaat,
en doet niet alsof hij een algemene TypeScript-scanner is. Alle vijf de regels zijn
geverifieerd door ze op een expres fout bestand af te vuren; twee ervan deden dat in hun
eerste versie niet, waaronder die op `dangerouslySetInnerHTML`.

Gemeten op 2026-08-21 door `create-next-app` een keer echt te draaien in een wegwerpmap in
plaats van de versies af te leiden uit wat het nieuwste is. Dat leverde meteen twee
correcties op deze tabel op, allebei gevallen waarin het nieuwste niet het juiste was.

Twee dingen die daarbij ook bleken en die het plan moet weten:

- `create-next-app` maakt een eigen git-repository aan, ook met `--no-git`. Scaffolden
  binnen deze repository levert dus een geneste `.git` op die weg moet.
- `output: "export"` werkt met Next 16.3.1 en levert een `out/` met statische HTML per
  route. Geverifieerd met een echte build, niet aangenomen.

## 4. Statisch gebouwd, en de browser praat zelf met de API

Dit is de belangrijkste architectuurbeslissing en hij komt niet uit een voorkeur maar uit
een eigenschap van de API die vandaag gebouwd is.

**De adviesAPI beperkt het aantal verzoeken per IP-adres.** Zou Next het advies op de
server ophalen, dan komen alle verzoeken van elke bezoeker van één IP-adres, namelijk dat
van de Next-server. Alle bezoekers delen dan één emmer van twintig berekeningen per uur,
en de twintigste bezoeker van dat uur krijgt een 429 die niets met zijn eigen gedrag te
maken heeft. Het tempolimiet zou van een bescherming in een storing veranderen.

Er is een tweede reden, en die weegt zwaarder dan de eerste. Kwartierverbruik en de
antwoorden eromheen zijn persoonsgegevens. Zou Next ze doorgeven, dan lopen ze door een
proces meer, met een toegangslogboek meer, en dat proces heeft er niets aan toe te voegen.

Dus: **de browser roept de API rechtstreeks aan.** Next rendert geen enkel verzoek per
bezoeker.

Daaruit volgt dat er in productie geen Node-proces hoeft te draaien. De site wordt
statisch gebouwd en door de reverse proxy geserveerd. Dat scheelt een runtime die
bewaakt, bijgewerkt en gepatcht moet worden, en het past bij de lijn die dit project al
volgt: geen Celery omdat er niets te wachten valt, Redis uit het verzoekpad omdat er niets
te delen valt, en nu geen applicatieserver voor de frontend omdat er niets per verzoek te
renderen valt.

**Gevolg voor deelproject 2:** de reverse proxy moet `/advies/<token>` naar de statisch
gebouwde adviespagina sturen, die het token uit het pad leest. Zonder die regel werkt de
deelbare link niet. Dat is één regel configuratie en hij staat hier opgeschreven zodat hij
niet vergeten wordt.

CORS: de API krijgt een `Access-Control-Allow-Origin` die op de eigen herkomst staat en
uit de omgeving komt, met dezelfde behandeling als `ALLOWED_HOSTS`. In productie is dat
één domein. Een wildcard is hier een fout, niet een gemak.

## 5. Routes

| Pad | Wat het is |
|---|---|
| `/` | De landingspagina. Wat er in 2027 verandert, en de eerste vraag. |
| `/berekenen` | De vragenstroom, ronde 1 en ronde 2. |
| `/advies/<token>` | Het advies. Ook de deelbare link. |
| `/methodologie` | `docs/methodologie.md`, gerenderd. |

`/methodologie` is geen bijzaak. Het is het document waarop dit product beoordeeld wordt en
het staat nu alleen in de repository. Het bij de bouw uit het bestand renderen zorgt dat de
gepubliceerde versie niet kan afwijken van de versie die de tests bewaken.

## 6. Het ontwerpsysteem

Ontwerptokens in CSS-variabelen, met Tailwind erbovenop. Geen componentbibliotheek van
derden: de componenten die dit product nodig heeft zijn er ongeveer acht, en de belangrijkste
daarvan bestaat nergens kant en klaar omdat niemand anders bandbreedtes als hoofdobject
toont.

Licht en donker allebei, gestuurd door `prefers-color-scheme` met een expliciete keuze die
voorgaat.

Nederlands is de taal van de interface, en de teksten komen bijna allemaal uit de API:
`title`, `text`, `confidence_label` en `basis_text` zijn Nederlands en worden door de
backend geleverd. De frontend schrijft zelf alleen navigatie en formuliertekst. Dat is de
harde scheiding uit `CLAUDE.md` en hij wordt afgedwongen met een test: geen adviestekst in
de frontend-broncode.

## 7. De band als hoofdobject

De API levert twee soorten band en die zijn niet hetzelfde. Ze moeten er ook niet hetzelfde
uitzien.

**De hoofdband** (`headline`) heeft `p10`, `p50`, `p90` en `runs: 243`. Dat zijn echte
percentielen over een volledig factorieel raster.

**De scenarioband** (elk bedrag in de routes en in het batterijblok) heeft `low`, `mid`,
`high`, plus `varied`, `pinned` en `combinations`. Dat is hetzelfde gesimuleerde jaar,
opnieuw beprijsd op drie tariefniveaus. Hij zegt iets smallers, en het antwoord vertelt zelf
waarover hij varieert en wat er vastgezet is.

De frontend maakt dat verschil zichtbaar in plaats van het glad te strijken. De hoofdband
krijgt de volle behandeling: een verlopende balk waarin de breedte de onzekerheid ís, met
het middelpunt als markering en de uiteinden gelabeld. De scenarioband krijgt een kleinere,
duidelijk andere vorm, met `varied` en `pinned` opvraagbaar in gewone taal.

Een bedrag waarvan `band` `null` is, zoals `sized_capacity_kwh`, toont zijn eigen
`basis_text` en niet een verzonnen marge. Het antwoord zegt daar zelf waarom er geen band
omheen staat, en dat is precies de zin die een lezer moet zien.

### Wat de audits hierover rechtzetten, 2026-08-21

De zin "een verlopende balk waarin de breedte de onzekerheid ís" stond hier vanaf het begin
en klopte niet met wat er gebouwd was. `.fill` stond altijd op honderd procent, dus een
regel met een marge van zestig euro en een met driehonderddrieentachtig werden als twee
identieke objecten van 416 pixels getekend, en de vijf capaciteitsbanden waren pixel voor
pixel dezelfde figuur. De lezer leerde de onzekerheid alleen door de getallen te lezen,
wat precies is wat deze pagina niet zou hoeven vereisen.

De balk is nu een as van nul tot het bovenste eind van de band zelf, en de vulling is een
segment daarop. De breedte is dus de onzekerheid als aandeel van het grootste bedrag dat
het model plausibel acht. Er is geen referentieconstante verzonnen: beide uiteinden van de
as zijn getallen die het model heeft geproduceerd, en omdat het een breuk is, is hij
vergelijkbaar tussen euro's, jaren en euro's per kWh. Een band met breedte nul wordt als
breedte nul getekend, want de oude terugval tekende daar een rail met een gecentreerde
markering: het beeld van een bereik waar er geen is.

Twee dingen die dezelfde vorm hadden en langs dezelfde regel glipten:

**De kleur draaide de lettergroottes om.** Het verloop vervaagde naar dertig procent
dekking aan de uiteinden, gemeten 1,94:1 tegen de pagina in het lichte thema, terwijl het
midden op 6,33:1 stond met een massieve markering erop. De lettergroottes gehoorzaamden
regel 1 keurig; de kleur deed het tegendeel, en het oog landde op het middelpunt terwijl de
band richting zijn eigen antwoord vervaagde. Het verloop loopt nu andersom.

**Het batterijblok was 38,5 procent van de pagina** bij een huishouden waarvan het oordeel
"dit verdient zich niet terug" is, tweeeneenvijfde keer beide gratis routes samen, met een
tabel van vijf capaciteiten en wat elk oplevert. Regel 3 zegt dat de gratis routes eerst
komen, en dat was geimplementeerd als volgorde in het document. Volgorde is de zwakste vorm
van voorrang die er is: ze stonden bovenaan en verloren op hoogte, op detail en op het
aantal getallen dat een lezer kreeg aangeboden.

Daarom staat er nu een zesde regel bij die vier in hoofdstuk 2:

6. **De betaalde route krijgt nooit meer ruimte dan de gratis routes samen.** Het
   doorgerekende detail zit achter een uitklapper die dicht is tenzij het model opslag
   daadwerkelijk aanbeveelt. Er wordt niets weggehaald: alle cijfers staan in het document,
   een klik ver. Een test meet de hoogte van de betaalde sectie tegen die van de gratis
   secties, in plaats van de volgorde te vertrouwen.

Alle drie deze fouten wezen dezelfde kant op, en dat is het patroon dat in dit project
inmiddels vaker voorkomt dan toeval verklaart: ze maakten het antwoord zekerder dan het is
of de batterij aantrekkelijker dan hij is, en geen van drieen gaf een foutmelding.

## 8. Het formulier

Vier vragen die vijf waarden opleveren, want dakrichting en hellingshoek zijn één vraag
over één dak. Daarna vijf vragen erbij voor ronde 2.

Eén vraag per scherm, met de voortgang zichtbaar. De dakrichting is een visuele keuze en
geen invoerveld met graden, want niemand kent zijn azimut. De invoer wordt clientseitig
gevalideerd tegen dezelfde grenzen die de serializer hanteert, en die grenzen worden uit
de API gehaald in plaats van overgeschreven, zodat er geen tweede plek is waar ze kunnen
wegdrijven.

De browser mag antwoorden lokaal bewaren zodat een half ingevuld formulier een herlaadbeurt
overleeft. In `sessionStorage` en niet in `localStorage`: het is verbruiksdata over een
huishouden en het hoort niet langer te blijven staan dan het tabblad.

## 9. Toegankelijkheid en snelheid, allebei als poort

Een interface die zijn eigen onzekerheid als hoofdonderwerp heeft, moet die onzekerheid ook
overbrengen aan iemand die de balk niet ziet. De band krijgt daarom een tekstuele vorm die
volledig is, niet een `aria-label` met alleen het middelpunt erin.

- WCAG 2.2 AA, met axe in de testronde en niet als handmatige controle achteraf
- Toetsenbordbediening voor de hele vragenstroom
- `prefers-reduced-motion` gerespecteerd, en dat betekent dat de betekenis nooit alleen in
  de beweging zit
- Prestatiebudgetten worden gemeten en vastgelegd bij de eerste build, en daarna alleen nog
  strenger. Zoals bij de dekkingsdrempel: omhoog mag, omlaag niet.

Dat laatste is bewust vaag over het getal en scherp over de regel. Een budget verzinnen
voordat er iets gebouwd is, is een verzonnen getal.

## 10. Testregime

1. **Componenten** (Vitest + Testing Library): de bandcomponent tegen echte
   API-antwoorden uit een fixture, inclusief het geval `band: null`.
2. **De vijf regels uit hoofdstuk 2** (Playwright): geen getal groter dan zijn band, het
   betrouwbaarheidsniveau in het eerste scherm, drie routes in vaste volgorde met de lege
   erbij, en precies twee soorten oproep tot actie.
3. **Taalgrens**: geen adviestekst in de frontend-broncode.
4. **Toegankelijkheid**: axe over elke route, zonder overtredingen.
5. **De contractband met de API**: een test die de fixture vergelijkt met wat de echte API
   nu teruggeeft, zodat een wijziging in het antwoord hier rood wordt en niet bij een
   bezoeker.

Punt 5 is het belangrijkste van de vijf. Twee codebases die een JSON-vorm delen zonder
gedeelde controle is de klassieke manier waarop een frontend stilletjes iets anders toont
dan de backend bedoelde.

## 11. Gevolgen voor de leverstraat

Twee nieuwe jobs, `frontend-quality` en `frontend-test`. Ze worden niet in de bestaande
`quality` en `test` gepropt: die draaien een Python-omgeving en een gemengde job maakt een
rode build moeilijker te lezen.

`CLAUDE.md` zegt dat de jobnamen een interface met de rulesets zijn en dat
`scripts/setup_rulesets.sh` in dezelfde commit meeverandert. Dat gebeurt hier ook, en de
bestaande contracttest die vereiste checks tegen gepubliceerde jobnamen houdt, dekt de twee
nieuwe daarmee automatisch.

Node komt met een vastgezette versie in `.nvmrc`, de lockfile wordt meegecommit, en
`dependencies` en `secrets` gaan ook over `frontend/`. Anders geldt hier hetzelfde als wat
vandaag bij `sast` bleek: een poort die alles dekt behalve het nieuwe deel.

## 12. Definition of done

- Een bezoeker komt van de landingspagina in vier vragen bij een advies
- Elk bedrag op de pagina toont zijn band, of zegt waarom het er geen heeft
- Het betrouwbaarheidsniveau staat in het eerste scherm, aantoonbaar met een test
- De drie routes staan er altijd alle drie, in volgorde, ook als er een leeg is
- De deelbare link opent het advies in een nieuwe browser zonder account
- axe vindt geen overtredingen op geen enkele route
- De contracttest tegen de echte API is groen
- Geen Nederlandse adviestekst in de frontend-broncode
- De vijf bestaande poorten blijven groen en de twee nieuwe zijn vereist
