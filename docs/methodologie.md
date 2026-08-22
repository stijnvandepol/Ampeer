# Hoe Ampeer rekent

Dit document beschrijft precies hoe wij aan ons antwoord komen, inclusief alles waar we
naast kunnen zitten. Wij vragen u iets te geloven over uw eigen huis, dus u mag weten
waarop dat berust. Reken het na en laat het ons weten als u een fout vindt.

Motorversie waarop dit document slaat: 0.1.0.

## Kort samengevat

Wij bouwen uit uw antwoorden een kunstmatig verbruikspatroon van een heel jaar, in
stapjes van een kwartier, en leggen daar een opwekpatroon van uw dak naast. Vervolgens
rekenen wij per kwartier uit hoeveel stroom u zelf gebruikt, hoeveel u van het net
haalt en hoeveel u teruglevert. Dat doen wij twee keer: een keer met de regels van nu en
een keer met de regels vanaf 2027. Het verschil is het bedrag dat u ziet.

## 1. Waar de vorm van uw verbruik vandaan komt

Wij gebruiken de standaardverbruiksprofielen die in opdracht van NEDU worden gemaakt en
die netbeheerders gebruiken om het verbruik van huishoudens in te schatten. Dat is een
lijst van 35.040 getallen, een voor elk kwartier van het jaar, die samen precies 1
vormen. Uw jaarverbruik maal zo'n getal geeft uw verbruik in dat kwartier.

**De beperking:** zo'n profiel is een gemiddelde over honderdduizenden aansluitingen en
is daardoor glad. Een echt huishouden heeft pieken die het gemiddelde niet heeft, zoals
het moment waarop de waterkoker en de oven tegelijk aanstaan. Voor de vraag hoeveel
stroom u over het jaar zelf gebruikt maakt dat weinig uit. Voor de vraag welk vermogen
uw batterij moet hebben maakt het wel uit, en daar zijn wij dus voorzichtiger.

## 2. Wij gebruiken het profiel van huizen zonder zonnepanelen

De profielen bestaan in twee smaken: aansluitingen zonder teruglevering en aansluitingen
met teruglevering. Wij gebruiken die zonder.

Dat lijkt gek, want u hebt juist wel panelen. De reden is dat het profiel van een
aansluiting met teruglevering de netto afname van het net is, dus daar is de zon al van
afgetrokken. Zouden wij dat gebruiken en er onze eigen opwekberekening bij optellen, dan
telden wij de zon dubbel.

**Welke van de drie wij nemen.** Voor huishoudens bestaan er drie van deze profielen:
een voor aansluitingen met een enkel tarief en twee voor aansluitingen met een dag- en
nachttarief. Wij gebruiken altijd die met een enkel tarief, ook als u een dubbeltarief
hebt, want de rekenmachine vraagt niet naar uw meter.

Wij hebben nagerekend wat dat scheelt in de vorm die er hier toe doet, namelijk hoeveel
van uw jaarverbruik in het zonnevenster valt. Tussen tien uur en vier uur ligt 27,05
procent bij het profiel dat wij gebruiken, tegen 26,63 en 27,95 procent bij de twee
andere. Ruim een procentpunt dus, en minder dan u zou verwachten van een tarief dat
mensen juist naar de nacht duwt.

**De beperking:** mensen die zonnepanelen kopen zijn geen willekeurige greep uit
Nederland. Ze wonen vaker in een eengezinswoning, hebben vaker een elektrische auto en
gebruiken gemiddeld meer stroom. Ons basisprofiel is dus systematisch net niet het
profiel van onze eigen gebruiker. Zodra genoeg mensen hun meter koppelen, ijken wij het
model daarop en verdwijnt deze afwijking. Tot die tijd staat hij hier.

## 3. Overdag thuis of niet

Dit is de grootste enkele factor in hoeveel van uw eigen stroom u gebruikt, en tegelijk
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
minst zeker over zijn. En in de eerste versie van de rekenmachine vragen wij helemaal niet
of er overdag iemand thuis is: dan nemen wij aan van niet. Hoofdstuk 17 zet erbij wat dat
met uw antwoord doet en welke kant het op duwt.

## 4. De elektrische auto

Wij kennen drie manieren van laden en vragen u welke bij u past:

- **'s Nachts**, op een laag tarief. Dit doet niets voor uw zelfconsumptie.
- **Bij thuiskomst**, tussen vijf en negen 's avonds. Ook grotendeels buiten de zon om.
- **Overdag op uw eigen overschot.**

**Belangrijk:** in het derde geval laden wij het deel dat de zon niet haalt alsnog bij
vanaf het net, 's nachts. Uw auto moet immers rijden, ook in november. Zonder die
bijlading zou ons model doen alsof u in een sombere week minder kilometers maakt, en dat
zou zonneladen mooier voorstellen dan het is.

