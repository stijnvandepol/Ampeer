import type { Metadata } from "next";
import Link from "next/link";
import { DayCounting } from "@/components/day/DayCounting";
import { Beam } from "@/components/motion/Beam";
import { CountUp } from "@/components/motion/CountUp";
import { Cursor } from "@/components/motion/Cursor";
import { HeroHeading } from "@/components/motion/HeroHeading";
import { Magnetic } from "@/components/motion/Magnetic";
import { Mesh } from "@/components/motion/Mesh";
import { Rail } from "@/components/motion/Rail";
import { SpotlightCard } from "@/components/motion/SpotlightCard";
import { PageJsonLd } from "./_shell/JsonLd";
import reveal from "@/components/motion/reveal.module.css";
import styles from "./home.module.css";

const PATH = "/";
const TITLE = "Zonnepanelen na saldering: reken uw huis door";
const DESCRIPTION =
  "Vier vragen over uw dak en uw verbruik, en u ziet wat het einde van de salderingsregeling bij uw huis doet, met de bandbreedte erbij. Gratis, geen account.";

export const metadata: Metadata = {
  /*
   * "Reken uw huis door" and not "wat het u kost". A title that presumes a cost
   * presumes the answer, and for a household with high self-consumption the
   * answer is close to nothing; "nu geen batterij" being a valid outcome and
   * "het kost u weinig" being a valid outcome are the same rule, and this page
   * is read before either has been computed.
   *
   * It carries "zonnepanelen", which the previous title did not, and which is
   * the head noun of nearly every search that could arrive here. It also stops
   * competing with /einde-saldering/, whose title says almost the same thing:
   * that page takes the informational phrasing and this one takes the verb.
   */
  title: TITLE,
  /*
   * Its own, rather than the root layout's. Until 2026-08-31 this page had no
   * description at all and inherited an 88 character one written for the site
   * as a whole, which is below the length a search result uses and says "kost"
   * where this page deliberately does not.
   */
  description: DESCRIPTION,
  alternates: { canonical: PATH },
};

/**
 * The four facts on the rail. Every one is checkable and none is about people.
 *
 * This is the slot a landing page normally fills with social proof, and rule
 * four of the frontend spec forbids that outright: no visitor counts, no
 * testimonials, no logos. The slot is not left empty, because what it does is
 * useful and the reason it is usually filled dishonestly is that honest
 * material is harder to find. These four are the honest material: what the
 * product is made of, what it refuses, and what it publishes.
 */
const FACTS: readonly {
  readonly value: number;
  readonly grouped?: boolean;
  readonly counted?: boolean;
  readonly unit: string;
  readonly text: string;
}[] = [
  {
    value: 35040,
    grouped: true,
    unit: "kwartieren",
    text: "Zoveel kwartieren heeft een jaar, en op elk ervan rekenen wij uw huis door. Geen gemiddelde dag en geen jaartotaal.",
  },
  {
    value: 243,
    unit: "doorrekeningen",
    text: "Zo vaak rekenen wij uw jaar opnieuw door, met de onzekere aannames op verschillende standen. Wat u ziet is de bandbreedte die daaruit komt.",
  },
  {
    value: 4,
    unit: "vragen",
    text: "Meer hoeft u niet in te vullen. Geen account, geen e-mailadres, en niets aan uw meterkast.",
  },
  {
    // Not counted up. A number that races to zero is a joke, and this is the
    // card where the argument is that nothing is being sold; a gag in that slot
    // costs more than the animation is worth.
    value: 0,
    counted: false,
    unit: "dingen te koop",
    text: "Geen panelen, geen batterijen, geen energiecontract, en geen doorverwijzing naar een partij die dat wel doet.",
  },
];

/** The three things the answer is made of. One card each. */
const FEATURES: readonly (readonly [string, string])[] = [
  [
    "Een bedrag van laag tot hoog, geen los getal",
    "U krijgt een bedrag per jaar als een bereik. Het middelpunt is een markering in dat bereik en niet het antwoord, want dat middelpunt weten wij minder zeker dan het eruitziet.",
  ],
  [
    "U ziet meteen hoe zeker het is",
    "Bij uw bedrag staat of het indicatief, goed of precies is. Dat staat er direct naast en niet in een voetnoot, want hoe zeker een antwoord is hoort bij het antwoord.",
  ],
  [
    "Eerst wat u niets kost",
    "Uw ritme verschuiven, en slimmer sturen met apparaten die u al heeft. Opslag komt daarna, en bij een deel van de huishoudens komt daar uit: nu geen batterij.",
  ],
];

