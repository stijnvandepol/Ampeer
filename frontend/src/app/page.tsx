import type { Metadata } from "next";
import Link from "next/link";
import { DayCounting } from "@/components/day/DayCounting";
import { FaqJsonLd, PageJsonLd } from "./_shell/JsonLd";
import styles from "./home.module.css";

const PATH = "/";
const TITLE = "Zonnepanelen na 2027: wat nu, en loont een thuisbatterij?";
const DESCRIPTION =
  "Heeft u zonnepanelen en stopt de saldering ook voor u? Vier vragen, en u ziet gratis wat er bij u verandert, wat niets kost en of een thuisbatterij loont.";

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
   *
   * Since 2026-10-01 it carries the year and the battery as well, and no verb
   * about reckoning. Search Console for 14 to 28 September found this page on
   * the word "ampeer" and on nothing else, and Google's suggestions that day
   * showed what the audience types instead: "zonnepanelen 2027 wat nu" and
   * "thuisbatterij rendabel". The title names the two questions somebody
   * arrives with, in their words, and still presumes no answer to either.
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
 * The sentence under the headline: who this is for and what they get, in one
 * breath, before anything else on the page has been read.
 *
 * Until 2026-10-01 it said what the product does and not for whom, and the
 * owner's brief that day was that somebody with panels and no interest in
 * electricity has to see at once that this is meant for them.
 */
const HERO_LEAD =
  "Voor iedereen met zonnepanelen op het eigen huis. Vier vragen over uw dak en uw verbruik, en u ziet wat er vanaf 1 januari 2027 bij u verandert, wat u gratis kunt doen, en of een thuisbatterij iets voor u is.";

/**
 * Three promises under the button, each one a rule this site is tested on
 * rather than a claim about it: no account in the flow, nothing for sale in
 * the source, and "nu geen batterij" as an outcome the advice can give.
 */
const PROMISES: readonly string[] = [
  "Gratis, zonder account",
  "Wij verkopen niets",
  "Nu geen batterij is ook een antwoord",
];

/**
 * Three lines a visitor checks themselves against. Plain enough that nobody
 * needs to know what saldering is to recognise themselves in one.
 */
const FOR_WHOM: readonly string[] = [
  "U heeft zonnepanelen op uw eigen huis.",
  "U weet niet precies wat er op 1 januari 2027 verandert, of wat het u gaat kosten.",
  "U twijfelt over een thuisbatterij, of u heeft er al een offerte voor gekregen.",
];

/** What happens after the button, in the order it happens. A sequence. */
const STEPS: readonly (readonly [string, string])[] = [
  [
    "U beantwoordt vier vragen",
    "De eerste vier cijfers van uw postcode, hoeveel panelen u heeft, welke kant uw dak op ligt en hoeveel stroom u per jaar gebruikt. Dat laatste staat op uw jaarafrekening.",
  ],
  [
    "Wij rekenen uw jaar door",
    "Met de zon zoals die bij u in de buurt schijnt en met hoe een gewoon huishouden door de dag stroom gebruikt. U hoeft niets te koppelen of te installeren.",
  ],
  [
    "U ziet wat er verandert en wat u kunt doen",
    "Wat het einde van de saldering u ongeveer kost, wat u gratis kunt doen, en of een thuisbatterij bij u past. Met een link om het later terug te lezen.",
  ],
];

/** The three things the answer is made of. Not a sequence, so not numbered. */
const FEATURES: readonly (readonly [string, string])[] = [
  [
    "Een bedrag van laag tot hoog",
    "Niemand weet de stroomprijs van 2027 precies. Daarom krijgt u een bereik, en niet één getal dat zekerder klinkt dan het is.",
  ],
  [
    "Hoe zeker het antwoord is",
    "Direct naast uw bedrag staat of het een eerste indruk is of een goed onderbouwd antwoord. Niet in een voetnoot.",
  ],
  [
    "Eerst wat u niets kost",
    "De wasmachine overdag, slimmer gebruik van wat u al heeft. Pas daarna kijken wij naar een batterij, en vaak is het antwoord: nu nog niet.",
  ],
];

