/**
 * The colours of the plate, and the rule that keeps every one of them
 * measurable.
 *
 * A cell of this plate is one pixel. It carries no label, no shape, no border
 * and no position of its own, so colour is the entire encoding: if two states
 * are not distinguishable the picture says nothing at all. That is why the
 * three states are in `GRAPHIC_PAIRS` in `tests/design/contrast.test.ts` rather
 * than exempt from it.
 *
 * THE FLOOR RULE. Each state has exactly one token in `globals.css` and this
 * module only ever LIGHTENS it, towards white, by that state's own fixed share
 * of the way. So the token is the dimmest cell the state can produce, the pair
 * measured in the contrast test is that state's worst case, and there is no
 * colour on this plate that was never measured. The obvious alternative, the
 * one the prototype used, blends each state towards the instrument's ground by
 * its magnitude; that draws a low quarter at a ratio approaching 1:1 against
 * the ground while the token it is derived from measures fine, which is a
 * check that agrees with a stylesheet and not with a screen.
 *
 * WHAT THE LIFTS ARE FOR AND WHY THEY ARE SMALL. Magnitude has to be visible
 * inside a state, or a winter evening and a January cold snap are the same
 * grey. It also has to stay inside its own band: the three states occupy three
 * non-overlapping ranges of contrast against the ground, so no cell of one
 * state can be mistaken for a cell of another, and a larger lift closes those
 * gaps. Measured on 2026-08-27 over all 65536 cells the format can hold:
 * export 3,10 to 4,53, offtake 6,70 to 7,63, own 11,90 to 13,57, worst
 * neighbouring pair 1,57:1. `tests/carpet/palette.test.ts` pins all of it.
 *
 * Those neighbouring pairs are 1,57:1 and not 3:1, and that is arithmetic
 * rather than a corner cut. Three states above a ground of relative luminance
 * 0,0049, each 3:1 from the next, would need 0,115 then 0,444 then 1,432, and
 * relative luminance stops at 1. So a ground and two states is the most a
 * pairwise ladder holds; the third is told apart by hue, and by the fact that
 * the bands do not overlap.
 */

import {
  EXPORT_FLAG,
  MAGNITUDE_MASK,
  OWN_FULL_SCALE,
  byteAt,
  type DecodedYear,
} from "./decode";

export type Rgb = readonly [number, number, number];

/** The three states a quarter of an hour can be in, as this plate draws them. */
export type CarpetState = "own" | "offtake" | "export";

export interface CarpetPalette {
  readonly ground: Rgb;
  readonly own: Rgb;
  readonly offtake: Rgb;
  readonly export: Rgb;
}

/**
 * The names in globals.css, spelled once.
 *
 * Held here rather than in the component so that the stylesheet, the contrast
 * test and the renderer are all naming the same four strings. A token this
 * file misspells resolves to the empty string in the browser, `paletteFrom`
 * returns null, and the plate quietly does not draw; the component test that
 * feeds these very names through a reader is what would catch it.
 */
export const CARPET_TOKENS = {
  ground: "--colour-carpet-ground",
  own: "--colour-carpet-own",
  offtake: "--colour-carpet-offtake",
  export: "--colour-carpet-export",
} as const;

/** How far towards white a state is lightened at full magnitude. */
export const STATE_LIFT: Readonly<Record<CarpetState, number>> = {
  own: 0.28,
  offtake: 0.1,
  export: 0.12,
};

/** Full scale for the alpha channel of the image being built. */
const OPAQUE = 255;

