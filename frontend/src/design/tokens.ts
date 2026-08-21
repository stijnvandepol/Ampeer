/**
 * The names the interface is built from.
 *
 * There is no component library here. This product needs about eight
 * components and its most important one does not exist off the shelf, because
 * nobody else makes an uncertainty band the main object on the page.
 *
 * Everything with a colour or a size lives in src/app/globals.css, once per
 * theme. This file holds only the values TypeScript has to know: the names of
 * CSS variables that code selects between, and the durations code passes to an
 * animation. A hex code in this file would be a colour with one definition,
 * which is the exact failure the two-theme rule exists to prevent.
 */

/**
 * Which CSS variable carries the tone for each confidence level.
 *
 * The keys are the three values `Advice["confidence"]` can hold. A component
 * reads the level off the API response and writes the matching variable into a
 * custom property, so the band is tinted by how sure the answer is. That is
 * also why the map is exhaustive rather than defaulted: a fourth level added to
 * the API should fail the type check here, not fall back to a tone that quietly
 * claims more certainty than the model has.
 */
export const CONFIDENCE_TONE = {
  INDICATIVE: "--colour-confidence-indicative",
  GOOD: "--colour-confidence-good",
  PRECISE: "--colour-confidence-precise",
} as const;

export type ConfidenceLevel = keyof typeof CONFIDENCE_TONE;

/**
 * Milliseconds. Nothing here is long enough for a reader to wait on: a
 * transition somebody notices as a delay reads as slowness, not as polish.
 *
 * These mirror --duration-instant, --duration-quick and --duration-considered
 * in globals.css, and tests/design/motion.test.ts checks the two agree. Under
 * prefers-reduced-motion the CSS values go to 0ms, and code should switch
 * presentation rather than read a smaller number out of here.
 */
export const DURATION = {
  instant: 0,
  quick: 120,
  considered: 320,
} as const;

/**
 * The custom properties the type scale is published under.
 *
 * `bandEnd` and `bandMiddle` are the pair rule 1 rests on: the band's ends are
 * the answer and the middle is a marking inside it, so `bandMiddle` names the
 * smaller of the two. They are separate names rather than two steps of the
 * general scale so that a change to either one is a change somebody has to mean.
 */
export const TYPE_SCALE = {
  xs: "--text-xs",
  sm: "--text-sm",
  base: "--text-base",
  lg: "--text-lg",
  xl: "--text-xl",
  "2xl": "--text-2xl",
  "3xl": "--text-3xl",
  bandEnd: "--text-band-end",
  bandMiddle: "--text-band-middle",
} as const;

/** The spacing steps, on a 4px base. */
export const SPACE = {
  1: "--space-1",
  2: "--space-2",
  3: "--space-3",
  4: "--space-4",
  5: "--space-5",
  6: "--space-6",
  7: "--space-7",
  8: "--space-8",
  9: "--space-9",
} as const;

/**
 * Reads a custom property off the document root.
 *
 * The one supported way to get a token's resolved value at runtime, so the
 * theme in force is the theme that answers. Returns an empty string on the
 * server and in any environment without a computed style, which is why callers
 * must treat an empty result as "not known yet" rather than as a colour.
 */
export function readToken(name: string): string {
  if (typeof window === "undefined") return "";
  return window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
