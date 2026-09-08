import type { Metadata } from "next";
import Link from "next/link";

import { PageJsonLd } from "../_shell/JsonLd";
import {
  IDENTITY,
  requireCompleteIdentity,
  type CompleteIdentity,
} from "./identity";
import styles from "./legal.module.css";

const PATH = "/privacy/";
const TITLE = "Privacyverklaring";
const DESCRIPTION =
  "Wat Ampeer van u vraagt, waarom, hoe lang wij het bewaren en wat u eraan kunt doen. In gewone taal, zonder verwijzing naar een document dat u niet krijgt te zien.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance: Next treats a URL here as a base and
  // resolves it against the pathname, which canonicalises this page to the
  // site root. The trailing slash arrives from `trailingSlash: true` once
  // metadataBase has made it absolute.
  alternates: { canonical: PATH },
  // Deliberately absent: `openGraph`. Metadata merging is shallow, so any part
  // of it here replaces the root layout's siteName, locale and type.
};

/**
 * The privacy statement.
 *
 * WHAT IT IS BUILT FROM. `docs/dpia.md`, and nothing else. Every figure on
 * this page is one the assessment measured out of the code: ninety days from
 * `AMPEER_ADVICE_TTL_DAYS`, seven days of backups from `scripts/backup_db.sh`,
 * four digits from the regular expression in the serializer, and the two
 * things Cloudflare can read from `infra/nginx/nginx.conf`. Nothing here is a
 * commitment somebody wrote for a page. `tests/app/LegalPages.test.tsx` reads
 * the retention window back out of the backend and fails when this page and
 * the service disagree, which is how `docs/methodologie.md` went stale once
 * already.
 *
 * HOW IT IS WRITTEN. Short sentences, and that is a measurement rather than a
 * style. The rest of this site averages nineteen to twenty-three words per
 * sentence, which is above what a general Dutch audience reads comfortably.
 * A privacy statement is the page with the widest audience and the least
 * motivated reader on the site, so it is written at roughly ten to fifteen.
 * Every sentence that needed a subordinate clause was split instead.
 *
 * WHAT IT DOES NOT SAY. It names no transfer mechanism for Cloudflare, no data
 * protection officer and no processing agreement, because this repository
 * knows about none of the three. A privacy statement that claims a safeguard
 * it does not have is worse than one that is silent about it.
 */