**Hoe groot die auto is, en wat wij daarover niet weten.** Wij vragen wel of u een auto
hebt en hoe u laadt, maar niet hoeveel u rijdt. Wij rekenen met 12.000 kilometer per jaar
en 18 kWh per 100 kilometer, dus met 2160 kWh aan laden per jaar, en met een laadpunt van
3,7 kilowatt. Ter vergelijking: het huishouden waarmee wij in hoofdstuk 17 rekenen gebruikt
zelf 3500 kWh. De auto is dus geen detail in het antwoord.

Die drie getallen zijn aannames van ons, net als de gedragingen hierboven. Ze komen niet
uit een meting en wij vragen ze niet uit. Rijdt u veel meer of veel minder dan 12.000
kilometer, dan klopt het deel van het antwoord dat over uw auto gaat navenant minder, en
wij hebben geen manier om dat te merken.

**De beperking:** deze drie gedragingen zijn stereotypen die wij zelf hebben opgesteld.
Ze komen niet uit een meting van hoe Nederlanders werkelijk laden. En in de eerste versie
van de rekenmachine vragen wij niet naar een auto: dan rekenen wij alsof u er geen hebt.
Zie hoofdstuk 17.

## 5. De warmtepomp

De warmtevraag volgt het aantal graaduren dat het buiten kouder is dan 15 graden. Het
stroomverbruik is die warmtevraag gedeeld door het rendement, en dat rendement daalt
naarmate het kouder wordt. Dat laatste is belangrijker dan het lijkt: met een vast
rendement zou uw winterverbruik te laag uitkomen, precies in de maanden waarin u geen
opwek hebt.

De getallen erachter: wij rekenen met een rendement van 3,5 bij 7 graden buiten, dat per
graad kouder met 0,06 daalt. Ook dat zijn aannames van ons en geen meting aan uw pomp.
Een pomp die daar bovenzit verbruikt minder dan wij tonen, een oudere pomp meer, en wij
vragen niet naar het merk of het bouwjaar.

De buitentemperatuur komt uit dezelfde bron als de instraling, dus voor uw locatie en
dezelfde uren.

## 6. De opwek van uw dak

Wij rekenen die niet zelf uit. Wij vragen hem op bij PVGIS, de rekentool van het
Gemeenschappelijk Centrum voor Onderzoek van de Europese Commissie, op basis van echte
instralingsmetingen voor uw postcodegebied, uw dakrichting en uw hellingshoek.

Dat is een bewuste keuze. Wij hebben het eerst zelf uitgerekend uit de instralingsgetallen
en kwamen toen 9,8 procent te hoog uit, omdat wij de temperatuur van de panelen, de
weerkaatsing en de kleurgevoeligheid niet meenamen. PVGIS doet dat wel. Wij vragen de
opbrengst per kWp op en passen daarna alleen nog drie eenvoudige factoren toe: hoeveel
wattpiek u hebt, het systeemverlies (standaard 14 procent, voor omvormer, kabels en
vuil) en veroudering van de panelen (een half procent per jaar, maximaal twintig procent).

**Die derde factor gebruiken wij nu nooit, en dat hoort u te weten.** Veroudering kunnen
wij alleen toepassen als wij weten uit welk jaar uw panelen komen, en de rekenmachine
vraagt dat niet. Dus rekenen wij op panelen die nieuw zijn, hoe oud die van u ook zijn.
Dat duwt dezelfde kant op als de andere dingen die wij invullen: nieuwe panelen leveren
meer op, meer opwek betekent meer teruglevering, en meer teruglevering betekent een groter
bedrag bovenaan. Hoeveel dat op uw rekening scheelt hangt van uw huis af, maar de opwek
zelf is exact: panelen van tien jaar oud zouden wij op vijf procent minder opwek rekenen
en panelen van twintig jaar oud op tien procent minder. Hoofdstuk 17 zet dit bij de
andere aannames.

**Als PVGIS niet bereikbaar is.** Dat gebeurt, en dan weigeren wij geen antwoord maar
rekenen wij met een eigen tabel. Die tabel is een gemiddelde van negen weerjaren, 2015 tot
en met 2023, voor een dak van 35 graden op het zuiden in Uden, en komt uit op 1221 kWh per
kWp voor aftrek van systeemverlies.

Dat is een slechter antwoord en het staat erbij in uw antwoord zelf, niet alleen hier. Uw
dakrichting en uw hellingshoek rekenen wij gewoon door; wat de tabel niet kent is uw
postcodegebied. Hij geeft voor elke postcode in Nederland precies dezelfde reeks terug, en
dat is nu juist waar wij PVGIS voor gebruiken. Bovendien is de vorm van een dag erin een
vaste halve sinus in plaats van de echte stand van de zon, dus winterdagen zijn er te lang
en zomerdagen te kort.

**Hoeveel dat scheelt.** Gemeten op 21 augustus 2026, op ons referentiehuishouden van
hoofdstuk 17 met dezelfde verbruiksvorm, alleen de opwekbron verschillend:

| Postcode | Met de tabel | Met PVGIS | Verschil |
|---|---|---|---|
| 5401, Uden | 632,05 | 668,66 | 5,5 procent lager |
| 9711, Groningen | 632,05 | 651,24 | 2,9 procent lager |
| 4331, Middelburg | 632,05 | 709,55 | 10,9 procent lager |

