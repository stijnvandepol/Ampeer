"use client";

import styles from "./beam.module.css";

/**
 * A line drawn between two points, arriving as the reader scrolls to it.
 *
 * WHERE TO TUNE IT. `beam.module.css`: `--beam-draw` is how long the stroke
 * takes to complete, and the `animation-range` on `.path` decides where in the
 * scroll it happens. The dash length is set from the path's own length in the
 * stylesheet via `pathLength`, so the drawing is exact whatever shape is passed.
 *
 * WHY pathLength="1". The SVG spec lets an element declare its own length, and
 * every dash value is then a fraction of it. Without it the stroke-dasharray
 * has to be the measured length in user units, which means measuring the path
 * in JavaScript on mount and again on every resize. This is the same effect
 * with no measurement and no layout read.
 *
 * WHAT IT SAYS. It connects the step it leaves to the step it arrives at, so
 * the sequence is visible as a sequence rather than as three cards that happen
 * to be next to each other. The steps are numbered in the markup as well: the
 * line is the same statement drawn, not the only place it is made.
 *
 * Hidden from the accessibility tree, and under prefers-reduced-motion the line
 * is simply complete.
 */

interface Props {
  /** An SVG path in a 0 0 100 100 box, so the caller thinks in percentages. */
  readonly d: string;
  /*
   * `| undefined` spelled out because exactOptionalPropertyTypes is on. A CSS
   * module's export is typed `string | undefined`, so every caller passing one
   * of these through is a type error without it.
   */
  readonly className?: string | undefined;
}

export function Beam({ d, className }: Props) {
  return (
    <svg
      className={`${styles.beam} ${className ?? ""}`}
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
      data-role="beam"
    >
      <path className={styles.track} d={d} pathLength={1} />
      <path className={styles.path} d={d} pathLength={1} />
    </svg>
  );
}