export function PrivacyStatement({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Privacy</p>
        <h1 className={styles.title}>Privacyverklaring</h1>
        <p className={styles.lead}>
          Ampeer stelt u een paar vragen en rekent daar een antwoord mee uit.
          Deze pagina zegt wat wij daarvan bewaren, hoe lang, en wie het verder
          kan zien. Wij hebben het zo kort mogelijk opgeschreven.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="verantwoordelijk">
        <h2 id="verantwoordelijk" className={styles.heading}>
          Wie verantwoordelijk is
        </h2>
        <p className={styles.body}>
          {identity.legalName} is verantwoordelijk voor de gegevens die via
          ampeer.nl worden verwerkt. Heeft u een vraag over uw gegevens, mail
          dan naar {identity.privacyEmail}. Wij antwoorden binnen een maand.
        </p>
        <dl className={styles.register}>
          <dt className={styles.term}>Naam</dt>
          <dd className={styles.detail}>{identity.legalName}</dd>
          <dt className={styles.term}>KvK-nummer</dt>
          <dd className={styles.detail}>{identity.kvkNumber}</dd>
          <dt className={styles.term}>Postadres</dt>
          <dd className={styles.detail}>{identity.postalAddress}</dd>
          <dt className={styles.term}>E-mail</dt>
          <dd className={styles.detail}>
            <a href={`mailto:${identity.contactEmail}`}>
              {identity.contactEmail}
            </a>
          </dd>
          <dt className={styles.term}>E-mail over uw gegevens</dt>
          <dd className={styles.detail}>
            <a href={`mailto:${identity.privacyEmail}`}>
              {identity.privacyEmail}
            </a>
          </dd>
        </dl>
      </section>

      <section className={styles.section} aria-labelledby="watwijvragen">
        <h2 id="watwijvragen" className={styles.heading}>
          Wat wij van u vragen
        </h2>
        <p className={styles.body}>
          U vult alles zelf in. Wij halen niets op bij uw meter, uw netbeheerder
          of uw leverancier. Er gebeurt niets voordat u op berekenen klikt.
        </p>
        <p className={styles.body}>De eerste ronde stelt vier vragen:</p>
        <ul className={styles.points}>
          <li className={styles.point}>
            De eerste vier cijfers van uw postcode.
          </li>
          <li className={styles.point}>Uw jaarverbruik in kilowattuur.</li>
          <li className={styles.point}>
            Het vermogen van uw zonnepanelen, in wattpiek.
          </li>
          <li className={styles.point}>
            Hoe uw dak ligt: de richting en de hellingshoek.
          </li>
        </ul>
        <p className={styles.body}>
          Wilt u een scherper antwoord, dan volgen er vijf vragen bij. Of u
          overdag thuis bent bijvoorbeeld, of u een elektrische auto heeft, en
          of u een warmtepomp heeft. Die vragen zijn vrijwillig.
        </p>
        <p className={styles.body}>
          Voor het advies vragen wij nog steeds geen naam, geen telefoonnummer
          en geen huisnummer, en de rekenmachine werkt zonder account. Wie een
          account aanmaakt, geeft een e-mailadres en kiest een wachtwoord, en
          meer niet.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="postcode">
        <h2 id="postcode" className={styles.heading}>
          Van uw postcode bewaren wij vier cijfers
        </h2>
        <p className={styles.body}>
          Het invoerveld accepteert alleen vier cijfers. Typt u er zes, dan
          wordt de invoer geweigerd. Hij wordt niet stilletjes afgekapt.
        </p>
        <p className={styles.body}>
          Dat verschil is belangrijk. Afkappen zou betekenen dat uw volledige
          postcode ons wel had bereikt. Nu bereikt hij ons nooit.
        </p>
        <p className={styles.body}>
          Voor de zonopbrengst gebruiken wij zelfs maar de eerste twee cijfers.
          Daarmee zoeken wij de instraling van uw regio op.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="waarom">
        <h2 id="waarom" className={styles.heading}>
          Waarom wij dit vragen
        </h2>
        <p className={styles.body}>
          Elk antwoord is nodig voor de berekening. Uw postcodegebied kiest de
          zonnereeks. Uw jaarverbruik schaalt uw verbruiksprofiel. Wattpiek en
          dakligging bepalen uw opbrengst.
        </p>
        <p className={styles.body}>
          Er is geen vraag die wij alleen voor de statistiek stellen. Er is ook
          geen tweede doel: geen advertenties, geen profiel en geen doorverkoop.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="grondslag">
        <h2 id="grondslag" className={styles.heading}>
          Op welke grondslag wij dit doen
        </h2>
        <LegalBasisParagraphs identity={identity} />
      </section>

      <section className={styles.section} aria-labelledby="account">
        <h2 id="account" className={styles.heading}>
          Uw account
        </h2>
        <p className={styles.body}>
          Maakt u een account, dan bewaren wij meer dan voor een berekening
          alleen.
        </p>
        <p className={styles.body}>
          Uw wachtwoord maken wij met Argon2id onleesbaar voordat het de
          database bereikt. Wij kunnen het niet lezen en niet teruggeven.
        </p>
        <p className={styles.body}>
          Wij bewaren het tijdstip van uw laatste keer inloggen. Wij bewaren ook
          het tijdstip waarop u uw adres bevestigde. Dat veld blijft leeg zolang
          u dat niet deed.
        </p>
        <p className={styles.body}>
          Een bevestigd adres is straks nodig om een slimme meter te koppelen.
          Vandaag is het nergens voor nodig.
        </p>
        <p className={styles.body}>
          Op uw accountpagina zet u twee toestemmingen apart aan of uit. Wij
          zetten er nooit een vooraf aan. Elke keuze bewaren wij met het
          tijdstip en de tekstversie die u toen las. Intrekken kost u een klik.
        </p>
        <p className={styles.body}>
          Herstel en bevestiging gaan per mail, met een link die eenmalig werkt.
          Een herstellink werkt een uur, een bevestigingslink zeven dagen.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="bewaren">
        <h2 id="bewaren" className={styles.heading}>
          Wat wij bewaren, en hoe lang
        </h2>
        <p className={styles.body}>
          Wij bewaren uw antwoorden en uw uitkomst achter de link die u krijgt.
          Zo kunt u er later nog bij. Die link is de enige sleutel. Wie hem
          heeft, ziet uw uitkomst. Deel hem dus alleen met mensen die hem mogen
          zien.
        </p>
        <p className={styles.body}>
          Na 90 dagen verwijderen wij uw advies. Dat gebeurt automatisch, elke
          dag opnieuw. Daarna werkt de link niet meer. U krijgt dan dezelfde
          melding als bij een link die nooit heeft bestaan.
        </p>
        <p className={styles.body}>
          Uw account bewaren wij tot u het verwijdert. Een herstel- of
          bevestigingslink bewaren wij als onomkeerbare afdruk tot hij verloopt.
          Een mail die wij nog moeten versturen staat in een wachtrij zonder uw
          adres erin. Die rij verdwijnt zodra de mail weg is, of zeven dagen
          nadat het versturen definitief mislukte.
        </p>
        <p className={styles.body}>
          Wij maken elke dag een reservekopie van onze database. Die kopieën
          bewaren wij zeven dagen. Een verwijderd advies of een verwijderd
          account kan daardoor nog hoogstens acht dagen in zo&apos;n bestand
          staan. Die bestanden staan op dezelfde server en zijn alleen voor ons
          leesbaar.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="logboek">
        <h2 id="logboek" className={styles.heading}>
          Wat er in ons logboek komt
        </h2>
        <p className={styles.body}>
          Bij elk advies schrijven wij één regel in een logboek. Daarin staan
          het tijdstip, uw postcodegebied, hoe zeker het antwoord was, en de
          versienummers van onze rekenmodule.
        </p>
        <p className={styles.body}>
          Ons logboek kent dertien soorten regels. Naast die ene bij elk advies
          schrijven wij er sinds er accounts zijn een bij twaalf handelingen:
        </p>
        <ul className={styles.points}>
          <li className={styles.point}>
            Aanmaken, inloggen of mislukt inloggen.
          </li>
          <li className={styles.point}>Uitloggen.</li>
          <li className={styles.point}>Een toestemming geven of intrekken.</li>
          <li className={styles.point}>Exporteren of verwijderen.</li>
          <li className={styles.point}>Een herstel aanvragen of afronden.</li>
          <li className={styles.point}>
            Een adres bevestigen, of een mail versturen.
          </li>
        </ul>
        <p className={styles.body}>
          In die regels staat een nummer dat naar uw account wijst, en nooit uw
          e-mailadres. Na verwijdering wijst dat nummer nergens meer naar. Bij
          een herstelverzoek voor een adres dat wij niet kennen schrijven wij
          niets.
        </p>
        <p className={styles.body}>
          Uw link zetten wij er niet in. Wij zetten er een onomkeerbare afdruk
          van in. Uit die afdruk is uw link niet terug te rekenen. Zo blijft een
          oude logregel geen werkende sleutel naar een advies dat allang weg is.
        </p>
        <p className={styles.body}>
          Dit logboek ruimen wij niet op. Zodra uw advies weg is, wijst die
          afdruk nergens meer naar. Wat overblijft is een postcodegebied, een
          tijdstip en twee versienummers.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="ipadres">
        <h2 id="ipadres" className={styles.heading}>
          Uw IP-adres bewaren wij niet
        </h2>
        <p className={styles.body}>
          Wij tellen hoeveel verzoeken er per bezoeker binnenkomen. Dat is nodig
          om misbruik te stoppen. Uw IP-adres wordt daarvoor eerst onomkeerbaar
          versleuteld.
        </p>
        <p className={styles.body}>
          Er is geen tabel bij ons met een IP-adres erin. Er is ook geen
          logregel die er een bewaart.
        </p>
        <p className={styles.body}>
          Een hulpprogramma tegen inbrekers brengt drie tabellen mee die een
          IP-adres zouden kunnen bevatten. Die blijven leeg, want wij tellen dat
          in het geheugen. Gemeten: na zes mislukte inlogpogingen staan alle
          drie op nul rijen.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="cloudflare">
        <h2 id="cloudflare" className={styles.heading}>
          Cloudflare ziet uw verzoek langskomen
        </h2>
        <p className={styles.body}>
          Het verkeer naar deze site loopt via Cloudflare Inc. Dat bedrijf is
          onze verwerker. Cloudflare beveiligt de verbinding en beëindigt die
          aan de rand van hun netwerk.
        </p>
        <p className={styles.body}>
          Daardoor ziet Cloudflare bij elk verzoek twee dingen. Uw IP-adres, en
          het webadres van de pagina die u opvraagt. In dat webadres staat ook
          uw link naar uw advies.
        </p>
        <p className={styles.body}>
          Uit onze eigen logboeken houden wij die link weg. Bij Cloudflare
          kunnen wij dat niet. Er is een oplossing voor, namelijk de link niet
          meer in het webadres zetten. Die is nog niet gebouwd.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="resend">
        <h2 id="resend" className={styles.heading}>
          Resend verstuurt onze mail
        </h2>
        <p className={styles.body}>
          Wij sturen mail voor twee dingen: een wachtwoord herstellen, of een
          adres bevestigen.
        </p>
        <p className={styles.body}>
          Nergens anders voor. Die mail vertrekt via Resend, Inc. Resend is onze
          tweede verwerker.
        </p>
        <p className={styles.body}>
          Resend ziet uw adres, dat er een account bij hoort of dat er herstel
          is gevraagd, en de tekst van de mail met de link erin.
        </p>
        <p className={styles.body}>
          Resend bewaart een eigen verzendlog met adres, onderwerp en tekst. Dat
          log staat in de Verenigde Staten, ook al versturen wij vanuit de
          Europese regio.
        </p>
        <p className={styles.body}>
          Die doorgifte rust op de standaardbepalingen van de Europese
          Commissie, in Resends verwerkersovereenkomst.
        </p>
        <p className={styles.body}>
          Ze rust ook op Resends certificering onder het Data Privacy Framework.
        </p>
        <p className={styles.body}>
          Die overeenkomst is voorgetekend bij elk account. Wij kunnen hem
          downloaden uit het dashboard.
        </p>
        <p className={styles.body}>
          Wat Resend niet ziet: waarom u herstel vroeg, uw wachtwoord, uw
          toestemmingen of uw advies.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="derden">
        <h2 id="derden" className={styles.heading}>
          Verder gaat er niets naar buiten
        </h2>
        <ul className={styles.points}>
          <li className={styles.point}>
            Het openen van een pagina van Ampeer doet geen enkel verzoek aan een
            ander bedrijf.
          </li>
          <li className={styles.point}>
            Wij gebruiken geen Google Analytics en geen ander meetprogramma.
          </li>
          <li className={styles.point}>
            Wij plaatsen geen advertenties en verkopen geen advertentieruimte.
          </li>
          <li className={styles.point}>
            Wij volgen uw gedrag niet en bouwen geen profiel van u op.
          </li>
          <li className={styles.point}>
            Onze lettertypen staan op onze eigen server. Er is geen extern
            lettertype en geen extern script.
          </li>
        </ul>
        <p className={styles.body}>
          Dit is geen belofte maar een test. Bij elke wijziging leest een test
          alle verzoeken mee die een pagina doet. Gaat er één naar een ander
          bedrijf, dan gaat die test rood en komt de wijziging er niet in.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="cookies">
        <h2 id="cookies" className={styles.heading}>
          Drie cookies, en geen enkele om u te volgen
        </h2>
        <p className={styles.body}>
          Opent u de accountpagina, dan zetten wij één cookie dat de pagina
          beschermt tegen verzoeken die niet van u komen. Logt u in, dan komen
          daar twee cookies bij die uw sessie zijn.
        </p>
        <p className={styles.body}>
          Een werkt een kwartier, de andere veertien dagen.
        </p>
        <p className={styles.body}>
          Alle drie zijn nodig om de accountpagina veilig te gebruiken, en voor
          niets anders. Ze volgen u niet, ze meten niets en ze gaan naar geen
          ander bedrijf.
        </p>
        <p className={styles.body}>
          Daarom is er geen cookiemelding. De wet vraagt geen toestemming voor
          cookies die alleen doen wat u zelf vroeg.
        </p>
        <p className={styles.body}>
          Uw antwoorden op de vragen staan in de opslag van uw eigen browser.
          Die verlaten uw browser niet. Uw keuze voor licht of donker ook niet.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="rechten">
        <h2 id="rechten" className={styles.heading}>
          Wat u met uw gegevens kunt
        </h2>

        <h3 className={styles.subheading}>Inzien</h3>
        <p className={styles.body}>
          Uw link is uw inzage. Open hem en u ziet wat wij hebben uitgerekend.
          Daar hoeft u niets voor aan te vragen. Wij bewaren daarnaast de
          antwoorden die u invulde. Die staan niet op het scherm. Wilt u ze
          zien, vraag ze dan op via het adres bovenaan.
        </p>
        <p className={styles.body}>
          Heeft u een account, dan staat op uw accountpagina uw adres en de
          stand van beide toestemmingen. De knop exporteren geeft alles wat wij
          over uw account hebben, als bestand dat een computer kan lezen.
        </p>

        <h3 className={styles.subheading}>Meenemen</h3>
        <p className={styles.body}>
          Het antwoord achter uw link is een bestand dat een computer kan lezen.
          U kunt het dus meenemen naar iemand anders.
        </p>
        <p className={styles.body}>
          Dat exportbestand van uw account is de overdracht voor uw account.
        </p>

        <h3 className={styles.subheading}>Corrigeren</h3>
        <p className={styles.body}>
          Heeft u iets verkeerd ingevuld, dan kunt u dat niet wijzigen. Reken
          opnieuw en u krijgt een nieuw advies met een nieuwe link. Het oude
          blijft staan tot het na 90 dagen verdwijnt.
        </p>
        <p className={styles.body}>
          Een toestemming kunt u altijd omzetten. Wij bewaren de oude keuze
          naast de nieuwe.
        </p>

        <h3 className={styles.subheading}>Laten verwijderen</h3>
        <p className={styles.body}>
          Op uw accountpagina staat een knop die uw account verwijdert. Hij
          vraagt uw wachtwoord opnieuw.
        </p>
        <p className={styles.body}>
          Weg zijn dan uw adres, uw wachtwoord, beide toestemmingen en alle
          adviezen die aan uw account hingen. Wat blijft is een logregel met een
          nummer dat nergens meer naar wijst.
        </p>
        <p className={styles.body}>
          Bent u uw wachtwoord kwijt, dan herstelt u het eerst via de mail.
          Daarna verwijdert u uw account.
        </p>

        <h3 className={styles.subheading}>Bezwaar maken</h3>
        <p className={styles.body}>
          Bent u het niet eens met wat wij doen, laat het ons weten. U kunt uw
          bezwaar sturen naar {identity.privacyEmail}.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="klagen">
        <h2 id="klagen" className={styles.heading}>
          Klagen kan bij de toezichthouder
        </h2>
        <p className={styles.body}>
          Komt u er met ons niet uit, dan kunt u een klacht indienen bij de
          Nederlandse toezichthouder. Dat kan altijd en het kost u niets.
        </p>
        <p className={styles.body}>
          <a href="https://www.autoriteitpersoonsgegevens.nl/">
            Autoriteit Persoonsgegevens
          </a>
        </p>
      </section>

      <section className={styles.section} aria-labelledby="verklaring">
        <h2 id="verklaring" className={styles.heading}>
          Over deze verklaring
        </h2>
        <p className={styles.body}>
          Deze verklaring hoort bij de dienst met accounts, herstel en
          bevestiging, zoals die vandaag draait. Komt er een koppeling met uw
          meter, dan verandert er veel en schrijven wij deze pagina opnieuw
          voordat dat gebeurt.
        </p>
        <p className={styles.body}>
          Wie wij zijn en waarvan Ampeer betaald wordt, staat op{" "}
          <Link href="/over-ons/">de pagina over ons</Link>. Hoe wij rekenen,
          staat in <Link href="/methodologie/">onze methodologie</Link>. De
          regels voor het gebruik staan in{" "}
          <Link href="/voorwaarden/">onze gebruiksvoorwaarden</Link>.
        </p>
        <p className={styles.note}>Laatst gewijzigd op 7 september 2026.</p>
      </section>
    </div>
  );
}

