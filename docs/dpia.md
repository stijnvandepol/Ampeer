# Gegevensbeschermingseffectbeoordeling

Over de rekenmachine en de adviseur zoals die vandaag draaien, fase 0.5.

## 0. Wat dit document is, en wat het niet is

Dit is de technische helft van een DPIA: een beschrijving van wat de dienst
werkelijk verwerkt, hoe lang, waar de kopieën staan, wie erbij kan en wat de
machine verlaat. Elk feit hierin is uit de code gelezen of gemeten, niet
onthouden, en `tests/test_dpia.py` houdt de getallen hieronder naast de plek in
de code waar ze vandaan komen. Verandert er een, dan valt die test om.

Dit is geen juridisch advies en het is niet ondertekend. Vier dingen zijn
beslissingen van de verwerkingsverantwoordelijke en staan in hoofdstuk 9 met de
informatie die nodig is om ze te nemen.

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

De afweging is dus: waarschijnlijk niet verplicht in fase 0.5, wel verstandig,
en verplicht zodra fase 1 begint. Hoofdstuk 8 zet uiteen wat er dan verandert.
Hoofdstuk 9 laat de conclusie zelf aan de verwerkingsverantwoordelijke.

## 2. Wat wij verwerken

Alles hieronder komt uit `backend/advice/models.py` en
`backend/advice/serializers.py`.

### Wat de bezoeker invult

De eerste ronde stelt vier vragen: viercijferige postcode, jaarverbruik in kWh,
vermogen aan panelen in wattpiek, en dakrichting en hellingshoek. Een tweede
ronde kan daar zeven antwoorden aan toevoegen: overdag thuis, elektrische auto
en het laadmoment, warmtepomp en warmtevraag, contractvorm, thuisbatterij en de
omvang daarvan.

**De postcode wordt op vier cijfers gevalideerd en er is geen veld waar meer in
past.** Dat is niet een afspraak maar een reguliere expressie in de serializer:
zes tekens worden geweigerd, niet afgekapt. Een afgekapte waarde zou betekenen
dat de volledige postcode ooit de applicatie bereikte.

### Wat de dienst zelf toevoegt

Bij elk antwoord hoort een token van 22 tekens uit `secrets.token_urlsafe(16)`.
Dat is de sleutel in de deelbare link. Hij is niet af te leiden uit de inhoud en
niet te raden.

### Wat er niet is

Geen naam, geen e-mailadres, geen telefoonnummer, geen huisnummer, geen account
en geen wachtwoord. Er is niets om in te loggen, dus er is ook geen inlogpoging
om vast te leggen.

**Geen IP-adres in enige tabel.** Het IP-adres wordt gebruikt, want het
tempolimiet moet ergens op tellen, maar het wordt daarvoor eerst gehasht
(`advice/throttling.py`) en de teller staat in een cache met een vervaltijd. Er
is geen model met een adresveld en geen logregel die er een bewaart.

### Het auditlogboek

`AuditEvent` is append-only en legt vandaag precies een soort gebeurtenis vast:
dat er een advies is gegenereerd, met het token en de viercijferige postcode
erbij. De andere gebeurtenissen die dit project wil vastleggen, een inlog, een
koppeling, een gegeven of ingetrokken toestemming, een verstuurde lead, een
export of een verwijdering, bestaan nog niet, omdat de handelingen zelf nog niet
bestaan. Een logboek dat ze nu al noemde zou een verwerking beschrijven die er
niet is.

Dat logboek heeft geen bewaartermijn, met opzet. Een auditlogboek dat verloopt
is geen auditlogboek. Wat het draagt verliest wel zijn zeggingskracht: zodra het
advies na negentig dagen weg is, wijst het token in het logboek nergens meer
naar, en wat overblijft is een postcodegebied en een tijdstip.

## 3. Waarom, en waarom niet meer

De vier vragen zijn precies wat de simulatie nodig heeft. De postcode kiest de
instralingsreeks, het jaarverbruik schaalt het profiel, en wattpiek en
dakopstelling bepalen de opwek. Er is geen vraag die alleen voor de statistiek
gesteld wordt.

De grondslag hoort bij de verwerkingsverantwoordelijke en staat in hoofdstuk 9.
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
Er wordt dagelijks een dump gemaakt en die dumps worden zeven dagen bewaard, dus
een advies dat de dienst niet meer teruggeeft kan nog ten hoogste een week in een
back-upbestand staan. Drie dingen begrenzen dat, en het zijn eigenschappen van
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

De vraag die de back-up daarmee oproept is niet hoe lang de cijfers in de dienst
leven, maar wie de bestanden kan lezen. Ze worden `0600` geschreven in een map
die het script `0700` aanmaakt, en de controle die de deploy draait weigert een
back-up gezond te noemen als een van beide ruimer staat.

## 5. Wie erbij kan

