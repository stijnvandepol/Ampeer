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

Wij draaien de hele berekening 81 keer, met elke combinatie van een lage, een middelste en
een hoge waarde voor de vier aannames waarvan wij weten dat wij ze niet zeker weten: je
jaarverbruik, de omvang van het verplaatsbare blok, het systeemverlies en de
terugleververgoeding in 2027. De uitkomsten daarvan vormen de band.

Dat is bewust zo gedaan. Zouden wij die aannames een voor een verschuiven en de rest op
hun middenwaarde laten staan, dan bereikt de band zijn eigen hoeken nooit en ziet het er
veel zekerder uit dan het is.

## 10. Wat wij niet weten

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