Drie postcodes, door ons gekozen op afstand tot Uden, en geen steekproef. Wat er wel uit
te lezen valt: de tabel geeft in alle drie de gevallen hetzelfde bedrag, want hij weet niet
waar u woont, en hij zit er in alle drie dezelfde kant op naast. Het bedrag valt dan lager
uit dan het is. In Middelburg het meest, omdat daar meer zon valt dan het landelijke
gemiddelde dat in deze tabel zit.

Ook in Uden zelf scheelt het nog vijf procent, en dat is geen fout in de tabel maar een
tweede verschil: de tabel middelt negen weerjaren en PVGIS is hier om een enkel jaar
gevraagd. De tabel bestaat om u een antwoord te kunnen geven wanneer PVGIS eruit ligt, en
voor niets anders. Vraag het advies later opnieuw op voor een scherper getal.

**De beperking:** wij weten niets van uw schaduw. Een boom, een dakkapel of het huis
van de buren kan zomaar tien procent schelen en daar vragen wij niet naar.

## 7. Het jaar waarop wij rekenen

Wij rekenen op het verbruikspatroon van het meest recente beschikbare profieljaar en op
het weer van een recent weerjaar, met de tarieven van 2027 eroverheen. Die twee jaren
hoeven niet hetzelfde te zijn en worden op kalenderdatum uitgelijnd. Zonneschijn trekt
zich niets aan van of het maandag of zondag is, dus dat kan; uw verbruik doet dat wel,
en dat volgt het profieljaar.

Wij zetten er altijd bij welke jaren wij gebruikt hebben.

**Een detail voor wie het nauw neemt:** de opwek komt per uur binnen en ons model rekent
per kwartier. Wij interpoleren daartussen. PVGIS zet zijn uurwaarde op tien over het uur
en wij behandelen hem als het gemiddelde van dat uur, wat een verschuiving van twintig
minuten geeft. Dat is verwaarloosbaar naast de andere onzekerheden, maar het staat hier.

## 8. Een batterij, en waarom onze getallen lager uitvallen

Wij rekenen een batterij door met laadvermogen, ontlaadvermogen, bruikbare diepte en
rendement. Bij een rendement van 90 procent voor een volledige cyclus verliest u aan
beide kanten ongeveer 5 procent. De bruikbare diepte stellen wij op 90 procent: van een
batterij van 10 kWh rekenen wij dus met 9 kWh, want een batterij die helemaal leeg en
helemaal vol gaat slijt sneller en de meeste systemen staan dat niet toe.

Het laad- en ontlaadvermogen leiden wij af uit de capaciteit: de helft ervan in kilowatt,
dus 5 kW bij een batterij van 10 kWh. Dat is ongeveer wat thuisbatterijen halen. Wij
hebben nagerekend wat er gebeurt als u dat verandert, en het antwoord is: niets. Tussen
0,3 en 1,0 keer de capaciteit beweegt onze uitkomst op de voorbeeldhuishoudens niet, omdat
een overschot dat een trage batterij om twaalf uur niet kan opnemen er om een uur nog
steeds is. Wij zetten het er toch bij, zodat het zichtbaar is op de dag dat het wel gaat
uitmaken.

**Wat onze batterij niet doet.** In een antwoord van Ampeer slaat een batterij alleen uw
eigen overschot op. Hij laadt nooit stroom van het net in om die later duurder te
verkopen, en hij handelt niet op de stroombeurs. Onze rekenmotor kan dat wel, en de regels
daarvoor staan hieronder, maar de rekenmachine kiest die stand niet en levert er ook geen
prijzen voor aan. Wij zeggen dat erbij omdat een batterij die handelt in verkooppraatjes
vaak het interessantste getal oplevert, en dat getal zit niet in ons antwoord.

Zouden wij een batterij laten handelen op de stroombeurs, dan mag hij alleen vooruitkijken
naar prijzen die op dat moment ook echt bekend zijn. Die worden rond 13:00 gepubliceerd
voor de dag erna, dus een dag vooruit mag en verder niet.

Dat klinkt als een detail en het is het belangrijkste getal in het hele hoofdstuk. Een
simulatie die het hele jaar aan prijzen vooraf kent, koopt altijd op het laagste punt en
verkoopt op het hoogste, en komt dan uit op een rendement dat in de praktijk niet bestaat.
Zo worden optimistische offertes gemaakt. Onze batterij is net zo slim als een echte
batterij, en geen haar slimmer.

Daar komt bij dat een batterij bij een prijsverschil van acht cent en een rendement van 90
procent praktisch niets verdient. Ook dat laten wij gewoon zien.

## 9. De bandbreedte

Wij tonen nooit een enkel getal. De bandbreedte die u ziet is gemeten en niet verzonnen.
Dit hoofdstuk gaat over het bedrag bovenaan; hoofdstuk 12 legt uit dat de marge om de
andere bedragen op een andere manier gemeten is en daarom ook anders heet.