/** "#f5c64a" to its three channels, or null when it is not that. */
export function parseHex(value: string): Rgb | null {
  const text = value.trim();
  if (!/^#[0-9a-f]{6}$/i.test(text)) return null;
  return [
    Number.parseInt(text.slice(1, 3), 16),
    Number.parseInt(text.slice(3, 5), 16),
    Number.parseInt(text.slice(5, 7), 16),
  ];
}

/**
 * The palette, read through whatever the caller uses to look a token up.
 *
 * A function rather than an element, so this can be exercised without a
 * document. Null when any one of the four is missing or is not a literal hex,
 * because a plate drawn in three of its four colours is a plate that says
 * something untrue rather than a plate that looks slightly off.
 */
export function paletteFrom(
  read: (name: string) => string,
): CarpetPalette | null {
  const ground = parseHex(read(CARPET_TOKENS.ground));
  const own = parseHex(read(CARPET_TOKENS.own));
  const offtake = parseHex(read(CARPET_TOKENS.offtake));
  const exported = parseHex(read(CARPET_TOKENS.export));
  if (ground === null || own === null) return null;
  if (offtake === null || exported === null) return null;
  return { ground, own, offtake, export: exported };
}

/** A colour, this far towards white. Never towards the ground. */
function lift(colour: Rgb, share: number): Rgb {
  return [
    colour[0] + (OPAQUE - colour[0]) * share,
    colour[1] + (OPAQUE - colour[1]) * share,
    colour[2] + (OPAQUE - colour[2]) * share,
  ];
}

/**
 * Which of the three a quarter belongs to.
 *
 * The larger of the two flows wins, in kWh, which is why `cellAt` returns kWh
 * rather than bytes: the two bytes are scaled against different ceilings and
 * comparing them directly would call a quarter self-consumed because its own
 * ceiling happened to be the smaller number.
 *
 * A quarter in which self-consumption is the larger flow is the one thing this
 * whole product is about, so it is the one that takes the saturated colour.
 * Every other quarter shows which way the meter ran.
 */
export function stateOf(
  ownKwh: number,
  meterKwh: number,
  exported: boolean,
): CarpetState {
  if (ownKwh > meterKwh) return "own";
  return exported ? "export" : "offtake";
}

/** One cell's colour: its state's floor, lifted by its magnitude in that state. */
export function cellColour(
  palette: CarpetPalette,
  state: CarpetState,
  magnitude: number,
): Rgb {
  const bounded = Math.min(1, Math.max(0, magnitude));
  return lift(palette[state], STATE_LIFT[state] * Math.sqrt(bounded));
}

/**
 * The whole year as one RGBA image, at data resolution.
 *
 * One pixel per quarter, 365 wide and 96 tall, drawn at that size and scaled up
 * by the stylesheet with smoothing off. Interpolating between two quarters
 * would invent a value the model never produced, and on a plate whose entire
 * argument is that the quarter is the unit, that is the one thing it may not
 * do.
 *
 * The image is transposed on the way in: the payload runs day by day, and the
 * picture runs hour by hour down each day's column.
 */
export function buildPixels(
  year: DecodedYear,
  palette: CarpetPalette,
): Uint8ClampedArray {
  const { days, quartersPerDay: rows } = year;
  const pixels = new Uint8ClampedArray(days * rows * 4);
  for (let day = 0; day < days; day += 1) {
    for (let quarter = 0; quarter < rows; quarter += 1) {
      const meter = byteAt(year.meter, day * rows + quarter);
      const exported = (meter & EXPORT_FLAG) !== 0;
      const ownShare = byteAt(year.own, day * rows + quarter) / OWN_FULL_SCALE;
      const meterShare = (meter & MAGNITUDE_MASK) / MAGNITUDE_MASK;
      const state = stateOf(
        ownShare * year.ceilings.own,
        meterShare * (exported ? year.ceilings.export : year.ceilings.grid),
        exported,
      );
      const colour = cellColour(
        palette,
        state,
        state === "own" ? ownShare : meterShare,
      );
      const at = (quarter * days + day) * 4;
      pixels[at] = colour[0];
      pixels[at + 1] = colour[1];
      pixels[at + 2] = colour[2];
      pixels[at + 3] = OPAQUE;
    }
  }
  return pixels;
}

/** A colour the canvas API will take, built from numbers rather than written. */
export function cssColour(colour: Rgb): string {
  return `rgb(${Math.round(colour[0])} ${Math.round(colour[1])} ${Math.round(colour[2])})`;
}
