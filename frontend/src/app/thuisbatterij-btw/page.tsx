import type { Metadata } from "next";
import Link from "next/link";
import { FaqJsonLd, PageJsonLd } from "../_shell/JsonLd";
import styles from "../_shell/content.module.css";

const PATH = "/thuisbatterij-btw/";
const TITLE = "Btw op een thuisbatterij: 21 procent, en geen nultarief in 2027";
const DESCRIPTION =
  "Op een thuisbatterij betaalt u 21 procent btw. Het nultarief voor zonnepanelen geldt er niet voor, ook niet samen geplaatst, en het Belastingplan 2027 verandert daar niets aan.";
/** The last day the words on this page changed; also the JSON-LD's date. */
const UPDATED = { iso: "2026-09-18", text: "18 september 2026" };

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance, for the reason written out on
  // /einde-saldering/: Next resolves a URL here against the current pathname
  // and would canonicalise this route to the site root.
  alternates: { canonical: PATH },
};

/**
 * What happened, in the order it happened. A sequence, so the list is
 * numbered; the site's rule against decorative numbering is about content
 * that is not one.
 */
const TIMELINE: readonly (readonly [string, string])[] = [
  [
    "1 januari 2023",
    "Het btw-tarief op de levering en installatie van zonnepanelen op of bij een woning gaat naar 0 procent. Een thuisbatterij staat bij de Belastingdienst uitdrukkelijk bij wat daar niet onder valt.",
  ],
  [
    "10 juni 2026",
    "De Tweede Kamer neemt met brede steun een motie aan die het kabinet vraagt te onderzoeken of het nultarief ook voor thuisbatterijen kan gelden, naar Duits voorbeeld. Het kabinet zegt toe uiterlijk op Prinsjesdag te reageren.",
  ],
  [
    "15 september 2026, Prinsjesdag",
    "In het Belastingplan 2027 staat geen maatregel die de btw op thuisbatterijen verandert. Ook een subsidie staat er niet in. Het tarief blijft 21 procent.",
  ],
];

const CHECKS: readonly string[] = [
  "Staat op de offerte 21 procent btw over de batterij, de omvormer en de installatie? Zo niet, vraag dan op welke regel de installateur zich baseert.",
  "Wordt de batterij in een offerte samen met panelen als een geheel op 0 procent gezet? De Belastingdienst noemt de batterij apart bij wat niet onder het nultarief valt. Een naheffing komt bij u terecht, niet bij de installateur.",
  "Rekent een terugverdientijd op een offerte met een prijs zonder btw? Dan is de terugverdientijd te kort. Reken met wat u betaalt.",
];

const QUESTIONS: readonly (readonly [string, string])[] = [
  [
    "Is er btw-korting als ik de thuisbatterij samen met zonnepanelen koop?",
    "Nee. Het nultarief geldt voor de levering en installatie van de zonnepanelen zelf. De Belastingdienst noemt een accupakket of thuisbatterij uitdrukkelijk bij wat er niet onder valt, en maakt geen uitzondering voor een batterij die tegelijk met de panelen wordt geplaatst.",
  ],
  [
    "Komt er nog een btw-nultarief voor thuisbatterijen?",
    "Niet per 1 januari 2027. De Tweede Kamer vroeg het kabinet op 10 juni 2026 om dat te onderzoeken, en het Belastingplan 2027 van Prinsjesdag bevat er geen maatregel over. Wat een volgend kabinet doet, weet niemand; reken met wat vandaag geldt.",
  ],
  [
    "Kan ik de btw op een thuisbatterij terugvragen?",
    "Alleen als u de batterij gebruikt om in stroom te handelen. Dan bent u volgens de Belastingdienst btw-plichtig, doet u elk kwartaal aangifte en mag u de btw op de aanschaf terugvragen, maar draagt u ook btw af over de vergoeding die u ontvangt. Een huishouden dat alleen zijn eigen zonnestroom opslaat, valt daar niet onder.",
  ],
  [
    "Is er subsidie op een thuisbatterij?",
    "Er is geen landelijke subsidie, en het Belastingplan 2027 voegt er geen toe. Sommige gemeenten of provincies hebben een eigen regeling; die verschilt per plaats en verandert vaak, dus kijk bij uw eigen gemeente.",
  ],
];

const SOURCES: readonly {
  readonly what: string;
  readonly who: string;
  readonly when: string;
  readonly url: string;
}[] = [
  {
    what: "Btw-tarief zonnepanelen, wat valt niet onder het 0%-tarief",
    who: "Belastingdienst",
    when: "gelezen op 15 september 2026",
    url: "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/btw/tarieven_en_vrijstellingen/goederen_0_btw/btw-tarief-zonnepanelen",
  },
  {
    what: "Thuisbatterij en btw",
    who: "Belastingdienst",
    when: "gelezen op 15 september 2026",
    url: "https://www.belastingdienst.nl/wps/wcm/connect/nl/btw/content/thuisbatterij-btw",
  },
  {
    what: "Tweede Kamer steunt onderzoek naar btw-nultarief voor thuisbatterij",
    who: "Solar Magazine",
    when: "motie van 10 juni 2026, gelezen op 15 september 2026",
    url: "https://solarmagazine.nl/nieuws-zonne-energie/i43976/tweede-kamer-steunt-onderzoek-naar-btw-nultarief-voor-thuisbatterij",
  },
  {
    what: "Miljoenennota 2027: geen subsidie of btw-nultarief thuisbatterij",
    who: "Eerlijk over Thuisbatterijen",
    when: "artikel van 15 september 2026, gelezen op 18 september 2026",
    url: "https://www.eerlijkoverthuisbatterijen.nl/kennisbank/thuisbatterij-subsidie-2027-miljoenennota/",
  },
];

