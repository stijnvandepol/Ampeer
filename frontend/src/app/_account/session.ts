import { ApiError } from "@/lib/api";
import { getMe, refresh, type Me } from "@/lib/accounts";
import { describeAuthError } from "./messages";

/**
 * Which of the three views is on the screen, and why.
 *
 * There is no flag in localStorage and none in sessionStorage saying somebody
 * is signed in. The cookies are httpOnly on purpose, so the frontend cannot
 * know: `GET me/` is the only source of this, on every load, and a local flag
 * that said "signed in" while the access token had expired would be a screen
 * promising something the next call contradicts.
 */
export type AccountState =
  | { readonly status: "loading" }
  | { readonly status: "signed_out"; readonly notice: string | null }
  | { readonly status: "signed_in"; readonly me: Me };

export const LOADING: AccountState = { status: "loading" };

export function signedOut(notice: string | null): AccountState {
  return { status: "signed_out", notice };
}

/**
 * One `me/`, and what its answer means.
 *
 * Null is reserved for the single outcome that earns the exchange below: a
 * 401. Everything else, a request that never arrived included, is a state of
 * its own and never a reason to spend a refresh token.
 */
async function askWhoIsSignedIn(): Promise<AccountState | null> {
  try {
    return { status: "signed_in", me: await getMe() };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    return signedOut(describeAuthError(error));
  }
}

/**
 * The one exception to "no retry", and it is not a retry.
 *
 * The access token lives fifteen minutes and the refresh token fourteen days,
 * so without this exchange a fourteen day token is worthless from minute
 * sixteen. The second request also asks a different question from the first,
 * because a different credential sits under it.
 *
 * Why a second 401 is the end rather than a third attempt: after a successful
 * rotation the server has just set a new access cookie, so a 401 on it means
 * that cookie is not being accepted, which is a fault in the configuration or
 * the server and not something another attempt repairs. Going on would rotate
 * once per page load, which empties the auth-refresh bucket of 60 an hour and,
 * the moment an already exchanged token is offered again, revokes every
 * session this account has. A client that keeps trying signs the visitor out
 * everywhere.
 *
 * This is the only place the exchange exists. `accounts.ts` has no retry on
 * any status at all.
 */
export async function loadSession(): Promise<AccountState> {
  const first = await askWhoIsSignedIn();
  if (first !== null) return first;
  try {
    await refresh();
  } catch {
    // No sentence above the sign-in form. "Your session expired" for somebody
    // who never had one is a message about something that did not happen.
    return signedOut(null);
  }
  return (await askWhoIsSignedIn()) ?? signedOut(null);
}
