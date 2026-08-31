/**
 * What a kilowatt hour is worth, before and after 1 January 2027, in cents.
 *
 * WHY THESE ARE HERE AND NOT FETCHED. Every other figure on this site comes
 * from the API, because every other figure is about one household. These are
 * not: they are the tariff landscape, the same for everybody, and they are what
 * the page has to state before a visitor has told us anything at all. There is
 * no household here to compute them for.
 *
 * They are a copy of `SUPPLY_PRICE`, `FEED_IN_GROSS_FIXED` and `FEED_IN_COST`
 * in `ampeer_advice/tariffs.py`, and a copy of a number is the thing this
 * repository distrusts most. So it is held: `tests/test_price_gap.py` reads
 * this file and compares every figure below against the model's own bands. A
 * tariff that moves in the engine and not here arrives as a red build rather
 * than as a marketing page quoting last year's landscape.
 *
 * WHY BANDS AND NOT MIDPOINTS. Rule one of the frontend spec says no figure is
 * drawn larger than its own band. It was written about a household's answer and
 * it is not weaker here: "3 tot 8 cent" is the number in every article about
 * this change, it is the GROSS figure, and the net one is different enough to
 * change what a household should do. A single midpoint on this page would be
 * the same mistake in a smaller font.
 */

/** Cents per kWh. Integers and one decimal, because that is the precision these carry. */
export interface PriceBand {
  readonly low: number;
  readonly high: number;
}

/**
 * What a kilowatt hour you use yourself is worth: what you did not have to buy.
 *
 * `SUPPLY_PRICE` in the model, 0,22 to 0,30 euro. This is the band that barely
 * moves in 2027, and saying so is half the point of the figure: the change is
 * not that self consumption became more valuable, it is that export stopped
 * being valuable.
 */
export const SELF_USED_CENTS: PriceBand = { low: 22, high: 30 };

/**
 * What a kilowatt hour you export is worth WHILE saldering exists.
 *
 * Identical to the band above, and that identity is not a simplification: it
 * is what the rule says. Saldering subtracts exported kilowatt hours from
 * imported ones and bills the difference, so an exported kWh is worth exactly
 * the one it cancels. The figure draws them as one band because they are one
 * band.
 */
export const EXPORTED_NOW_CENTS: PriceBand = SELF_USED_CENTS;

/**
 * What a kilowatt hour you export is worth from 2027, on a fixed contract,
 * after terugleverkosten.
 *
 * `FEED_IN_GROSS_FIXED` minus `FEED_IN_COST` across every combination: the
 * lowest gross against the highest cost is 0,050 - 0,115, and the highest gross
 * against the lowest is 0,077 - 0,0446. Chapter 11 of docs/methodologie.md
 * carries the same pair and notes it agrees with the published net figures,
 * which run from -7,43 to +1,19 cents.
 *
 * The bottom is NEGATIVE, and that is the fact this whole figure exists to
 * carry. At the unfavourable end, exporting a kilowatt hour costs money rather
 * than earning any. Nothing in the "3 tot 8 cent" a reader has seen elsewhere
 * says that, because that is the gross figure with the costs still in front
 * of it.
 */
export const EXPORTED_2027_CENTS: PriceBand = { low: -6.5, high: 3.2 };

/** The two states the figure can be in. */
export type Regime = "nu" | "2027";

/** The exported band in a given regime. The self-used band is the same in both. */
export function exportedIn(regime: Regime): PriceBand {
  return regime === "nu" ? EXPORTED_NOW_CENTS : EXPORTED_2027_CENTS;
}

/**
 * The scale the figure is drawn on, in cents.
 *
 * Fixed rather than fitted to whichever band is showing. A scale that resized
 * between the two states would keep the bars the same height and move the axis
 * underneath them, which is the one way to draw this change and have it look
 * like nothing happened.
 */
export const SCALE_TOP_CENTS = 32;
export const SCALE_BOTTOM_CENTS = -8;

/** Where a value sits on the scale, as a percentage down from the top. */
export function downOf(cents: number): number {
  const span = SCALE_TOP_CENTS - SCALE_BOTTOM_CENTS;
  const clamped = Math.min(
    SCALE_TOP_CENTS,
    Math.max(SCALE_BOTTOM_CENTS, cents),
  );
  return ((SCALE_TOP_CENTS - clamped) / span) * 100;
}

/**
 * A band as a top and a height in percent, for a rectangle on that scale.
 *
 * Never a zero height. A band whose ends round to the same pixel would vanish,
 * and an invisible band reads as an absent one, which on this figure would say
 * a price is certain when it is not.
 */
export function boxOf(band: PriceBand): { top: number; height: number } {
  const top = downOf(band.high);
  const bottom = downOf(band.low);
  return { top, height: Math.max(0.8, bottom - top) };
}

/** Dutch for a cent figure: a comma, and a minus that reads as one. */
export function cents(value: number): string {
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1);
  return text.replace(".", ",");
}
