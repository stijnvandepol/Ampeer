# Hoe Ampeer rekent

Dit document beschrijft precies hoe wij aan ons antwoord komen, inclusief alles waar we
naast kunnen zitten. Wij vragen je iets te geloven over je eigen huis, dus je mag weten
waarop dat berust. Reken het na en laat het ons weten als je een fout vindt.

Motorversie waarop dit document slaat: 0.1.0.

## Kort samengevat

Wij bouwen uit jouw antwoorden een kunstmatig verbruikspatroon van een heel jaar, in
stapjes van een kwartier, en leggen daar een opwekpatroon van jouw dak naast. Vervolgens
rekenen wij per kwartier uit hoeveel stroom je zelf gebruikt, hoeveel je van het net
haalt en hoeveel je teruglevert. Dat doen wij twee keer: een keer met de regels van nu en
een keer met de regels vanaf 2027. Het verschil is het bedrag dat je ziet.

## 1. Waar de vorm van je verbruik vandaan komt

Wij gebruiken de standaardverbruiksprofielen die in opdracht van NEDU worden gemaakt en
die netbeheerders gebruiken om het verbruik van huishoudens in te schatten. Dat is een
lijst van 35.040 getallen, een voor elk kwartier van het jaar, die samen precies 1
vormen. Jouw jaarverbruik maal zo'n getal geeft je verbruik in dat kwartier.

**De beperking:** zo'n profiel is een gemiddelde over honderdduizenden aansluitingen en
is daardoor glad. Een echt huishouden heeft pieken die het gemiddelde niet heeft, zoals
het moment waarop de waterkoker en de oven tegelijk aanstaan. Voor de vraag hoeveel
stroom je over het jaar zelf gebruikt maakt dat weinig uit. Voor de vraag welk vermogen
je batterij moet hebben maakt het wel uit, en daar zijn wij dus voorzichtiger.

## 2. Wij gebruiken het profiel van huizen zonder zonnepanelen

De profielen bestaan in twee smaken: aansluitingen zonder teruglevering en aansluitingen
met teruglevering. Wij gebruiken die zonder.

Dat lijkt gek, want jij hebt juist wel panelen. De reden is dat het profiel van een
aansluiting met teruglevering de netto afname van het net is, dus daar is de zon al van
afgetrokken. Zouden wij dat gebruiken en er onze eigen opwekberekening bij optellen, dan
telden wij de zon dubbel.

**De beperking:** mensen die zonnepanelen kopen zijn geen willekeurige greep uit
Nederland. Ze wonen vaker in een eengezinswoning, hebben vaker een elektrische auto en
gebruiken gemiddeld meer stroom. Ons basisprofiel is dus systematisch net niet het
profiel van onze eigen gebruiker. Zodra genoeg mensen hun meter koppelen, ijken wij het
model daarop en verdwijnt deze afwijking. Tot die tijd staat hij hier.

## 3. Overdag thuis of niet

Dit is de grootste enkele factor in hoeveel van je eigen stroom je gebruikt, en tegelijk
het stuk waar wij het meest een keuze maken en het minst iets meten.

Wij nemen aan dat er per dag ongeveer 1 kWh aan verplaatsbaar verbruik is: de wasmachine,
de vaatwasser, de droger, de boiler. Als er overdag iemand thuis is, verhuist dat blok van
de avond naar het midden van de dag. Als er niemand is, de andere kant op. Het is een
verschuiving en geen vermeerdering: het dagtotaal blijft gelijk, want iemand die thuis
werkt gebruikt niet meer stroom, alleen op een ander moment.

**Waarom 1 kWh:** bij die waarde scheelt overdag thuis zijn ongeveer 13 procentpunt
zelfconsumptie, wat past bij de tien tot vijftien procentpunt die in de literatuur en in
de praktijk genoemd wordt. Bij 1,75 kWh kwam ons model op 22 procentpunt uit en dat is te
veel. In de bandbreedte varieren wij deze aanname tussen 0,5 en 2,0 kWh per dag.