/**
 * The three questions, as plain text, for the FAQPage markup.
 *
 * The page renders them as JSX rather than from this array, because the second
 * answer ends in a link and JSON-LD carries text. So the same sentences live
 * twice, and that is a drift risk rather than a convenience: a FAQPage whose
 * answers differ from the answers on the page is the kind of thing that gets a
 * site ignored rather than cited.
 *
 * `frontend/tests/app/pages.test.tsx` holds them together by comparing every
 * entry here against the rendered `dt` and `dd` text, so the two cannot
 * disagree without a red test. That is also why the link's own words were
 * changed on 2026-09-15 from "is een thuisbatterij iets voor mij" to "onze
 * pagina over de thuisbatterij": the first only reads as a sentence while it is
 * a link, and the plain text a search engine gets was not one.
 */
const FAQ: readonly (readonly [string, string])[] = [
  [
    "Waarom krijg ik een bereik en niet een bedrag?",
    "Omdat een deel van de invoer nog niet vaststaat, zoals de terugleververgoeding in 2027 en de stroomprijs. Wij rekenen uw jaar daarom op veel verschillende standen door en laten zien wat daaruit komt. Een getal daaruit oppakken zou zekerder klinken dan het is.",
  ],
  [
    "Krijg ik straks te horen dat ik een batterij moet kopen?",
    "Alleen als het bij u uitkomt, en bij een deel van de huishoudens komt dat er niet uit. Nu geen batterij is bij ons een volwaardige uitkomst, en wij verdienen niets aan de andere. Waar het van afhangt, leest u bij de vraag is een thuisbatterij iets voor mij.",
  ],
  [
    "Wat kan ik met de link die ik krijg?",
    "Daarmee opent u uw antwoord later opnieuw, ook op een andere telefoon of computer, zonder in te loggen. Bewaar hem dus, en bedenk dat wie hem heeft het antwoord ook ziet.",
  ],
];

/**
 * The landing page.
 *
 * REDRAWN ON 2026-10-01, on the owner's brief that the site read as a system:
 * abstract, impersonal, built for somebody who already knows what a quarter
 * hour of offtake is. The first screen stood on the year plate's near-black
 * instrument ground, every small label was set in a monospace face, the facts
 * under it were "35.040 kwartieren" and "243 doorrekeningen" counting up, and
 * six motion components (a trailing cursor ring, a button that leaned towards
 * the pointer, spotlights, a word-by-word headline) gave it the feel of a
 * product demo. All of that is gone.
 *
 * What replaced it is daylight: the page's own ground, a heading that asks the
 * visitor's question in their words, one sun-coloured button, and the day
 * figure in a white card beside it as the one picture on the page. The figure
 * is still the only thing that moves, and only when somebody presses it.
 *
 * WHAT IS STILL NOT ON IT, and neither is an oversight. No euro amount: every
 * figure this product knows comes out of a simulation of one household with a
 * band around it. No countdown: `ampeer-no-reading-the-clock` in
 * `.semgrep/frontend.yml` makes that a gate. No social proof, which is rule
 * four: no visitor counts, no testimonials, no logos.
 */
