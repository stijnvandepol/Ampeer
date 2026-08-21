# Ontwerp: LXC, runner en deploy (deelproject 2)

Datum: 2026-08-21
Status: vastgesteld, klaar voor implementatieplan
Betreft: `infra/`, de Proxmox LXC, de deploy-workflow en alles wat de drie audits van
vandaag naar dit deelproject hebben doorgeschoven

## 1. Doel en afbakening

Een tag op `main` moet de draaiende site worden, zonder dat er iemand op de server inlogt
en zonder dat er een poort van buiten open staat.

Binnen scope:

- `infra/`: compose-bestand, nginx-configuratie, Dockerfiles, tunnelconfiguratie
- De deploy-workflow en wat de runner precies mag
- Het opruimen van verlopen advies, en hoe je merkt dat dat niet meer gebeurt
- De omgevingsvariabelen die de dienst nodig heeft, en wat er gebeurt als er een ontbreekt
- Toegangslogboeken, waar dit deelproject een belofte kan breken die de rest bewaakt

Buiten scope:

- Accounts en meterkoppeling (fase 1 en 2)
- Monitoring en alarmering voorbij wat hieronder staat. Dat verdient zijn eigen ronde en
  is nu speculatie

**Buiten mijn bereik, en dat blijft zo.** Ik heb geen toegang tot de Proxmox-host en raak
de runner `web2` niet aan. Wat hier staat is te schrijven, te bouwen en lokaal te testen;
het aanmaken van de container en het registreren van een runner zijn handelingen van
Stijn. Waar dat zo is, staat het erbij.

## 2. De vondst die de vorm bepaalt: dit wordt same-origin

Het frontend-ontwerp gaat ervan uit dat de browser de API rechtstreeks aanroept, en dat
blijft zo. Waar het ontwerp niet over ging is *van welke herkomst*.

Als nginx de statische site op `ampeer.nl` serveert en `/api/` doorstuurt naar Django,
dan zijn de twee helften **dezelfde herkomst**. Dan is er geen preflight, geen
`Access-Control-Allow-Origin` in het verzoekpad, en geen faalvorm waarin een bezoeker te
horen krijgt dat hij zijn verbinding moet controleren terwijl er een header ontbreekt.

Dat is beter dan de API op `api.ampeer.nl` zetten, om drie redenen. Het scheelt een
rondgang per berekening, want de POSTs sturen `content-type: application/json` en die
worden anders vooraf gepolst. Het scheelt een certificaat en een tunnelroute. En het haalt
de faalvorm weg die vandaag pas ontdekt werd doordat een audit ernaar zocht.

**Het CORS-werk van vanochtend blijft staan en is niet voor niets geweest.** Het is nu
diepteverdediging in plaats van de hoofdweg: het is wat de dienst dichthoudt op de dag dat
iemand de API alsnog op een andere host zet, en het is wat een verkeerd geconfigureerde
herkomst laat falen in plaats van laat slagen. `CORS_ALLOWED_ORIGINS` blijft verplicht uit
de omgeving komen, en staat in deze opzet op de eigen herkomst.

**Gevolg voor de frontend:** `NEXT_PUBLIC_API_BASE` is in productie leeg, zodat de client
relatieve paden gebruikt. Hij staat nu op `http://127.0.0.1:8000` als ontwikkelstandaard,
en dat moet een build-time waarde worden die in productie de lege string is.

## 3. De vorm: CI bouwt, de LXC haalt op

Drie images, alle drie gebouwd door een GitHub-hosted runner en gepubliceerd naar GHCR:

| Image | Wat erin zit |
|---|---|
| `ampeer-api` | Python 3.12, de gesynchroniseerde omgeving, `backend/`, gunicorn |
| `ampeer-web` | nginx met de statische `out/` erin gekopieerd |
| `ampeer-purge` | dezelfde basis als de API, met het opruimcommando als entrypoint |

De LXC bouwt niets. Hij haalt op wat CI heeft gebouwd, en dat is de grootste
beveiligingswinst die hier te halen valt: er staat geen broncode op de host, geen
buildketen, en geen token dat de repository kan lezen.

Elke image krijgt de tag mee die de deploy aanzette, en `docker-compose.yml` verwijst naar
die tag en niet naar `latest`. Een deploy is daarmee een tekstwijziging in één bestand die
te lezen en terug te draaien is. Hetzelfde principe als elders in dit project: geen
bewegend doel waar een vastgezette verwijzing kan.

## 4. De runner, en de beslissing die bij Stijn ligt

De deploy-job draait op de self-hosted runner en doet precies dit:

```
docker compose pull
docker compose up -d --remove-orphans
docker compose run --rm api python manage.py migrate --noinput
```