**De beperking:** dit getal is aangenomen en niet gemeten. Het is de aanname waar wij het
minst zeker over zijn.

## 4. De elektrische auto

Wij kennen drie manieren van laden en vragen je welke bij je past:

- **'s Nachts**, op een laag tarief. Dit doet niets voor je zelfconsumptie.
- **Bij thuiskomst**, tussen vijf en negen 's avonds. Ook grotendeels buiten de zon om.
- **Overdag op je eigen overschot.**

**Belangrijk:** in het derde geval laden wij het deel dat de zon niet haalt alsnog bij
vanaf het net, 's nachts. Je auto moet immers rijden, ook in november. Zonder die
bijlading zou ons model doen alsof je in een sombere week minder kilometers maakt, en dat
zou zonneladen mooier voorstellen dan het is.

**De beperking:** deze drie gedragingen zijn stereotypen die wij zelf hebben opgesteld.
Ze komen niet uit een meting van hoe Nederlanders werkelijk laden.

## 5. De warmtepomp

De warmtevraag volgt het aantal graaduren dat het buiten kouder is dan 15 graden. Het
stroomverbruik is die warmtevraag gedeeld door het rendement, en dat rendement daalt
naarmate het kouder wordt. Dat laatste is belangrijker dan het lijkt: met een vast
rendement zou je winterverbruik te laag uitkomen, precies in de maanden waarin je geen
opwek hebt.

De buitentemperatuur komt uit dezelfde bron als de instraling, dus voor jouw locatie en
dezelfde uren.

## 6. De opwek van je dak

Wij rekenen die niet zelf uit. Wij vragen hem op bij PVGIS, de rekentool van het
Gemeenschappelijk Centrum voor Onderzoek van de Europese Commissie, op basis van echte
instralingsmetingen voor jouw postcodegebied, jouw dakrichting en jouw hellingshoek.

Dat is een bewuste keuze. Wij hebben het eerst zelf uitgerekend uit de instralingsgetallen
en kwamen toen 9,8 procent te hoog uit, omdat wij de temperatuur van de panelen, de
weerkaatsing en de kleurgevoeligheid niet meenamen. PVGIS doet dat wel. Wij vragen de
opbrengst per kWp op en passen daarna alleen nog drie eenvoudige factoren toe: hoeveel
wattpiek je hebt, het systeemverlies (standaard 14 procent, voor omvormer, kabels en
vuil) en veroudering van de panelen (een half procent per jaar, maximaal twintig procent).

**De beperking:** wij weten niets van jouw schaduw. Een boom, een dakkapel of het huis
van de buren kan zomaar tien procent schelen en daar vragen wij niet naar.

## 7. Het jaar waarop wij rekenen

Wij rekenen op het verbruikspatroon van het meest recente beschikbare profieljaar en op
het weer van een recent weerjaar, met de tarieven van 2027 eroverheen. Die twee jaren
hoeven niet hetzelfde te zijn en worden op kalenderdatum uitgelijnd. Zonneschijn trekt
zich niets aan van of het maandag of zondag is, dus dat kan; jouw verbruik doet dat wel,
en dat volgt het profieljaar.

Wij zetten er altijd bij welke jaren wij gebruikt hebben.

**Een detail voor wie het nauw neemt:** de opwek komt per uur binnen en ons model rekent
per kwartier. Wij interpoleren daartussen. PVGIS zet zijn uurwaarde op tien over het uur
en wij behandelen hem als het gemiddelde van dat uur, wat een verschuiving van twintig
minuten geeft. Dat is verwaarloosbaar naast de andere onzekerheden, maar het staat hier.

## 8. Een batterij, en waarom onze getallen lager uitvallen

Wij rekenen een batterij door met laadvermogen, ontlaadvermogen, bruikbare diepte en
rendement. Bij een rendement van 90 procent voor een volledige cyclus verlies je aan
beide kanten ongeveer 5 procent.

