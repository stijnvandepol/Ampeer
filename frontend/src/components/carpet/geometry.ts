/**
 * Where a cell is, what it is called, and how a pointer or an arrow key finds
 * it.
 *
 * All of it pure, because none of it needs a browser to be right and every one
 * of these is a place a plate can be quietly off by one: a month label a day
 * wide of its column, an hour that reads 24:00, a pointer that lands on the
 * last day whenever it leaves the right edge.
 */

/**
 * The twelve months with their lengths, as one table.
 *
 * One array of pairs rather than two arrays read by the same index. Two arrays
 * need an index to line them up, `noUncheckedIndexedAccess` makes every such
 * read a `number | undefined`, and the `?? 0` that satisfies it is a branch no
 * test can reach, which is a permanently uncovered line in a file whose whole
 * point is that it is covered.
 */
const MONTHS = [
  { label: "jan", length: 31 },
  { label: "feb", length: 28 },
  { label: "mrt", length: 31 },
  { label: "apr", length: 30 },
  { label: "mei", length: 31 },
  { label: "jun", length: 30 },
  { label: "jul", length: 31 },
  { label: "aug", length: 31 },
  { label: "sep", length: 30 },
  { label: "okt", length: 31 },
  { label: "nov", length: 30 },
  { label: "dec", length: 31 },
] as const;

/** A year with a 29th of February in it. */
const LEAP_YEAR_DAYS = 366;

/** February, counting from January at zero. */
const FEBRUARY = 1;

export interface Month {
  readonly label: string;
  readonly length: number;
}

export interface Cursor {
  readonly day: number;
  readonly quarter: number;
}

/**
 * The twelve months of a year of this many days.
 *
 * The plate is as wide as the year is long, so a leap year is 366 columns and
 * February is one wider. Drawing twelve equal columns instead would put every
 * label after February between one and two days off its own block, which on a
 * picture whose argument is that the quarter is the unit is not a rounding.
 */
export function monthsOf(days: number): readonly Month[] {
  return MONTHS.map((month, at) =>
    at === FEBRUARY && days === LEAP_YEAR_DAYS
      ? { label: month.label, length: month.length + 1 }
      : month,
  );
}

/** "3 mrt" for day 61 of a common year. Empty for a day outside the year. */
export function dayLabel(day: number, days: number): string {
  let remaining = day;
  for (const month of monthsOf(days)) {
    if (remaining < month.length) return `${remaining + 1} ${month.label}`;
    remaining -= month.length;
  }
  return "";
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** "13:45" for quarter 55. The clock the grid runs on, not the wall's. */
export function quarterLabel(quarter: number): string {
  return `${pad(Math.floor(quarter / 4))}:${pad((quarter % 4) * 15)}`;
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/**
 * The cell under a pointer, from its position across and down the plate as
 * fractions of the plate's own box.
 *
 * Fractions rather than pixels, so this never has to know how large the canvas
 * was drawn. Null when either fraction is not a number, which is what a
 * zero-width box gives: dividing by it produces Infinity or NaN, `Math.floor`
 * of that is not an index, and clamping it silently lands on the last day of
 * the year. A plate that reports 31 December for every hover is worse than one
 * that reports nothing.
 */
export function cellFromPointer(
  across: number,
  down: number,
  days: number,
  rows: number,
): Cursor | null {
  if (!Number.isFinite(across) || !Number.isFinite(down)) return null;
  return {
    day: clamp(Math.floor(across * days), 0, days - 1),
    quarter: clamp(Math.floor(down * rows), 0, rows - 1),
  };
}

/** One step per arrow key: a day sideways, a quarter of an hour up or down. */
const STEPS: Readonly<Record<string, readonly [number, number]>> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
};

/**
 * The cell an arrow key moves to, or null when the key is not one of the four.
 *
 * Null rather than the cell unchanged, because the caller uses it to decide
 * whether to swallow the key. A plate that consumed every keystroke would take
 * Tab and Escape away from a visitor who is trying to leave it.
 *
 * From nowhere, the first arrow lands on the first quarter of 1 January rather
 * than on the middle of the plate. It is the origin of both axes, so a reader
 * who cannot see the plate at least knows where the cursor started.
 */
export function moveCursor(
  from: Cursor | null,
  key: string,
  days: number,
  rows: number,
): Cursor | null {
  const step = STEPS[key];
  if (step === undefined) return null;
  const at = from ?? { day: 0, quarter: 0 };
  return {
    day: clamp(at.day + step[0], 0, days - 1),
    quarter: clamp(at.quarter + step[1], 0, rows - 1),
  };
}

/**
 * A quantity of energy, written the way a Dutch reader writes one.
 *
 * `dutchAmount` in components/band is for money and refuses to go near a
 * number on purpose, because an amount that passes through a float is rounded
 * by whoever touched it last. This is energy: `CLAUDE.md` draws that line
 * itself, kWh are floats out of models with an uncertainty of percentages, and
 * these particular floats have already been through a byte. So the value here
 * is a number and the only thing that happens to it is a decimal comma.
 */
export function dutchQuantity(value: number, decimals: number): string {
  return value.toFixed(decimals).replace(".", ",");
}

/**
 * Where a cursor sits along the plate, as a CSS percentage of its width.
 *
 * The plate is drawn at one pixel per quarter and scaled by the stylesheet, so
 * nothing in the component knows how wide it is on screen. A percentage is the
 * only position that survives that, and it is why the crosshair is two absolute
 * elements over the canvas rather than anything drawn into the image.
 *
 * The half is the middle of the column rather than its left edge: a hairline on
 * the edge sits between two days and names neither.
 *
 * With no cursor it answers the centre. The crosshair is transparent then, so
 * the value is never seen; what it avoids is a jump from a corner the first
 * time a reader arrives, which is the one moment the transition is visible.
 */
export function acrossOf(cursor: Cursor | null, days: number): string {
  if (cursor === null || days <= 0) return "50%";
  return `${(((cursor.day + 0.5) / days) * 100).toFixed(4)}%`;
}

/** Where a cursor sits down the plate, as a CSS percentage of its height. */
export function downOf(cursor: Cursor | null, rows: number): string {
  if (cursor === null || rows <= 0) return "50%";
  return `${(((cursor.quarter + 0.5) / rows) * 100).toFixed(4)}%`;
}
