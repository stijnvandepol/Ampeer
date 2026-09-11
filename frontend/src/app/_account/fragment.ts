/**
 * The token off the link in a mail, read once and then gone.
 *
 * A fragment never leaves the browser: nginx does not see it, so the access
 * log does not, Cloudflare does not, and a Referer does not carry it. That is
 * why the link is `/account/#herstel=<token>` rather than a path of its own,
 * and why none of what `/advies/<token>/` needed (a location, a serve.json
 * rule, a log redaction) exists for this.
 *
 * `replaceState` clears it in the same call, so the token does not linger in
 * the history, a tab title or a shared URL. The page keeps the token in its
 * own state and nowhere in the DOM.
 *
 * Exactly 43 url-safe characters, which is `secrets.token_urlsafe(32)` on the
 * Python side; tests/test_frontend_contract.py holds the two numbers
 * together. Anything else reads as no fragment at all, and is left alone.
 */
export type RecoveryFragment = {
  readonly kind: "reset" | "verify";
  readonly token: string;
};

/** `secrets.token_urlsafe(32)`'s length, pinned against the backend by tests/test_frontend_contract.py. */
export const TOKEN_LENGTH = 43;

const PATTERN = new RegExp(
  `^#(herstel|verificatie)=([A-Za-z0-9_-]{${TOKEN_LENGTH}})$`,
);

export function readRecoveryFragment(): RecoveryFragment | null {
  const match = PATTERN.exec(window.location.hash);
  if (match === null) return null;
  window.history.replaceState(
    window.history.state,
    "",
    window.location.pathname + window.location.search,
  );
  return {
    kind: match[1] === "herstel" ? "reset" : "verify",
    // noUncheckedIndexedAccess types every numeric index of a match array as
    // `string | undefined`, regardless of the group being mandatory in the
    // pattern above; this fallback is therefore unreachable whenever `match`
    // is non-null, and exists only to satisfy that type.
    token: match[2] ?? "",
  };
}
