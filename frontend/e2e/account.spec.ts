import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import consentTexts from "../tests/fixtures/consent-texts.json";
import me from "../tests/fixtures/me-response.json";
import exportPayload from "../tests/fixtures/export-response.json";

/**
 * The account flow against a mocked API.
 *
 * What this proves is the flow. What it cannot prove is the two properties the
 * whole client is built around: `credentials: "include"` and the CSRF header.
 * `page.route` answers whatever it is asked, so a frontend that forgot both
 * would pass every test in this file and work nowhere. That is
 * tests/test_stack_smoke.py's job, over a real connection.
 */

const ORIGIN = "http://127.0.0.1:4173";

/** The headers a credentialed cross-origin answer has to carry, or it is refused. */
const CORS = {
  "access-control-allow-origin": ORIGIN,
  "access-control-allow-credentials": "true",
} as const;

interface Answer {
  readonly status: number;
  readonly body?: unknown;
  /** Set the csrftoken cookie along with this answer, as the real API does. */
  readonly setsCsrf?: boolean;
}

/** One or more answers for a path, used in order, the last one repeating. */
type Plan = Readonly<Record<string, Answer | readonly Answer[]>>;

/**
 * Answer the CORS preflight every POST in this file triggers.
 *
 * Extracted once rather than pasted at each of the four route handlers that
 * need it (`serveAuth` and the three tests that layer a narrower route on
 * top of it), so the four cannot drift from each other.
 */
async function preflight(route: Route): Promise<void> {
  await route.fulfill({
    status: 204,
    headers: {
      ...CORS,
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "content-type, x-csrftoken",
    },
  });
}

/**
 * Serve /api/auth/ from a plan, and count what was asked for.
 *
 * Counted per path, because three of the tests below are about how many
 * requests were made and not about what ended up on the screen. A screen
 * cannot show the difference between one exchange and three.
 *
 * `page.route` receives the CORS preflight `OPTIONS` request as well as the
 * real one: measured against this file's own first two tests, with a
 * temporary log of `request.method()` (see task-10-report.md), the browser
 * sends `OPTIONS` for every POST in this suite (each carries
 * `content-type: application/json`, an `X-CSRFToken` header, or both) and
 * Playwright routes it here rather than letting it reach the unreachable real
 * host. So no `serve.json` rewrite and no `context.route` split were needed:
 * the single `page.route` handler below, answering `OPTIONS` on the spot,
 * is enough.
 */
async function serveAuth(
  page: Page,
  plan: Plan,
): Promise<Readonly<Record<string, number>>> {
  const counts: Record<string, number> = {};
  await page.route("**/api/auth/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "OPTIONS") {
      // The preflight every POST here triggers, because of the content type
      // and the CSRF header. Not counted: it is the browser asking, not the
      // page.
      await preflight(route);
      return;
    }
    const seen = (counts[path] ?? 0) + 1;
    counts[path] = seen;
    const planned = plan[path];
    if (planned === undefined) {
      throw new Error(`no answer planned for ${path}`);
    }
    const answers: readonly Answer[] = Array.isArray(planned)
      ? planned
      : [planned as Answer];
    const answer = answers[Math.min(seen - 1, answers.length - 1)];
    if (answer === undefined) throw new Error(`no answer left for ${path}`);
    await route.fulfill({
      status: answer.status,
      contentType: "application/json",
      headers: {
        ...CORS,
        ...(answer.setsCsrf === true
          ? { "set-cookie": "csrftoken=een-e2e-token; Path=/; SameSite=Strict" }
          : {}),
      },
      body: answer.body === undefined ? "" : JSON.stringify(answer.body),
    });
  });
  return counts;
}

const UNAUTHENTICATED: Answer = {
  status: 401,
  body: { detail: "u bent niet ingelogd" },
  setsCsrf: true,
};

