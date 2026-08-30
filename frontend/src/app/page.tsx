import type { Metadata } from "next";
import Link from "next/link";
import { DayCounting } from "@/components/day/DayCounting";
import styles from "./home.module.css";

export const metadata: Metadata = {
  // Deliberately "betekent" and not "kost". A title that presumes a cost
  // presumes the answer, and for a household with high self-consumption the
  // answer is close to nothing. "Nu geen batterij" being a valid outcome and
  // "het kost u weinig" being a valid outcome are the same rule; this page is
  // read before either has been computed.
  title: "Wat het einde van de saldering voor u betekent",
};

/** What a visitor gets, as a name and what it means rather than as a claim. */
const PROMISES: readonly (readonly [string, string])[] = [
  [
    "Een bedrag met zijn marge",
    "Een bedrag per jaar met de bandbreedte eromheen, nooit een enkel getal zonder.",
  ],
  [
    "Hoe zeker het is",
    "Het betrouwbaarheidsniveau staat naast de uitkomst zelf, niet in een voetnoot.",
  ],
  [
    "Drie routes, gratis eerst",
    "Uw ritme verschuiven, slimmer sturen met wat u al heeft, en pas daarna opslag.",
  ],
  [
    "Een link, geen account",
    "U krijgt een adres waarmee u er later bij kunt. Wij vragen niets anders.",
  ],
];

/**
 * The landing page: what changes, and the way in.
 *
 * Everything here is a statement of fact about the rules or about this site.
 * There is no euro amount on this page and there will not be one, because
 * every euro amount this product knows comes out of a simulation of one
 * specific household, with a band around it. A number printed here would be a
 * number nobody computed for the person reading it.
 *
 * There is no date arithmetic either. A page that counts down to 1 January
 * 2027 is manufacturing urgency out of a calendar, and rule four exists
 * precisely because that is the easiest thing in the world to add. Since
 * 2026-08-30 that is a gate rather than a resolution: `ampeer-no-reading-the-clock`
 * in `.semgrep/frontend.yml` refuses this tree the clock, so there is nothing
 * here to count down from.
 *
 * The figure carries the rule instead of the date. It is the one moving thing
 * on the page, and what it moves is the time axis out of the picture, which is
 * what saldering does and what its ending undoes. Chapter 2 of the frontend
 * spec allows movement towards uncertainty and never towards a purchase; this
 * is the first half.
 */
export default function Home() {
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <p className={styles.eyebrow}>Salderen stopt in 2027</p>
        <h1 className={styles.title}>
          Uw zonnestroom wordt in kwartieren afgerekend
        </h1>
        <p className={styles.lead}>
          Vanaf 1 januari 2027 vervalt de salderingsregeling. Een kWh die u zelf
          gebruikt is vanaf dat moment meer waard dan diezelfde kWh die u
          teruglevert. Hoeveel dat voor u scheelt hangt af van uw dak, uw
          verbruik en het moment waarop u stroom gebruikt.
        </p>
      </section>

      <DayCounting />

      <section className={styles.section}>
        <h2 className={styles.heading}>Wat u terugkrijgt</h2>
        <dl className={styles.promises}>
          {PROMISES.map(([name, text]) => (
            <div key={name} className={styles.promise}>
              <dt className={styles.promiseName}>{name}</dt>
              <dd className={styles.promiseText}>{text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={styles.section}>
        <h2 className={styles.heading}>Wat wij niet doen</h2>
        <p className={styles.body}>
          Wij verkopen geen panelen, geen batterijen en geen energiecontract, en
          wij sturen u niet door naar een partij die dat wel doet. &quot;Geen
          batterij&quot; is hier een geldige uitkomst, en voor een deel van de
          huishoudens is het de juiste.
        </p>
      </section>

      <div className={styles.act}>
        <Link href="/berekenen/" className="button-accent">
          Beantwoord vier vragen
        </Link>
        <p className={styles.note}>
          Zonder inloggen, en zonder dat u iets hoeft te koppelen.
        </p>
      </div>
    </div>
  );
}
