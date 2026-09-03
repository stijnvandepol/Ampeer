import type { Metadata } from "next";
import Link from "next/link";

import { PageJsonLd } from "../_shell/JsonLd";
import {
  IDENTITY,
  requireCompleteIdentity,
  type CompleteIdentity,
} from "../privacy/identity";
import styles from "../privacy/legal.module.css";

const PATH = "/over-ons/";
const TITLE = "Over Ampeer";
const DESCRIPTION =
  "Wie er achter Ampeer zit, waarom het bestaat en waarvan het betaald wordt. Wij verkopen geen panelen, geen batterijen en geen energiecontract, en wij plaatsen geen advertenties.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: PATH },
  // Deliberately absent: `openGraph`. Metadata merging is shallow.
};

/**
 * The page that says who is talking.
 *
 * WHY THE DISCLOSURE COMES FIRST. Everything else on this site is about the
 * visitor's house. This is the only page about the entity, and the only claim
 * on it a reader cannot verify anywhere else is what Ampeer does not do for
 * money. A page that introduces itself first and discloses second has buried
 * the disclosure under the pitch, so the first section under the headline is
 * the list of things that are not for sale.
 * `tests/app/LegalPages.test.tsx` fixes that order, because it is an argument
 * rather than a layout preference.
 *
 * WHAT IT MAY NOT BECOME. No team photographs, no founder story, no counter of
 * households helped, and no testimonial. Those are the ordinary furniture of a
 * page like this and every one of them is either social proof, which rule four
 * of the frontend spec forbids, or a claim about people this repository knows
 * nothing about. What is left is what is checkable.
 *
 * There is no call to action on this page and that is deliberate. The two the
 * spec allows both refer to an answer that does not exist yet, and a third
 * would turn a disclosure into a funnel. The links out of here go to the
 * method and to the privacy statement, which are the two documents a sceptical
 * reader would want next.
 */
