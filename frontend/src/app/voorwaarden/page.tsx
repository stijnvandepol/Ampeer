import type { Metadata } from "next";
import Link from "next/link";

import { PageJsonLd } from "../_shell/JsonLd";
import {
  IDENTITY,
  requireCompleteIdentity,
  type CompleteIdentity,
} from "../privacy/identity";
import styles from "../privacy/legal.module.css";

const PATH = "/voorwaarden/";
const TITLE = "Gebruiksvoorwaarden";
const DESCRIPTION =
  "Wat de rekenmachine van Ampeer is en niet is, waarvan Ampeer betaald wordt, en waar u zelf voor instaat als u de dienst gebruikt.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: PATH },
  // Deliberately absent: `openGraph`, the reason privacy/page.tsx gives.
};

/**
 * The terms of use, and the disclaimer the advice needs.
 *
 * WHY ITS OWN PAGE. A disclaimer that sat on a methodology page would be one
 * nobody finds at the moment it matters. The owner chose a dedicated route
 * over a section, on 2026-09-07.
 *
 * WHY THE ORDER. `/over-ons/`'s principle: what a reader has to know before
 * trusting the advice comes first, then who Ampeer is, then the rules. A page
 * that opened with the rules would have buried the disclaimer.
 *
 * WHAT IT MAY NOT CARRY. No countdown, no scarcity, no social proof and no
 * call to action, the five rules `frontend/CLAUDE.md` states for the whole
 * site. A third kind of call to action on top of the two the spec allows
 * would turn a disclaimer into a funnel.
 */
