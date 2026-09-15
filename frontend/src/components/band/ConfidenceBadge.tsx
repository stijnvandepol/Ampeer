import type { CSSProperties } from "react";
import type { Advice } from "@/lib/types";
import { confidenceTone } from "@/design/tokens";
import styles from "./band.module.css";

interface Props {
  readonly confidence: Advice["confidence"];
  readonly label: string;
}

/**
 * How sure the answer is, at the top of the page rather than inside the band.
 *
 * WHY IT MOVED. Rule two in frontend/CLAUDE.md puts this in the first screen,
 * and e2e/rules.spec.ts measures it on a phone as well as a desktop. It used
 * to be the first child of the headline band, which satisfied that while the
 * band was the first thing on the page. Putting a concrete first step above
 * the band pushed it past the fold at 375px, and the test said so.
 *
 * Moving it up is the better answer rather than the cheaper one. This word
 * qualifies everything below it, the first step included, and it belonged
 * above that block and not inside one of the things it qualifies.
 *
 * The band keeps the label in its `aria-label`, because the figure's spoken
 * description is one sentence and a screen reader should not have to have
 * heard a separate badge for it to make sense.
 *
 * It sets `--tone` itself. That variable used to arrive from the band's own
 * inline style, so a copy of this markup outside that element rendered the
 * indicative colour whatever the confidence was: readable, and wrong for two
 * of the three values.
 */
export function ConfidenceBadge({ confidence, label }: Props) {
  const tone = {
    ["--tone" as string]: `var(${confidenceTone(confidence)})`,
  } as CSSProperties;

  return (
    <span className={styles.confidence} style={tone}>
      {label}
    </span>
  );
}