Wij draaien de hele berekening 243 keer, met elke combinatie van een lage, een middelste
en een hoge waarde voor de vijf aannames waarvan wij weten dat wij ze niet zeker weten: uw
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
gemaakt hebben. Een fout die uw eigen boodschap versterkt, is de fout die het minst snel
iemand opvalt.

**Waarom geen lijst per leverancier.** Zo'n lijst moet met de hand worden bijgehouden.
Gaat hij verouderen, dan geeft hij geen foutmelding maar gewoon een verkeerd getal, en u
kunt niet zien dat dat gebeurd is. Een bandbreedte kan niet op die manier stilletjes
verouderen: hij draagt zijn eigen spreiding met zich mee, hij draagt de datum met zich mee
en de 243 doorrekeningen variëren eroverheen. Bovendien lopen de leveranciers zo ver uiteen
dat een landelijk midden met een band u eerlijker informeert dan een precies getal dat
toevallig van de verkeerde leverancier komt.

Hebt u uw eigen contract bij de hand, vul dan uw eigen bedragen in. Deze getallen zijn wat
wij gebruiken als u dat niet doet.

## 11. De terugleververgoeding is lager dan vaak gedacht

U leest vaak dat u na 2027 nog drie tot acht cent per teruggeleverde kWh krijgt. Dat is
de bruto vergoeding. Daar gaan de terugleverkosten nog vanaf, en die rekenen leveranciers
per teruggeleverde kWh en niet als een vast bedrag per jaar.

Trekt u die er wel vanaf, dan houdt u op een vast contract dit over per teruggeleverde
kWh:

- laag: 0,050 min 0,0446 is plus 0,5 cent
- midden: 0,065 min 0,0625 is plus 0,25 cent
- hoog: 0,077 min 0,115 is min 3,8 cent

Aan de bovenkant is dat dus negatief: dan kost terugleveren uw geld in plaats van dat het
iets oplevert. Over alle combinaties heen loopt het van ongeveer min 6,5 cent tot plus 3,2
cent, en dat strookt met de gepubliceerde nettocijfers, die van min 7,43 tot plus 1,19
cent lopen.

Waar het op neerkomt: waar u nu ongeveer 27 cent bespaart op elke kWh die u zelf
gebruikt in plaats van teruglevert, wordt dat vanaf 2027 rond de 26 cent, terwijl de kWh
die u wél teruglevert vrijwel niets meer opbrengt. Het verschil zit niet in wat zelf
gebruiken oplevert, maar in wat terugleveren stopt op te leveren.

Dat verandert het hele advies, en precies daarom staan verschuiven en zelf verbruiken bij
ons bovenaan, ook al verdienen wij daar niets aan.

Op een dynamisch contract ligt het anders. Daar wordt met het uurtarief afgerekend en
zitten er geen aparte terugleverkosten op, dus de netto vergoeding blijft daar 5 tot 7
cent en dus positief.

## 12. Twee soorten band, en ze heten niet hetzelfde

Er staan twee soorten marge in uw advies en ze betekenen niet hetzelfde. Dat is niet
altijd zo geweest: tot 21 augustus 2026 heetten ze allebei p10, p50 en p90, alsof het
allebei percentielen waren. Dat was er één te veel.

**Het bedrag bovenaan** komt uit 243 doorrekeningen, met elke combinatie van laag, midden
en hoog voor de vijf aannames uit hoofdstuk 9. De p10 en de p90 die u daar ziet zijn
echte percentielen: van die 243 uitkomsten ligt tien procent onder de p10 en tien procent
boven de p90. Er staat bij hoeveel doorrekeningen het waren.

**Alle andere bedragen** in uw advies, dus wat een gratis stap oplevert, wat een batterij
per jaar bespaart, de terugverdientijd en de omslagprijs, zijn geen percentielen. Wij
rekenen die door op drie tariefniveaus, laag, midden en hoog, en tonen de laagste, de
middelste en de hoogste uitkomst. Dat zijn drie doorgerekende gevallen en geen verdeling.
Ze heten daarom laag, midden en hoog en niet p10, p50 en p90, want een percentiel
suggereert dat wij weten hoe waarschijnlijk de uiteinden zijn en dat weten wij niet.

Dat kan zo goedkoop omdat een tarief niet verandert waar een kilowattuur heen gaat, alleen
wat het waard is. Wij hoeven het jaar dus niet opnieuw te simuleren om het opnieuw te
kunnen beprijzen.

**Wat er niet in meebeweegt.** De capaciteitscurve van de batterij draaien wij niet 243
keer maar één keer per tariefniveau, op de middenwaarden van de rest. Uw jaarverbruik, de
omvang van het verplaatsbare blok en het systeemverlies staan daarbij stil. Die drie staan
met naam en toenaam in het antwoord zelf, bij elke band, onder het kopje wat er vastgezet
is. De echte marge is dus breder dan de marge die u ziet, en nooit smaller.