Als wij een batterij laten handelen op de stroombeurs, mag hij alleen vooruitkijken naar
prijzen die op dat moment ook echt bekend zijn. Die worden rond 13:00 gepubliceerd voor de
dag erna, dus een dag vooruit mag en verder niet.

Dat klinkt als een detail en het is het belangrijkste getal in het hele hoofdstuk. Een
simulatie die het hele jaar aan prijzen vooraf kent, koopt altijd op het laagste punt en
verkoopt op het hoogste, en komt dan uit op een rendement dat in de praktijk niet bestaat.
Zo worden optimistische offertes gemaakt. Onze batterij is net zo slim als een echte
batterij, en geen haar slimmer.

Daar komt bij dat een batterij bij een prijsverschil van acht cent en een rendement van 90
procent praktisch niets verdient. Ook dat laten wij gewoon zien.

## 9. De bandbreedte

Wij tonen nooit een enkel getal. De bandbreedte die je ziet is gemeten en niet verzonnen.

Wij draaien de hele berekening 243 keer, met elke combinatie van een lage, een middelste
en een hoge waarde voor de vijf aannames waarvan wij weten dat wij ze niet zeker weten: je
jaarverbruik, de omvang van het verplaatsbare blok, het systeemverlies, de
terugleververgoeding in 2027 en de terugleverkosten. De uitkomsten daarvan vormen de band.

Die laatste is er later bij gekomen en dat had eerder gemoeten. De terugleverkosten lopen
van 4,46 tot 11,50 cent per kWh, een factor 2,6, en dat is de breedste spreiding van alles
wat in deze berekening zit. Zolang die niet meevariëerde, zweeg de band juist over de
meest onzekere post. De band werd daardoor ongeveer anderhalf keer zo breed, en dat is
geen verslechtering maar een eerlijker beeld.

Dat is bewust zo gedaan. Zouden wij die aannames een voor een verschuiven en de rest op
hun middenwaarde laten staan, dan bereikt de band zijn eigen hoeken nooit en ziet het er
veel zekerder uit dan het is.

## 10. Waar onze tariefgetallen vandaan komen

Wij werken niet met een lijst van leveranciers. Wij gebruiken landelijke waarden met een
lage, een middelste en een hoge waarde erbij, allemaal op dezelfde dag opgezocht, en die
datum staat in de code naast het getal.

Dit zijn ze, opgezocht op 20 augustus 2026:

| Wat | Laag | Midden | Hoog |
|---|---|---|---|
| Stroomprijs per kWh, alles inbegrepen | 0,22 | 0,26 | 0,30 |
| Bruto terugleververgoeding, vast contract | 0,050 | 0,065 | 0,077 |
| Terugleverkosten per teruggeleverde kWh | 0,0446 | 0,0625 | 0,115 |
| Netto terugleververgoeding, dynamisch contract | 0,05 | 0,06 | 0,07 |
| Thuisbatterij per kWh capaciteit, geplaatst | 450 | 675 | 900 |

**Waarom het midden van de terugleverkosten geen rekenkundig midden is.** Bij alle andere
rijen staat in het midden gewoon het midden van het bereik. Bij de terugleverkosten niet,
en dat is met opzet.

Namen wij daar wel het rekenkundige midden, 0,075, dan kwam de netto vergoeding in het
midden uit op min 1,0 cent per kWh. Dat is een bedrag dat geen enkele leverancier
aanbiedt. De gepubliceerde nettocijfers lopen van min 7,43 tot plus 1,19 cent en de
meeste grote leveranciers zitten rond plus 0,25 cent. Het midden van twee los gekozen
middens is geen waarneming.

Daarom staat het midden van de kosten op 0,0625, precies zo dat de netto uitkomst gelijk
is aan wat er werkelijk wordt aangeboden. Het waargenomen bereik bepaalt nog steeds de
band, dus de spreiding verandert niet.

Die correctie maakt ons eigen verhaal zwakker: het bedrag dat wij bovenaan tonen daalde
voor het referentiehuishouden van 700 naar 665 euro. Dat is precies de reden dat wij hem
gemaakt hebben. Een fout die je eigen boodschap versterkt, is de fout die het minst snel
iemand opvalt.

