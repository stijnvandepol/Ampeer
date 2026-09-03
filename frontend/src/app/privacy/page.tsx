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
          dan naar het adres hieronder. Wij antwoorden binnen een maand.
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
          Wij vragen geen naam, geen e-mailadres en geen telefoonnummer. Wij
          vragen ook geen huisnummer. Er is geen account en er is geen
          wachtwoord.
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
          Wij maken elke dag een reservekopie van onze database. Die kopieën
          bewaren wij zeven dagen. Een verwijderd advies kan daardoor nog
          hoogstens acht dagen in zo&apos;n bestand staan. Die bestanden staan
          op dezelfde server en zijn alleen voor ons leesbaar.
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
          Cookies zetten wij niet
        </h2>
        <p className={styles.body}>
          Wij plaatsen geen cookies. Er is dus ook geen cookiemelding die u moet
          wegklikken.
        </p>
        <p className={styles.body}>
          Uw antwoorden en uw keuze voor licht of donker staan in de opslag van
          uw eigen browser. Die blijven op uw apparaat en komen niet bij ons
          binnen. Sluit u het tabblad, dan zijn uw antwoorden weg.
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

        <h3 className={styles.subheading}>Meenemen</h3>
        <p className={styles.body}>
          Het antwoord achter uw link is een bestand dat een computer kan lezen.
          U kunt het dus meenemen naar iemand anders.
        </p>

        <h3 className={styles.subheading}>Corrigeren</h3>
        <p className={styles.body}>
          Heeft u iets verkeerd ingevuld, dan kunt u dat niet wijzigen. Reken
          opnieuw en u krijgt een nieuw advies met een nieuwe link. Het oude
          blijft staan tot het na 90 dagen verdwijnt.
        </p>

        <h3 className={styles.subheading}>Laten verwijderen</h3>
        <p className={styles.body}>
          Er is nog geen knop waarmee u uw advies zelf weggooit. Uw advies
          verdwijnt sowieso na 90 dagen. Wilt u het eerder weg hebben, stuur ons
          dan een bericht met uw link erbij.
        </p>

        <h3 className={styles.subheading}>Bezwaar maken</h3>
        <p className={styles.body}>
          Bent u het niet eens met wat wij doen, laat het ons weten. U kunt uw
          bezwaar sturen naar het adres bovenaan deze pagina.
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
          Deze verklaring hoort bij de dienst zoals die vandaag draait. Krijgt
          Ampeer accounts of een koppeling met uw meter, dan verandert er veel
          en schrijven wij deze pagina opnieuw.
        </p>
        <p className={styles.body}>
          Wie wij zijn en waarvan Ampeer betaald wordt, staat op{" "}
          <Link href="/over-ons/">de pagina over ons</Link>. Hoe wij rekenen,
          staat in <Link href="/methodologie/">onze methodologie</Link>.
        </p>
        <p className={styles.note}>Laatst gewijzigd op 2 september 2026.</p>
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
