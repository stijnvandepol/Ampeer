/**
 * The type sizes a band is drawn at, in rem, and the one rule they exist to
 * keep.
 *
 * The middle is never set larger than the ends. That single choice is the whole
 * difference between a band and a headline figure with decoration: set the p50
 * in display type with the ends in small print and the band is gone, whatever
 * the markup says. Every calculator in this market has already made the other
 * choice.
 *
 * The sizes are applied as inline styles rather than as classes, which is worth
 * a sentence because it looks like a shortcut and is not. The rule is checked by
 * reading the computed font size in jsdom, and jsdom loads no stylesheet, so a
 * size that lives only in a stylesheet reads back as zero on both elements and
 * the check passes without ever having looked at anything. Inline is the only
 * place the test environment can see.
 */

/** The two ends of the headline band: the widest thing on the page. */
export const BAND_END_REM = 1.75;

/** The marking inside it. Smaller than the ends, deliberately. */
export const BAND_MIDDLE_REM = 1.25;

/** A scenario band is a smaller object throughout, and obeys the same rule. */
export const SCENARIO_END_REM = 1.05;
export const SCENARIO_MIDDLE_REM = 0.95;