export function TermsPage({
  identity,
}: {
  readonly identity: CompleteIdentity;
}) {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Voorwaarden</p>
        <h1 className={styles.title}>Gebruiksvoorwaarden</h1>
        <p className={styles.lead}>
          Deze pagina zegt wat Ampeer is en niet is, waarvan het betaald wordt,
          en waar u zelf voor instaat.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="wataimpeer">
        <h2 id="wataimpeer" className={styles.heading}>
          Wat Ampeer is
        </h2>
        <p className={styles.body}>
          Ampeer is een rekenmachine. Met uw antwoorden en met
          standaardprofielen rekent hij uit wat het einde van de
          salderingsregeling u kost.
        </p>
        <p className={styles.body}>
          Hij zegt ook welke van drie routes voor u het beste past. Elk bedrag
          komt met een bandbreedte, want wij rekenen de hele berekening 243 keer
          door, met aannames die wij niet zeker weten.
        </p>
        <p className={styles.body}>
          Het woord bij uw advies (indicatief, goed of precies) zegt hoeveel u
          ons verteld heeft. Precies kunt u vandaag niet krijgen.
        </p>
        <p className={styles.body}>
          Dit is de samenvatting. De volledige methode staat in{" "}
          <Link href="/methodologie/">onze methodologie</Link>.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="watietniet">
        <h2 id="watietniet" className={styles.heading}>
          Wat Ampeer niet is
        </h2>
        <p className={styles.body}>
          Ampeer geeft geen financieel advies, geen installatieadvies en geen
          advies over een energiecontract.
        </p>
        <p className={styles.body}>
          Onze getallen zijn een schatting op een verzonnen jaar met
          standaardprofielen. Uw dak, uw apparaten en het tarief van 2027 kennen
          wij niet.
        </p>
        <p className={styles.body}>
          U beslist zelf. Een beslissing over een batterij of panelen neemt u
          met een offerte in de hand, niet met dit scherm.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="betaald">
        <h2 id="betaald" className={styles.heading}>
          Waarvan Ampeer betaald wordt
        </h2>
        <p className={styles.body}>
          Wij verkopen geen panelen, geen batterijen en geen energiecontract, en
          plaatsen geen advertenties. Niemand betaalt ons voor de uitkomst die u
          krijgt.
        </p>
        <p className={styles.body}>
          Vandaag verdienen wij niets aan uw advies. Verandert dat, dan staat
          het hier en op <Link href="/over-ons/">de pagina over ons</Link>{" "}
          voordat het gebeurt.
        </p>
        <p className={styles.body}>
          Gaat Ampeer ooit doorverwijzen, dan vragen wij daar apart toestemming
          voor. Uw advies verandert er niet door.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="accountvoorwaarden">
        <h2 id="accountvoorwaarden" className={styles.heading}>
          Uw account
        </h2>
        <p className={styles.body}>
          Een account per e-mailadres. U kiest en bewaart uw wachtwoord; wij
          kunnen het niet lezen en geven het niet terug. Bent u het kwijt, dan
          herstelt u het via de mail.
        </p>
        <p className={styles.body}>
          Verwijderen is definitief en doet u zelf, met uw wachtwoord erbij.
          Vandaag bewaart een account uw toestemmingen en kunt u exporteren.
          Straks koppelt het, met een bevestigd adres, een slimme meter.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="niet-instaan">
        <h2 id="niet-instaan" className={styles.heading}>
          Waarvoor wij niet instaan
        </h2>
        <p className={styles.body}>
          De uitkomst is een schatting en geen belofte. Wij zijn niet
          aansprakelijk voor een beslissing die u op die schatting neemt, voor
          zover de wet ons toestaat dat uit te sluiten.
        </p>
        <p className={styles.body}>
          De dienst kan er even niet zijn. Wij beloven geen beschikbaarheid.
        </p>
      </section>

      <section
        className={styles.section}
        aria-labelledby="watwijvragenvoorwaarden"
      >
        <h2 id="watwijvragenvoorwaarden" className={styles.heading}>
          Wat wij van u vragen
        </h2>
        <p className={styles.body}>
          Gebruik de dienst voor uw eigen huishouden, of voor iemand die u
          daarom vroeg. Probeer niet in te breken, te overbelasten of om de
          tempolimieten heen te werken. Maak geen account op een adres dat niet
          van u is.
        </p>
        <p className={styles.body}>Meer regels zijn er niet.</p>
      </section>

      <section className={styles.section} aria-labelledby="rechtenklachten">
        <h2 id="rechtenklachten" className={styles.heading}>
          Recht en klachten
        </h2>
        <p className={styles.body}>Nederlands recht is van toepassing.</p>
        <p className={styles.body}>
          Een klacht over de dienst gaat naar {identity.contactEmail}. Een vraag
          of klacht over uw gegevens gaat naar {identity.privacyEmail}.
        </p>
        <p className={styles.body}>
          Over uw gegevens kunt u ook terecht bij de{" "}
          <a href="https://www.autoriteitpersoonsgegevens.nl/">
            Autoriteit Persoonsgegevens
          </a>
          .
        </p>
      </section>

      <section className={styles.section} aria-labelledby="overdezevoorwaarden">
        <h2 id="overdezevoorwaarden" className={styles.heading}>
          Over deze voorwaarden
        </h2>
        <p className={styles.body}>
          Een wijziging komt op deze pagina te staan, met een nieuwe datum. Een
          wijziging die u iets kost komt hier te staan voordat hij ingaat.
        </p>
        <p className={styles.body}>
          Zie ook <Link href="/privacy/">onze privacyverklaring</Link>,{" "}
          <Link href="/over-ons/">de pagina over ons</Link> en{" "}
          <Link href="/methodologie/">onze methodologie</Link>.
        </p>
        <p className={styles.note}>Laatst gewijzigd op 7 september 2026.</p>
      </section>
    </div>
  );
}

/**
 * The route.
 *
 * Same gate as `/privacy/` and `/over-ons/`, for the same reason: this page
 * names the entity behind Ampeer twice, in the colophon-free form of two
 * email addresses, and a fact nobody has supplied must stop the build.
 */
export default function VoorwaardenPage() {
  return <TermsPage identity={requireCompleteIdentity(IDENTITY)} />;
}