test.describe("the three views", () => {
  test("a 200 on me/ shows the account", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
    });
    await page.goto("/account/");
    await expect(page.getByText(me.email)).toBeVisible();
    await expect(page.getByText(consentTexts.texts.METER_LINK)).toBeVisible();
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("a 401 twice around one exchange shows the sign-in view with the register switch present", async ({
    page,
  }) => {
    const counts = await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": { status: 200, body: null },
    });
    await page.goto("/account/");
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
    // Corrected reading of spec 6: the switch to registration is unconditional
    // in the signed-out state, not something that only appears after a
    // successful exchange.
    await expect(
      page.getByRole("button", { name: "Nog geen account? Account aanmaken" }),
    ).toBeVisible();
    // Counted on requests and not on what is on the screen: the sign-in view
    // looks identical after one exchange and after five, and five is the
    // version that empties the auth-refresh bucket and, once a spent token is
    // offered again, ends every session this account has.
    expect(counts["/api/auth/me/"]).toBe(2);
    expect(counts["/api/auth/refresh/"]).toBe(1);
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("one exchange that works ends on the account", async ({ page }) => {
    const counts = await serveAuth(page, {
      "/api/auth/me/": [UNAUTHENTICATED, { status: 200, body: me }],
      "/api/auth/refresh/": { status: 200, body: null },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
    });
    await page.goto("/account/");
    await expect(page.getByText(me.email)).toBeVisible();
    expect(counts["/api/auth/refresh/"]).toBe(1);
  });

  test("a request that is aborted shows the sign-in view with a message, and the register switch stays present", async ({
    page,
  }) => {
    // Chapter 6.5. Nothing came back, so nothing was said about who is signed
    // in, and no exchange is attempted: there is nothing to react to.
    let refreshes = 0;
    await page.route("**/api/auth/refresh/", (route) => {
      refreshes += 1;
      return route.abort();
    });
    await page.route("**/api/auth/me/", (route) => route.abort());
    await page.goto("/account/");
    // Scoped to main: Next appends its own route announcer with role="alert"
    // to the body, and an unscoped query matches two things.
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "Wij konden de server niet bereiken.",
    );
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Nog geen account? Account aanmaken" }),
    ).toBeVisible();
    expect(refreshes).toBe(0);
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });
});

