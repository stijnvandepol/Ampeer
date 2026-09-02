"use client";

import { useState } from "react";
import {
  EXPORTED_2027_CENTS,
  SCALE_BOTTOM_CENTS,
  SCALE_TOP_CENTS,
  SELF_USED_CENTS,
  boxOf,
  cents,
  downOf,
  exportedIn,
  type Regime,
} from "./prices";
import styles from "./gap.module.css";

/**
 * The gap, drawn as two bands that come apart.
 *
 * WHAT IT ARGUES. A kilowatt hour you use yourself is worth what you did not
 * have to buy. A kilowatt hour you export is worth, today, exactly the same,
 * because saldering subtracts one from the other. That is not a simplification
 * of the rule, it IS the rule, so the two bands start as one band. From 2027
 * the lower one detaches and falls, and it does not fall to a line: it falls
 * to a band running from below zero to a little above it. At the unfavourable
 * end, exporting costs money.
 *
 * WHY THE THING THAT MOVES IS A BAND. The frontend spec allows motion that
 * draws attention to uncertainty and forbids motion that draws attention to a
 * purchase. Here the moving object is the uncertainty itself: a reader watches
 * one confident price become a wide unknown one, and the width of that band is
 * the honest answer to "wat kost het mij" before they have told us anything.
 * It is also the argument for answering four questions, made without asking.
 *
 * WHAT IT REFUSES TO DRAW. No euro total, no annual figure, no volume. These
 * are prices per kilowatt hour, which are facts about the tariff landscape;
 * multiply one by a number of kilowatt hours and you have invented a household
 * and printed a number nobody computed for the person reading it.
 *
 * The change is user driven and not scrolled or timed. A figure that animates
 * itself while a reader is still reading the paragraph above it is telling them
 * when to look, and this one has nothing urgent to say.
 */

const LABELS: Readonly<Record<Regime, string>> = {
  nu: "Zoals het nu is",
  "2027": "Vanaf 2027",
};

/** The marks on the scale, in cents. Zero is in the list because it is the line. */
const TICKS = [30, 20, 10, 0] as const;

const FIGURE_LABEL =
  "Wat een kilowattuur waard is, in centen. De bovenste band is een kilowattuur die u zelf gebruikt en die verandert nauwelijks. De onderste band is een kilowattuur die u teruglevert: nu even veel waard als de bovenste, en vanaf 2027 bijna niets, aan de ongunstige kant zelfs minder dan nul.";

export function PriceGap() {
  const [regime, setRegime] = useState<Regime>("nu");
  const exported = exportedIn(regime);
  const self = boxOf(SELF_USED_CENTS);
  const away = boxOf(exported);

  return (
    <figure className={styles.figure}>
      <div
        className={styles.plot}
        data-regime={regime}
        role="img"
        aria-label={FIGURE_LABEL}
      >
        <div className={styles.axis} aria-hidden="true">
          {TICKS.map((tick) => (
            <span
              key={tick}
              className={tick === 0 ? styles.zero : styles.tick}
              style={{ top: `${downOf(tick)}%` }}
            >
              {cents(tick)}
            </span>
          ))}
        </div>

        <div className={styles.lanes}>
          {/* The line the lower band crosses. Drawn once, across both lanes. */}
          <span
            aria-hidden="true"
            className={styles.zeroLine}
            style={{ top: `${downOf(0)}%` }}
          />
          <div className={styles.lane}>
            <span
              className={`${styles.band} ${styles.self}`}
              style={{ top: `${self.top}%`, height: `${self.height}%` }}
            />
          </div>
          <div className={styles.lane}>
            <span
              className={`${styles.band} ${styles.away}`}
              style={{ top: `${away.top}%`, height: `${away.height}%` }}
            />
          </div>
        </div>
      </div>

      <div className={styles.names} aria-hidden="true">
        <span />
        <div className={styles.nameRow}>
          <span>zelf gebruikt</span>
          <span>teruggeleverd</span>
        </div>
      </div>

      <div className={styles.control} role="group" aria-label="Welk jaar">
        {(["nu", "2027"] as const).map((option) => (
          <button
            key={option}
            type="button"
            className={styles.choice}
            aria-pressed={regime === option}
            onClick={() => setRegime(option)}
          >
            {LABELS[option]}
          </button>
        ))}
      </div>

      <figcaption className={styles.caption}>
        {regime === "nu" ? (
          <>
            Zolang u mag salderen is een teruggeleverde kilowattuur precies zo
            veel waard als een die u zelf gebruikt, want de ene wordt van de
            andere afgetrokken. Daarom staan beide banden op dezelfde hoogte:
            dat is niet vereenvoudigd, dat is de regeling.
          </>
        ) : (
          <>
            Vanaf 2027 houdt u van een teruggeleverde kilowattuur op een vast
            contract {cents(EXPORTED_2027_CENTS.low)} tot{" "}
            {cents(EXPORTED_2027_CENTS.high)} cent over, nadat de
            terugleverkosten eraf zijn. Aan de ongunstige kant is dat negatief:
            dan kost terugleveren u geld. Wat u zelf gebruikt blijft{" "}
            {cents(SELF_USED_CENTS.low)} tot {cents(SELF_USED_CENTS.high)} cent
            waard. Het verschil zit dus niet in wat zelf gebruiken oplevert.
          </>
        )}
      </figcaption>

      <p className={styles.source}>
        Bedragen per kilowattuur, exclusief btw, op een vast contract. De
        veelgenoemde 3 tot 8 cent is de brutovergoeding, met de terugleverkosten
        er nog voor. Op een dynamisch contract blijft de vergoeding 5 tot 7 cent
        en positief. Zie{" "}
        <a href="/methodologie/#11-de-terugleververgoeding-is-lager-dan-vaak-gedacht">
          hoofdstuk 11 van onze methodologie
        </a>
        .
      </p>

      {/*
        The scale in words, for a reader who gets the figure as an image and
        the caption as prose but never sees where the bands sit. It is not
        aria-hidden and it is not visually hidden either: it reads as the
        footnote it is.
      */}
      <p className={styles.range}>
        De schaal loopt van {cents(SCALE_BOTTOM_CENTS)} tot{" "}
        {cents(SCALE_TOP_CENTS)} cent.
      </p>
    </figure>
  );
}