**Waarom geen lijst per leverancier.** Zo'n lijst moet met de hand worden bijgehouden.
Gaat hij verouderen, dan geeft hij geen foutmelding maar gewoon een verkeerd getal, en jij
kunt niet zien dat dat gebeurd is. Een bandbreedte kan niet op die manier stilletjes
verouderen: hij draagt zijn eigen spreiding met zich mee, hij draagt de datum met zich mee
en de 243 doorrekeningen variëren eroverheen. Bovendien lopen de leveranciers zo ver uiteen
dat een landelijk midden met een band je eerlijker informeert dan een precies getal dat
toevallig van de verkeerde leverancier komt.

Heb je je eigen contract bij de hand, vul dan je eigen bedragen in. Deze getallen zijn wat
wij gebruiken als je dat niet doet.

## 11. De terugleververgoeding is lager dan vaak gedacht

Je leest vaak dat je na 2027 nog drie tot acht cent per teruggeleverde kWh krijgt. Dat is
de bruto vergoeding. Daar gaan de terugleverkosten nog vanaf, en die rekenen leveranciers
per teruggeleverde kWh en niet als een vast bedrag per jaar.

Trek je die er wel vanaf, dan houd je op een vast contract dit over per teruggeleverde
kWh:

- laag: 0,050 min 0,0446 is plus 0,5 cent
- midden: 0,065 min 0,0625 is plus 0,25 cent
- hoog: 0,077 min 0,115 is min 3,8 cent

Aan de bovenkant is dat dus negatief: dan kost terugleveren je geld in plaats van dat het
iets oplevert. Over alle combinaties heen loopt het van ongeveer min 6,5 cent tot plus 3,2
cent, en dat strookt met de gepubliceerde nettocijfers, die van min 7,43 tot plus 1,19
cent lopen.

Waar het op neerkomt: waar je nu ongeveer 27 cent bespaart op elke kWh die je zelf
gebruikt in plaats van teruglevert, wordt dat vanaf 2027 rond de 26 cent, terwijl de kWh
die je wél teruglevert vrijwel niets meer opbrengt. Het verschil zit niet in wat zelf
gebruiken oplevert, maar in wat terugleveren stopt op te leveren.

Dat verandert het hele advies, en precies daarom staan verschuiven en zelf verbruiken bij
ons bovenaan, ook al verdienen wij daar niets aan.

Op een dynamisch contract ligt het anders. Daar wordt met het uurtarief afgerekend en
zitten er geen aparte terugleverkosten op, dus de netto vergoeding blijft daar 5 tot 7
cent en dus positief.

## 12. Het batterijadvies heeft een grovere band dan het bedrag bovenaan

Het bedrag bovenaan komt uit 243 doorrekeningen, met elke combinatie van laag, midden en
hoog voor de vijf aannames uit hoofdstuk 9. De capaciteitscurve van de batterij draaien
wij niet 243 keer maar één keer, op de middenwaarden. Dat is een bewuste keuze om de
berekening snel te houden.

Gevolg: de marge die je bij de terugverdientijd ziet komt alleen uit de prijs van de
batterij zelf, die 450 tot 900 euro per kWh loopt. De onzekerheid over je jaarverbruik,
het systeemverlies en de terugleververgoeding zit er niet in. De echte marge rond die
terugverdientijd is dus breder dan de marge die je ziet, en niet smaller. Wij zeggen dat
er liever bij dan dat wij een cijfer achter de komma suggereren dat er niet is.

Twaalf jaar is onze grens, omdat er doorgaans tien jaar garantie op een batterij zit:
verdien je hem pas daarna terug, dan gok je erop dat hij langer meegaat dan de garantie
die je erop krijgt.

## 13. Wij zeggen niet alleen ja of nee over een batterij

