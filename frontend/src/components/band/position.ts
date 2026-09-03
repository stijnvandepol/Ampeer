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
 * Where an amount sits on the band's own axis, as a percentage.
 *
 * Written for the middle and correct for any of the three: the ends and the
 * axis's zero are placed by this same call, so a label and the thing it names
 * can never come out of two different roundings.
 *
 * Unclamped, because the marker has to be inside the band it belongs to and
 * moving it would say the model put the middle somewhere it did not. 50 is
 * returned only when there is no axis to place it on, which is a state in which
 * nothing is drawn anyway.
 */
export function axisPercentage(
  lowText: string,
  amountText: string,
  highText: string,
): number {
  const axis = axisFor(lowText, highText);
  const amount = readAmount(amountText);
  if (axis === null || amount === null) return 50;
  return Math.min(
    100,
    Math.max(0, ((amount - axis.min) / (axis.max - axis.min)) * 100),
  );
}

/**
 * The custom property `.anchored` in band.module.css reads. One number reaches
 * the stylesheet and the stylesheet derives both declarations from it, so the
 * offset along the track and the offset into the label are the same number by
 * construction and cannot be written apart.
 */
export const LABEL_ANCHOR_PROPERTY = "--band-label-at";

/** The one inline declaration that places a label. */
export type LabelAnchor = Readonly<Record<string, string>>;

/**
 * How a label is put over the point it names, without ever leaving the track.
 *
 * The stylesheet sets `left` to this percentage of the track and translates the
 * label by the same percentage of its own width, so a label at 0% is flush with
 * the left of the track, one at 100% flush with the right, and one at 40% has
 * its own 40% mark over the axis's 40% mark. The label therefore always covers
 * the point it names and never extends past either end, whatever the label
 * turns out to measure and whatever the track measures. There is no threshold
 * in it and nothing is measured at runtime.
 *
 * This replaced a clamp that kept a centred label between 10% and 90% of the
 * track, which was an approximation of the same idea that assumed a label was
 * at most a fifth of the track. Measured on the built page at a 320px viewport:
 * the track is 272px, the middle label is 104px, and the clamped label's right
 * edge landed at 307px against a content edge of 296px. It stayed inside the
 * viewport only because the page's own gutter absorbed the overflow, so nothing
 * caught it. The two end labels are 148px, more than half the track, and the
 * clamp is not even close for them.
 *
 * Not centred, then, which costs something and is worth naming: for a value in
 * the middle of the axis a centred label points more precisely than this one
 * does. What this buys is that the label is always over its own value and
 * always on the track, at every width. The marker keeps the exact position, as
 * it always did: it may not be moved, because its position is a claim about the
 * answer, while a label's position is typesetting.
 *
 * A percentage and not a pair of CSS strings, which is worth a sentence because
 * the pair was written first and reads more directly. `translateX(-` in a
 * template literal here is a string in a returned object, which is a text
 * position to the extractor in e2e/language.spec.ts, so it landed in
 * tests/ui-strings.txt beside the sentences that file exists to make reviewable.
 * A custom property is dropped by that walk by shape, and the CSS ends up in
 * the stylesheet where it belongs.
 */
export function labelAnchor(percentage: number): LabelAnchor {
  const at = Math.min(100, Math.max(0, percentage));
  return { [LABEL_ANCHOR_PROPERTY]: `${at}%` };
}