export default function Home() {
  return (
    <>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />
      <FaqJsonLd questions={FAQ} />

      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div className={styles.heroCopy}>
            <h1 className={styles.title}>
              Wat verandert er in 2027 voor uw zonnepanelen?
            </h1>
            <p className={styles.lead}>{HERO_LEAD}</p>
            <div className={styles.heroActions}>
              <Link href="/berekenen/" className="button-accent">
                Bereken wat er bij u verandert
              </Link>
              <Link href="/thuisbatterij/" className={styles.heroSecondary}>
                Is een thuisbatterij iets voor mij?
              </Link>
            </div>
            <ul
              className={styles.promises}
              aria-label="Wat u van Ampeer mag verwachten"
            >
              {PROMISES.map((line) => (
                <li key={line} className={styles.promise}>
                  {line}
                </li>
              ))}
            </ul>
          </div>
          {/*
            The one picture, in a card of its own so the instrument keeps its
            dark strip while the page around it is day. The line above it says
            what the strip is, in words, for somebody who has never seen a load
            profile and should not need to.
          */}
          <div className={styles.heroFigure}>
            <p className={styles.figureTitle}>
              Een zonnige dag bij een gewoon huishouden
            </p>
            <DayCounting />
          </div>
        </div>
      </section>

      <div className={styles.page}>
        {/*
          Directly under the first screen, because the question a visitor
          asks first is not "how does it work" but "is this for me". The link
          is the page written for the question this audience types most:
          what, if anything, to do before the date.
        */}
        <section className={styles.section}>
          <h2 className={styles.heading}>Voor wie dit is</h2>
          <ul className={styles.forWhom}>
            {FOR_WHOM.map((line) => (
              <li key={line} className={styles.forWhomLine}>
                {line}
              </li>
            ))}
          </ul>
          <p className={styles.body}>
            Herkent u zich hierin, dan is Ampeer voor u gemaakt. U hoeft niets
            te installeren en niets van stroomprijzen te weten. Wilt u eerst
            weten of u vóór 1 januari iets moet doen, lees dan{" "}
            <Link href="/zonnepanelen-2027/">
              wat u vóór 1 januari moet regelen
            </Link>
            .
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.heading}>Hoe het werkt</h2>
          <ol className={styles.steps}>
            {STEPS.map(([name, text]) => (
              <li key={name} className={styles.step}>
                <h3 className={styles.stepName}>{name}</h3>
                <p className={styles.stepText}>{text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.section}>
          {/*
            Not "Wat u terugkrijgt". On a page about solar, "terugkrijgen"
            collides with "teruglevering" and with getting money back, and for
            a second a reader thinks something is being refunded.
          */}
          <h2 className={styles.heading}>Wat u te zien krijgt</h2>
          {/*
            Headings and paragraphs, not a description list: the page's only
            dt elements are the questions, which the FAQPage markup is checked
            against one for one.
          */}
          <div className={styles.features}>
            {FEATURES.map(([name, text]) => (
              <div key={name} className={styles.feature}>
                <h3 className={styles.featureName}>{name}</h3>
                <p className={styles.featureText}>{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={styles.trust}>
          <h2 className={styles.heading}>Waarom u ons kunt vertrouwen</h2>
          <p className={styles.body}>
            Ampeer is gratis. Er is geen abonnement, geen proefperiode en geen
            versie die wel geld kost. Wij verkopen geen panelen, geen batterijen
            en geen energiecontract, wij plaatsen geen advertenties en wij
            verkopen uw gegevens niet door.
          </p>
          <p className={styles.body}>
            Niemand betaalt ons voor de uitkomst die u krijgt. Daarom kan hier
            ook uit komen dat u nu niets hoeft te kopen, en dat is bij ons een
            gewoon antwoord. Wie er achter Ampeer zit, staat op{" "}
            <Link href="/over-ons/">over ons</Link>.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.heading}>Veelgestelde vragen</h2>
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
              uitkomst, en wij verdienen niets aan de andere. Waar het van
              afhangt, leest u bij de vraag{" "}
              <Link href="/thuisbatterij/">
                is een thuisbatterij iets voor mij
              </Link>
              .
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
            <Link href="/einde-saldering/">het einde van de saldering</Link>. De
            goedkoopste stap staat apart, want die kost niets:{" "}
            <Link href="/zelf-verbruiken/">
              meer van uw eigen stroom zelf gebruiken
            </Link>
            .
          </p>
        </section>

        <div className={styles.close}>
          <p className={styles.closeText}>
            Vier vragen over uw eigen dak, en geen enkele over uw e-mailadres.
          </p>
          <Link href="/berekenen/" className="button-accent">
            Bereken wat er bij u verandert
          </Link>
        </div>
      </div>
    </>
  );
}
