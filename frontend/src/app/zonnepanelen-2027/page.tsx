import type { Metadata } from "next";
import Link from "next/link";
import { FaqJsonLd, PageJsonLd } from "../_shell/JsonLd";
import styles from "../_shell/content.module.css";

const PATH = "/zonnepanelen-2027/";
const TITLE = "Zonnepanelen in 2027: wat moet u regelen vóór 1 januari?";
const DESCRIPTION =
  "Kort antwoord: niets dat niet kan wachten. Uw panelen blijven lonen. Vijf dingen om rustig na te gaan, waarvan vier niets kosten, en waarom een batterij geen haast heeft.";
/** The last day the words on this page changed; also the JSON-LD's date. */
const UPDATED = { iso: "2026-10-01", text: "1 oktober 2026" };

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance, for the reason written out on
  // /einde-saldering/: Next resolves a URL here against the current pathname
  // and would canonicalise this route to the site root.
  alternates: { canonical: PATH },
};

/**
 * What to do, in the order that makes sense to do it. A sequence, so the list
 * is numbered: each step uses what the one before it found out.
 */
const STEPS: readonly (readonly [string, string])[] = [
  [
    "Zoek op hoeveel stroom u teruglevert",
    "Op uw jaarafrekening staan twee getallen: wat u van het net afnam en wat u eraan teruggaf. Dat tweede getal is het getal dat telt. Niet hoeveel uw panelen opwekken, maar hoeveel daarvan het net op gaat, want alleen dat deel wordt na 1 januari minder waard.",
  ],
  [
    "Kijk wat uw leverancier vanaf 2027 betaalt en rekent",
    "U krijgt een vergoeding per teruggeleverde kilowattuur, en veel leveranciers rekenen er ook kosten voor. Het verschil tussen die twee is wat u werkelijk krijgt. Staat het niet in uw contract of in een brief, vraag het dan na. Overstappen kan, maar een ander contract is niet vanzelf beter.",
  ],
  [
    "Gebruik meer van uw eigen stroom overdag",
    "De wasmachine, de vaatwasser of de droger aanzetten terwijl de zon schijnt, kost niets en levert vanaf 2027 meteen iets op. Dit is bij veel huishoudens de grootste stap van allemaal.",
  ],
  [
    "Reken uit wat het bij u verandert",
    "Een gemiddeld bedrag uit de krant zegt weinig over uw eigen huis. Met vier vragen over uw dak en uw verbruik ziet u wat het bij u doet, met de marge erbij.",
  ],
  [
    "Laat u niet haasten tot een thuisbatterij",
    "Aan 1 januari hangt geen korting en geen subsidie. Een batterij die u in maart koopt, bespaart in 2027 bijna evenveel als een die u in december koopt. Er is dus tijd om eerst de gratis stappen te zetten en daarna pas te kijken of opslag bij u past.",
  ],
];

/**
 * The questions, rendered and marked up from the same array.
 *
 * Phrased the way people type them, which is the whole reason this page
 * exists: "wat moet ik met mijn zonnepanelen in 2027" and "ik heb zonnepanelen
 * wat moet ik doen" were in Google's suggestions on 2026-10-01, and the pages
 * answering them were suppliers and comparison sites that end on a switch.
 */
const QUESTIONS: readonly (readonly [string, string])[] = [
  [
    "Moet ik vóór 1 januari 2027 iets regelen?",
    "Nee, niets wat niet kan wachten. De salderingsregeling stopt voor iedereen tegelijk en vanzelf. U hoeft niets aan te vragen, op te zeggen of te laten aanpassen, en uw panelen blijven gewoon stroom leveren.",
  ],
  [
    "Zijn mijn zonnepanelen na 2027 nog rendabel?",
    "Ja. Volgens de Rijksoverheid gaan zonnepanelen gemiddeld 25 jaar mee en verdienen ze zich ruim binnen die tijd terug, zowel voor als na het einde van de salderingsregeling. Wat verandert is hoeveel de stroom waard is die u teruglevert, niet of opwekken loont.",
  ],
  [
    "Moet ik mijn zonnepanelen uitzetten?",
    "Nee. Stroom die u zelf gebruikt, hoeft u niet te kopen, en dat blijft na 2027 precies zo. Alleen het deel dat u teruglevert, levert minder op dan nu.",
  ],
  [
    "Wat krijg ik na 2027 voor stroom die ik teruglever?",
    "Een vergoeding van uw leverancier. Tot 2030 moet die volgens de Rijksoverheid minimaal de helft van het kale leveringstarief zijn. Rekent uw leverancier terugleverkosten, dan mogen dat alleen de kosten zijn die hij maakt om die stroom te verwerken; de ACM houdt daar toezicht op.",
  ],
  [
    "Moet ik nu een thuisbatterij kopen?",
    "Nee. Voor een flink deel van de huishoudens komt een thuisbatterij, ook wel thuisaccu genoemd, nu niet uit. Er is geen subsidie en u betaalt 21 procent btw, en daar verandert op 1 januari niets aan. Of hij bij u past, hangt af van hoeveel u teruglevert en wat u 's avonds gebruikt.",
  ],
];

