# Verwerkingsregister

Datum: 7 september 2026
Betreft: het register van verwerkingsactiviteiten dat artikel 30 AVG vraagt.

## 0. De verantwoordelijke

Stijn IT, eenmanszaak. KvK 42015984. Snavelbiesstraat 8, 5445 NV Landhorst.
Algemeen adres: info@ampeer.nl. Adres voor verzoeken over persoonsgegevens:
privacy@ampeer.nl.

Geen functionaris gegevensbescherming en geen vertegenwoordiger. Geen van
beide is verplicht voor deze verwerking, en er is er geen.

## 1. Het advies

**Doel.** Uitrekenen wat het einde van de salderingsregeling een huishouden
kost.

**Betrokkenen.** Bezoekers van ampeer.nl.

**Categorieën gegevens.** De vijf antwoorden uit de eerste ronde en de acht
uit de tweede ronde, het berekende advies, en een token van 22 tekens dat
naar dat advies wijst.

**Grondslag.** Toestemming, gegeven door te rekenen.

**Ontvangers.** Cloudflare Inc., als verwerker voor al het verkeer naar
ampeer.nl.

**Doorgifte buiten de EER.** Cloudflare Inc. is in de Verenigde Staten
gevestigd. Aanvaarding van zijn standaardovereenkomst is niet vastgelegd;
die beoordeling ligt bij de verwerkingsverantwoordelijke (DPIA hoofdstuk 10,
slotalinea).

**Bewaartermijn.** negentig dagen, dagelijks opgeruimd. Een reservekopie
bewaart een verwijderd advies nog hoogstens zeven dagen langer.

**Maatregelen.** De postcode wordt op vier cijfers geweigerd, niet afgekapt.
Het token komt nooit in een logregel. Er geldt een tempolimiet per gehasht
IP-adres.

**Tabellen.** `StoredAdvice`, `ProductionCache`, `DailyCounter`, in
`backend/advice/models.py`.

## 2. Het account

**Doel.** Een huishouden laten inloggen, zijn toestemmingen bewaren, en zijn
gegevens laten exporteren of verwijderen.

**Betrokkenen.** Wie een account aanmaakt.

**Categorieën gegevens.** E-mailadres, wachtwoord als Argon2id-hash,
tijdstip van de laatste keer inloggen, tijdstip van adresbevestiging.

**Grondslag.** Toestemming, gegeven door registratie (DPIA hoofdstuk 10,
punt 2).

**Ontvangers.** Geen buiten Cloudflare (hoofdstuk 1) voor het verkeer zelf.

**Doorgifte buiten de EER.** Zoals bij hoofdstuk 1: Cloudflare Inc. is in de
Verenigde Staten gevestigd en de aanvaarding van zijn standaardovereenkomst
is niet vastgelegd (DPIA hoofdstuk 10, slotalinea).

**Bewaartermijn.** Tot verwijdering van het account. Een reservekopie
bewaart een verwijderd account nog hoogstens zeven dagen langer.

**Maatregelen.** Argon2id. httpOnly-cookies met SameSite=Strict, een voor
een kwartier en een voor veertien dagen. Refresh-tokens als digest, nooit
als geldig token. Inbraakbeveiliging in het geheugen, zonder een tabel met
een IP-adres erin. Het wachtwoord wordt opnieuw gevraagd voordat een account
wordt verwijderd.

**Tabellen.** `User`, `RefreshSession`, in `backend/accounts/models.py`.

## 3. De toestemmingen

**Doel.** Vastleggen welke toestemming een huishouden gaf of introk, en
wanneer.

**Betrokkenen.** Wie een account heeft.

**Categorieën gegevens.** Soort toestemming, handeling (geven of intrekken),
tijdstip, versie van de tekst die op dat moment gold.

**Grondslag.** Toestemming; dit is de toestemming zelf.

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Tot verwijdering van het account. Elke rij blijft staan;
intrekken is een nieuwe rij en geen wijziging van de oude.

**Maatregelen.** Nooit voorgevinkt. Een label narrowt nooit verder dan de
tekst onder dezelfde versie toestaat.

**Tabellen.** `Consent`, in `backend/accounts/models.py`.

## 4. Herstel en bevestiging per mail

**Doel.** Een wachtwoord herstellen of een e-mailadres bevestigen.

**Betrokkenen.** Wie een account heeft en een link aanvraagt of ontvangt.

**Categorieën gegevens.** Het e-mailadres, de soort mail (herstel of
bevestiging), de sha256-afdruk van een link.

