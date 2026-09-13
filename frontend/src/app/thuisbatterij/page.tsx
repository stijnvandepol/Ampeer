import type { Metadata } from "next";
import Link from "next/link";
import { FaqJsonLd, PageJsonLd } from "../_shell/JsonLd";
import styles from "../_shell/content.module.css";

const PATH = "/thuisbatterij/";
const TITLE = "Is een thuisbatterij iets voor mij?";
const DESCRIPTION =
  "Voor een deel van de huishoudens niet. Waar het van afhangt, wat er goedkoper is en eerst komt, en hoe u het voor uw eigen huis doorrekent.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance, for the reason written out on
  // /einde-saldering/: Next resolves a URL here against the current pathname
  // and would canonicalise this route to the site root.
  alternates: { canonical: PATH },
  // No `openGraph` here. Metadata merging is shallow, so setting any part of
  // it would replace the root layout's siteName, locale and type for this
  // route; Next copies title and description across on its own.
};

/** What decides it, in the order it decides it. */
const FACTORS: readonly (readonly [string, string])[] = [
  [
    "Wanneer u stroom gebruikt",
    "Een batterij verdient alleen aan stroom die u anders had teruggeleverd en later had teruggekocht. Gebruikt u het grootste deel van uw opwek al meteen zelf, dan is er weinig over om op te slaan.",
  ],
  [
    "Of er overdag iemand thuis is",
    "Een huis dat doordeweeks leeg is levert overdag bijna alles terug en koopt 's avonds bijna alles terug. Daar zit de grootste ruimte. Een huis waar de hele dag iemand is, gebruikt veel van die stroom al.",
  ],
  [
    "Hoeveel u teruglevert, niet hoeveel u opwekt",
    "Twee huizen met evenveel panelen kunnen een heel verschillend antwoord krijgen. Het gaat om het deel dat het net op gaat, en dat hangt af van uw dag en niet van uw dak.",
  ],
  [
    "Wat teruglevering u straks oplevert",
    "Na 1 januari 2027 krijgt u voor teruglevering een vergoeding in plaats van wegstrepen tegen uw afname. Hoe lager die vergoeding, hoe meer een batterij kan opleveren. Niemand weet vandaag wat het precies wordt.",
  ],
];

/** The order this product puts them in, and why that order is not arbitrary. */
const FIRST: readonly (readonly [string, string])[] = [
  [
    "Uw ritme verschuiven kost niets",
    "De wasmachine, de vaatwasser en de droger draaien terwijl uw panelen leveren. Dit vraagt geen apparaat en geen investering, en bij veel huishoudens is het de grootste post van de drie.",
  ],
  [
    "Wat u al heeft, anders inregelen",
    "Een boiler, een laadpaal of een warmtepomp die op een ander moment aanslaat. U bezit die apparaten al; ze staan alleen op een tijdstip dat niet bij uw opwek past.",
  ],
];

/** Where a battery does earn its price back, stated without a euro figure. */
const WORKS: readonly string[] = [
  "U levert een groot deel van uw opwek terug, omdat er overdag weinig gebruikt wordt.",
  "U gebruikt 's avonds en 's nachts veel, dus er is iets om de opgeslagen stroom aan kwijt te raken.",
  "U heeft al gedaan wat gratis is, zodat de batterij niet betaald wordt voor besparing die u ook zonder hem had gehad.",
  "U blijft lang genoeg in dit huis wonen om de terugverdientijd uit te zitten.",
];

/** And where it does not, which is the answer this product refuses to hide. */
const DOES_NOT: readonly string[] = [
  "U bent overdag thuis en gebruikt uw opwek al grotendeels zelf.",
  "U heeft weinig panelen, dus er is weinig overschot om op te slaan.",
  "Uw avondverbruik is klein, waardoor een volle batterij 's ochtends nog vol is.",
  "U wilt binnen een paar jaar verhuizen.",
];

const UNKNOWNS: readonly string[] = [
  "Wij weten niet hoeveel schaduw er op uw dak valt en vragen er niet naar.",
  "Wij weten niet welke apparaten u heeft of wanneer u ze aanzet.",
  "Niemand weet wat de terugleververgoeding in 2027 werkelijk wordt. Wij rekenen met een band en niet met een getal.",
  "Wat een batterij kost verschilt sterk per offerte, en die prijs bepaalt de terugverdientijd meer dan welke andere aanname ook.",
];

/**
 * The questions, rendered and marked up from the same array.
 *
 * Short enough to be read in a search result and complete enough to be an
 * answer there. A question whose answer is "het hangt ervan af, reken het uit"
 * is a question that wasted somebody's click.
 */
const QUESTIONS: readonly (readonly [string, string])[] = [
  [
    "Verdient een thuisbatterij zich terug?",
    "Bij een deel van de huishoudens wel en bij een deel niet. Het hangt af van hoeveel u teruglevert en wat u 's avonds gebruikt, en van de prijs van de offerte. Wij rekenen met een bandbreedte, omdat een enkel getal hier altijd te veel zekerheid uitstraalt.",
  ],
  [
    "Heb ik een thuisbatterij nodig als de saldering stopt?",
    "Nodig is het niet. Het einde van de saldering maakt het aantrekkelijker om uw eigen stroom zelf te gebruiken, en dat kan ook door apparaten op een ander moment te laten draaien. Dat kost niets en komt daarom eerst.",
  ],
  [
    "Hoe groot moet een thuisbatterij zijn?",
    "Groot genoeg om uw avondverbruik te dragen en niet groter. Een batterij die 's ochtends nog halfvol is heeft capaciteit die u betaald heeft en niet gebruikt. Wat bij u past hangt af van uw eigen dagpatroon.",
  ],
  [
    "Kan ik met een thuisbatterij van het net af?",
    "Nee. In de winter wekken panelen in Nederland een fractie op van wat ze in de zomer doen, en geen batterij van huishoudelijke omvang overbrugt dat seizoen. Een batterij verschuift stroom over uren, niet over maanden.",
  ],
];

