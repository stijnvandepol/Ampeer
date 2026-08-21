"use client";

import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { Advice, PercentileBand } from "@/lib/types";
import { confidenceTone, DURATION } from "@/design/tokens";
import { useReducedMotion } from "@/design/motion";
import { BAND_END_REM, BAND_MIDDLE_REM } from "./scale";
import { dutchAmount } from "./format";
import {
  axisPercentage,
  bandOffsetFraction,
  bandSpanFraction,
  labelPercentage,
} from "./position";
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
 * else.
 *
 * Three things carry the answer and each carries a different part of it. The
 * track is the axis, from zero to the band's own upper end. The fill is the
 * band: its width is the spread, so a household whose answer is nearly certain
 * gets a short band and one whose answer is not gets a long one, and the two
 * are told apart without reading a digit. The marker is the middle, at its own
 * place on the axis. Type size is the fourth: the ends are set larger than the
 * middle, because the ends are the answer and the middle is a marking inside
 * it, and a test enforces it.
 *
 * Colour used to contradict all of that. The gradient faded to 30% alpha at
 * both ends, which composited to about 2:1 against the page while the middle
 * sat at 6:1 with a solid marker on it, so the eye landed on the centre and the
 * band faded out towards its own answer. It runs the other way now: full tone
 * at the ends, lighter in the middle, and every point of it clears the 3:1 that
 * WCAG 1.4.11 asks of a graphic that carries meaning. That is measured against
 * the built page in e2e/rules.spec.ts rather than asserted here, because
 * neither the stylesheet-parsing contrast test nor axe can see a
 * `background-image` at all.
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

  const span = bandSpanFraction(band.p10, band.p90);
  const offset = bandOffsetFraction(band.p10, band.p90);

  // Motion may draw attention to the uncertainty and never to a purchase, so
  // the one animated property is the width of the band itself. Under a reduced
  // motion preference the band is simply there at its width: shortening the
  // same animation would leave the meaning in the movement, which is the thing
  // the preference exists to remove.
  const drawnWidth = `${(reduced || grown ? span : 0) * 100}%`;
  const trackStyle: CSSProperties = {
    ["--tone" as string]: `var(${confidenceTone(confidence)})`,
  };
  const fillStyle: CSSProperties = {
    left: `${offset * 100}%`,
    width: drawnWidth,
    transitionDuration: `${reduced ? DURATION.instant : DURATION.considered}ms`,
  };
  const markerAt = `${axisPercentage(band.p10, band.p50, band.p90)}%`;
  const middleLabelAt = `${labelPercentage(band.p10, band.p50, band.p90)}%`;

  const description =
    `Tussen ${dutchAmount(band.p10)} en ${dutchAmount(band.p90)} euro per jaar, met ` +
    `${dutchAmount(band.p50)} euro als middelpunt, uit ${band.runs} doorrekeningen. ` +
    `Betrouwbaarheid: ${label}.`;

  return (
    <figure
      role="figure"
      aria-label={description}
      data-band-kind="percentile"
      data-band-span={span.toFixed(4)}
      className={styles.headline}
      style={trackStyle}
    >
      <span className={styles.confidence}>{label}</span>

      <div data-band-part="axis" className={styles.track}>
        <div
          data-role="band-fill"
          data-band-part="band"
          className={styles.fill}
          style={fillStyle}
          aria-hidden="true"
        />
        <span
          className={styles.marker}
          style={{ left: markerAt }}
          aria-hidden="true"
        />
        <span
          data-role="band-middle"
          className={styles.middleLabel}
          style={{ left: middleLabelAt, fontSize: `${BAND_MIDDLE_REM}rem` }}
        >
          &euro; {dutchAmount(band.p50)}
        </span>
      </div>

      <div className={styles.ends}>
        <span data-role="band-end" style={{ fontSize: `${BAND_END_REM}rem` }}>
          &euro; {dutchAmount(band.p10)}
        </span>
        <span data-role="band-end" style={{ fontSize: `${BAND_END_REM}rem` }}>
          &euro; {dutchAmount(band.p90)}
        </span>
      </div>

      <figcaption className={styles.caption}>
        <span>{band.runs} doorrekeningen</span>
        <span>per jaar</span>
      </figcaption>
    </figure>
  );
}
