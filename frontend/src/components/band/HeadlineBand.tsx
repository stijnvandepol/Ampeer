"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { Advice, PercentileBand } from "@/lib/types";
import { CONFIDENCE_TONE, DURATION } from "@/design/tokens";
import { useReducedMotion } from "@/design/motion";
import { BAND_END_REM, BAND_MIDDLE_REM } from "./scale";
import { middlePercentage } from "./position";
import styles from "./band.module.css";

interface Props {
  readonly band: PercentileBand;
  readonly confidence: Advice["confidence"];
  readonly label: string;
}

/**
 * The band, drawn as the object it is.
 *
 * Every calculator in this market shows one number and hides the margin. This
 * shows the margin and marks the middle inside it, which is both the honest
 * picture of what the model knows and the reason the page looks like nothing
 * else. The middle is never set larger than the ends; a test enforces it,
 * because that single styling choice is the whole difference between a band
 * and a headline figure with decoration.
 *
 * The Dutch here is interface text, not advice text: it names the shape of the
 * figure rather than telling the household what to do. `label` is the API's
 * own sentence and is rendered, never rewritten.
 */
export function HeadlineBand({ band, confidence, label }: Props) {
  const reduced = useReducedMotion();
  const [grown, setGrown] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setGrown(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  // Motion may draw attention to the uncertainty and never to a purchase, so
  // the one animated property is the width of the band itself. Under a reduced
  // motion preference the band is simply there at full width: shortening the
  // same animation would leave the meaning in the movement, which is the thing
  // the preference exists to remove.
  const width = reduced || grown ? "100%" : "0%";
  const trackStyle: CSSProperties = {
    ["--tone" as string]: `var(${CONFIDENCE_TONE[confidence]})`,
  };
  const fillStyle: CSSProperties = {
    width,
    transitionDuration: `${reduced ? DURATION.instant : DURATION.considered}ms`,
  };
  const middleAt = `${middlePercentage(band.p10, band.p50, band.p90)}%`;

  const description =
    `Tussen ${band.p10} en ${band.p90} euro per jaar, met ${band.p50} als middelpunt, ` +
    `uit ${band.runs} doorrekeningen. Betrouwbaarheid: ${label}.`;

  return (
    <figure
      role="figure"
      aria-label={description}
      data-band-kind="percentile"
      className={styles.headline}
      style={trackStyle}
    >
      <span className={styles.confidence}>{label}</span>

      <div className={styles.track}>
        <div data-role="band-fill" className={styles.fill} style={fillStyle} aria-hidden="true" />
        <span className={styles.marker} style={{ left: middleAt }} aria-hidden="true" />
        <span
          data-role="band-middle"
          className={styles.middleLabel}
          style={{ left: middleAt, fontSize: `${BAND_MIDDLE_REM}rem` }}
        >
          &euro; {band.p50}
        </span>
      </div>

      <div className={styles.ends}>
        <span data-role="band-end" style={{ fontSize: `${BAND_END_REM}rem` }}>
          &euro; {band.p10}
        </span>
        <span data-role="band-end" style={{ fontSize: `${BAND_END_REM}rem` }}>
          &euro; {band.p90}
        </span>
      </div>

      <figcaption className={styles.caption}>
        <span>{band.runs} doorrekeningen</span>
        <span>per jaar</span>
      </figcaption>
    </figure>
  );
}