const SOURCES: readonly {
  readonly what: string;
  readonly who: string;
  readonly when: string;
  readonly url: string;
}[] = [
  {
    what: "Salderingsregeling stopt in 2027",
    who: "Rijksoverheid",
    when: "gelezen op 1 oktober 2026",
    url: "https://www.rijksoverheid.nl/themas/klimaat-milieu-en-natuur/energie-thuis/salderingsregeling",
  },
  {
    what: "Btw-tarief zonnepanelen, wat valt niet onder het 0%-tarief",
    who: "Belastingdienst",
    when: "gelezen op 15 september 2026",
    url: "https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/belastingdienst/zakelijk/btw/tarieven_en_vrijstellingen/goederen_0_btw/btw-tarief-zonnepanelen",
  },
  {
    what: "Miljoenennota 2027: geen subsidie of btw-nultarief thuisbatterij",
    who: "Eerlijk over Thuisbatterijen",
    when: "artikel van 15 september 2026, gelezen op 18 september 2026",
    url: "https://www.eerlijkoverthuisbatterijen.nl/kennisbank/thuisbatterij-subsidie-2027-miljoenennota/",
  },
];

/**
 * The page for somebody who has panels, has heard that something stops on
 * 1 January, and does not know what that asks of them.
 *
 * WHY IT EXISTS. Search Console for 14 to 28 September 2026 showed this site
 * found on its own name and almost nothing else, and Google's suggestions on
 * 2026-10-01 showed the question this audience actually types: not "einde
 * salderingsregeling" but "ik heb zonnepanelen, wat moet ik doen". The pages
 * that answer it today are checklists from comparison sites and suppliers, and
 * every one ends on a contract switch or a battery. The honest answer is
 * shorter and calmer than theirs, and that is what this page is for.
 *
 * NO COUNTDOWN. The date is in the title because it is the date people search
 * for, and that is all it does: rule four forbids counting down to it, and the
 * last step exists to take the urgency away rather than add to it. A battery
 * bought in a hurry before a date that changes nothing about its price is the
 * one mistake this page can actually prevent.
 *
 * Every claim about the regeling traces to a source below with the date read;
 * the rest is arithmetic a reader can follow without one.
 */
export default function Zonnepanelen2027Page() {
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
        <p className={styles.eyebrow}>Voor wie zonnepanelen heeft</p>
        <h1 className={styles.title}>
          Ik heb zonnepanelen. Wat moet ik regelen vóór 1 januari?
        </h1>
        <p className={styles.lead}>
          Kort antwoord: niets dat niet kan wachten. Uw panelen blijven werken
          en blijven lonen, en de saldering stopt vanzelf. Wel is dit een goed
          moment om vijf dingen na te gaan, en vier daarvan kosten niets.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="verandert">
        <h2 id="verandert" className={styles.heading}>
          Wat er op 1 januari 2027 verandert
        </h2>
        <p className={styles.body}>
          Nu mag u de stroom die u teruglevert wegstrepen tegen de stroom die u
          afneemt. Dat heet salderen, en het stopt op 1 januari 2027. Daarna
          krijgt u voor teruggeleverde stroom een vergoeding van uw leverancier,
          en die is lager dan wat u voor stroom betaalt. Stroom die u zelf
          gebruikt, wordt daardoor meer waard dan stroom die u teruglevert. Dat
          is de hele verandering. Hoe het precies werkt staat op{" "}
          <Link href="/einde-saldering/">het einde van de saldering</Link>.
        </p>
      </section>

      <section className={styles.section} aria-labelledby="stappen">
        <h2 id="stappen" className={styles.heading}>
          Vijf dingen om rustig na te gaan
        </h2>
        <ol className={styles.routes}>
          {STEPS.map(([name, text]) => (
            <li key={name} className={styles.route}>
              <span className={styles.routeName}>{name}</span>
              <span className={styles.routeText}>{text}</span>
            </li>
          ))}
        </ol>
        <p className={styles.body}>
          Welke apparaten het meeste verschil maken, staat op{" "}
          <Link href="/zelf-verbruiken/">
            meer van uw eigen stroom zelf gebruiken
          </Link>
          . Of opslag bij u past, staat op{" "}
          <Link href="/thuisbatterij/">is een thuisbatterij iets voor mij</Link>
          .
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
          Vier vragen over uw dak en uw verbruik. Geen account, geen
          e-mailadres, en niets te koop.
        </p>
        <p className={styles.act}>
          <Link href="/berekenen/" className="button-accent">
            Bereken wat er bij u verandert
          </Link>
        </p>
        <p className={styles.note}>
          Wij verkopen geen panelen, geen batterijen en geen energiecontract.
          Daarom kan uit de berekening ook komen dat u nu niets hoeft te kopen.
        </p>
      </section>
    </div>
  );
}