/**
 * The page for one question, because Search Console showed the question.
 *
 * Measured on 2026-09-18, from the first four days the site was in Google's
 * index: of seven impressions, four were "btw thuisbatterij" in three
 * spellings, all landing on /thuisbatterij/ at position two to three, and
 * none of them clicked. A page titled "Is een thuisbatterij iets voor mij?"
 * is the wrong door for somebody asking about tax, however good the answer
 * is three screens down. This is the right door: the answer in the first
 * sentence, then what the Belastingdienst says, then what happened in Den
 * Haag, then what it means for the decision.
 *
 * NO EURO AMOUNT OF OUR OWN, as on /thuisbatterij/: a percentage is a rule
 * and a price is a household nobody described.
 */
export default function ThuisbatterijBtwPage() {
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
        <p className={styles.eyebrow}>Het korte antwoord</p>
        <h1 className={styles.title}>Btw op een thuisbatterij: 21 procent</h1>
        <p className={styles.lead}>
          Het nultarief dat sinds 2023 voor zonnepanelen geldt, geldt niet voor
          een thuisbatterij, ook niet als u hem tegelijk met de panelen laat
          plaatsen. De Tweede Kamer vroeg in juni 2026 om een nultarief te
          onderzoeken; in het Belastingplan 2027 van Prinsjesdag staat er niets
          over. U rekent dus met 21 procent.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="belastingdienst">
        <h2 id="belastingdienst" className={styles.heading}>
          Wat de Belastingdienst zegt
        </h2>
        <p className={styles.body}>
          Op de pagina over het btw-tarief voor zonnepanelen staat een lijst van
          wat wel en wat niet onder het nultarief valt. Bij wat er niet onder
          valt staat, letterlijk, de levering en installatie van een accupakket
          en thuisbatterij. Dat is de hele regel. Er staat geen uitzondering bij
          voor een batterij die in dezelfde opdracht als de panelen wordt
          geleverd, en de pagina van de Belastingdienst over de thuisbatterij
          zelf noemt geen nultarief.
        </p>
        <p className={styles.body}>
          Verkopers schrijven soms dat een batterij samen met panelen wel op 0
          procent kan. Wij hebben die regel bij de Belastingdienst niet
          gevonden. Wie hem toepast, doet dat op eigen lezing, en een naheffing
          landt bij de koper.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="den-haag">
        <h2 id="den-haag" className={styles.heading}>
          Wat er in Den Haag gebeurde
        </h2>
        <ol className={styles.routes}>
          {TIMELINE.map(([when, what]) => (
            <li key={when} className={styles.route}>
              <span className={styles.routeName}>{when}</span>
              <span className={styles.routeText}>{what}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.section} aria-labelledby="terugvragen">
        <h2 id="terugvragen" className={styles.heading}>
          Btw terugvragen kan alleen wie handelt
        </h2>
        <p className={styles.body}>
          Gebruikt u de batterij om stroom in te kopen en te verkopen, dan bent
          u volgens de Belastingdienst btw-plichtig: u doet elk kwartaal
          aangifte, mag de btw op de aanschaf terugvragen en draagt btw af over
          de vergoeding die u van uw leverancier krijgt. Dat is een bedrijfje en
          geen huishouden. Slaat u alleen uw eigen zonnestroom op voor de avond,
          dan is er niets terug te vragen.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="keuze">
        <h2 id="keuze" className={styles.heading}>
          Wat dit betekent voor uw keuze
        </h2>
        <p className={styles.body}>
          De 21 procent zit in de prijs die u betaalt, en die prijs bepaalt de
          terugverdientijd meer dan welke andere aanname ook. Een batterij die
          alleen uit kan met een nultarief dat er niet is, kan vandaag niet uit.
          Drie dingen om na te kijken op een offerte:
        </p>
        <ul className={styles.unknowns}>
          {CHECKS.map((line) => (
            <li key={line} className={styles.unknown}>
              {line}
            </li>
          ))}
        </ul>
        <p className={styles.body}>
          Of een batterij bij u uit kan, hangt niet van de btw af maar van
          hoeveel u teruglevert en wat u &apos;s avonds gebruikt. Dat staat op{" "}
          <Link href="/thuisbatterij/">is een thuisbatterij iets voor mij</Link>
          , en het is per huis door te rekenen.
        </p>
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

      <section className={styles.section} aria-labelledby="bronnen">
        <h2 id="bronnen" className={styles.heading}>
          Bronnen
        </h2>
        <p className={styles.body}>
          Elke regel op deze pagina komt hiervandaan, met de datum waarop wij
          het lazen. Deze pagina is voor het laatst bijgewerkt op {UPDATED.text}
          .
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
          Vier vragen zijn genoeg voor een eerste antwoord op wat het einde van
          de saldering u kost en of opslag daar iets aan doet. Geen account,
          niets te koop.
        </p>
        <p className={styles.act}>
          <Link href="/berekenen/">Bereken wat er bij u verandert</Link>
        </p>
      </section>
    </div>
  );
}
