/**
 * Where the middle sits inside its own band, as a percentage of the width.
 *
 * This is the one place in the frontend that turns an amount into a number, and
 * the number never reaches the screen: it becomes a CSS offset. A marker parked
 * at 50% regardless of the values would be decoration, and a band whose middle
 * is not where the model put it says something the model did not say. Amounts
 * are still rendered as the strings they arrived as, everywhere, including in
 * the component that calls this.
 */

/** Kept off the very edges so the label under the marker stays on the track. */
const MIN_PERCENT = 8;
const MAX_PERCENT = 92;

export function middlePercentage(lowText: string, middleText: string, highText: string): number {
  const low = Number.parseFloat(lowText);
  const middle = Number.parseFloat(middleText);
  const high = Number.parseFloat(highText);
  if (!Number.isFinite(low) || !Number.isFinite(middle) || !Number.isFinite(high)) return 50;
  if (high <= low) return 50;
  const fraction = (middle - low) / (high - low);
  return Math.min(MAX_PERCENT, Math.max(MIN_PERCENT, fraction * 100));
}