/** What happens after the button, in the order it happens. */
const STEPS: readonly (readonly [string, string])[] = [
  [
    "U beantwoordt vier vragen",
    "De eerste vier cijfers van uw postcode, hoeveel wattpiek er op uw dak ligt, welke kant dat dak op ligt, en uw jaarverbruik.",
  ],
  [
    "Wij bouwen uw jaar op",
    "Een kwartierprofiel van een heel jaar, uit de verbruiksprofielen die netbeheerders publiceren en de instraling voor uw postcodegebied.",
  ],
  [
    "U ziet uw bereik en drie routes",
    "Met een link waarmee u er later bij kunt, zonder account. Wilt u het scherper, dan komen er vijf vragen bij.",
  ],
];

/**
 * The landing page.
 *
 * WHAT THE FIRST SCREEN DOES. It says what this is, once, large, and offers the
 * way in. Nothing else. Everything that explains, qualifies or measures is
 * below it, because a first screen that carries six short paragraphs is a first
 * screen a visitor has to read before they know whether to.
 *
 * WHAT IS NOT ON IT, and neither is an oversight. There is no euro amount
 * anywhere: every euro figure this product knows comes out of a simulation of
 * one household with a band around it, and one printed here would be a number
 * nobody computed for the person reading it. There is no date arithmetic: a
 * page that counts down to 1 January 2027 manufactures urgency out of a
 * calendar, and `ampeer-no-reading-the-clock` in `.semgrep/frontend.yml` makes
 * that a gate rather than a resolution. And there is no social proof, which is
 * rule four: the rail where a landing page usually puts visitor counts and
 * testimonials carries four checkable facts about the product instead.
 *
 * WHERE THE MOTION IS TUNED. Each component owns its own timing and says so at
 * the top of its file: HeroHeading, Mesh, SpotlightCard, CountUp, Beam,
 * Magnetic, Cursor, Rail, and reveal.module.css for the section wipe. Nothing
 * on this page reaches into another component's numbers.
 */
