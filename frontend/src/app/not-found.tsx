import type { Metadata } from "next";
import Link from "next/link";
import styles from "./_shell/content.module.css";

export const metadata: Metadata = {
  title: "Deze pagina bestaat niet",
  // NO `robots` KEY. Next emits `<meta name="robots" content="noindex">` for
  // this route by itself, which is the right thing: the file is served for
  // every address that does not exist, and a search engine that followed a
  // broken link here could otherwise index an apology under that address.
  // Setting it again produced two robots tags in the built page, measured on
  // 2026-09-13. They agreed, so nothing was broken; the second one was just a
  // claim this file did not need to make.
};

/**
 * What a visitor reads when the address does not exist.
 *
 * WHY THIS FILE EXISTS. Without a `not-found.tsx` Next serves its own built in
 * page, and it says "404: This page could not be found." in English, inside
 * this site's Dutch shell, with its own `<title>` appended after the layout's
 * so the document carried two. Measured on the built site on 2026-09-13, on
 * the page every mistyped address and every stale search result lands on.
 * `CLAUDE.md` makes the split hard: everything a user reads is Dutch.
 *
 * WHAT IT OFFERS. Three ways on and no apology beyond one sentence. Somebody
 * here wanted something; the useful thing is the shortest route to it, and for
 * this site that is the calculator or the two pages that answer a question.
 * Not a search box: there is nothing to search, and a box that finds nothing is
 * worse than a list of four pages that exist.
 */
export default function NotFound() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <p className={styles.eyebrow}>Pagina niet gevonden</p>
        <h1 className={styles.title}>Deze pagina bestaat niet</h1>
        <p className={styles.lead}>
          Het adres klopt niet, of de pagina is verplaatst. Hieronder staat waar
          u wel terecht kunt.
        </p>
      </header>

      <section className={styles.section} aria-labelledby="verder">
        <h2 id="verder" className={styles.heading}>
          Waar u verder kunt
        </h2>
        <ul className={styles.routes}>
          <li className={styles.route}>
            <span className={styles.routeName}>
              <Link href="/berekenen/">Bereken wat het bij u doet</Link>
            </span>
            <span className={styles.routeText}>
              Vier vragen over uw dak en uw verbruik. U hoeft niets te koppelen
              en geen account te maken.
            </span>
          </li>
          <li className={styles.route}>
            <span className={styles.routeName}>
              <Link href="/thuisbatterij/">
                Is een thuisbatterij iets voor mij
              </Link>
            </span>
            <span className={styles.routeText}>
              Waar het van afhangt, en wanneer het antwoord nee is.
            </span>
          </li>
          <li className={styles.route}>
            <span className={styles.routeName}>
              <Link href="/zelf-verbruiken/">
                Meer van uw eigen stroom zelf gebruiken
              </Link>
            </span>
            <span className={styles.routeText}>
              De goedkoopste stap, want die kost niets.
            </span>
          </li>
          <li className={styles.route}>
            <span className={styles.routeName}>
              <Link href="/einde-saldering/">Het einde van de saldering</Link>
            </span>
            <span className={styles.routeText}>
              Wat er op 1 januari 2027 verandert en voor wie.
            </span>
          </li>
        </ul>
      </section>

      <section className={styles.close} aria-labelledby="terug">
        <h2 id="terug" className={styles.heading}>
          Of begin opnieuw
        </h2>
        <p className={styles.act}>
          <Link href="/">Naar de startpagina</Link>
        </p>
      </section>
    </div>
  );
}
