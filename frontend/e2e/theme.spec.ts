import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../tests/fixtures/advice-response.json";
import { ADVICE_PATH, ALL_PATHS } from "./routes";

/**
 * Light and dark, with the explicit choice that has to beat the system.
 *
 * `globals.css` carries four complete palettes and nothing was setting the
 * attribute that selects two of them, so until this page was assembled the
 * explicit choice existed in the stylesheet and nowhere else. The interesting
 * question is not whether a select box changes an attribute; it is whether the
 * choice is on the page before the first paint, and whether the dark palette
 * has ever been looked at by anything that measures contrast. Both are only
 * answerable in a real browser.
 */

async function serveFixture(page: Page): Promise<void> {
  await page.route("**/api/advice/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(fixture),
    }),
  );
  // The account route answers 401 to a visitor who is not signed in, which is
  // the state the dark palette has to be measured in here. Without this the
  // page would fall into the "nothing came back" state, which is a different
  // screen and one that depends on whether a server happens to be running.
  //
  // The two CORS headers are not decoration. The account client sends
  // `credentials: "include"`, and a browser refuses a credentialed response
  // whose allow-origin is `*`, so the wildcard used above for the advice API
  // would turn every one of these into a network error.
  await page.route("**/api/auth/me/", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": "http://127.0.0.1:4173",
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify({ detail: "u bent niet ingelogd" }),
    }),
  );
  // `loadSession` spends its one exchange on a 401: one `refresh/`, then one
  // more `me/`. Left unmocked, that POST would be an unmocked request to a
  // server this build does not run, which is a network error and not the
  // signed-out state this test means to measure.
  await page.route("**/api/auth/refresh/", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": "http://127.0.0.1:4173",
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify({ detail: "u bent niet ingelogd" }),
    }),
  );
}

test("the choice is applied before anything else on the page runs", async ({
  page,
}) => {
  // Written straight into storage, so the first document this browser loads is
  // already one where the choice and the system preference disagree. That is
  // the case the inline script exists for and the only one where a flash is
  // visible.
  await page.goto("/");
  await page.evaluate(() =>
    window.localStorage.setItem("ampeer-thema", "dark"),
  );

  await page.goto("/methodologie/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  // Before the first paint, argued from the document rather than from a
  // stopwatch. The script is inline and carries neither async nor defer, so
  // the parser stops and runs it where it stands; it stands before every
  // element that renders anything; and every script ahead of it is async or
  // noModule, so none of them can have run first either. Together that is the
  // whole claim: the attribute is on the root element before there is
  // anything on screen to be wrong about.
  const order = await page.evaluate(() => {
    const nodes = [
      ...document.querySelectorAll("script, header, main, footer"),
    ];
    const isTheme = (node: Element) =>
      node.tagName === "SCRIPT" &&
      (node.textContent ?? "").includes("ampeer-thema");
    const inline = nodes.findIndex(isTheme);
    const themeScript = nodes[inline] as HTMLScriptElement | undefined;
    const blockingBefore = nodes
      .slice(0, Math.max(inline, 0))
      .filter((node): node is HTMLScriptElement => node.tagName === "SCRIPT")
      .filter(
        (script) => !script.async && !script.defer && !script.noModule,
      ).length;
    return {
      inline,
      firstVisible: nodes.findIndex((node) => node.tagName !== "SCRIPT"),
      blockingBefore,
      deferred: themeScript?.async === true || themeScript?.defer === true,
    };
  });
  expect(
    order.inline,
    "the theme script is not in the document at all",
  ).toBeGreaterThanOrEqual(0);
  expect(
    order.firstVisible,
    "no header, main or footer was found",
  ).toBeGreaterThanOrEqual(0);
  expect(order.inline).toBeLessThan(order.firstVisible);
  expect(
    order.blockingBefore,
    "a blocking script runs before the theme is decided",
  ).toBe(0);
  expect(
    order.deferred,
    "the theme script is deferred, so it cannot beat the paint",
  ).toBe(false);
});

test("the visitor can pick a palette, and it survives the next page", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Thema").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.goto("/berekenen/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.getByLabel("Thema").selectOption("system");
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
  await page.goto("/");
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", /.*/);
});

test("every route passes axe in the dark palette too", async ({ page }) => {
  // The palette a contrast test cannot see. `tests/design/contrast.test.ts`
  // parses globals.css, so it checks the tokens and not what any component
  // actually resolved: a rule reaching for a variable that does not exist
  // falls through to a hard-coded fallback, and a light-theme fallback on a
  // dark background is a real failure that no token can reveal. This is what
  // looks at the pixels.
  await serveFixture(page);
  await page.emulateMedia({ colorScheme: "dark" });
  // Without this line "the loop walked every path" is an assumption: nothing
  // checks how many paths sit in ALL_PATHS. Nine since 2026-09-11, when this
  // sweep and the light one in rules.spec.ts were given the same list. Six
  // stood here before that, and the three the dark palette had never been
  // looked at on were /einde-saldering/, /over-ons/ and /privacy/.
  expect(ALL_PATHS).toHaveLength(12);
  for (const path of ALL_PATHS) {
    await page.goto(path);
    await page.evaluate(() =>
      document.documentElement.setAttribute("data-theme", "dark"),
    );
    if (path === ADVICE_PATH)
      await expect(page.locator("[data-band-kind]").first()).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations,
      `${path} in dark: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
    ).toEqual([]);
  }
});