export default function Home() {
  return (
    <>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />
      <Cursor />

      <section className={styles.hero}>
        <Mesh />
        <div className={styles.heroInner}>
          {/*
            The eyebrow says who this is for. It used to carry the date, which
            reads as a deadline banner directly above display type; the date is
            an orienting fact and it belongs in the sentence below rather than
            over the headline.
          */}
          <p className={styles.eyebrow}>Voor huishoudens met zonnepanelen</p>
          {/*
            The subject is in the type a stranger actually reads. It used to be
            "Reken het door voor uw eigen huis": at this size the headline is
            read before the eyebrow, so "het" met a reader with no antecedent
            while the eyebrow carried the whole subject at a tenth the size.
            The full stop is also the setter's guaranteed break point.
          */}
          <HeroHeading
            text="Saldering stopt. Reken uw eigen huis door."
            className={styles.title}
          />
          <p className={styles.lead}>
            Vier vragen over uw dak en uw verbruik, en u ziet wat er vanaf 1
            januari 2027 bij u verandert, met de marge eromheen.
          </p>
          <Magnetic>
            <Link href="/berekenen/" className="button-accent">
              Beantwoord vier vragen
            </Link>
          </Magnetic>
          {/*
            "Duurt ongeveer een minuut" stood here and is gone. Nobody timed
            it, so it was the one unmeasured claim on the page, and its job was
            to reassure that this would be quick, which is the softest possible
            form of the thing rule four is about. "Vier vragen" is on the button
            and a reader can draw their own conclusion.
          */}
          <p className={styles.note}>
            Geen account, geen e-mailadres. U krijgt een link waarmee u er later
            bij kunt.
          </p>
        </div>
      </section>

      <div className={styles.page}>
        <h2 className={styles.heading}>Waar het antwoord op rust</h2>
        <Rail className={reveal.reveal}>
          {FACTS.map((fact) => (
            <SpotlightCard key={fact.unit} className={styles.fact}>
              <p className={styles.factValue}>
                {fact.counted === false ? (
                  fact.value
                ) : (
                  <CountUp to={fact.value} grouped={fact.grouped ?? false} />
                )}{" "}
                <span className={styles.factUnit}>{fact.unit}</span>
              </p>
              <p className={styles.factText}>{fact.text}</p>
            </SpotlightCard>
          ))}
        </Rail>

        {/*
          The paragraph that stood here explained the regeling, and
          /einde-saldering/ explains it better and at length. This page does not
          need to teach the rule; it needs to show what it does about it, and
          the figure is the best thing on either page for that.
        */}
        <section className={`${styles.section} ${reveal.reveal}`}>
          <h2 className={styles.heading}>Waarom het moment telt</h2>
          <DayCounting />
        </section>

        <section className={`${styles.section} ${reveal.reveal}`}>
          {/*
            Not "Wat u terugkrijgt". On a page about solar, "terugkrijgen"
            collides with "teruglevering" and with getting money back, and for
            a second a reader thinks something is being refunded.
          */}
          <h2 className={styles.heading}>Wat u te zien krijgt</h2>
          <div className={styles.features}>
            {FEATURES.map(([name, text]) => (
              <SpotlightCard key={name} className={styles.feature}>
                <h3 className={styles.featureName}>{name}</h3>
                <p className={styles.featureText}>{text}</p>
              </SpotlightCard>
            ))}
          </div>
        </section>

        <section className={`${styles.section} ${reveal.reveal}`}>
          <h2 className={styles.heading}>Hoe het werkt</h2>
          <ol className={styles.steps}>
            {STEPS.map(([name, text], at) => (
              <li key={name} className={styles.step}>
                {at < STEPS.length - 1 && (
                  <Beam className={styles.beam} d="M 50 0 L 50 100" />
                )}
                <span className={styles.stepNumber} aria-hidden="true">
                  {at + 1}
                </span>
                <div>
                  <h3 className={styles.stepName}>{name}</h3>
                  <p className={styles.stepText}>{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className={`${styles.section} ${reveal.reveal}`}>
          <h2 className={styles.heading}>Wat het kost</h2>
          <p className={styles.body}>
            Niets. Er is geen abonnement, geen proefperiode en geen versie die
            wel geld kost. Wij verkopen geen panelen, geen batterijen en geen
            energiecontract, wij plaatsen geen advertenties en wij verkopen uw
            gegevens niet door.
          </p>
          {/*
            This paragraph used to argue with an unnamed opponent, and that same
            sentence already stands on /einde-saldering/. Stating the outcome
            plainly is stronger than explaining why somebody else could not
            state it.
          */}
          <p className={styles.body}>
            Daarom kan hier ook uit komen dat u nu geen batterij nodig heeft, en
            dat is bij ons een gewone uitkomst.
          </p>
        </section>

        <section className={`${styles.section} ${reveal.reveal}`}>
          <h2 className={styles.heading}>Veelgestelde vragen</h2>
          {/*
            All three are about the tool. /einde-saldering/ already carries the
            seven questions about the regeling itself, and asking "moet ik iets
            installeren" on both pages is the same answer printed twice; that
            one now lives in the third fact card, where it is the objection that
            actually stops people.
          */}
          <dl className={styles.faq}>
            <dt className={styles.question}>
              Waarom krijg ik een bereik en niet een bedrag?
            </dt>
            <dd className={styles.answer}>
              Omdat een deel van de invoer nog niet vaststaat, zoals de
              terugleververgoeding in 2027 en de stroomprijs. Wij rekenen uw
              jaar daarom op veel verschillende standen door en laten zien wat
              daaruit komt. Een getal daaruit oppakken zou zekerder klinken dan
              het is.
            </dd>
            <dt className={styles.question}>
              Krijg ik straks te horen dat ik een batterij moet kopen?
            </dt>
            <dd className={styles.answer}>
              Alleen als het bij u uitkomt, en bij een deel van de huishoudens
              komt dat er niet uit. Nu geen batterij is bij ons een volwaardige
              uitkomst, en wij verdienen niets aan de andere.
            </dd>
            <dt className={styles.question}>
              Wat kan ik met de link die ik krijg?
            </dt>
            <dd className={styles.answer}>
              Daarmee opent u uw antwoord later opnieuw, ook op een andere
              telefoon of computer, zonder in te loggen. Bewaar hem dus, en
              bedenk dat wie hem heeft het antwoord ook ziet.
            </dd>
          </dl>
          <p className={styles.body}>
            Wat er op 1 januari 2027 precies verandert, staat op{" "}
            <Link href="/einde-saldering/">het einde van de saldering</Link>.
          </p>
        </section>

        <div className={styles.close}>
          {/*
            Not "Vier vragen, en u weet wat het bij u doet in plaats van
            gemiddeld". That is the better line and it closes
            /einde-saldering/, where the argument against averages has just been
            made at length and it lands as a conclusion. Identical closing lines
            on two pages make both of them read as a template.
          */}
          <p className={styles.closeText}>
            Vier vragen over uw eigen dak, en geen enkele over uw e-mailadres.
          </p>
          <Magnetic>
            <Link href="/berekenen/" className="button-accent">
              Beantwoord vier vragen
            </Link>
          </Magnetic>
        </div>
      </div>
    </>
  );
}