/**
 * The lawful basis, and the paragraph that follows from it.
 *
 * Two texts rather than one that covers both, because the two bases give the
 * visitor different rights. Consent can be withdrawn and performance of a
 * contract cannot; writing a sentence that is vague enough to fit either would
 * be hiding the one thing this section is for.
 */
function LegalBasisParagraphs({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  if (identity.legalBasis === "toestemming") {
    return (
      <>
        <p className={styles.body}>
          Wij verwerken uw antwoorden met uw toestemming. Die geeft u door de
          vragen in te vullen en op berekenen te klikken.
        </p>
        <p className={styles.body}>
          U mag uw toestemming intrekken wanneer u wilt. Stuur ons dan een
          bericht met uw link erbij. Wat wij tot dat moment deden blijft
          rechtmatig.
        </p>
        <p className={styles.body}>
          Wij verwerken ook uw account met uw toestemming. Die geeft u door het
          account aan te maken.
        </p>
        <p className={styles.body}>
          U trekt die toestemming in door uw account te verwijderen. Dat kan
          altijd, zonder ons iets te vragen. Voor doorgeven aan een installateur
          en voor het koppelen van uw meter vragen wij apart toestemming.
        </p>
      </>
    );
  }
  return (
    <>
      <p className={styles.body}>
        Wij verwerken uw antwoorden om de berekening te maken waar u zelf om
        vraagt. Dat is de uitvoering van de overeenkomst die u met ons aangaat
        door de vragen te beantwoorden.
      </p>
      <p className={styles.body}>
        Zonder die antwoorden kunnen wij geen antwoord geven. Er is geen andere
        grondslag en er is geen tweede doel.
      </p>
    </>
  );
}

/**
 * The route.
 *
 * `requireCompleteIdentity(IDENTITY)` is the gate, and it is here rather than
 * in the component above so that the component stays renderable from a test
 * with an identity of its own. Next prerenders this function during
 * `next build`, so while a fact is missing the build fails and `out/` is never
 * written. See the header of `identity.ts` for why that is the build and not a
 * test.
 */
export default function PrivacyPage() {
  return <PrivacyStatement identity={requireCompleteIdentity(IDENTITY)} />;
}