export function AboutAmpeer({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Over ons</p>
        <h1 className={styles.title}>Over Ampeer</h1>
        <p className={styles.lead}>
          Ampeer rekent uit wat het einde van de saldering u kost. Wij verkopen
          niets en wij bemiddelen niets. Hieronder staat waarvan Ampeer betaald
          wordt, en wie erachter zit.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="nietverkopen">
        <h2 id="nietverkopen" className={styles.heading}>
          Wat wij niet doen en niet verkopen
        </h2>
        <ul className={styles.points}>
          <li className={styles.point}>
            Wij verkopen geen zonnepanelen en geen thuisbatterijen.
          </li>
          <li className={styles.point}>
            Wij verkopen geen energiecontract en wij bemiddelen er ook geen.
          </li>
          <li className={styles.point}>
            Wij plaatsen geen advertenties en verkopen geen advertentieruimte.
          </li>
          <li className={styles.point}>
            Wij verkopen vandaag geen leads en sturen u niet door naar een
            installateur of een leverancier.
          </li>
          <li className={styles.point}>
            Wij sturen uw apparaten niet aan. Wij geven advies en grijpen niet
            in.
          </li>
        </ul>
        <p className={styles.body}>
          Er staat geen knop op deze site die naar een verkopende partij leidt.
          Zoekt u er een, dan is die er niet.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="betaald">
        <h2 id="betaald" className={styles.heading}>
          Waarvan Ampeer betaald wordt
        </h2>
        <p className={styles.body}>
          Vandaag verdienen wij niets aan uw advies. Er komt geen commissie
          binnen, geen advertentiegeld en geen vergoeding per doorverwijzing.{" "}
          {identity.legalName} betaalt de server en de domeinnaam zelf.
        </p>
        <p className={styles.body}>
          Verandert dat, dan komt het hier te staan voordat het gebeurt. Gaat
          Ampeer ooit doorverwijzen, dan vragen wij daar apart toestemming voor.
          Die toestemming staat nooit voorgevinkt aan, en uw advies verandert er
          niet door.
        </p>
        <p className={styles.body}>
          Dat laatste is de kern. Ons advies mag nooit afhangen van wie ons
          betaalt. Elke regel code die dat wel zou doen is bij ons een fout en
          geen verdienmodel.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="geenbatterij">
        <h2 id="geenbatterij" className={styles.heading}>
          Wij mogen zeggen dat u niets hoeft te kopen
        </h2>
        <p className={styles.body}>
          Onze rekenmodule mag als uitkomst geven: &quot;nu geen batterij&quot;.
          Bij een deel van de huishoudens is dat het eerlijke antwoord, en dan
          krijgt u het ook.
        </p>
        <p className={styles.body}>
          Aan die uitkomst verdienen wij niets. Aan de andere uitkomsten
          verdienen wij ook niets, en dat is precies waarom wij deze kunnen
          geven. Een adviseur die batterijen verkoopt kan die zin niet
          schrijven.
        </p>
        <p className={styles.body}>
          Wij tonen ook altijd eerst de routes die u niets kosten. Uw ritme
          verschuiven, en slimmer omgaan met apparaten die u al heeft. Een
          investering komt als laatste in beeld.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="bestaat">
        <h2 id="bestaat" className={styles.heading}>
          Waarom Ampeer bestaat
        </h2>
        <p className={styles.body}>
          Op 1 januari 2027 stopt de salderingsregeling. Bijna 3 miljoen
          woningen in Nederland hebben zonnepanelen. Voor al die huishoudens
          verandert er iets, en niet voor iedereen evenveel.
        </p>
        <p className={styles.body}>
          Wat het u kost, hangt vooral af van wanneer u stroom gebruikt. Niet
          van hoeveel panelen u heeft. Twee huizen met hetzelfde dak en
          hetzelfde verbruik krijgen een ander antwoord.
        </p>
        <p className={styles.body}>
          Bijna elke rekenhulp geeft toch één gemiddeld bedrag. Dat bedrag geldt
          voor niemand. Wij rekenen daarom uw eigen jaar door, in kwartieren, en
          geven u een bandbreedte in plaats van één getal.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="nakijken">
        <h2 id="nakijken" className={styles.heading}>
          Hoe u ons kunt nakijken
        </h2>
        <ul className={styles.points}>
          <li className={styles.point}>
            Onze methode staat volledig uitgeschreven, met de aannames, de
            bronnen en de bandbreedtes erbij.
          </li>
          <li className={styles.point}>
            Elk advies zegt welke regels gevuurd hebben. U ziet dus waarom u
            juist dit antwoord kreeg.
          </li>
          <li className={styles.point}>
            Boven elk bedrag staat hoe zeker het is: indicatief, goed of
            precies. Dat staat er direct bij en niet in een voetnoot.
          </li>
          <li className={styles.point}>
            Wij schrijven ook op wat wij niet weten. Over uw schaduw, uw
            apparaten en de leeftijd van uw panelen weten wij niets.
          </li>
        </ul>
        <p className={styles.body}>
          Dat staat allemaal in{" "}
          <Link href="/methodologie/">onze methodologie</Link>. Dat document is
          er om nagerekend te worden.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="wiewijzijn">
        <h2 id="wiewijzijn" className={styles.heading}>
          Wie wij zijn
        </h2>
        <dl className={styles.register}>
          <dt className={styles.term}>Naam</dt>
          <dd className={styles.detail}>{identity.legalName}</dd>
          <dt className={styles.term}>KvK-nummer</dt>
          <dd className={styles.detail}>{identity.kvkNumber}</dd>
          <dt className={styles.term}>Btw-nummer</dt>
          <dd className={styles.detail}>{identity.vatNumber}</dd>
          <dt className={styles.term}>Postadres</dt>
          <dd className={styles.detail}>{identity.postalAddress}</dd>
          <dt className={styles.term}>E-mail</dt>
          <dd className={styles.detail}>
            <a href={`mailto:${identity.contactEmail}`}>
              {identity.contactEmail}
            </a>
          </dd>
        </dl>
        <p className={styles.body}>
          Op dit webadres zat eerder een andere dienst. Die bemiddelde wel in
          energiecontracten. Die dienst heeft niets met Ampeer te maken.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="gegevens">
        <h2 id="gegevens" className={styles.heading}>
          Wat wij met uw gegevens doen
        </h2>
        <p className={styles.body}>
          Wij vragen u vier dingen en bewaren die achter uw eigen link. Van uw
          postcode bewaren wij alleen de eerste vier cijfers. Na 90 dagen is uw
          advies weg.
        </p>
        <p className={styles.body}>
          Alles daarover staat in{" "}
          <Link href="/privacy/">onze privacyverklaring</Link>.
        </p>
      </section>
    </div>
  );
}

/**
 * The route.
 *
 * Same gate as `/privacy/`, and the same reason: this page prints a
 * registration, and a registration nobody has supplied must stop the build
 * rather than reach a reader.
 */
export default function OverOnsPage() {
  return <AboutAmpeer identity={requireCompleteIdentity(IDENTITY)} />;
}
