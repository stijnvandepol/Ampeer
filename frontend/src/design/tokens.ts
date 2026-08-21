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
 * custom property, so the band is tinted by how sure the answer is.
 *
 * This map used to be indexed directly, with a comment claiming that a fourth
 * level added to the API "should fail the type check here". It does not:
 * `Advice` is a description of JSON, and JSON arriving over the wire is not
 * checked by anything at runtime. A response with a fourth level produced
 * `var(undefined)`, which React drops, which left band.module.css falling
 * through to a hard-coded #5b8def, a colour in neither palette, never measured
 * against any background, and close enough to the PRECISE navy to read as more
 * certain than PRECISE. Nothing on the page said the level was unknown.
 *
 * So the lookup goes through `confidenceTone` instead, and the claim in this
 * comment is now the code's behaviour rather than a hope about the compiler.
 */
export const CONFIDENCE_TONE = {
  INDICATIVE: "--colour-confidence-indicative",
  GOOD: "--colour-confidence-good",
  PRECISE: "--colour-confidence-precise",
} as const;

export type ConfidenceLevel = keyof typeof CONFIDENCE_TONE;

/**
 * The tone for a level, and the least certain tone for a level this build has
 * never heard of.
 *
 * INDICATIVE rather than a fourth colour, because the tone is a claim about how
 * much the answer is worth and an unrecognised level is a level this code
 * cannot vouch for. Claiming less than the model meant is recoverable; claiming
 * more is the failure this product exists to avoid. The value is always a token
 * that both palettes define and that the contrast test measures.
 */
export function confidenceTone(level: string): string {
  // Object.hasOwn rather than a plain lookup, because a plain lookup walks the
  // prototype chain: confidenceTone("constructor") handed back a function, and
  // `var(function Object() ...)` is not a colour. The level comes off a JSON
  // response, so the set of strings that can reach here is whatever the wire
  // carries.
  if (!Object.hasOwn(CONFIDENCE_TONE, level)) return CONFIDENCE_TONE.INDICATIVE;
  return (
    (CONFIDENCE_TONE as Readonly<Record<string, string>>)[level] ??
    CONFIDENCE_TONE.INDICATIVE
  );
}

/**
 * Milliseconds. Nothing here is long enough for a reader to wait on: a
 * transition somebody notices as a delay reads as slowness, not as polish.
 *
 * These mirror --duration-instant, --duration-quick and --duration-considered
 * in globals.css, and tests/design/motion.test.tsx checks the two agree. Under
 * prefers-reduced-motion the CSS values go to 0ms, and code should switch
 * presentation rather than read a smaller number out of here.
 */
export const DURATION = {
  instant: 0,
  quick: 120,
  considered: 320,
} as const;