test.describe("the round the definition of done describes", () => {
  test("register with both consents refused, then see the account", async ({
    page,
  }) => {
    let registerBody: unknown = null;
    await serveAuth(page, {
      "/api/auth/me/": [UNAUTHENTICATED, { status: 200, body: me }],
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/register/": { status: 201 },
    });
    // `route.fallback()`, not `route.continue()`: routes are checked in
    // reverse registration order, and `route.continue()` sends the request
    // straight to the network, bypassing `serveAuth`'s handler registered
    // above rather than falling through to it.
    await page.route("**/api/auth/register/", async (route) => {
      if (route.request().method() === "POST") {
        registerBody = route.request().postDataJSON();
        // Ruling 55: a flow whose POSTs carry an empty CSRF token must fail
        // here, not against the real API, which would answer 403.
        expect(route.request().headers()["x-csrftoken"]).toBeTruthy();
      }
      await route.fallback();
    });
    await page.goto("/account/");
    await page
      .getByRole("button", { name: "Nog geen account? Account aanmaken" })
      .click();
    // The consent texts on screen are byte-identical to the mock's.
    await expect(
      page.getByText(consentTexts.texts.METER_LINK, { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(consentTexts.texts.LEAD_GENERATION, { exact: true }),
    ).toBeVisible();
    // Ruling 50: METER_LINK renders above LEAD_GENERATION.
    const order = await page
      .locator("form")
      .evaluate((form) => form.textContent ?? "");
    const meterIndex = order.indexOf(consentTexts.texts.METER_LINK);
    const leadIndex = order.indexOf(consentTexts.texts.LEAD_GENERATION);
    expect(meterIndex).toBeGreaterThanOrEqual(0);
    expect(leadIndex).toBeGreaterThan(meterIndex);
    // Both boxes are left alone, which the API accepts: article 7(4).
    for (const box of await page.getByRole("checkbox").all()) {
      await expect(box).not.toBeChecked();
    }
    await page.getByLabel("E-mailadres").fill("iemand@voorbeeld.nl");
    await page.getByLabel("Wachtwoord").fill("een-heel-lang-wachtwoord");
    await page.getByRole("button", { name: "Account aanmaken" }).click();
    await expect(page.getByText(me.email)).toBeVisible();
    expect(registerBody).toEqual({
      email: "iemand@voorbeeld.nl",
      password: "een-heel-lang-wachtwoord",
      consent_meter_link: false,
      consent_lead_generation: false,
      text_version: consentTexts.text_version,
    });
  });

  test("the submit button is absent until consent texts resolve", async ({
    page,
  }) => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
    });
    await page.route("**/api/auth/consent-texts/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      await gate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: CORS,
        body: JSON.stringify(consentTexts),
      });
    });
    await page.goto("/account/");
    await page
      .getByRole("button", { name: "Nog geen account? Account aanmaken" })
      .click();
    await expect(
      page.getByRole("button", { name: "Account aanmaken" }),
    ).toHaveCount(0);
    release();
    await expect(
      page.getByRole("button", { name: "Account aanmaken" }),
    ).toBeVisible();
  });

  test("turn one consent on, and the row says so", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/consent/": {
        status: 200,
        body: { kind: "LEAD_GENERATION", granted: true },
      },
    });
    await page.goto("/account/");
    await page.getByRole("button", { name: "Toestemming geven" }).click();
    // `exact: true`: without it this assertion is vacuous. Playwright's
    // `getByText` matches case-insensitively by substring by default, so
    // "Geen toestemming gegeven" (the LEAD_GENERATION row's own unchanged
    // text) already contains "toestemming gegeven" and satisfies a count of
    // 2 whether or not the click did anything at all. Red-proofed: with the
    // mock changed to answer `granted: false`, this assertion (exact) fails
    // on a count of 1, where the unscoped version stayed green at 2.
    await expect(
      page.getByText("Toestemming gegeven", { exact: true }),
    ).toHaveCount(2);
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("consent grant sends the text_version, withdraw sends none", async ({
    page,
  }) => {
    const recorded: Array<{ kind: string } & Record<string, unknown>> = [];
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/consent/": [
        // me-response.json starts with METER_LINK granted, LEAD_GENERATION
        // withdrawn. The row order is METER_LINK, then LEAD_GENERATION, so
        // this test withdraws the first (a WITHDRAWN, no text_version) and
        // grants the second (a GRANTED, with text_version).
        { status: 200, body: { kind: "METER_LINK", granted: false } },
        { status: 200, body: { kind: "LEAD_GENERATION", granted: true } },
      ],
    });
    // `route.fallback()`, not `route.continue()`: see the comment on the same
    // pattern in the registration test above.
    await page.route("**/api/auth/consent/", async (route) => {
      if (route.request().method() === "POST") {
        recorded.push(route.request().postDataJSON() as { kind: string });
        // Ruling 55: a flow whose POSTs carry an empty CSRF token must fail
        // here, not against the real API, which would answer 403.
        expect(route.request().headers()["x-csrftoken"]).toBeTruthy();
      }
      await route.fallback();
    });
    await page.goto("/account/");
    // Scoped to each row's own wrapper (one level above its label paragraph),
    // because after the withdrawal below both rows show a "Toestemming
    // geven" button. Every ancestor further up, including the page shell,
    // contains both rows' text, so filtering divs by that text alone matches
    // more than the one row it was meant to isolate.
    const meterRow = page
      .locator('[id="consent-label-meter_link"]')
      .locator("xpath=..");
    const leadRow = page
      .locator('[id="consent-label-lead_generation"]')
      .locator("xpath=..");
    await meterRow
      .getByRole("button", { name: "Toestemming intrekken" })
      .click();
    // Both consents are now withdrawn: METER_LINK just now, LEAD_GENERATION
    // already in me-response.json. `exact: true`, because Playwright's
    // `getByText` matches case-insensitively by substring by default, and
    // "Geen toestemming gegeven" itself contains "Toestemming gegeven".
    await expect(
      page.getByText("Geen toestemming gegeven", { exact: true }),
    ).toHaveCount(2);
    await leadRow.getByRole("button", { name: "Toestemming geven" }).click();
    await expect(
      page.getByText("Toestemming gegeven", { exact: true }),
    ).toHaveCount(1);
    await expect(
      page.getByText("Geen toestemming gegeven", { exact: true }),
    ).toHaveCount(1);
    expect(recorded).toEqual([
      { kind: "METER_LINK", action: "WITHDRAWN" },
      {
        kind: "LEAD_GENERATION",
        action: "GRANTED",
        text_version: consentTexts.text_version,
      },
    ]);
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("withdraw stays possible when consent texts fail to load, grant does not", async ({
    page,
  }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      // No contract pins a 500 body for this route: the page reacts to the
      // status alone and renders the generic network sentence regardless of
      // what, if anything, the body says, so this body is invented and
      // uncontracted on purpose.
      "/api/auth/consent-texts/": { status: 500, body: { detail: "storing" } },
      "/api/auth/consent/": {
        status: 200,
        body: { kind: "METER_LINK", granted: false },
      },
    });
    await page.goto("/account/");
    // METER_LINK is granted in me-response.json: its toggle withdraws, and
    // withdrawing does not depend on the text having loaded.
    const withdraw = page.getByRole("button", {
      name: "Toestemming intrekken",
    });
    await expect(withdraw).toBeEnabled();
    // LEAD_GENERATION is not granted: its toggle would grant, and granting
    // with no sentence on the screen would be agreeing to something nobody
    // read, so it stays disabled.
    const grant = page.getByRole("button", { name: "Toestemming geven" });
    await expect(grant).toBeDisabled();
  });

  test("export hands the browser a file whose bytes equal the mocked body", async ({
    page,
  }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/export/": { status: 200, body: exportPayload },
    });
    await page.goto("/account/");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: "Gegevens exporteren" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("ampeer-gegevens.json");
    const path = await download.path();
    expect(path).not.toBeNull();
    const fs = await import("node:fs/promises");
    const bytes = await fs.readFile(path as string, "utf-8");
    // This catches alteration and truncation, because the mock already sends
    // compact bytes (`JSON.stringify` with no extra whitespace). It does not
    // catch a `JSON.stringify(JSON.parse(text))` round trip, which would
    // reformat but not corrupt the text: `exportAccount()` resolving to the
    // exact text it received, unparsed, is what `frontend/tests/lib/accounts.test.ts`
    // (Vitest) pins.
    expect(bytes).toBe(JSON.stringify(exportPayload));
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("delete asks for the password and confirms in one line", async ({
    page,
  }) => {
    const counts = await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/delete/": { status: 204 },
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
    });
    await page.goto("/account/");
    const opener = page.getByRole("button", { name: "Account verwijderen" });
    await expect(opener).toHaveAttribute("aria-expanded", "false");
    // Ruling 52, the other half: the informed-consent sentence does not
    // exist before the disclosure is opened. "Visible after opening" alone
    // does not rule out it being there, hidden, from page load.
    const consequence = page.getByText(
      "Hiermee verdwijnen uw e-mailadres, uw twee toestemmingen, uw opgeslagen adviezen en uw sessies.",
      { exact: false },
    );
    await expect(consequence).toHaveCount(0);
    await opener.click();
    await expect(opener).toHaveAttribute("aria-expanded", "true");
    // Ruling 52: the informed-consent sentence is visible after the
    // disclosure opens, and before the confirm button in the DOM order.
    await expect(consequence).toBeVisible();
    const confirmButton = page.getByRole("button", {
      name: "Verwijderen bevestigen",
    });
    const positions = await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll("p, button"));
      const consequenceIndex = all.findIndex((node) =>
        (node.textContent ?? "").includes("Hiermee verdwijnen uw e-mailadres"),
      );
      const buttonIndex = all.findIndex(
        (node) => (node.textContent ?? "").trim() === "Verwijderen bevestigen",
      );
      return { consequenceIndex, buttonIndex };
    });
    expect(positions.consequenceIndex).toBeGreaterThanOrEqual(0);
    expect(positions.buttonIndex).toBeGreaterThan(positions.consequenceIndex);

    await page.getByLabel("Uw wachtwoord").fill("verkeerd-wachtwoord");
    // The real API's own sentence for this: `DeleteView` raises
    // `PermissionDenied(NL["credentials_invalid"])`
    // (backend/accounts/nl.py:43), not an invented one.
    const WRONG_PASSWORD = "e-mailadres of wachtwoord klopt niet";
    await page.route("**/api/auth/delete/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        headers: CORS,
        body: JSON.stringify({ detail: WRONG_PASSWORD }),
      });
    });
    await confirmButton.click();
    // A wrong password leaves the account view. Checked in this order: the
    // error text first, because `toBeVisible()` on the heading below would
    // pass instantly regardless (it never left the screen on this path), so
    // it proves nothing about a wrong password specifically.
    await expect(page.getByText(WRONG_PASSWORD)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Uw gegevens" }),
    ).toBeVisible();

    await page.unroute("**/api/auth/delete/");
    await page.route("**/api/auth/delete/", async (route) => {
      if (route.request().method() === "OPTIONS") {
        await preflight(route);
        return;
      }
      await route.fulfill({ status: 204, headers: CORS });
    });
    await page.getByLabel("Uw wachtwoord").fill("een-heel-lang-wachtwoord");
    await confirmButton.click();
    await expect(page.getByRole("status")).toContainText(
      "Uw account is verwijderd.",
    );
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveText(
      "Uw account is verwijderd.",
    );
    // The 204 is the proof. Nothing is asked afterwards, and there is nothing
    // left to exchange: the RefreshSession rows went with the account.
    expect(counts["/api/auth/me/"]).toBe(1);
    expect(counts["/api/auth/refresh/"]).toBeUndefined();
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });

  test("focus lands on the deletion confirmation, exactly once", async ({
    page,
  }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/delete/": { status: 204 },
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
    });
    await page.goto("/account/");
    await page.getByRole("button", { name: "Account verwijderen" }).click();
    await page.getByLabel("Uw wachtwoord").fill("een-heel-lang-wachtwoord");
    await page.getByRole("button", { name: "Verwijderen bevestigen" }).click();
    const status = page.getByRole("status");
    await expect(status).toContainText("Uw account is verwijderd.");
    await expect(status).toBeFocused();
    await expect(page.getByText("Uw account is verwijderd.")).toHaveCount(1);
  });

  test("the whole round works from the keyboard alone", async ({ page }) => {
    await serveAuth(page, {
      "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      "/api/auth/delete/": { status: 204 },
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
    });
    await page.goto("/account/");
    const opener = page.getByRole("button", { name: "Account verwijderen" });
    await opener.focus();
    await expect(opener).toHaveAttribute("aria-expanded", "false");
    await page.keyboard.press("Enter");
    await expect(opener).toHaveAttribute("aria-expanded", "true");
    // The field that appeared has focus, so typing continues where the reader
    // is looking rather than somewhere above it.
    await expect(page.getByLabel("Uw wachtwoord")).toBeFocused();
    await page.keyboard.type("een-heel-lang-wachtwoord");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText(
      "Uw account is verwijderd.",
    );
  });
});

