"use client";

import type { ReactNode } from "react";
import styles from "./rail.module.css";

/**
 * A section that stays put while its contents travel sideways.
 *
 * WHERE TO TUNE IT. `rail.module.css`: `--rail-length` is how much vertical
 * scroll the section occupies, expressed in viewport heights, and it is the
 * only knob most changes need. Longer means the sideways travel is slower per
 * pixel of scroll. `--rail-travel` is how far the track moves and is computed
 * from the track's own width, so adding a card lengthens the travel without
 * touching anything here.
 *
 * WHY THIS IS NOT SCROLL HIJACKING. Nothing cancels a wheel event and nothing
 * moves the page itself. The section is `position: sticky` inside a tall
 * container, so the browser scrolls exactly as it always does; what changes is
 * a `transform` driven by how far through that container the reader is.
 * Scrollbar dragging, keyboard paging, find-in-page and scroll anchoring all
 * keep working, which is what a library that takes over the wheel gives up.
 *
 * WHAT IT IS WITHOUT `animation-timeline`. A normal section with its cards
 * wrapped onto as many lines as they need. The whole sideways arrangement lives
 * inside `@supports`, and the fallback is a layout rather than a broken
 * version of this one. That is also what a reader with prefers-reduced-motion
 * gets, and what a printed page gets.
 */

interface Props {
  readonly children: ReactNode;
  /*
   * `| undefined` spelled out because exactOptionalPropertyTypes is on. A CSS
   * module's export is typed `string | undefined`, so every caller passing one
   * of these through is a type error without it.
   */
  readonly className?: string | undefined;
}

export function Rail({ children, className }: Props) {
  return (
    <div className={`${styles.container} ${className ?? ""}`} data-role="rail">
      <div className={styles.sticky}>
        <div className={styles.track}>{children}</div>
      </div>
    </div>
  );
}
