import fixture from "../tests/fixtures/advice-response.json";

/**
 * Every route this site serves, in one place, because two copies drifted.
 *
 * `rules.spec.ts` swept nine and `theme.spec.ts` swept six. The three the dark
 * palette never saw were `/einde-saldering/`, `/over-ons/` and `/privacy/`,
 * and nothing failed: a sweep over a short list passes exactly as loudly as a
 * sweep over a complete one. A route added to one list and not the other is
 * the same defect again, which is why there is now one list and not two.
 *
 * The count is asserted in both specs rather than here. A constant that
 * checked its own length would pass the day somebody edited both the list and
 * the number together, which is the edit that needs a second pair of eyes, and
 * the assertion belongs where a reader of the sweep will see it.
 */

/** The token in the fixture, which is the shape the API issues: 22 url-safe characters. */
export const TOKEN = fixture.token;

export const ADVICE_PATH = `/advies/${TOKEN}/`;

export const ALL_PATHS = [
  "/",
  "/einde-saldering/",
  "/thuisbatterij/",
  "/berekenen/",
  ADVICE_PATH,
  "/methodologie/",
  "/over-ons/",
  "/privacy/",
  "/voorwaarden/",
  "/account/",
] as const;
