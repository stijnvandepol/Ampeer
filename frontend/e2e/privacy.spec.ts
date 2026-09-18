import { expect, test } from "@playwright/test";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * Nothing this site loads may reach a host outside the machine serving it.
 *
 * "Geen Google Analytics" was written down in CLAUDE.md and was, until this
 * file, enforced by nobody. Since 2026-09-15 the rule reads "not before a
 * yes", and the sweep below is unchanged because it never answers the
 * question; the second half of this file does. The failure it guards against is not somebody
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
  "/thuisbatterij-btw/",
  "/zelf-verbruiken/",
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

/**
 * The second half, since 2026-09-15. The sweep above now proves the floor:
 * before a visitor answers the measurement question, nothing leaves. What it
 * cannot prove on its own is that the question works, because a banner that
 * loaded nothing after yes would pass the sweep too. So this says yes, and
 * expects exactly one new host to appear; and says no, reloads, and expects
 * the answer to have been remembered.
 *
 * The build the e2e run uses carries the measurement ID G-TESTTESTTE, set in
 * ci.yml and scripts/gates.sh, so the banner renders. The script request is
 * intercepted and answered with an empty body: the test is about what the
 * page asks for, not about what Google would answer.
 */
const GTAG = "https://www.googletagmanager.com/gtag/js?id=G-TESTTESTTE";

test.describe("the question about measuring", () => {
  test("is asked with two equal answers, and yes loads exactly Google", async ({
    page,
  }) => {
    await page.route("https://www.googletagmanager.com/**", (route) =>
      route.fulfill({ status: 200, contentType: "text/javascript", body: "" }),
    );
    const foreign = foreignRequests(page);
    await page.goto("/");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button")).toHaveText([
      "Nee, liever niet",
      "Ja, dat mag",
    ]);
    expect(foreign, "something loaded before the answer").toEqual([]);

    await dialog.getByRole("button", { name: "Ja, dat mag" }).click();
    await expect(dialog).toBeHidden();
    await expect.poll(() => foreign).toEqual([GTAG]);
  });

  test("no is remembered across a reload and loads nothing", async ({
    page,
  }) => {
    const foreign = foreignRequests(page);
    await page.goto("/thuisbatterij/");
    await page.getByRole("button", { name: "Nee, liever niet" }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("dialog")).toBeHidden();
    expect(foreign).toEqual([]);
  });

  test("the privacy page offers the way back", async ({ page }) => {
    await page.goto("/privacy/");
    await page.getByRole("button", { name: "Nee, liever niet" }).click();
    await expect(page.getByText("U heeft nee gezegd.")).toBeVisible();
    await page.getByRole("button", { name: "Uw keuze wijzigen" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
  });
});

test("checks exactly the twelve pages this list names, not more and not fewer", () => {
  expect(PAGES).toHaveLength(12);
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