/**
 * The page somebody lands on after typing the question into a search engine.
 *
 * WHAT IT IS FOR. It answers in the first paragraph and then explains. A page
 * that introduces itself first is a page people leave, and the question here
 * has an answer that is genuinely useful before any calculation: for a lot of
 * households it is no, or not yet.
 *
 * WHY THE ORDER IS THIS ORDER. The two free routes come before the battery,
 * which is the same order the advice itself uses and the same order `CLAUDE.md`
 * requires. It is not a rhetorical device: a battery credited with savings that
 * shifting your washing machine would also have produced looks better than it
 * is, and that is the single easiest way to make this product dishonest.
 *
 * NO EURO AMOUNT, anywhere, for the reason /einde-saldering/ states: every euro
 * figure this product knows comes out of a simulation of one household with a
 * band around it. A figure here would be a household nobody described.
 */
export default function ThuisbatterijPage() {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />
      <FaqJsonLd questions={QUESTIONS} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>Het eerlijke antwoord</p>
        <h1 className={styles.title}>Is een thuisbatterij iets voor mij?</h1>
        <p className={styles.lead}>
          Voor een flink deel van de huishoudens is het antwoord nee, of nog
          niet. Het hangt niet af van hoeveel panelen u heeft, maar van wanneer
          u stroom gebruikt. En er zijn twee dingen die goedkoper zijn en die
          eerst komen.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="waarvan">
        <h2 id="waarvan" className={styles.heading}>
          Waar het van afhangt
        </h2>
        <p className={styles.body}>
          Een thuisbatterij verdient aan één ding: stroom die u anders had
          teruggeleverd en later duurder had teruggekocht. Alles wat u al meteen
          zelf gebruikt, levert een batterij niets op. Daarom zijn dit de vier
          dingen die de uitkomst bepalen.
        </p>
        <ul className={styles.routes}>
          {FACTORS.map(([name, text]) => (
            <li key={name} className={styles.route}>
              <span className={styles.routeName}>{name}</span>
              <span className={styles.routeText}>{text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="eerst">
        <h2 id="eerst" className={styles.heading}>
          Wat vóór een batterij komt
        </h2>
        <p className={styles.body}>
          Deze twee kosten niets of bijna niets, en ze doen deels hetzelfde werk
          als een batterij. Wie ze overslaat en meteen een batterij koopt,
          betaalt voor besparing die ook gratis te krijgen was.
        </p>
        <ul className={styles.routes}>
          {FIRST.map(([name, text]) => (
            <li key={name} className={styles.route}>
              <span className={styles.routeName}>{name}</span>
              <span className={styles.routeText}>{text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="wel">
        <h2 id="wel" className={styles.heading}>
          Wanneer een batterij wel kan uitkomen
        </h2>
        <p className={styles.body}>
          Hoe meer van deze vier op u van toepassing zijn, hoe waarschijnlijker
          het wordt.
        </p>
        <ul className={styles.unknowns}>
          {WORKS.map((line) => (
            <li key={line} className={styles.unknown}>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="niet">
        <h2 id="niet" className={styles.heading}>
          Wanneer hij dat niet doet
        </h2>
        <p className={styles.body}>
          Dit is een volwaardige uitkomst en bij ons geen mislukking. Een advies
          dat nooit nee zegt, is geen advies.
        </p>
        <ul className={styles.unknowns}>
          {DOES_NOT.map((line) => (
            <li key={line} className={styles.unknown}>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="vragen">
        <h2 id="vragen" className={styles.heading}>
          Veelgestelde vragen
        </h2>
        <dl className={styles.faq}>
          {QUESTIONS.map(([question, answer]) => (
            <div key={question}>
              <dt className={styles.question}>{question}</dt>
              <dd className={styles.answer}>{answer}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={styles.section} aria-labelledby="niet-weten">
        <h2 id="niet-weten" className={styles.heading}>
          Wat wij niet weten
        </h2>
        <ul className={styles.unknowns}>
          {UNKNOWNS.map((line) => (
            <li key={line} className={styles.unknown}>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.close} aria-labelledby="zelf">
        <h2 id="zelf" className={styles.heading}>
          Reken het uit voor uw eigen huis
        </h2>
        <p className={styles.body}>
          Vier vragen zijn genoeg voor een eerste antwoord. U hoeft niets te
          koppelen en geen account te maken.
        </p>
        <p className={styles.act}>
          <Link href="/berekenen/">Bereken wat het bij u doet</Link>
        </p>
        <p className={styles.note}>
          Heeft u de gratis route nog niet uitgeprobeerd, begin daar:{" "}
          <Link href="/zelf-verbruiken/">
            meer van uw eigen stroom zelf gebruiken
          </Link>
          . Wij verkopen geen batterijen en geven uw gegevens niet door aan een
          installateur. Hoe het antwoord tot stand komt staat op{" "}
          <Link href="/methodologie/">de methodepagina</Link>.
        </p>
      </section>
    </div>
  );
}
