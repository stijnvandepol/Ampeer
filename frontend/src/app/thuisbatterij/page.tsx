import type { Metadata } from "next";
import Link from "next/link";
import { FaqJsonLd, PageJsonLd } from "../_shell/JsonLd";
import styles from "../_shell/content.module.css";

const PATH = "/thuisbatterij/";
const TITLE = "Is een thuisbatterij iets voor mij?";
const DESCRIPTION =
  "Voor een deel van de huishoudens is een thuisbatterij niets, of nog niet. Waar het van afhangt, wat goedkoper is en eerst komt, en hoe u het voor uw eigen huis doorrekent.";
/** The last day the words on this page changed; also the JSON-LD's date. */
const UPDATED = { iso: "2026-09-18", text: "18 september 2026" };

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
  "Niemand weet wat uw leverancier in 2027 werkelijk voor teruglevering betaalt. De wet geeft alleen een ondergrens, tot 2030 minimaal de helft van het kale leveringstarief. Wij rekenen met een band en niet met een getal.",
  "Wat een batterij kost verschilt sterk per offerte, en die prijs bepaalt de terugverdientijd meer dan welke andere aanname ook.",
];

/**
 * What to check in a quote. Practical and without a number of our own, because
 * the number that matters is on the quote and not on this page.
 */
const QUOTE_CHECKS: readonly (readonly [string, string])[] = [
  [
    "Nuttige capaciteit, niet bruto",
    "Een batterij mag nooit helemaal leeg. De capaciteit die u werkelijk kunt gebruiken staat soms kleiner in de specificaties dan het getal op de doos. Vraag naar de nuttige capaciteit in kWh.",
  ],
  [
    "Vermogen in kW, naast capaciteit in kWh",
    "Capaciteit zegt hoeveel erin past, vermogen zegt hoe snel het erin en eruit kan. Een batterij die langzamer laadt dan uw panelen opwekken, mist het middaguur.",
  ],
  [
    "Garantie in jaren en in laadcycli",
    "Fabrikanten garanderen een aantal jaren of een aantal cycli, wat het eerst komt. Een batterij die elke dag een keer vol en leeg gaat maakt 365 cycli per jaar. Reken dat om naar jaren voordat u garanties vergelijkt.",
  ],
  [
    "Wat er in de prijs zit",
    "Omvormer, montage, aansluiting op de meterkast en een eventuele aanpassing van de groepenkast. Een lage prijs zonder installatie is geen lage prijs.",
  ],
  [
    "Welke besparing de offerte u belooft",
    "Rekent de installateur besparing mee die u ook krijgt door de wasmachine overdag te laten draaien, dan wordt de batterij betaald voor werk dat gratis was. Vraag naar de besparing bovenop wat u zonder batterij ook kunt doen.",
  ],
];

/**
 * Where the facts on this page come from.
 *
 * Every number and every claim about a regeling on this page traces to one of
 * these, with the date it was read. Named sources are the difference between
 * a page that says something and a page that can be checked, and the pages
 * that get cited by a search engine or an AI answer are the second kind.
 */
