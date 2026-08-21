"use client";

import { useId, useState } from "react";
import type { CSSProperties } from "react";
import type { ScenarioBand } from "@/lib/types";
import { DURATION } from "@/design/tokens";
import { SCENARIO_END_REM, SCENARIO_MIDDLE_REM } from "./scale";
import { middlePercentage } from "./position";
import styles from "./band.module.css";

/**
 * What the three amounts are counted in. `eur_per_kwh` is here because the
 * battery block reports a break-even price per kWh; it is the same band in a
 * different unit, not a different kind of figure.
 */
export type ScenarioUnit = "eur" | "years" | "eur_per_kwh";

interface Props {
  readonly band: ScenarioBand;
  readonly unit: ScenarioUnit;
}

function amount(unit: ScenarioUnit, value: string) {
  // The value is passed through as the string it arrived as. Only the unit
  // around it is chosen here.
  if (unit === "years") return <>{value} jaar</>;
  if (unit === "eur_per_kwh") return <>&euro; {value} per kWh</>;
  return <>&euro; {value}</>;
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

  const middleAt = `${middlePercentage(band.low, band.mid, band.high)}%`;
  const panelStyle: CSSProperties = { transitionDuration: `${DURATION.quick}ms` };

  const description =
    `Tussen ${band.low} en ${band.high}, met ${band.mid} als middelpunt, ` +
    `uit ${band.combinations} tariefcombinaties.`;

  return (
    <figure
      role="figure"
      aria-label={description}
      data-band-kind="scenario"
      className={styles.scenario}
    >
      <div className={styles.rail} aria-hidden="true">
        <span className={`${styles.cap} ${styles.capLow}`} />
        <span className={styles.diamond} style={{ left: middleAt }} />
        <span className={`${styles.cap} ${styles.capHigh}`} />
      </div>

      <div className={styles.scenarioEnds}>
        <span data-role="band-end" style={{ fontSize: `${SCENARIO_END_REM}rem` }}>
          {amount(unit, band.low)}
        </span>
        <span
          data-role="band-middle"
          className={styles.scenarioMiddle}
          style={{ fontSize: `${SCENARIO_MIDDLE_REM}rem` }}
        >
          {amount(unit, band.mid)}
        </span>
        <span data-role="band-end" style={{ fontSize: `${SCENARIO_END_REM}rem` }}>
          {amount(unit, band.high)}
        </span>
      </div>

      <button
        type="button"
        id={buttonId}
        className={styles.disclosure}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((was) => !was)}
      >
        Waarover varieert dit bedrag?
      </button>

      {open ? (
        <div
          id={panelId}
          role="group"
          aria-labelledby={buttonId}
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
      ) : null}
    </figure>
  );
}