test.describe("errors are Dutch", () => {
  test("a 429 on login/ shows the API's own Dutch sentence, and no English leaks anywhere", async ({
    page,
  }) => {
    await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
      // NL["throttled"] in backend/accounts/nl.py, %(seconds)d filled in with
      // 3600 (a plausible auth-login Retry-After under its 10/hour scope).
      // tests/test_accounts_api.py::test_the_login_route_answers_a_throttle_in_dutch_with_a_matching_retry_after
      // pins this exact sentence at the API side, formatted with whatever
      // `wait` DRF actually computed, so this mock is the real API shape and
      // not an invented one.
      "/api/auth/login/": {
        status: 429,
        body: {
          detail:
            "te veel verzoeken achter elkaar; probeer het over 3600 seconden opnieuw",
        },
      },
    });
    await page.goto("/account/");
    await page.getByLabel("E-mailadres").fill("iemand@voorbeeld.nl");
    await page.getByLabel("Wachtwoord").fill("een-heel-lang-wachtwoord");
    await page.getByRole("button", { name: "Inloggen" }).click();
    // Scoped to main: Next's own route announcer also carries role="alert".
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "te veel verzoeken achter elkaar; probeer het over 3600 seconden opnieuw",
    );
    await expect(page.locator("body")).not.toContainText("advice API returned");
    await expect(page.locator("body")).not.toContainText("auth API returned");
  });
});