De database luistert niet naar buiten. Er is geen enkele gepubliceerde poort in
de stack; de tunnelverbinding wordt van binnenuit opgezet. De enige weg naar de
gegevens loopt via de API, en die geeft op een token precies een advies terug.

Op de host kan root bij alles, en dat is de verwerkingsverantwoordelijke.
Toegang tot de host is geen onderwerp van dit document en hoort bij hoofdstuk 9.

Er is geen verwerker. Niets wordt uitbesteed, er draait geen dienst van derden
mee in de stack behalve de tunnelverbinding die het verkeer doorgeeft, en er
gaat geen gegeven naar een advertentie- of analysepartij.

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

## 7. Risico's, en wat ertegen staat

| Risico | Wat ertegen staat |
|---|---|
| Iemand raadt of doorloopt tokens en leest andermans advies | 22 tekens uit een cryptografische bron, en een tempolimiet van 120 leesverzoeken per uur per gehashte identiteit |
| Een deelbare link belandt bij iemand anders, bijvoorbeeld in een doorgestuurd bericht | Dit is inherent aan een link zonder account. De link verloopt na negentig dagen. Wat erachter staat is een postcodegebied en een jaarverbruik, geen naam |
| Het IP-adres van een bezoeker wordt bewaard | Het wordt gehasht voordat het teller wordt, en er is geen tabel met een adresveld |
| De volledige postcode bereikt de dienst | De serializer weigert alles wat geen vier cijfers is, in plaats van af te kappen |
| Een back-upbestand lekt | `0600` in een map `0700`, ten hoogste zeven bestanden, en de deploy weigert door te gaan als een van beide ruimer staat |
| Verwijderde gegevens leven voort in een back-up | Ten hoogste zeven dagen, en de dagelijkse opruiming haalt herleefde rijen na een terugzetting weer weg |
| De opruiming stopt zonder dat iemand het merkt | De deploy draait een controle die rood wordt zodra er iets over datum is, en de timer zelf faalt zichtbaar |
| Een derde partij krijgt het surfgedrag van de bezoeker | Geen enkel verzoek buiten de eigen oorsprong, afgedwongen door een test |
| Het advies wordt gestuurd door een commercieel belang | Geen advertenties, geen leads, geen eigen contract en geen hardwareverkoop. Elke regel die vuurt komt terug in het antwoord, dus een advies is na te lopen |

**Wat hier niet tegen staat.** Er is geen kopie buiten de host, dus een storing
die de machine meeneemt neemt de gegevens en de back-ups mee. Dat is een
beschikbaarheidsrisico en geen vertrouwelijkheidsrisico, en het is opgeschreven
in hoofdstuk 8 van `infra/README.md` in plaats van hier opgelost.

## 8. Wat er verandert bij fase 1 en 2

Dit document beschrijft fase 0.5 en houdt op te kloppen zodra er een account of
een meterkoppeling bestaat. Wat er dan bij komt:

- **Kwartierdata uit de P1-poort.** Dat is de verwerking die dit document in
  hoofdstuk 1 als afwezig aanmerkt en die de afweging omdraait. Daaruit is af te
  leiden wanneer iemand thuis is.
- **Accounts.** Een e-mailadres, een wachtwoord, inlogpogingen, en daarmee de
  gebeurtenissen die het auditlogboek vandaag nog niet kent.
- **Twee aparte toestemmingen**, voor datakoppeling en voor leadgeneratie, geen
  van beide voorgevinkt en elk met een eigen tijdstempel.
- **Een export- en verwijderknop**, die vanaf dat moment moeten werken.

Bij elk van die vier hoort dit document opnieuw geschreven te worden, en op dat
moment is de beoordeling waarschijnlijk wel verplicht.

## 9. Wat bij Stijn ligt

Vier dingen kan dit document niet voor de verwerkingsverantwoordelijke
beslissen.

1. **Of de conclusie in hoofdstuk 1 wordt overgenomen.** De feiten staan er; de
   afweging of artikel 35 van toepassing is, is zijn oordeel.
2. **De grondslag.** Uitvoering van een overeenkomst op verzoek van de betrokkene
   dan wel toestemming, en welke van de twee is een keuze die ook de
   privacyverklaring bepaalt.
3. **De back-upruil uit hoofdstuk 4.** Zeven dagen is een keuze die ik heb
   gemaakt en verantwoord; korter maakt de kopie kleiner en het herstel
   krapper, en alleen het auditlogboek dumpen laat de dienst onherstelbaar.
4. **Toegang tot de host**, en of `web2` ephemeer wordt. Die staat los van dit
   document en is elders opgeschreven.

Er is verder geen privacyverklaring en geen verwerkersregister. Allebei zijn ze
nodig voordat de dienst publiek gaat, en allebei vallen ze buiten wat uit deze
repository te schrijven is.
