import { expect, test } from "@playwright/test";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * Nothing this site loads may reach a host outside the machine serving it.
 *
 * "Geen Google Analytics" is written down in CLAUDE.md and was, until this
 * file, enforced by nobody. The failure it guards against is not somebody
 * deliberately adding a tracker. It is the ordinary way a third party request
 * arrives in a static site: a font referenced by URL instead of bundled, an
 * icon set pulled from a CDN, a script tag copied out of a tutorial. Each of
 * those hands the visitor's IP address and the page they are reading to a
 * company that has nothing to do with the advice, and each of them looks like
 * an implementation detail in the diff that adds it.
 *
 * Measured on 2026-08-21 before this test existed: the exported site referenced
 * no Google host and served its two fonts as .woff2 files from
 * _next/static/media, which is what `next/font/google` does at build time. That
 * is a property of how the fonts are imported, not a promise, and importing
 * them the other way is a one line change.
 *
 * The assertion is about hosts and not about counts. Requests to 127.0.0.1 and
 * localhost are the site itself and the advice API, and both are the machine
 * the visitor already chose to talk to.
 */

/** Hosts that are this machine. Anything else is somebody else. */
const OWN_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);

const TOKEN = fixture.token;
const ADVICE_PATH = `/advies/${TOKEN}/`;

/**
 * Every page a visitor can reach, plus the one behind a bearer token, plus
 * /voorwaarden/. Nine, and the sweep this file runs is the proof that no
 * page a visitor actually loads asks anything of a third party; a list that
 * left out /privacy/ or /over-ons/ was a sweep that promised that and did
 * not load the two pages that make the promise.
 */
const PAGES = [
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
];

function foreignRequests(page: import("@playwright/test").Page): string[] {
  const foreign: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    // data: and blob: never leave the browser, so they are not a request to
    // anybody. about:blank is the frame Playwright starts on.
    if (/^(data|blob|about):/.test(url)) return;
    let host: string;
    try {
      host = new URL(url).hostname;
    } catch {
      return;
    }
    if (OWN_HOSTS.has(host)) return;
    foreign.push(url);
  });
  return foreign;
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/advice/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(fixture),
    }),
  );
});

for (const path of PAGES) {
  test(`${path} asks nothing of anybody but this machine`, async ({ page }) => {
    const foreign = foreignRequests(page);
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(
      foreign,
      `loading ${path} sent the visitor's IP address to a third party:\n  ${foreign.join("\n  ")}`,
    ).toEqual([]);
  });
}

test("checks exactly the ten pages this list names, not more and not fewer", () => {
  expect(PAGES).toHaveLength(10);
});

test("the fonts are served from this origin rather than fetched from one", async ({
  page,
}) => {
  const foreign = foreignRequests(page);
  const fonts: string[] = [];
  page.on("request", (request) => {
    if (request.resourceType() === "font") fonts.push(request.url());
  });

  await page.goto("/");
  await page.waitForLoadState("networkidle");

  // The count is not asserted. A browser fetches only the faces a page
  // actually uses, so pinning a number here would make this test fail on a
  // heading that changed weight. What matters is where they come from.
  expect(foreign).toEqual([]);
  for (const url of fonts) {
    expect(url, `a font was fetched from somewhere else: ${url}`).toMatch(
      /^https?:\/\/(127\.0\.0\.1|localhost)/,
    );
  }
});
