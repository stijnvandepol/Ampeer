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
  bandIsRightPinned,
  bandOffsetFraction,
  bandSpanFraction,
  labelAnchor,
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
 * WHERE THE LABELS GO. All four of them are anchored to a point on the axis,
 * by the one mechanism in position.ts. The two ends used to be a flex row
 * spanning the whole track with justify-content: space-between, so on a band
 * running 1382 to 1964 on an axis to 1964 the fill covered the right third of
 * the track while "€ 1.382,13" was typeset under the axis's zero. Measured at
 * 1280x900: the low label's box ran 280..427.9 and the edge it names was at
 * 786.8, sixty percent of the track away. The only reading left was that the
 * grey rail is the range, which leaves the coloured band unexplained and puts
 * the middle nonsensically high inside it. The middle label was already
 * anchored, which is what made the figure contradict itself rather than merely
 * be wrong.
 *
 * The two ends are never on the same line, and that is a decision rather than
 * an accident of wrapping. At a 320px viewport the track is 272px and each end
 * label is 148px, so the pair needs 296px it does not have; any layout that
 * puts them on one line there collapses back into the row this replaced. They
 * could share a line at 1280 for a wide band and not for a narrow one, and a
 * figure whose labels change places depending on the answer is harder to read
 * than one whose labels are always in the same two places. So: the low end on
 * the line under the axis, the high end on the line under that, each over its
 * own point. Nothing needs measuring, nothing has a threshold, and the picture
 * is the same on a phone and on a desktop. The middle keeps the line above the
 * axis, so it cannot collide with either of them.
 *
 * None of this depends on the animation: the anchors come from the amounts, not
 * from the drawn width, so they are in the right place on the first frame under
 * a reduced motion preference and on every frame without one. The band happens
 * to grow from its low label towards its high one.
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
  // Anchored by whichever edge sits at the axis's own extreme, so
  // band.module.css's min-width floor (for a band too tight to read as a
  // band at all) grows into the track instead of past it. See
  // bandIsRightPinned for why that edge is never the same one for every band.
  const rightPinned = bandIsRightPinned(band.p10);
  const fillStyle: CSSProperties = {
    ...(rightPinned
      ? { right: `${Math.max(0, (1 - offset - span) * 100)}%` }
      : { left: `${offset * 100}%` }),
    width: drawnWidth,
    transitionDuration: `${reduced ? DURATION.instant : DURATION.considered}ms`,
  };
  const markerAt = `${axisPercentage(band.p10, band.p50, band.p90)}%`;

  // Every label is anchored the same way and every one of them to a point on
  // the axis. The two ends take the fill's own left and right rather than a
  // second computation of the same amounts, so a label and the edge it names
  // cannot drift apart by a rounding step. Zero is placed rather than assumed
  // to be on the left: an all-negative band is measured from its low end up to
  // zero, and for that one zero is the right-hand end of the track.
  const middleAnchor = labelAnchor(
    axisPercentage(band.p10, band.p50, band.p90),
  );
  const lowAnchor = labelAnchor(offset * 100);
  const highAnchor = labelAnchor((offset + span) * 100);
  const zeroAnchor = labelAnchor(axisPercentage(band.p10, "0", band.p90));

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
      {/*
        No visible label here since 2026-09-15. It sits in ConfidenceBadge,
        above the first step, because rule two wants it in the first screen and
        this band is no longer the first thing on the page. `label` stays a
        prop: the aria-label below is one sentence and it ends with the
        confidence, which is how a screen reader should hear a figure.
      */}
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
          className={`${styles.anchored} ${styles.middleLabel}`}
          style={{ ...middleAnchor, fontSize: `${BAND_MIDDLE_REM}rem` }}
        >
          &euro; {dutchAmount(band.p50)}
        </span>
      </div>

      <div className={styles.ends}>
        {/*
          The axis's own origin, and the one thing on this figure that is not an
          amount the model produced. It is here because without it the track is
          an unexplained grey rail: the width of the band is the spread as a
          share of the largest amount the model thinks plausible, which is the
          argument position.ts makes, and a reader can only read that share off
          the picture if the far end of the rail is marked as zero. It is set at
          caption size in the subtle ink so it reads as the scale it is and not
          as a fourth figure, and it is hidden from assistive technology: the
          band's aria-label already spells the answer out, and adding "0 euro"
          to it would suggest the model said something about zero.
        */}
        <span
          className={`${styles.anchored} ${styles.zeroMark}`}
          style={zeroAnchor}
          aria-hidden="true"
        >
          &euro; 0
        </span>
        <span
          data-role="band-end"
          className={`${styles.anchored} ${styles.endLabel}`}
          style={{ ...lowAnchor, fontSize: `${BAND_END_REM}rem` }}
        >
          &euro; {dutchAmount(band.p10)}
        </span>
        <span
          data-role="band-end"
          className={`${styles.anchored} ${styles.endLabel}`}
          style={{ ...highAnchor, fontSize: `${BAND_END_REM}rem` }}
        >
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
