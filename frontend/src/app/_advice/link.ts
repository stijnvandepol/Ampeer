/**
 * The shareable link, in both directions.
 *
 * There is one page at /advies/ and the token lives in the path after it, so
 * every advice is one built HTML file and one URL a visitor can send to
 * somebody else. `next.config.ts` sets trailingSlash, so the path a browser
 * ends up on is /advies/<token>/ with the slash.
 *
 * CONSEQUENCE FOR DEELPROJECT 2, and it is one line of configuration: because
 * the site is statically exported, /advies/<token>/ is not a file on disk. The
 * reverse proxy has to serve /advies/index.html for anything under /advies/.
 * Without that rule the shareable link 404s, which is the failure mode where
 * everything works for the person who computed the advice and nothing works
 * for the person they sent it to. `frontend/serve.json` is the same rule for
 * the static server the end-to-end tests run against, so the tests exercise
 * the arrangement production needs rather than a friendlier one.
 */

/** The one route that renders an advice. */
export const ADVICE_BASE_PATH = "/advies";

/** Where a fresh token should send the browser. */
export function advicePath(token: string): string {
  return `${ADVICE_BASE_PATH}/${token}/`;
}

/**
 * The token out of a pathname, or null when there is none.
 *
 * No validation of the shape here: `getAdvice` owns that, and owning it twice
 * is how two definitions of a token end up disagreeing. This only answers
 * which part of the path is meant to be one.
 */
export function tokenFromPath(pathname: string): string | null {
  const segments = pathname.split("/").filter((segment) => segment.length > 0);
  const last = segments[segments.length - 1];
  if (last === undefined || last === "advies") return null;
  return last;
}
