import { ApiError } from "@/lib/api";
import { fieldMessages } from "../_flow/messages";

/**
 * `ApiError`'s own default, from `api.ts`, word for word.
 *
 * `accounts.ts`'s `call()` always passes an explicit third argument
 * (`detail ?? ""`), so this file never receives this text from that path.
 * The check exists anyway, as the second of two layers: the client contract
 * is the real fix, and this is what keeps a future `ApiError` built with the
 * constructor's own default parameters from putting English on a Dutch
 * screen.
 */
const API_ERROR_DEFAULT_MESSAGE = /^advice API returned \d+$/;

/**
 * What to put on the screen when the account API said no.
 *
 * Almost every sentence here comes from the API, and that is the design rather
 * than laziness: the validation messages live in `backend/accounts/nl.py`
 * keyed by an English id, and a second table in the frontend is a second table
 * that can drift from the first. So a 401, a 403 and a 429 are shown literally,
 * word for word, including the one that says how long to wait, which the API
 * knows and this page does not.
 *
 * `fieldMessages` is imported from the question flow rather than written again
 * here, and that is load bearing. It tests `error instanceof ApiError`, so a
 * second class of that name would make it silently return nothing for an error
 * that does have field messages. One class, one reader.
 *
 * The three sentences below are the cases where the API said nothing a reader
 * can use: no answer at all, a fault with no body, and a body this frontend
 * could not read.
 */
export function describeAuthError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    // fetch() rejects rather than resolving when the network is gone, the
    // origin is unreachable, or CORS refused the response. The browser
    // deliberately does not say which, so neither does this.
    return "Wij konden de server niet bereiken. Controleer uw verbinding en probeer het opnieuw.";
  }
  // The API's own sentence, when it sent one. `accounts.ts` leaves the message
  // empty when it did not, and a message equal to ApiError's own default is
  // treated the same way, precisely so this line cannot print that English
  // sentence at a household.
  const hasOwnMessage =
    error.message.length > 0 && !API_ERROR_DEFAULT_MESSAGE.test(error.message);
  if (hasOwnMessage) return error.message;
  const messages = fieldMessages(error);
  if (messages.length > 0) return messages.join(" ");
  if (error.status >= 500) {
    return "De server had een storing. Probeer het straks opnieuw.";
  }
  return "De server gaf een antwoord dat wij niet konden lezen.";
}
