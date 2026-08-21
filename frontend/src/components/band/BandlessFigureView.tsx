import type { BandlessFigure } from "@/lib/types";
import styles from "./band.module.css";

/** The units a figure without a band can arrive in. */
export type BandlessUnit = "kwh";

const UNIT_SUFFIX: Readonly<Record<BandlessUnit, string>> = {
  kwh: "kWh",
};

interface Props {
  readonly figure: BandlessFigure;
  readonly unit: BandlessUnit;
}

/**
 * A figure the model deliberately put no margin around.
 *
 * `basis_text` travels with it and is rendered as it arrived. This component
 * writes no sentence of its own and draws no band: inventing either would be
 * the frontend answering a question the model declined to answer.
 */
export function BandlessFigureView({ figure, unit }: Props) {
  return (
    <figure className={styles.bandless} data-band-kind="none">
      <p className={styles.bandlessValue} data-role="bandless-value">
        {figure.value} {UNIT_SUFFIX[unit]}
      </p>
      <figcaption className={styles.basis} data-role="basis-text">
        {figure.basis_text}
      </figcaption>
    </figure>
  );
}
