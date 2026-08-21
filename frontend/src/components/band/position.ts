/**
 * The geometry of a band: how wide it is drawn, where it sits, and where its
 * middle is marked.
 *
 * This is the one place in the frontend that turns an amount into a number, and
 * the number never reaches the screen: it becomes a CSS length. Amounts are
 * still rendered as the strings they arrived as, everywhere, including in the
 * components that call this.
 *
 * WHAT THE WIDTH MEANS. Chapter 7 of the spec asks for "een verlopende balk
 * waarin de breedte de onzekerheid ís", and for a while the fill was
 * `width: 100%` on every band. A rule worth 105 to 166 euro and one worth 270
 * to 653 euro were then drawn as the same object at the same size, and the only
 * visual variable left was the marker, which encodes skew rather than spread. A
 * reader could only learn the uncertainty by reading the numbers, which is the
 * thing this page exists not to require.
 *
 * The axis a band is drawn on runs from zero to the band's own upper end, or
 * from its lower end to zero when the whole band is negative. Both ends of that
 * axis are numbers the model produced, so there is no invented reference
 * constant here and no page-wide maximum that a second band could shift. The
 * width of the band is the share of that axis it covers, which is its
 * uncertainty as a fraction of the largest amount the model considers
 * plausible, and it is comparable between a band in euro and one in years
 * precisely because it is a fraction rather than an amount.
 *
 * A band with no spread therefore has no width, which is the point: it is a
 * marker on an axis and not a rail. The previous version returned a centred
 * marker on a full-width track for exactly that case, which is the picture of a
 * range where there is none.
 */

/** Everything unreadable resolves to this: draw nothing rather than guess. */
const NO_BAND = 0;

/** Kept off the very edges so a label anchored to it stays on the track. */
const MIN_LABEL_PERCENT = 10;
const MAX_LABEL_PERCENT = 90;

interface Axis {
  readonly min: number;
  readonly max: number;
}

function readAmount(text: string): number | null {
  const value = Number.parseFloat(text);
  return Number.isFinite(value) ? value : null;
}

/**
 * The axis a band of low..high is measured against, or null when there is
 * none. Zero is always on it, so a band that straddles zero covers the whole
 * axis and a band that does not is measured from zero to its far end.
 */
function axisFor(lowText: string, highText: string): Axis | null {
  const low = readAmount(lowText);
  const high = readAmount(highText);
  if (low === null || high === null) return null;
  if (high < low) return null;
  const min = Math.min(0, low);
  const max = Math.max(0, high);
  if (max <= min) return null;
  return { min, max };
}

/**
 * How much of its axis the band covers, from 0 to 1. This is the width the band
 * is drawn at, as a fraction of the track.
 */
export function bandSpanFraction(lowText: string, highText: string): number {
  const axis = axisFor(lowText, highText);
  if (axis === null) return NO_BAND;
  const low = readAmount(lowText) ?? 0;
  const high = readAmount(highText) ?? 0;
  return Math.min(1, Math.max(0, (high - low) / (axis.max - axis.min)));
}

/** Where the band starts on its axis, from 0 to 1. */
export function bandOffsetFraction(lowText: string, highText: string): number {
  const axis = axisFor(lowText, highText);
  if (axis === null) return NO_BAND;
  const low = readAmount(lowText) ?? 0;
  return Math.min(1, Math.max(0, (low - axis.min) / (axis.max - axis.min)));
}

/**
 * Where the middle sits on the same axis, as a percentage.
 *
 * Unclamped, because the marker has to be inside the band it belongs to and
 * moving it would say the model put the middle somewhere it did not. 50 is
 * returned only when there is no axis to place it on, which is a state in which
 * nothing is drawn anyway.
 */
export function axisPercentage(
  lowText: string,
  middleText: string,
  highText: string,
): number {
  const axis = axisFor(lowText, highText);
  const middle = readAmount(middleText);
  if (axis === null || middle === null) return 50;
  return Math.min(
    100,
    Math.max(0, ((middle - axis.min) / (axis.max - axis.min)) * 100),
  );
}

/**
 * The same place, pulled far enough from the edges that a label centred on it
 * stays on the track.
 *
 * Separate from the marker on purpose: the marker may not be moved, because its
 * position is a claim about the answer, while the label's position is only
 * typesetting. A label that ran off the track would push the page sideways,
 * which is a reflow failure on the phone this site is mostly read on.
 */
export function labelPercentage(
  lowText: string,
  middleText: string,
  highText: string,
): number {
  const at = axisPercentage(lowText, middleText, highText);
  return Math.min(MAX_LABEL_PERCENT, Math.max(MIN_LABEL_PERCENT, at));
}