Meer niet. Geen checkout, geen build, geen `docker build`. Hoe minder een runner mag, hoe
minder het uitmaakt dat hij bestaat.

**De runner moet ephemeer zijn.** Gemeten op 2026-08-21: `web2` staat online met
`ephemeral=false`. Een niet-ephemere runner houdt zijn werkmap tussen jobs, dus alles wat
een job achterlaat is er de volgende keer nog, en dat is precies de eigenschap die een
gecompromitteerde job permanent maakt.

Daar komt bij wat al eerder is vastgesteld en waarom `tests/test_pipeline_contract.py`
faalt op elke job die `self-hosted` zegt: de workflows draaien op `push` naar `feat/**`,
waar geen ruleset geldt, dus een job die de self-hosted runner koos zou ongereviewde code
binnen Stijns eigen netwerk draaien. Die test blijft staan, met één uitzondering die
expliciet benoemd moet worden: de deploy-job draait op `push` van een **tag** op `main`,
niet op een branch, en heeft `environment: production` met een verplichte review.

**Dit is de beslissing die bij Stijn ligt en die ik niet neem.** De bestaande runner
opnieuw registreren als ephemeer, of hem laten staan en accepteren wat dat betekent.

## 5. Het netwerk: niets staat open

`cloudflared` draait in dezelfde compose-stack en maakt een uitgaande verbinding. Er is
geen inkomende poort, geen port forward, geen publiek IP-adres van de LXC.

nginx staat ervoor en doet twee dingen:

- `/` en alles eronder: de statisch gebouwde site uit `out/`
- `/api/`: doorsturen naar gunicorn

`SECURE_PROXY_SSL_HEADER` in `prod.py` vertrouwt `X-Forwarded-Proto`. Dat is alleen
correct als de proxy die header **overschrijft** en niet aanvult. nginx moet hem daarom
zetten met `proxy_set_header X-Forwarded-Proto $scheme;` en niet doorgeven wat de client
stuurde. Hetzelfde geldt voor `X-Forwarded-For`: `DJANGO_NUM_PROXIES` moet gelijk zijn aan
het werkelijke aantal hops, en in deze opzet zijn dat er twee, de tunnelconnector en
nginx. Een verkeerd getal daar maakt het tempolimiet omzeilbaar met één header, wat vandaag
al een keer is gemeten.

## 6. De regel zonder welke het product niet werkt

De site is statisch geexporteerd, dus er bestaat één gebouwde adviespagina en geen route
per token. nginx moet `/advies/<token>` naar die pagina sturen:

```
location /advies/ {
    try_files $uri $uri/ /advies/index.html;
}
```

Zonder die regel krijgt **niet alleen de ontvanger van een gedeelde link een 404, maar ook
de bezoeker die net vier vragen heeft beantwoord**, want de vragenstroom eindigt met een
volledige navigatie naar dat pad. Het advies is dan berekend, opgeslagen en van zijn
uurbudget afgeschreven, en hij ziet het nooit. Honderd procent stuk, niet vijftig.

Die eis stond tot nu toe op vier plaatsen, alle vier binnen deelproject 4, en `infra/`
bestond niet. Een audit merkte op dat het enige bestand dat iemand opent bij het opzetten
van een deploy `frontend/README.md` was, en dat daar tot vandaag de standaardtekst van
`create-next-app` in stond die eindigt met "Deploy on Vercel". Hij staat nu hier, in het
deelproject dat hem moet uitvoeren, met een test in de e2e-suite die hem afdwingt via
`serve.json`.

## 7. Negen variabelen, en wat er gebeurt als er een ontbreekt

`prod.py` eist er negen, geen met een standaardwaarde: `DJANGO_SECRET_KEY`,
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_NUM_PROXIES`,
`AMPEER_NEDU_PROFILE_PATH`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_HOST`.

Ontbreekt er een, dan start het proces niet. Dat is de bedoeling en het is vandaag al een
keer gebeurd toen CORS erbij kwam en de deploy-check in CI zijn eigen lijst niet had
bijgewerkt; er staat nu een test op die die twee lijsten aan elkaar koppelt.

Voor de deploy betekent het één ding: **er komt geen `.env` met standaardwaarden in de
repository.** De waarden staan in een bestand op de host dat compose inleest, buiten git,
en de deploy-workflow controleert vooraf of alle negen gezet zijn en stopt met een
leesbare fout als er een mist. Een container die in een herstartlus zit omdat een variabele
ontbreekt is een storing die er als een codefout uitziet.

## 8. De bewaartermijn, en hoe je merkt dat hij niet meer draait