Een thuisbatterij kost tussen de 450 en 900 euro per kWh geplaatst. Dat is een factor
twee, en bij de meeste huishoudens ligt de terugverdientijd ergens ín die band: aan de
onderkant van de prijs haalt hij de twaalf jaar wel, aan de bovenkant niet.

Wij hebben dat eerst als één ja of nee gepresenteerd, op basis van de middelste prijs. Dat
was fout. Een huishouden met een terugverdientijd van 11,8 jaar kreeg "koop er een",
terwijl bij de bovenkant van diezelfde band 15,8 jaar hoorde. Eén getal uit een band besliste
de zwaarste zin die wij uitspreken.

Nu zijn er drie uitkomsten:

- **De moeite waard**, als hij zichzelf zelfs bij de hoogste prijs binnen twaalf jaar
  terugverdient
- **Niet de moeite waard**, als hij dat bij de middelste prijs al niet doet
- **Het hangt af van wat je betaalt**, voor alles daartussen

In dat laatste geval noemen wij de prijs waarbij het omslaat. Blijf je onder dat bedrag
per geplaatste kWh, dan verdient de batterij zichzelf binnen twaalf jaar terug; kom je
erboven, dan niet. Dat is het enige getal in ons hele advies waar je direct iets mee kunt,
want anders dan de terugleververgoeding van 2027 is de prijs van een batterij gewoon op te
vragen.

Wat dat oplevert, mag je weten: van de zes huishoudens die wij als voorbeeld doorrekenen,
krijgt er niet één een onvoorwaardelijk "koop er een". Daarvoor zou de omslagprijs boven
de 900 euro per kWh moeten liggen en het meest extreme geval haalt 833. Bij de prijzen van
vandaag en de tarieven die leveranciers voor 2027 hebben gepubliceerd, is een batterij die
onmiskenbaar de moeite waard is dus zeldzaam.

## 14. Wat de gratis routes opleveren, rekenen wij door in plaats van te schatten

Bij elk advies dat je niets kost staat een bedrag. Dat bedrag is niet met een formule
geschat maar doorgerekend: wij draaien je hele jaar opnieuw door dezelfde simulatie, met
die ene verandering erin, en kijken wat je jaarrekening dan doet.

Dat is niet alleen nauwkeuriger, het maakt de bedragen ook optelbaar. Wij passen de
adviezen op elkaar toe: eerst je apparaten verschuiven, dan je auto op je eigen overschot
laden, dan pas het contract. Elke stap wordt gemeten bovenop de vorige, dus geen enkele
kilowattuur wordt twee keer geteld.

De eerste versie deed dat niet. Drie adviezen schatten elk hun eigen bedrag uit dezelfde
zonnestroom, en de bedragen bij elkaar optellen gaf dus een besparing die niet bestond.

Het heeft ook gevolgen voor het batterijadvies, en dat is de belangrijkste: wij kijken naar
de teruglevering die je nog **overhoudt** nadat je de gratis dingen gedaan hebt. Een
huishouden dat zijn auto overdag op eigen stroom laadt, houdt vaak zo weinig over dat een
batterij niets meer te bewaren heeft. Eerder kreeg zo iemand alsnog een batterijadvies,
voor kilowatturen die het advies erboven net had geleerd zelf te gebruiken.

## 15. Wat wij niet weten

Voor de volledigheid, op een rij:

- Wij kennen je schaduw niet.
- Wij kennen je werkelijke apparaten niet, alleen een gemiddelde vorm.
- Wij weten niet wat de terugleververgoeding in 2027 werkelijk wordt. Niemand weet dat.
- Wij rekenen op een historisch jaar aan weer en verbruik, en volgend jaar is anders.
- Ons basisprofiel is dat van huizen zonder zonnepanelen.
- De omvang van het verplaatsbare blok is aangenomen.

Koppel je je meter, dan vervallen de eerste twee en wordt de vijfde en zesde gekalibreerd
op jouw eigen gegevens. Daarom is dat antwoord scherper, en daarom zeggen wij er eerlijk
bij welk niveau je nu hebt.