const SOURCES: readonly {
  readonly what: string;
  readonly who: string;
  readonly when: string;
  readonly url: string;
}[] = [
  {
    what: "Thuisbatterij: zonne-energie opslaan",
    who: "Milieu Centraal",
    when: "pagina van 10 september 2026, gelezen op 15 september 2026",
    url: "https://www.milieucentraal.nl/energie-besparen/zonnepanelen/thuisbatterij-zonne-energie-opslaan/",
  },
  {
    what: "Btw-tarief zonnepanelen, wat valt niet onder het 0%-tarief",
    who: "Belastingdienst",
    when: "gelezen op 15 september 2026",
    url: "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/btw/tarieven_en_vrijstellingen/goederen_0_btw/btw-tarief-zonnepanelen",
  },
  {
    what: "Salderingsregeling stopt in 2027",
    who: "Rijksoverheid",
    when: "gelezen op 15 september 2026",
    url: "https://www.rijksoverheid.nl/themas/klimaat-milieu-en-natuur/energie-thuis/salderingsregeling",
  },
  {
    what: "Miljoenennota 2027: geen subsidie of btw-nultarief thuisbatterij",
    who: "Eerlijk over Thuisbatterijen",
    when: "artikel van 15 september 2026, gelezen op 18 september 2026",
    url: "https://www.eerlijkoverthuisbatterijen.nl/kennisbank/thuisbatterij-subsidie-2027-miljoenennota/",
  },
  {
    what: "Tweede Kamer steunt onderzoek naar btw-nultarief voor thuisbatterij",
    who: "Solar Magazine",
    when: "motie van 10 juni 2026, gelezen op 15 september 2026",
    url: "https://solarmagazine.nl/nieuws-zonne-energie/i43976/tweede-kamer-steunt-onderzoek-naar-btw-nultarief-voor-thuisbatterij",
  },
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
    "Wat kost een thuisbatterij?",
    "Milieu Centraal noemt voor een gemiddelde batterij van 6 kWh, inclusief omvormer en installatie, een paar duizend euro. De prijs verschilt sterk per offerte en per merk, en juist die prijs bepaalt de terugverdientijd meer dan welke andere aanname ook.",
  ],
  [
    "Krijg ik subsidie of btw-korting op een thuisbatterij?",
    "Nee. Er is geen landelijke subsidie en de levering en installatie van een thuisbatterij valt niet onder het btw-nultarief dat wel voor zonnepanelen geldt, dus u betaalt 21 procent btw. De Tweede Kamer vroeg het kabinet op 10 juni 2026 om een nultarief te onderzoeken; in het Belastingplan 2027 van Prinsjesdag staat er niets over, dus het blijft 21 procent.",
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
 * NO EURO AMOUNT OF OUR OWN, for the reason /einde-saldering/ states: every
 * euro figure this product knows comes out of a simulation of one household
 * with a band around it. A figure here would be a household nobody described.
 * A figure from a named source, quoted as that source's and dated, is a
 * different thing: Milieu Centraal's "een paar duizend euro" is on the page
 * with its name attached, and the test that keeps digits away from the word
 * euro lets it through because it carries none.
 *
 * SOURCES, since 2026-09-15. Measured against the page that outranks this one
 * for the question in the title: 2433 words to 906, and the difference was
 * not prose but facts with a name on them. What went in is what could be
 * checked: the btw rule as the Belastingdienst states it, the floor under the
 * feed-in fee as Rijksoverheid states it, the price and the average
 * self-consumption as Milieu Centraal states them, each with the date read.
 * A retrieval crawler cites a page that names its sources over one that
 * asserts, and so does a careful reader.
 */
export default function ThuisbatterijPage() {
  return (
    <div className={styles.page}>
      <PageJsonLd
        path={PATH}
        name={TITLE}
        description={DESCRIPTION}
        dateModified={UPDATED.iso}
      />
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
          zelf gebruikt, levert een batterij niets op. Gemiddeld gebruikt een
          huishouden ongeveer 30 procent van de stroom van de eigen panelen
          meteen zelf, volgens Milieu Centraal, en gaat de rest het net op. Hoe
          ver u van dat gemiddelde af zit, bepaalt het antwoord. Daarom zijn dit
          de vier dingen die de uitkomst bepalen.
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
          Wanneer een thuisbatterij wel kan uitkomen
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
          Wanneer een thuisbatterij dat niet doet
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

      <section className={styles.section} aria-labelledby="kosten">
        <h2 id="kosten" className={styles.heading}>
          Wat een batterij kost en wat de overheid doet
        </h2>
        <p className={styles.body}>
          Milieu Centraal noemt voor een gemiddelde thuisbatterij van 6 kWh,
          inclusief omvormer en installatie, een paar duizend euro, en schrijft
          erbij dat u die op dit moment hoogstwaarschijnlijk niet terugverdient
          met de besparing op uw stroomrekening. Dat is een gemiddelde over
          huishoudens die sterk van elkaar verschillen, en precies daarom rekent
          Ampeer het per huis uit.
        </p>
        <p className={styles.body}>
          Er is geen landelijke subsidie op een thuisbatterij. Het btw-nultarief
          dat sinds 2023 voor zonnepanelen geldt, geldt niet voor de levering en
          installatie van een batterij: de Belastingdienst noemt die
          uitdrukkelijk bij wat er niet onder valt, dus u betaalt 21 procent
          btw. Op 10 juni 2026 nam de Tweede Kamer een motie aan die het kabinet
          vroeg te onderzoeken of het nultarief ook voor batterijen kan gelden;
          in het Belastingplan 2027 van Prinsjesdag 2026 staat daar geen
          maatregel over. Hoe dat zit, met de regel van de Belastingdienst
          erbij, staat op{" "}
          <Link href="/thuisbatterij-btw/">btw op een thuisbatterij</Link>.
        </p>
        <p className={styles.body}>
          Na 1 januari 2027 krijgt u voor teruggeleverde stroom een vergoeding
          van uw leverancier. Tot 2030 moet die minimaal de helft van het kale
          leveringstarief zijn, onder toezicht van de ACM. Wat dat bij uw
          leverancier wordt, weet niemand vandaag, en daarom rekenen wij met een
          bandbreedte. Wat er precies verandert staat op{" "}
          <Link href="/einde-saldering/">
            de pagina over het einde van de saldering
          </Link>
          .
        </p>
      </section>

      <section className={styles.section} aria-labelledby="offerte">
        <h2 id="offerte" className={styles.heading}>
          Vijf dingen om na te kijken in een offerte
        </h2>
        <p className={styles.body}>
          Vraagt u toch een offerte aan, dan zijn dit de regels waar de
          terugverdientijd in zit.
        </p>
        <ul className={styles.routes}>
          {QUOTE_CHECKS.map(([name, text]) => (
            <li key={name} className={styles.route}>
              <span className={styles.routeName}>{name}</span>
              <span className={styles.routeText}>{text}</span>
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

      <section className={styles.section} aria-labelledby="bronnen">
        <h2 id="bronnen" className={styles.heading}>
          Bronnen
        </h2>
        <p className={styles.body}>
          Elk cijfer en elke regeling op deze pagina komt hiervandaan, met de
          datum waarop wij het lazen. Deze pagina is voor het laatst bijgewerkt
          op {UPDATED.text}.
        </p>
        <ul className={styles.unknowns}>
          {SOURCES.map(({ what, who, when, url }) => (
            <li key={url} className={styles.unknown}>
              <a href={url} rel="noopener">
                {what}
              </a>
              , {who}, {when}.
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