**Wat er wel in meebeweegt.** Bij de terugverdientijd zijn dat de prijs van de batterij,
die 450 tot 900 euro per kWh loopt, én de tarieven, want wat een batterij bespaart hangt
af van wat de kilowattuur die u niet meer teruglevert had opgebracht. Dat waren tot 21
augustus 2026 alleen de batterijprijzen. De gunstige kant van die oude band betekende
"terugverdientijd bij de goedkoopste offerte in de markt, met tarieven die precies
uitkomen zoals wij aannemen", en dat is de kant die de batterij mooier maakt. Bij ons
referentiehuishouden liep die band van 11,2 tot 22,4 jaar en nu van 9,7 tot 26,3. Het
midden, 16,8 jaar, veranderde niet en er is dus ook geen advies van omgeslagen.

Twaalf jaar is onze grens, omdat er doorgaans tien jaar garantie op een batterij zit:
verdient u hem pas daarna terug, dan gokt u erop dat hij langer meegaat dan de garantie
die u erop krijgt.

## 13. Wanneer wij iets adviseren

Bij elk antwoord staat welke regels gevuurd hebben. Dat is alleen een verklaring
als u er ook bij kunt lezen wat die regels toetsen, anders is het een naam.

| Wat wij zeggen | Wanneer |
|---|---|
| Verschuif uw flexibele verbruik | U gebruikt minder dan 35 procent van uw opwek zelf, en er is overdag niemand thuis |
| Laad uw auto op uw eigen overschot | U hebt een auto die dat nog niet doet, en er blijft over het jaar meer dan 500 kWh overschot liggen tussen elf en drie |
| Kijk naar een dynamisch contract | U hebt nog een vast contract en levert meer dan 40 procent van uw opwek terug |
| Kijk naar een thuisbatterij | U hebt er nog geen, houdt na de gratis adviezen meer dan 1500 kWh teruglevering over, en gebruikt tussen vijf uur 's middags en zeven uur 's ochtends gemiddeld meer dan 3 kWh per dag |
| Kijk naar uw bestaande batterij | U hebt er al een |

**Deze vijf grenzen zijn keuzes van ons.** Ze komen niet uit een meting en niet
uit een norm. Wat er wel achter zit:

- **35 procent zelfconsumptie.** Daaronder is er iets te verschuiven. Is er
  overdag iemand thuis, dan is het makkelijke verschuiven meestal al gebeurd, en
  dan is dit advies een open deur.
- **500 kWh middagoverschot.** Onder dat bedrag ligt er over een heel jaar te
  weinig zon in het midden van de dag om het laadmoment van een auto voor te
  verzetten.
- **40 procent teruglevering.** Dat is waar het verschil tussen de twee manieren
  van teruglevering begint op te wegen tegen de moeite van overstappen.
- **1500 kWh en 3 kWh.** Opslag heeft twee dingen nodig: iets om op te slaan en
  iemand die het later gebruikt. Onder 3 kWh tussen vijf uur 's middags en zeven
  uur 's ochtends is de batterij vol bij zonsondergang en nog steeds vol bij
  zonsopgang, en dan koopt u een kast die niets doet.

**Wat dat betekent voor een huishouden dat er net onder zit.** Zit u op 36
procent zelfconsumptie, dan zeggen wij niets over verschuiven, terwijl uw buurman
op 34 procent het advies wel krijgt. Dat is een harde grens en wij verzachten hem
niet. Een advies is een ja of een nee: of wij vinden het de moeite waard om uw
week anders in te delen, of niet.

De bedragen ernaast zijn iets anders. Die dragen allemaal een bandbreedte, want
dat zijn schattingen. De grens is een keuze en het bedrag is een schatting, en
die twee horen niet dezelfde vorm te hebben.

## 14. Wij zeggen niet alleen ja of nee over een batterij

Een thuisbatterij kost tussen de 450 en 900 euro per kWh geplaatst. Dat is een factor
twee, en bij de meeste huishoudens ligt de terugverdientijd ergens ín die band: aan de
onderkant van de prijs haalt hij de twaalf jaar wel, aan de bovenkant niet.

Wij hebben dat eerst als één ja of nee gepresenteerd, op basis van de middelste prijs. Dat
was fout. Een huishouden met een terugverdientijd van 11,8 jaar kreeg "koop er een",
terwijl bij de bovenkant van diezelfde band 15,8 jaar hoorde. Eén getal uit een band besliste
de zwaarste zin die wij uitspreken.

Nu zijn er drie uitkomsten:

- **De moeite waard**, als hij zichzelf terugverdient binnen twaalf jaar bij de hoogste
  prijs én bij het tariefniveau waarop opslag het minst oplevert
- **Niet de moeite waard**, als hij dat in het midden al niet doet
- **Het hangt af van wat u betaalt**, voor alles daartussen