**Grondslag.** Noodzaak voor de dienst (DPIA hoofdstuk 10, bij punt 5):
zonder bevestigd adres kan de dienst geen wachtwoord herstellen en straks
geen meter koppelen.

**Ontvangers.** Resend, Inc., als verwerker voor het versturen van de mail.

**Doorgifte buiten de EER.** Verenigde Staten, voor Resends eigen
verzendlog. De standaardbepalingen van de Europese Commissie in Resends
verwerkersovereenkomst en Resends certificering onder het Data Privacy
Framework zijn de grondslag voor die doorgifte. De verzendregio is de
Europese Unie.

**Bewaartermijn.** De afdruk van een link tot hij verloopt: een uur voor
herstel, zeven dagen voor bevestiging. De rij in de wachtrij tot verzending,
of zeven dagen na een definitief mislukte poging.

**Maatregelen.** Het ruwe token bestaat alleen in het geheugen van het
verstuurcommando en in de mail zelf; de database bewaart alleen de
sha256-afdruk. Geen e-mailadres in de wachtrij. Een link werkt precies een
keer. `backend/accounts/mailer.py` is de enige module die Resend bereikt, en
een test dwingt dat af.

**Tabellen.** `OneTimeToken`, `OutboundMail`, in `backend/accounts/models.py`.

## 5. Het auditlogboek

**Doel.** Vastleggen wat er gebeurde, zodat de dienst controleerbaar is.

**Betrokkenen.** Iedereen van wie de dienst iets vastlegt: een advies, een
account, een toestemming, een mail.

**Categorieën gegevens.** Soort handeling, tijdstip, een accountnummer of
niets, een onomkeerbare afdruk van een advieslink, een postcodegebied,
versienummers. Nooit een e-mailadres.

**Grondslag.** Gerechtvaardigd belang van de verantwoordelijke bij een
controleerbaar systeem, en artikel 5 lid 2 AVG (verantwoordingsplicht).

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Geen opruiming. Na verwijdering van een account of een
advies wijst het nummer in een regel nergens meer naar.

**Maatregelen.** Alleen toevoegen; nooit wijzigen of verwijderen. Dertien
soorten handelingen worden vastgelegd, en niet meer dan dat.

**Tabellen.** `AuditEvent`, in `backend/advice/models.py`.

## 6. De tempolimiet

**Doel.** Misbruik tegengaan: te veel verzoeken van een en dezelfde
bezoeker.

**Betrokkenen.** Elke bezoeker.

**Categorieën gegevens.** Een teller per gehasht IP-adres, in het geheugen.

**Grondslag.** Gerechtvaardigd belang: misbruik tegengaan.

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** Een uur, in het geheugen. Nooit in een tabel.

**Maatregelen.** HMAC onder de geheime sleutel. Gemeten: de drie tabellen
die het inbraakbeveiligingsprogramma zou kunnen vullen blijven leeg.

## 7. De reservekopieen

**Doel.** Herstel mogelijk maken na een fout of een storing.

**Betrokkenen.** Iedereen van wie de database op dat moment een gegeven
draagt.

**Categorieën gegevens.** Een dump van de hele database.

**Grondslag.** Dezelfde als de verwerking die in de dump staat.

**Ontvangers.** Geen.

**Doorgifte buiten de EER.** Geen.

**Bewaartermijn.** zeven dagen. Een verwijderd gegeven kan daardoor nog
hoogstens acht dagen in een kopie staan.

**Maatregelen.** Bestanden op modus 0600, in een map op modus 0700,
dagelijks. De deploy weigert een kopie gezond te noemen die breder leesbaar
is dan dat.

## 8. De verwerkers

| Verwerker | Verwerking | Ziet | Verwerkersovereenkomst |
|---|---|---|---|
| Cloudflare Inc. | Al het verkeer naar ampeer.nl | IP-adres, pad | De standaardovereenkomst bij het account; aanvaarding niet vastgelegd; bij de verantwoordelijke (DPIA hoofdstuk 10, slotalinea). |
| Resend, Inc. | Herstel- en bevestigingsmail | E-mailadres, inhoud | De voorgetekende DPA uit het dashboard; beoordeling bij de verantwoordelijke (DPIA hoofdstuk 10, punt 5). |

Geen derde verwerker.

## 9. Wat er verandert bij fase 2

Zodra kwartierdata van een slimme meter binnenkomt, ontstaat een achtste
verwerking, met een eigen bewaartermijn: negentig dagen ruw, daarna alleen
uuraggregaten. Dit register wordt dan herschreven, samen met de DPIA.