`purge_expired_advice` bestaat en wordt door niets aangeroepen behalve een test. Ruwe data
verdwijnt dus niet na negentig dagen; hij wordt alleen onzichtbaar, want `get_live` filtert
op `expires_at`. Dat zijn twee verschillende beloftes en `CLAUDE.md` doet de sterkste.

Een audit noemde precies waarom dit gevaarlijk is: **als de cron nooit wordt aangezet, is
het enige waarneembare gedrag dat een link na negentig dagen een 404 geeft, en dat is
exact hoe correct werken eruitziet.** De fout is stil per constructie.

Dus twee dingen, en het tweede is het punt:

- Een `ampeer-purge`-service in compose, aangezet door een systemd-timer op de host,
  dagelijks. Geen Celery: een `DELETE` over een tabel met een index op `expires_at` heeft
  geen takenwachtrij nodig.
- Een `--check`-modus op datzelfde commando die met een niet-nul exitcode eindigt zodra er
  een rij bestaat die meer dan een dag over zijn vervaldatum is.

Dat tweede is geen extraatje. Zonder controle is de eerste keer dat iemand merkt dat er
niet is opgeruimd het moment dat er een databaseback-up wordt opgevraagd.

**Waar `--check` draait, en waarom niet als healthcheck.** Bij het schrijven van deze
paragraaf stond er dat `--check` de healthcheck van de container zou worden. Dat botst met
een beslissing die deelproject 2 zelf neemt in paragraaf 10: de readiness-check van de
api-container doet expres geen databasevraag. Hij draait elke dertig seconden, en een
controle die zo vaak rijen telt is een belastinggenerator met een nette naam. De twee eisen
kunnen niet allebei waar zijn in een healthcheck, dus draait `--check` op twee plaatsen die
geen healthcheck zijn:

- `ExecStartPost=` op `ampeer-purge.service`. Die regel draait alleen als de opruiming zelf
  is geslaagd, en stelt dan precies de vraag die overblijft: staat er nog iets over datum?
  Zo ja, dan heeft de `DELETE` niet gedaan wat zijn eigen uitvoer beweerde, en de unit gaat
  naar `failed` in plaats van een getal in de journal te laten dat niemand leest
- Een stap in de deploy-job, na `migrate`. Een deploy die groen wordt terwijl er niets meer
  wordt verwijderd is een groen vinkje dat een gebroken belofte afdekt. Een deploy is zeldzaam
  en is al een moment waarop iemand kijkt, wat de juiste frequentie is voor een vraag over
  een dagelijkse timer

**Wat geen van beide ziet: een timer die nooit is aangezet.** `ExecStartPost=` draait alleen
als de unit draait, en die draait niet. De stap in de deploy vindt niets zolang er nog geen
rij eenennegentig dagen oud is, dus in de eerste drie maanden van de dienst zwijgt hij ook.
Alleen `systemctl list-timers ampeer-purge.timer` beantwoordt die vraag, en niets in deze
repository kan dat commando draaien. Dat staat in `infra/README.md` als bekende grens.
Monitoring staat in paragraaf 1 expliciet buiten scope, en een zin hier die suggereerde dat
dit gat gedekt is zou dezelfde vorm van vals comfort zijn die dit project telkens tegenkomt.

## 9. Het toegangslogboek kan een belofte breken die de rest bewaakt

Het auditlogboek slaat bewust geen IP-adres op, en het token staat er gehasht in. nginx
schrijft standaard `client_ip - - [tijd] "GET /api/advice/<token>/"`. Daarmee staat de
combinatie die dit project weigert te maken alsnog op schijf, in een bestand met een
bewaartermijn die niemand hier heeft gekozen.

Dus:

- Voor `location /api/advice/` een logformaat zonder het pad, of `access_log off`. De
  route is bekend; het token hoort er niet in
- Geen `X-Forwarded-For` naar het applicatielogboek doorschrijven
- De bewaartermijn van wat er wel gelogd wordt expliciet vastzetten, zodat het een keuze is
  en geen standaardwaarde. Bij de uitvoering bleek dat dat niet in een
  logrotatie-configuratie kan: nginx schrijft naar `/dev/stdout` en `/dev/stderr`, gunicorn
  en Django naar stderr, en er staat geen logbestand in een container. Er is dus niets voor
  `logrotate` om te roteren. De enige plek waar de termijn te kiezen valt is het
  log-stuurprogramma van Docker, en dat staat standaard op `json-file` zonder rotatie: het
  bewaart alles tot de container wordt verwijderd, en `restart: unless-stopped` betekent dat
  dat nooit gebeurt. De keuze staat daarom als `logging:` bij elke service in
  `infra/docker-compose.yml`, met de gekozen grootte en het aantal bestanden onderbouwd