In dat laatste geval noemen wij de prijs waarbij het omslaat. Dat is geen enkel bedrag
maar een marge, en dat is met opzet: die prijs is uw jaarlijkse besparing maal twaalf,
gedeeld door de capaciteit, en die besparing hangt af van tarieven die niemand kent. Blijft
u onder de onderkant van die marge, dan verdient de batterij zichzelf binnen twaalf jaar
terug bij alle tarieven die wij doorrekenen. Zit u erboven, dan hangt het ervan af welke
kant die tarieven op gaan. Tot 21 augustus 2026 stond hier één getal, en juist bij dit
getal is dat het ergste: het is het getal waarvan wij zeggen dat u er een offerte naast
mag leggen, en dan mag het geen zekerheid voorwenden die het niet heeft.

Wat dat oplevert, mag u weten: van de zes huishoudens die wij als voorbeeld doorrekenen,
krijgt er niet één een onvoorwaardelijk "koop er een". Daarvoor zou de omslagprijs ook bij
het ongunstigste tariefniveau boven de 900 euro per kWh moeten liggen. Het huishouden dat
er het dichtst bij komt zit daar op 572 euro, en op 672 euro in het midden. Bij de prijzen
van vandaag en de tarieven die leveranciers voor 2027 hebben gepubliceerd, is een batterij
die onmiskenbaar de moeite waard is dus zeldzaam.

Hier stond eerder 833 euro. Dat cijfer hoorde bij een eerdere versie van het model en
klopte al niet meer toen wij het lieten staan. Waarom het bleef staan is het vermelden
waard: de omslagprijs stond wel in ons voorbeeldbestand, maar geen enkele test vergeleek
hem met wat het model uitrekende, dus kon hij verouderen zonder dat er iets rood werd. Dat
doet nu wel iets.

## 15. Wat de gratis routes opleveren, rekenen wij door in plaats van te schatten

Bij elk advies dat u niets kost staat een bedrag. Dat bedrag is niet met een formule
geschat maar doorgerekend: wij draaien uw hele jaar opnieuw door dezelfde simulatie, met
die ene verandering erin, en kijken wat uw jaarrekening dan doet.

Ook bij die bedragen staat een marge, en ook die is doorgerekend en niet geschat: wij
beprijzen hetzelfde jaar op alle drie de tariefniveaus uit hoofdstuk 10. Tot 21 augustus
2026 stond er één bedrag. Dat was de meest openlijke overtreding van onze eigen
regel die er is, want dit is het getal waarop iemand besluit zijn week anders in te delen.

Dat is niet alleen nauwkeuriger, het maakt de bedragen ook optelbaar. Wij passen de
adviezen op elkaar toe: eerst uw apparaten verschuiven, dan uw auto op uw eigen overschot
laden, dan pas het contract. Elke stap wordt gemeten bovenop de vorige, dus geen enkele
kilowattuur wordt twee keer geteld.

De eerste versie deed dat niet. Drie adviezen schatten elk hun eigen bedrag uit dezelfde
zonnestroom, en de bedragen bij elkaar optellen gaf dus een besparing die niet bestond.

Het heeft ook gevolgen voor het batterijadvies, en dat is de belangrijkste: wij kijken naar
de teruglevering die u nog **overhoudt** nadat u de gratis dingen gedaan hebt. Een
huishouden dat zijn auto overdag op eigen stroom laadt, houdt vaak zo weinig over dat een
batterij niets meer te bewaren heeft. Eerder kreeg zo iemand alsnog een batterijadvies,
voor kilowatturen die het advies erboven net had geleerd zelf te gebruiken.

Die zin stond hier vanaf 20 augustus 2026, en tot 21 augustus klopte hij maar half. Wij
gebruikten de overgebleven teruglevering wel om te beslissen **of** wij een batterij lieten
zien, maar niet om te berekenen **welke** en **wat die opbrengt**. Die berekening liep nog
op uw verbruik van voor de gratis adviezen, en op uw huidige contract, ook als wij u net
hadden aangeraden over te stappen. Het gevolg was precies wat deze paragraaf belooft dat
niet gebeurt: dezelfde kilowatturen werden twee keer verkocht, een keer als gratis
besparing en daarna nog een keer als reden om een batterij te kopen.

Wat dat scheelde, op ons eigen referentiehuishouden: een batterij van 7,0 kWh met een
terugverdientijd van 11,6 jaar werd 5,0 kWh met 16,8 jaar, en de prijs waaronder het uit
kan zakte van 697 naar 482 euro per geinstalleerde kWh. Het oordeel klapte van "het hangt
van de prijs af" naar "dit verdient zich niet terug". Bij alle zes de huishoudens waarmee
wij het model vastleggen ging het dezelfde kant op: de batterij werd minder aantrekkelijk,
en geen van de zes krijgt nu nog het advies er een te kopen.

Wij zetten dit erbij omdat het de kant op ging die ons ongelegen komt. Een fout die het
antwoord toevallig gunstiger maakt voor de partij die hem maakt, is precies de fout waarvan
u mag verwachten dat hij blijft zitten.

## 16. Wij houden ons model tegen echte Nederlandse meetgegevens

