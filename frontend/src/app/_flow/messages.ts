import { ApiError } from "@/lib/api";

/**
 * What to put on the screen when the API said no.
 *
 * These are interface messages, which is the one kind of Dutch the frontend
 * writes. They are not advice: none of them tells a household anything about
 * its own electricity, they tell a visitor what just happened to their
 * request. Advice sentences arrive from the API and are rendered as they came.
 *
 * Every branch says what happened and what the visitor can do next, because a
 * message that only says something went wrong turns a page into guessing. The
 * two failures that need saying out loud are the 429, where waiting is the
 * whole answer, and the 404, where waiting will never help.
 */

/** Said for a link that is truncated, mistyped, or simply no longer an advice. */
const LINK_IS_NOT_AN_ADVICE =
  "Deze link hoort niet bij een berekening. Controleer of hij compleet is overgenomen.";

/** The field messages DRF sent, flattened for display. Empty when there are none. */
export function fieldMessages(error: unknown): readonly string[] {
  if (!(error instanceof ApiError)) return [];
  return Object.values(error.fields).flat();
}

/**
 * Which of the two things was being asked for.
 *
 * A 400 means two different things on the two paths, and the difference is the
 * whole message. Computing an advice sends a body, so a 400 is about a value
 * the visitor typed. Reading one back sends no body at all, so a 400 can only
 * be the token: `getAdvice` refuses a string that is not the shape the API
 * issues before spending a request on it. Telling somebody with a truncated
 * link to check their input would send them looking in the wrong place.
 */
export type Attempt = "compute" | "link";

export function describeApiError(
  error: unknown,
  attempt: Attempt = "compute",
): string {
  if (!(error instanceof ApiError)) {
    // fetch() rejects rather than resolving when the network is gone, the
    // origin is unreachable, or CORS refused the response. The browser
    // deliberately does not say which, so neither does this.
    return "Wij konden de rekenserver niet bereiken. Controleer uw verbinding en probeer het opnieuw.";
  }
  if (error.status === 400 && attempt === "link") {
    return LINK_IS_NOT_AN_ADVICE;
  }
  if (error.status === 400) {
    const messages = fieldMessages(error);
    return messages.length > 0
      ? `De rekenserver kon dit antwoord niet gebruiken: ${messages.join(" ")}`
      : "De rekenserver kon dit antwoord niet gebruiken. Controleer uw invoer.";
  }
  if (error.status === 404) {
    return LINK_IS_NOT_AN_ADVICE;
  }
  if (error.status === 429) {
    return "Er zijn kort achter elkaar veel berekeningen gedaan vanaf dit adres. Probeer het over een uur opnieuw.";
  }
  if (error.status >= 500) {
    return "De rekenserver had een storing. Probeer het straks opnieuw.";
  }
  return "De rekenserver gaf een antwoord dat wij niet konden lezen.";
}
