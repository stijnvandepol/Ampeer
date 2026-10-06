import type { Metadata } from "next";
import Link from "next/link";
import { FaqJsonLd, PageJsonLd } from "../_shell/JsonLd";
import styles from "../_shell/content.module.css";

const PATH = "/zelf-verbruiken/";
const TITLE = "Meer van uw eigen zonnestroom zelf gebruiken";
const DESCRIPTION =
  "De goedkoopste manier om het einde van de saldering op te vangen kost niets. Welke apparaten het verschil maken, wanneer u ze het best aanzet, en waar het ophoudt te helpen.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance, for the reason written out on
  // /einde-saldering/: Next resolves a URL here against the current pathname
  // and would canonicalise this route to the site root.
  alternates: { canonical: PATH },
  // No `openGraph` here. Metadata merging is shallow, so setting any part of
  // it would replace the root layout's siteName, locale and type.
};

/**
 * The appliances, ordered by how much of a day they can be moved.
 *
 * Named as categories rather than brands, and without a kilowatt-hour figure
 * each: what a dryer uses depends on the dryer, and a number here would be a
 * household nobody described.
 */
const APPLIANCES: readonly (readonly [string, string])[] = [
  [
    "Wasmachine, vaatwasser en droger",
    "Deze drie zijn het makkelijkst te verschuiven, want het maakt u meestal niet uit wanneer ze draaien zolang ze klaar zijn. Samen zijn ze bij veel huishoudens de grootste post die zomaar te verzetten is.",
  ],
  [
    "De elektrische boiler of warmtepompboiler",
    "Warm water dat u 's middags maakt, is 's avonds nog warm. Een boiler die standaard 's nachts opwarmt doet dat op het moment dat uw panelen niets leveren.",
  ],
  [
    "De laadpaal",
    "Een auto die overdag thuisstaat kan op de zon laden in plaats van 's nachts op het net. Staat de auto doordeweeks elders, dan geldt dit alleen in het weekend, en dat is precies het soort verschil dat een gemiddelde wegpoetst.",
  ],
  [
    "De warmtepomp",
    "Het huis een paar graden voorverwarmen terwijl de zon schijnt, zodat de pomp 's avonds minder hoeft. Dit werkt alleen bij een goed geïsoleerd huis, want een huis dat de warmte niet vasthoudt slaat niets op.",
  ],
];

/** What the window is, and why it is not a fixed clock time. */
const WINDOW: readonly string[] = [
  "In de zomer levert een dak in Nederland grofweg tussen acht uur 's ochtends en zes uur 's avonds, met het zwaartepunt rond het midden van die periode.",
  "In de winter is dat venster een stuk korter en de opbrengst een fractie, dus verschuiven levert dan minder op.",
  "Ligt uw dak op het oosten, dan zit uw piek eerder op de dag; op het westen later. Een vaste klok past dus niet op elk dak.",
  "Een bewolkte dag heeft geen scherpe piek. Het venster is er dan nog wel, maar vlakker.",
];

/** The honest limits, which is what separates this from a tip list. */
const LIMITS: readonly string[] = [
  "Wat u overdag niet gebruikt, gaat alsnog het net op. Verschuiven verhoogt uw eigen verbruik; het maakt uw teruglevering niet nul.",
  "Bent u overdag thuis en gebruikt u uw opwek al grotendeels zelf, dan is er weinig te verschuiven en levert dit weinig op.",
  "Apparaten die niet kunnen wachten, zoals een koelkast of verlichting, vallen hier buiten. Die draaien wanneer ze moeten.",
  "Er is een grens: als alles wat kan verschuiven verschoven is, is de volgende stap slimmer sturen of opslag, en dat kost wel iets.",
];

const QUESTIONS: readonly (readonly [string, string])[] = [
  [
    "Waarom loont zelf verbruiken meer na 2027?",
    "Zolang er gesaldeerd wordt, is een kilowattuur die u teruglevert bijna evenveel waard als een die u zelf gebruikt. Als dat wegstrepen stopt, krijgt u voor teruglevering een vergoeding die lager ligt dan wat u voor afname betaalt. Het verschil tussen die twee is wat u wint door de stroom zelf te gebruiken.",
  ],
  [
    "Hoe weet ik wanneer mijn panelen leveren?",
    "De omvormer van vrijwel elke installatie laat dat zien, meestal in een app. Wie een slimme meter heeft, ziet het ook aan de meterstand die op dat moment niet oploopt. Een vaste klok werkt minder goed, omdat het venster per seizoen en per dakrichting verschilt.",
  ],
  [
    "Moet ik hiervoor iets kopen?",
    "Nee. Dit is de route die niets kost: dezelfde apparaten, op een ander moment. Er bestaan timers en slimme stekkers die het automatisch doen, maar de winst zit in het verschuiven zelf en niet in het apparaat dat het voor u doet.",
  ],
  [
    "Is een wasmachine 's nachts niet goedkoper?",
    "Dat hangt van uw contract af en het is een andere vraag dan deze. Bij een dubbeltarief is nachtstroom goedkoper dan dagstroom van het net, maar zonnestroom van uw eigen dak is goedkoper dan allebei zolang u hem zelf gebruikt.",
  ],
];