Er is één gemeten Nederlandse reeks die wij kunnen gebruiken zonder dat er ook maar
iemand zijn meter gekoppeld heeft: het NEDU-profiel van aansluitingen die daadwerkelijk
terugleveren. Dat is het landelijk gemiddelde van wanneer er stroom het net op gaat.

Wij leggen ons eigen gemodelleerde terugleverprofiel daarnaast. Niet om te kijken of de
hoeveelheden kloppen, want dat gemiddelde gaat over het hele land en ons model over één
huis, maar om te kijken of de vórm klopt: in welke maanden en op welke uren de stroom
weggaat.

**Wat dat oplevert.** Per maand zitten wij er hooguit een paar procentpunt naast en de
piek zit bij ons en bij de meting allebei in de hoogzomer. Over het dagverloop is er wel
een duidelijk verschil:

| uur | landelijk gemeten | ons model |
|---|---|---|
| 12:00 | 13,6 % | 16,2 % |
| 16:00 | 8,9 % | 5,2 % |
| 18:00 | 3,0 % | vrijwel niets |

Ons model levert 's avonds vrijwel niets meer terug, terwijl Nederlandse huishoudens dat
gemiddeld wel doen. De verklaring is dat het landelijk gemiddelde alle dakoriëntaties
bevat. Daken op het westen produceren later op de dag door, daken op het oosten juist
eerder, en samen geven die een bredere dagcurve dan één dak ooit kan hebben.

**Wat dat voor uw advies betekent.** Als uw dak op het zuiden ligt, klopt onze
smallere curve voor u beter dan het landelijk gemiddelde. Ligt hij op het westen, dan
schatten wij uw overschot in de late middag te laag in en dus ook wat u verdient met uw
auto op eigen stroom laden. Wij vragen naar uw dakoriëntatie en rekenen die mee, maar de
vergelijking hierboven is met een zuidelijk dak gemaakt en dat is waar dit verschil
vandaan komt.

**Wat het al gerepareerd heeft.** Deze vergelijking heeft een fout in onze eigen
terugvaloptie gevonden, de tabel die wij gebruiken als de Europese rekentool onbereikbaar
is. Die was afgeleid uit één weerjaar, en dat jaar legde de zonnigste maand op mei terwijl
Nederland in juni piekt, en maakte november helderder dan oktober. Allebei waar voor dat
ene jaar en geen van beide waar voor Nederland. De tabel is nu een gemiddelde over negen
jaar.

## 17. Wat wij aannemen als wij het niet vragen

De eerste versie van de rekenmachine stelt vier vragen: uw postcode, uw jaarverbruik, uw
vermogen aan panelen en de richting en helling van uw dak. Alles wat wij verder nodig
hebben, vullen wij zelf in. Dat staat nergens anders in dit document, want de hoofdstukken
hierboven beschrijven wat wij doen met een antwoord, niet wat wij doen zonder.

Dit vullen wij in als u het niet zegt:

| Wat | Wat wij aannemen |
|---|---|
| Overdag iemand thuis | Nee |
| Elektrische auto | Geen |
| Warmtepomp | Geen |
| Thuisbatterij | Geen |
| Contract | Vast |
| Verplaatsbaar verbruik per dag | 1 kWh (hoofdstuk 3) |
| Hoe oud uw panelen zijn | Nieuw (hoofdstuk 6) |

**Welke kant die aannames op duwen.** De eerste vijf duwen dezelfde kant op: klopt een
van hen niet voor u, dan is het bedrag bovenaan lager dan wat wij u tonen en nooit
hoger. De leeftijd van uw panelen duwt dezelfde kant op en staat los van de tabel
hieronder, omdat hij niet aan of uit is maar geleidelijk: elk jaar ouder is een half
procent minder opwek, tot maximaal twintig procent. Wij zetten hier met opzet geen bedrag
bij. De tabel hieronder is op een huishouden gemeten, en een tweede getal dat wij er niet
op dezelfde manier naast kunnen leggen zou meer zekerheid suggereren dan wij hebben. Dat is de kant die ons uitkomt. Op ons referentiehuishouden, 3,5 kWp en 3500 kWh in
postcode 5401, kost het einde van saldering met deze aannames 634 euro per jaar. Verandert
u er één, dan wordt dat bedrag lager:

| Als dit wel zo is | Dan wordt het bedrag bovenaan |
|---|---|
| Overdag iemand thuis | 492 euro, dus 142 lager |
| Auto die overdag op eigen overschot laadt | 212 euro, dus 422 lager |
| Warmtepomp | 510 euro, dus 123 lager |
| Thuisbatterij van 5 kWh | 276 euro, dus 357 lager |
| Dynamisch contract | 492 euro, dus 142 lager |

Alleen een auto die 's nachts laadt verandert het bedrag niet, en dat is geen toeval: zolang
u meer van het net haalt dan u teruglevert, valt extra nachtverbruik onder saldering
precies weg tegen zichzelf.

