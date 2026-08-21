"use client";

import { useId, useState } from "react";
import type { CSSProperties } from "react";
import type { ScenarioBand } from "@/lib/types";
import { DURATION } from "@/design/tokens";
import { SCENARIO_END_REM, SCENARIO_MIDDLE_REM } from "./scale";
import { dutchAmount } from "./format";
import {
  axisPercentage,
  bandOffsetFraction,
  bandSpanFraction,
} from "./position";
import styles from "./band.module.css";

/**
 * What the three amounts are counted in. `eur_per_kwh` is here because the
 * battery block reports a break-even price per kWh; it is the same band in a
 * different unit, not a different kind of figure.
 */
export type ScenarioUnit = "eur" | "years" | "eur_per_kwh";

/**
 * The unit, spelled out, for anybody who is listening rather than looking.
 *
 * The visible figures carry a euro sign or the word "jaar"; the accessible name
 * used to carry neither, because it interpolated the raw values and only the
 * visible half got a unit. Ten figures on the advice page then said the same
 * unitless sentence for euro, for years and for euro per kWh, so a blind
 * visitor heard "Tussen 6,99 en 18,89" for a payback time and could not tell it
 * from a price. These are unit names, which is interface text; nothing here
 * tells a household what to do.
 */
const SPOKEN_UNIT: Readonly<Record<ScenarioUnit, string>> = {
  eur: "euro",
  years: "jaar",
  eur_per_kwh: "euro per kWh",
};

interface Props {
  readonly band: ScenarioBand;
  readonly unit: ScenarioUnit;
}

function amount(unit: ScenarioUnit, value: string) {
  // The digits are the digits the API sent, in the same order. Only the
  // separators move, and the unit around them is chosen here. See format.ts
  // for why this may not go through a number.
  const written = dutchAmount(value);
  if (unit === "years") return <>{written} jaar</>;
  if (unit === "eur_per_kwh") return <>&euro; {written} per kWh</>;
  return <>&euro; {written}</>;
}

/**
 * A scenario band: the same simulated year re-priced at three tariff levels.
 *
 * Narrower than the headline band and drawn as a different object on purpose,
 * a thin capped rail rather than a filled bar, so a reader does not have to be
 * told the two are not the same kind of answer. It can also say what moved and
 * what was held, which is the part that keeps it from being read as a
 * percentile band.
 *
 * The rail is the axis, from zero to this band's own upper end, and the capped
 * segment on it is the band, so its width is the spread. Until that was true
 * every figure on the advice page was the same 416 pixels wide and the five
 * capacities of the battery curve were the same picture five times over.
 *
 * It renders `varied_text` and `pinned_text`, not `varied` and `pinned`. The
 * latter are English identifiers from the simulation core; a Dutch glossary for
 * them here would be a second copy of the model's vocabulary, drifting the
 * first time an assumption is added. The mapping lives in the API's language
 * layer next to the advice text, and a test there pairs it with every variation
 * so a new assumption without a Dutch name fails the build rather than reaching
 * a reader as an identifier.
 */
export function ScenarioBandFigure({ band, unit }: Props) {
  const [open, setOpen] = useState(false);
  const buttonId = useId();
  const panelId = `${buttonId}-panel`;

  const span = bandSpanFraction(band.low, band.high);
  const offset = bandOffsetFraction(band.low, band.high);
  const segmentStyle: CSSProperties = {
    left: `${offset * 100}%`,
    width: `${span * 100}%`,
  };
  const markerAt = `${axisPercentage(band.low, band.mid, band.high)}%`;
  const panelStyle: CSSProperties = {
    transitionDuration: `${DURATION.quick}ms`,
  };

  const spoken = SPOKEN_UNIT[unit];
  const description =
    `Tussen ${dutchAmount(band.low)} en ${dutchAmount(band.high)} ${spoken}, met ` +
    `${dutchAmount(band.mid)} ${spoken} als middelpunt, uit ${band.combinations} ` +
    `tariefcombinaties.`;

  // The visible label is the same sentence on every one of these, and there are
  // ten on an advice page, so on its own it is ten buttons with one name. The
  // accessible name keeps the visible text as its opening words, which is what
  // SC 2.5.3 asks, and adds the band it belongs to so the ten can be told
  // apart.
  const disclosureLabel = `Waarover varieert dit bedrag? ${dutchAmount(band.low)} tot ${dutchAmount(band.high)} ${spoken}`;

  return (
    <figure
      role="figure"
      aria-label={description}
      data-band-kind="scenario"
      data-band-span={span.toFixed(4)}
      className={styles.scenario}
    >
      <div data-band-part="axis" className={styles.rail} aria-hidden="true">
        <span
          data-band-part="band"
          className={styles.segment}
          style={segmentStyle}
        >
          <span className={`${styles.cap} ${styles.capLow}`} />
          <span className={`${styles.cap} ${styles.capHigh}`} />
        </span>
        <span className={styles.diamond} style={{ left: markerAt }} />
      </div>

      <div className={styles.scenarioEnds}>
        <span
          data-role="band-end"
          style={{ fontSize: `${SCENARIO_END_REM}rem` }}
        >
          {amount(unit, band.low)}
        </span>
        <span
          data-role="band-middle"
          className={styles.scenarioMiddle}
          style={{ fontSize: `${SCENARIO_MIDDLE_REM}rem` }}
        >
          {amount(unit, band.mid)}
        </span>
        <span
          data-role="band-end"
          style={{ fontSize: `${SCENARIO_END_REM}rem` }}
        >
          {amount(unit, band.high)}
        </span>
      </div>

      <button
        type="button"
        id={buttonId}
        className={styles.disclosure}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={disclosureLabel}
        onClick={() => setOpen((was) => !was)}
      >
        Waarover varieert dit bedrag?
      </button>

      {/*
        Rendered whether it is open or not, and hidden with the `hidden`
        attribute. aria-controls has to name an element that exists, and while
        this panel was conditionally rendered it named one that did not exist
        for as long as the panel was closed, which is every one of them until
        somebody clicks.
      */}
      <div
        id={panelId}
        role="group"
        aria-labelledby={buttonId}
        hidden={!open}
        className={styles.panel}
        style={panelStyle}
      >
        <dl className={styles.panelList}>
          <dt className={styles.panelTerm}>Varieerde</dt>
          <dd className={styles.panelValue}>{band.varied_text.join(", ")}</dd>
          <dt className={styles.panelTerm}>Stond vast</dt>
          <dd className={styles.panelValue}>{band.pinned_text.join(", ")}</dd>
          <dt className={styles.panelTerm}>Combinaties</dt>
          <dd className={styles.panelValue}>{band.combinations}</dd>
        </dl>
      </div>
    </figure>
  );
}