test.describe("keyboard access", () => {
  test("every control in the sign-in view is reachable by Tab, in order, and the view switch moves focus", async ({
    page,
  }) => {
    await serveAuth(page, {
      "/api/auth/me/": UNAUTHENTICATED,
      "/api/auth/refresh/": {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
      "/api/auth/consent-texts/": { status: 200, body: consentTexts },
    });
    await page.goto("/account/");
    await expect(page.getByRole("button", { name: "Inloggen" })).toBeVisible();

    const emailField = page.getByLabel("E-mailadres");
    const passwordField = page.getByLabel("Wachtwoord");
    const signInButton = page.getByRole("button", { name: "Inloggen" });
    const registerSwitch = page.getByRole("button", {
      name: "Nog geen account? Account aanmaken",
    });

    // Tabs forward from wherever the page starts (the header carries a skip
    // link, the logo, the nav links and the theme select before the main
    // content is reached at all) until the given control has focus, and
    // returns the CUMULATIVE number of presses since this walk began (not
    // the number spent on this leg alone), so the four returned numbers are
    // directly comparable: each call resumes tabbing where the previous one
    // left off, reaching a control at all proves it is not unreachable, and
    // a strictly higher cumulative count than the control before it proves
    // the two are in that order, without hard-coding how many controls sit
    // ahead of the form in the header.
    let totalPresses = 0;
    async function tabUntilFocused(
      target: ReturnType<Page["getByRole"]>,
      maxTabs: number,
    ): Promise<number> {
      for (let leg = 1; leg <= maxTabs; leg += 1) {
        await page.keyboard.press("Tab");
        totalPresses += 1;
        if (await target.evaluate((el) => el === document.activeElement)) {
          return totalPresses;
        }
      }
      throw new Error("control was not reached within the tab budget");
    }

    const emailAt = await tabUntilFocused(emailField, 20);
    await expect(emailField).toBeFocused();
    const passwordAt = await tabUntilFocused(passwordField, 5);
    await expect(passwordField).toBeFocused();
    const buttonAt = await tabUntilFocused(signInButton, 5);
    await expect(signInButton).toBeFocused();
    const switchAt = await tabUntilFocused(registerSwitch, 5);
    await expect(registerSwitch).toBeFocused();
    // Each control's cumulative tab count is strictly higher than the one
    // before it: the four are reached in this order and not some other one.
    expect(passwordAt).toBeGreaterThan(emailAt);
    expect(buttonAt).toBeGreaterThan(passwordAt);
    expect(switchAt).toBeGreaterThan(buttonAt);

    // The switch itself moves focus to the new view's heading or group.
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("group", { name: "Account aanmaken" }),
    ).toBeFocused();
  });
});

