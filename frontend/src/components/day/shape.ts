/**
 * One day of ninety six quarters, drawn rather than simulated, and the two
 * orders it can be put in.
 *
 * WHAT THIS IS NOT. It is not a household, not a model output and not a
 * prediction. Nothing here comes from `ampeer_sim`, and it must not: a shape
 * on the landing page that looked like a computed answer would be a number
 * nobody computed for the person reading it, which is the rule the page's own
 * comment states. It is a diagram of a rule, in the same position a diagram of
 * a rule belongs, and the page says so in as many words.
 *
 * WHAT IT IS FOR. Saldering nets what crossed the meter and pays the
 * difference, over a whole year. Two things follow that the figure exists to
 * show, and neither is obvious from a sentence:
 *
 *   - the order in time is thrown away. A kWh exported in June cancels one
 *     imported in December, so a quarter's moment carries no value at all.
 *   - the quarters you used yourself never crossed the meter, so they were
 *     never in that sum. From 1 January 2027 they are the ones that matter.
 *
 * So the animation is a SORT. The same ninety six cells stand in time order and
 * then move into three blocks by state. What a reader watches disappear is the
 * time axis, and that is exactly what the end of saldering gives back.
 *
 * The numbers below are shape parameters for a curve, not measurements, and
 * they are named so nobody mistakes one for the other.
 */

/** Quarters in a day. The same unit the plate on the advice page is made of. */
export const QUARTERS = 96;

/** The three states a quarter can be in, spelled as the carpet spells them. */
export type DayState = "own" | "offtake" | "export";

export interface DayQuarter {
  /** Its place in the day, 0 at midnight. */
  readonly at: number;
  readonly state: DayState;
  /** 0 to 1 within its own state, for how strongly the cell is drawn. */
  readonly magnitude: number;
}

/** Solar noon, in quarters past midnight. Half past one, near enough. */
const NOON = 54;

/** How wide the production bell is, in quarters. */
const DAY_WIDTH = 20;

/** Peak production and the flat base of consumption, in the same arbitrary unit. */
const PEAK = 1;
const BASE = 0.18;

/** The two moments a household is busy, in quarters past midnight. */
const MORNING = 30;
const EVENING = 76;
const PEAK_WIDTH = 7;
const MORNING_SIZE = 0.35;
const EVENING_SIZE = 0.55;

function bell(at: number, centre: number, width: number): number {
  const away = (at - centre) / width;
  return Math.exp(-away * away);
}

/**
 * The height the bell has to be lowered by so that it reaches zero at both
 * ends of the day.
 *
 * The larger of the two endpoints and not the value at midnight. Solar noon is
 * at quarter 54, which is not the middle of the day as the clock counts it, so
 * the last quarter sits 41 quarters from the peak while the first sits 54 from
 * it. Subtracting only the first left 0,0143 of production at a quarter to
 * midnight: a small number, and a curve that says the panels were making
 * something at 23:45.
 */
const NIGHT_FLOOR = Math.max(
  bell(0, NOON, DAY_WIDTH),
  bell(QUARTERS - 1, NOON, DAY_WIDTH),
);

/** The drawn curve of what the panels make, zero through the night. */
export function production(at: number): number {
  return Math.max(0, (bell(at, NOON, DAY_WIDTH) - NIGHT_FLOOR) * PEAK);
}

/** The drawn curve of what the household uses: a base and two peaks. */
export function consumption(at: number): number {
  return (
    BASE +
    MORNING_SIZE * bell(at, MORNING, PEAK_WIDTH) +
    EVENING_SIZE * bell(at, EVENING, PEAK_WIDTH)
  );
}

/**
 * The day, one entry per quarter.
 *
 * The state is decided the way the plate decides it, and for the same reason:
 * two figures in one product that disagree about what a quarter is are worse
 * than one figure. Own use is the larger flow or it is not; a tie is the meter,
 * because a dark quarter has nothing of either and calling that self
 * consumption would light up the night.
 */
export function illustrativeDay(): readonly DayQuarter[] {
  const rows: DayQuarter[] = [];
  for (let at = 0; at < QUARTERS; at += 1) {
    const made = production(at);
    const used = consumption(at);
    const own = Math.min(made, used);
    const over = made - used;
    const meter = Math.abs(over);
    const state: DayState =
      own > meter ? "own" : over > 0 ? "export" : "offtake";
    const size = state === "own" ? own : meter;
    rows.push({ at, state, magnitude: Math.min(1, size / PEAK) });
  }
  return rows;
}

/**
 * The order the meter's sum leaves the day in.
 *
 * Own first, then what was taken from the grid, then what was given back,
 * each block keeping the day's own order inside it. Stable on purpose: a cell
 * that jumped its neighbours would read as movement in time, and time is the
 * thing this figure is showing being removed.
 */
const BLOCKS: readonly DayState[] = ["own", "offtake", "export"];

export function sortedOrder(day: readonly DayQuarter[]): readonly number[] {
  const places = new Array<number>(day.length);
  let next = 0;
  for (const block of BLOCKS) {
    for (const quarter of day) {
      if (quarter.state === block) {
        places[quarter.at] = next;
        next += 1;
      }
    }
  }
  return places;
}

/** How many quarters each block holds, for the labels under the sorted view. */
export function blockSizes(
  day: readonly DayQuarter[],
): Readonly<Record<DayState, number>> {
  const counts: Record<DayState, number> = { own: 0, offtake: 0, export: 0 };
  for (const quarter of day) counts[quarter.state] += 1;
  return counts;
}

/**
 * Where a cell sits, as a percentage of the strip's width.
 *
 * A percentage and not a pixel: the strip is fluid, the cells are positioned
 * inside it, and a pixel computed in TypeScript would be a second opinion about
 * a width the stylesheet already has.
 */
export function placeAt(order: number, total: number): string {
  if (total <= 0) return "0%";
  return `${((order / total) * 100).toFixed(4)}%`;
}