## 10. Het NEDU-bestand, en waarom de deploy nog niet kan

`AMPEER_NEDU_PROFILE_PATH` is verplicht en `profiles.py` weigert te starten zonder. Het
bestand komt als read-only bind-mount de container in; het gaat niet in een image, want dan
staat het in een registry.

**En hier zit een gat dat pas bij het schrijven van het plan zichtbaar werd.** `prod.py`
eist dat `AMPEER_NEDU_PROFILE_PATH` *gezet* is, niet dat het bestand *bestaat*, en
`profile_provider()` wordt pas aangeroepen wanneer er een advies berekend wordt. Een
container met een verkeerd gemonteerd pad start dus vrolijk op, meldt zich gezond, en laat
elk verzoek stuklopen. Honderd procent kapot, en het ziet er van buiten uit alsof het
draait.

Dat is dezelfde vorm als de andere stille faalvormen in dit project, en de reparatie hoort
hier: **de healthcheck van de API-container moet het profiel daadwerkelijk openen**, niet
alleen controleren of het proces leeft. Een verkeerde mount maakt de container dan ongezond
in plaats van stil kapot. Een readiness-endpoint dat `profile_provider()` aanroept en verder
niets doet is genoeg; het rekent niets uit en raakt de database niet.

**En dit blokkeert de publieke deploy.** De herdistributievoorwaarden van de
NEDU-profielen zijn niet bevestigd. Zolang dat zo is kan de stack draaien op Stijns eigen
machine met zijn eigen kopie, en kan hij niet publiek. Dat is een bewuste ontwerpkeuze en
geen omissie: er is geen terugvalprofiel, omdat een verzonnen verbruikscurve een verzonnen
getal in het midden van elk antwoord zou zetten terwijl elke test groen bleef.

## 11. Een klein gat in `.gitattributes`

`*.py`, `*.sh`, `*.yml`, `*.md`, `*.toml` en `*.json` staan vastgezet op LF. `*.ts`,
`*.tsx`, `*.css` en `*.txt` niet, en dat is waarom elke commit in deelproject 4 een scherm
vol CRLF-waarschuwingen gaf. Dat wordt hier rechtgezet, want dit deelproject is het eerste
waar een bestand met verkeerde regeleindes in een Linux-container terechtkomt.

## 12. Testregime

Wat lokaal te toetsen is, wordt lokaal getoetst. Docker draait op de ontwikkelmachine.

1. **De stack start.** `docker compose up` met een test-envbestand brengt alle vier de
   services omhoog en de healthchecks worden groen
2. **De rewrite werkt.** `GET /advies/<22 tekens>` levert de adviespagina en geen 404
3. **Same-origin.** `GET /api/advice/estimate/` via nginx bereikt Django, en het antwoord
   heeft geen `Access-Control-Allow-Origin` nodig omdat het dezelfde herkomst is
4. **Een ontbrekende variabele stopt de deploy** met een leesbare fout, niet met een
   herstartlus
5. **Het opruimen werkt en de controle bijt.** Een rij die over datum is wordt verwijderd;
   met de timer uit meldt `--check` het en wordt de container ongezond
6. **Het token staat niet in het toegangslogboek.** Een verzoek doen en het logbestand
   afzoeken op het token
7. **De proxyheaders kloppen.** Een verzoek met een vervalste `X-Forwarded-Proto` en
   `X-Forwarded-For` komt bij Django aan met de waarden die nginx heeft gezet

Punt 6 en 7 zijn de twee die niemand zou schrijven als ze niet in een spec stonden, en het
zijn de twee die een belofte bewaken die elders in dit project met tests is afgedwongen.

## 13. Definition of done

- Een tag op `main` levert een draaiende site af zonder dat iemand op de host inlogt
- Er staat geen inkomende poort open
- `/advies/<token>` opent het advies, ook in een browser die er nooit eerder is geweest
- Een ontbrekende omgevingsvariabele stopt de deploy voordat er iets herstart
- Verlopen advies wordt daadwerkelijk verwijderd, en een gestopte opruiming is zichtbaar
- Geen token en geen IP-adres in een logbestand dat langer bewaard wordt dan de rij zelf
- De vijf bestaande poorten blijven groen

**Twee dingen die niet in deze lijst kunnen staan omdat ze niet van mij zijn:** of de
runner ephemeer wordt, en of het NEDU-bestand publiek gebruikt mag worden. Zonder het
eerste is de deploy minder veilig dan hij hoort te zijn; zonder het tweede kan hij niet
publiek. Allebei zijn ze opgeschreven zodat ze een beslissing zijn en geen vergetelheid.