test.describe("what the page is without JavaScript, and what axe says with it", () => {
  test.describe("no JavaScript", () => {
    test.use({ javaScriptEnabled: false });

    test("/account/ ships one h1 and a paragraph saying what this page is", async ({
      page,
    }) => {
      // Measured on /berekenen/ on 2026-09-02: zero h1 and 32 words of body
      // text, all of it header and footer. Cheaper here, because nobody has to
      // find this page, and still the wrong answer for a visitor on a slow
      // connection.
      await page.goto("/account/");
      const headings = await page.locator("h1").allTextContents();
      expect(headings).toHaveLength(1);
      expect(headings[0]?.trim()).toBe("Uw account");
      const words = (await page.locator("main").innerText())
        .split(/\s+/)
        .filter(Boolean);
      expect(words.length).toBeGreaterThan(30);
    });
  });

  for (const scheme of ["light", "dark"] as const) {
    test(`axe finds nothing on the signed-out view in ${scheme}`, async ({
      page,
    }) => {
      await serveAuth(page, {
        "/api/auth/me/": UNAUTHENTICATED,
        "/api/auth/refresh/": {
          status: 401,
          body: { detail: "uw sessie is verlopen, log opnieuw in" },
        },
      });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/account/");
      await page.evaluate(
        (value) => document.documentElement.setAttribute("data-theme", value),
        scheme,
      );
      await expect(
        page.getByRole("button", { name: "Inloggen" }),
      ).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations,
        `signed out in ${scheme}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
      ).toEqual([]);
    });

    test(`axe finds nothing on the register view in ${scheme}`, async ({
      page,
    }) => {
      await serveAuth(page, {
        "/api/auth/me/": UNAUTHENTICATED,
        "/api/auth/refresh/": {
          status: 401,
          body: { detail: "uw sessie is verlopen, log opnieuw in" },
        },
        "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/account/");
      await page.evaluate(
        (value) => document.documentElement.setAttribute("data-theme", value),
        scheme,
      );
      await page
        .getByRole("button", { name: "Nog geen account? Account aanmaken" })
        .click();
      await expect(
        page.getByRole("button", { name: "Account aanmaken" }),
      ).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations,
        `register in ${scheme}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
      ).toEqual([]);
    });

    test(`axe finds nothing on the account view in ${scheme}`, async ({
      page,
    }) => {
      await serveAuth(page, {
        "/api/auth/me/": { status: 200, body: me, setsCsrf: true },
        "/api/auth/consent-texts/": { status: 200, body: consentTexts },
      });
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/account/");
      await page.evaluate(
        (value) => document.documentElement.setAttribute("data-theme", value),
        scheme,
      );
      await expect(page.getByText(me.email)).toBeVisible();
      // Expanded as well as collapsed: the delete block is the one part of
      // this page that is not in the tree until somebody presses a button.
      await page.getByRole("button", { name: "Account verwijderen" }).click();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
        .analyze();
      expect(
        results.violations,
        `signed in in ${scheme}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
      ).toEqual([]);
    });
  }
});
