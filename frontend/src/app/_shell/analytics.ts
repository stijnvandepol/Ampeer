/**
 * Google Analytics, and the one rule that governs it: nothing loads before yes.
 *
 * Until 2026-09-15 this site measured nothing about a visitor and said so on
 * /privacy/, in the DPIA and in CLAUDE.md. The owner decided on that day to
 * measure with Google Analytics 4, and the three documents changed with the
 * code rather than before or after it. What did not change is the shape of
 * the promise, only its condition: before a visitor has chosen, and after a
 * visitor has said no, a page still asks nothing of anybody but this machine,
 * and frontend/e2e/privacy.spec.ts still reads every request to prove it.
 *
 * WHY THE CHOICE IS ASKED AT ALL. Article 11.7a of the Telecommunicatiewet
 * requires consent for cookies that are not needed for what the visitor
 * asked, and the Autoriteit Persoonsgegevens does not accept Google Analytics
 * 4 as exempt. So there is a question with two equal answers, neither of them
 * pre-selected and neither of them harder than the other, which is what the
 * law means by consent and what the banner in ConsentBanner.tsx does.
 *
 * WHAT IS SENT WHEN YES. gtag.js from googletagmanager.com, configured with
 * Google Signals and ad personalisation off, cookies limited to six months
 * and marked SameSite=Strict, and nothing else: no Tag Manager, no ads. The
 * measurement ID is a build-time constant from NEXT_PUBLIC_GA_MEASUREMENT_ID.
 * Empty means there is no measurement and no banner, which is how every
 * build without the variable behaves, including a developer's.
 *
 * The functions take their storage and document as arguments so that a unit
 * test can hand them a fake and see exactly what each one touches.
 */

/** The measurement ID this build was made with, or "" for no measurement. */
export const GA_MEASUREMENT_ID: string =
  process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ?? "";

/** Where the visitor's answer lives, in their own browser and nowhere else. */
export const CONSENT_STORAGE_KEY = "ampeer-meting";

/** The only host a yes reaches for the script itself. */
export const GTAG_HOST = "https://www.googletagmanager.com";

/** Six months, in seconds: the lifetime of Google's two cookies after a yes. */
export const COOKIE_LIFETIME_SECONDS = 15_552_000;

/**
 * "unknown" is a visitor who has not answered. It is deliberately not the
 * same as "denied": a page renders the question for the first and nothing
 * for the second, and a test that could not tell them apart could not check
 * that no is remembered.
 */
export type Consent = "granted" | "denied" | "unknown";

export function readConsent(storage: Pick<Storage, "getItem">): Consent {
  try {
    const stored = storage.getItem(CONSENT_STORAGE_KEY);
    if (stored === "ja") return "granted";
    if (stored === "nee") return "denied";
  } catch {
    // A browser that refuses storage has a visitor who has not answered.
  }
  return "unknown";
}

export function writeConsent(
  storage: Pick<Storage, "setItem" | "removeItem">,
  consent: Consent,
): void {
  try {
    if (consent === "unknown") storage.removeItem(CONSENT_STORAGE_KEY);
    else
      storage.setItem(
        CONSENT_STORAGE_KEY,
        consent === "granted" ? "ja" : "nee",
      );
  } catch {
    // Nothing to do: the banner will simply ask again next time.
  }
}

export function gtagScriptUrl(measurementId: string): string {
  return `${GTAG_HOST}/gtag/js?id=${encodeURIComponent(measurementId)}`;
}

/** The window gtag.js writes into, typed for exactly what this file touches. */
export type GtagWindow = Window & { dataLayer?: unknown[] };

/**
 * Load gtag.js once and configure it. Idempotent: a second call finds the
 * script already in the document and does nothing, so a component that
 * re-renders cannot send a second page view.
 */
export function loadAnalytics(
  doc: Document,
  win: GtagWindow,
  measurementId: string,
): void {
  if (measurementId === "") return;
  const url = gtagScriptUrl(measurementId);
  if (doc.querySelector(`script[src="${url}"]`) !== null) return;

  Object.assign(win, { [`ga-disable-${measurementId}`]: false });
  win.dataLayer = win.dataLayer ?? [];
  const dataLayer = win.dataLayer;
  // gtag.js reads the `arguments` object its snippet pushes, and an array in
  // its place is silently ignored, so this is the snippet's own function and
  // not a tidier one. The clock read is the "js" command gtag.js asks for; it
  // is read for Google and never for the advice, which is what the semgrep
  // rule that keeps the clock out of this code base is about.
  const gtag: (...args: unknown[]) => void = function () {
    // eslint-disable-next-line prefer-rest-params
    dataLayer.push(arguments);
  };
  // nosemgrep: ampeer-no-reading-the-clock
  gtag("js", new Date());
  gtag("config", measurementId, {
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
    cookie_expires: COOKIE_LIFETIME_SECONDS,
    cookie_flags: "SameSite=Strict;Secure",
  });

  const script = doc.createElement("script");
  script.async = true;
  script.src = url;
  doc.head.appendChild(script);
}

/**
 * A no after a yes. The script may already be running, and there is no way
 * to unload it, but Google documents this flag as the switch that stops it
 * sending anything further.
 */
export function disableAnalytics(win: GtagWindow, measurementId: string): void {
  if (measurementId === "") return;
  Object.assign(win, { [`ga-disable-${measurementId}`]: true });
}