/**
 * The page for the route this product puts first.
 *
 * WHY IT EXISTS SEPARATELY. /einde-saldering/ names the three routes in one
 * section and moves on. This is the one that costs nothing, the one the advice
 * shows first, and the one nobody sells, so there is no page anywhere that
 * explains how to actually do it. That is a gap in the search results as much
 * as in this site.
 *
 * ON THE LANGUAGE BOUNDARY. `frontend/CLAUDE.md` says the frontend writes
 * navigation and form text and no sentence that tells a household what to do,
 * and this page is a page of exactly such sentences. The rule is about advice:
 * `title`, `text` and `basis_text` describe one household's answer and come
 * from the API so that wording and behaviour cannot break the same test. A
 * static explainer says the same thing to everybody and is the category
 * /einde-saldering/ already established, whose ROUTES array carries the same
 * sentence about a washing machine.
 *
 * NO EURO AMOUNT and no kilowatt-hour per appliance, for the reason the two
 * sibling pages state: a figure here would be a household nobody described.
 */
export default function ZelfVerbruikenPage() {
  return (
    <div className={styles.page}>
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />
      <FaqJsonLd questions={QUESTIONS} />

      <header className={styles.hero}>
        <p className={styles.eyebrow}>De route die niets kost</p>
        <h1 className={styles.title}>
          Meer van uw eigen zonnestroom zelf gebruiken
        </h1>
        <p className={styles.lead}>
          Dit is het eerste dat u kunt doen en het kost niets: dezelfde
          apparaten, op een ander moment. Als de saldering stopt wordt een
          kilowattuur die u zelf gebruikt een stuk meer waard dan een die u
          teruglevert, en dat verschil is precies wat verschuiven u oplevert.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="waarom">
        <h2 id="waarom" className={styles.heading}>
          Waarom dit nu meer oplevert dan vroeger
        </h2>
        <p className={styles.body}>
          Salderen streept teruggeleverde stroom weg tegen afgenomen stroom. Zo
          lang dat kan, maakt het niet veel uit of u een kilowattuur meteen
          gebruikt of later terugkoopt. Als dat wegstrepen stopt, krijgt u voor
          teruglevering een vergoeding die lager ligt dan de prijs die u voor
          afname betaalt.
        </p>
        <p className={styles.body}>
          Daarmee wordt een kilowattuur die u zelf gebruikt meer waard dan een
          die het net op gaat. Verschuiven kost u niets en vergroot precies dat
          deel. Daarom staat deze route bij ons voor de twee andere, en niet
          omdat hij spannender is.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="apparaten">
        <h2 id="apparaten" className={styles.heading}>
          Welke apparaten het verschil maken
        </h2>
        <p className={styles.body}>
          Niet alles kan wachten. Wat hieronder staat kan dat meestal wel, en
          juist daar zit de winst.
        </p>
        <ul className={styles.routes}>
          {APPLIANCES.map(([name, text]) => (
            <li key={name} className={styles.route}>
              <span className={styles.routeName}>{name}</span>
              <span className={styles.routeText}>{text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="wanneer">
        <h2 id="wanneer" className={styles.heading}>
          Wanneer is overdag
        </h2>
        <p className={styles.body}>
          Er is geen vast tijdstip dat voor elk dak klopt. Dit is wat het
          venster bepaalt.
        </p>
        <ul className={styles.unknowns}>
          {WINDOW.map((line) => (
            <li key={line} className={styles.unknown}>
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section} aria-labelledby="grenzen">
        <h2 id="grenzen" className={styles.heading}>
          Waar het ophoudt te helpen
        </h2>
        <p className={styles.body}>
          Een lijst met tips die alleen de goede kant laat zien, is geen advies.
          Dit zijn de grenzen van deze route.
        </p>
        <ul className={styles.unknowns}>
          {LIMITS.map((line) => (
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

      <section className={styles.close} aria-labelledby="zelf">
        <h2 id="zelf" className={styles.heading}>
          Kijk wat het bij u doet
        </h2>
        <p className={styles.body}>
          Hoeveel deze route u oplevert hangt af van uw dak, uw verbruik en of
          er overdag iemand thuis is. Vier vragen zijn genoeg voor een eerste
          antwoord.
        </p>
        <p className={styles.act}>
          <Link href="/berekenen/">Bereken wat het bij u doet</Link>
        </p>
        <p className={styles.note}>
          Helpt verschuiven bij u niet genoeg, dan leest u op{" "}
          <Link href="/thuisbatterij/">de pagina over thuisbatterijen</Link> wat
          de volgende stap wel en niet oplevert.
        </p>
      </section>
    </div>
  );
}