**Het woord dat wij hier niet gebruiken.** In onze eigen code stond bij deze keuze het
woord "conservatief". Dat was het verkeerde woord. Aannemen dat er niemand thuis is, is
voorzichtig ten opzichte van uw zelfconsumptie, maar het maakt het bedrag dat wij bovenaan
tonen zo groot mogelijk, en het maakt de kans zo groot mogelijk dat er een gratis advies
verschijnt, want dat advies vraagt juist om een lage zelfconsumptie zonder iemand thuis.
Voorzichtig in de richting die ons goed uitkomt is niet voorzichtig, het is gunstig.

Waarom wij het dan toch zo doen: de andere kant op is niet neutraler. Aannemen dat er wel
iemand thuis is bij iemand die dat niet is, verzint zelfconsumptie die er niet is, en dat
verzwijgt een probleem dat die persoon echt heeft. Bij vier vragen bestaat er geen keuze
die geen kant op duwt. Wat wel bestaat, is die kant hardop noemen, en dat is wat dit
hoofdstuk doet.

**Wat het niet is.** Het is geen garantie dat er altijd een gratis advies verschijnt.
Dat advies vraagt naast "niemand thuis" ook dat u minder dan 35 procent van uw opwek zelf
gebruikt, en een huishouden met weinig panelen en veel verbruik haalt dat niet. Twee van
onze zes voorbeeldhuishoudens hebben overdag niemand thuis en krijgen toch geen enkel
advies, precies om die reden, en dat is voor die twee de juiste uitkomst.

Beantwoordt u meer vragen, dan vervalt de aanname en niet alleen de onzekerheid. Daarom
staat er "Indicatief" boven een antwoord op vier vragen: niet omdat de band breder is,
maar omdat dit de dingen zijn die wij hebben ingevuld in plaats van gevraagd.

## 18. Wat "indicatief", "goed" en "precies" betekenen

Boven elk antwoord staat een van deze drie woorden. Ze zeggen iets anders dan de
bandbreedte eronder, en dat verschil is met opzet.

**De band zegt hoe zeker het model is. Het woord zegt hoeveel u ons verteld
hebt.** Een smalle band onder het woord "indicatief" is dus geen tegenspraak: het
model is zeker over het antwoord op de vraag die daadwerkelijk gesteld is. Als
volledigheid van invoer de band mocht versmallen, of een smalle band het woord
mocht opwaarderen, dan zouden die twee elkaar versterken en zag een zeker
verkeerd getal eruit als een precies goed getal.

Dit krijgt u wanneer:

| Woord | Wanneer |
|---|---|
| Indicatief | U hebt de vier vragen van ronde 1 beantwoord |
| Goed | U hebt ook de vijf vragen van ronde 2 beantwoord, dus negen in totaal |
| Precies | Alleen met uw eigen kwartierdata uit de meter |

Het is geen glijdende schaal. In deze versie tellen wij vier of negen, want dat
zijn de twee formulieren die bestaan, en de grens ligt bij vijf.

**"Precies" kunt u vandaag niet krijgen, en dat hoort u te weten.** Die stand is
er voor het moment dat u uw meter koppelt, en deze versie neemt geen meterdata
aan. Zolang dat zo is, komt er nooit "precies" boven een antwoord te staan. Wij
laten het woord in de schaal staan omdat het beschrijft waar deze schaal heen
gaat, en niet omdat het bereikbaar is.

Waarom meterdata een eigen woord verdient en niet gewoon een tiende antwoord is:
de vragen vervangen elk een parameter van ons standaardprofiel, en kwartierdata
vervangt dat profiel zelf. Dat is het onderdeel dat het antwoord het meest
bepaalt, dus een huishouden met meterdata en verder niets ingevuld weet meer over
zijn antwoord dan een huishouden dat negen vragen beantwoordde.

## 19. Wat wij niet weten

Voor de volledigheid, op een rij:

- Wij kennen uw schaduw niet.
- Wij kennen uw werkelijke apparaten niet, alleen een gemiddelde vorm.
- Wij weten niet wat de terugleververgoeding in 2027 werkelijk wordt. Niemand weet dat.
- Wij rekenen op een historisch jaar aan weer en verbruik, en volgend jaar is anders.
- Ons basisprofiel is dat van huizen zonder zonnepanelen.
- De omvang van het verplaatsbare blok is aangenomen.
- Wij weten niet hoe oud uw panelen zijn en vragen er niet naar, dus rekenen wij ze als
  nieuw. Bij oudere panelen is het bedrag bovenaan hoger dan het bij u is.
- Als u maar vier vragen beantwoordt, weten wij niet of er overdag iemand thuis is, of u
  een elektrische auto hebt, of u een warmtepomp hebt, of u al een thuisbatterij hebt en
  wat voor contract u hebt. Wij nemen dan aan van niet, en dat maakt het bedrag bovenaan
  groter dan het bij veel huishoudens is. Hoofdstuk 17 zet erbij hoeveel.

Koppelt u uw meter, dan vervallen de eerste twee en wordt de vijfde en zesde gekalibreerd
op uw eigen gegevens. Daarom is dat antwoord scherper, en daarom zeggen wij er eerlijk
bij welk niveau u nu hebt.
