import { expect, test, type Locator, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * The five rules from chapter 2 of the spec, one test each, in a real browser.
 *
 * A real browser rather than jsdom, and that distinction has already cost this
 * repository once. Lane B's version of rule one reads the computed font size
 * in jsdom, which loads no stylesheet, so a size that lives in a stylesheet
 * reads back as the empty string on both elements and the comparison passes
 * without having measured anything. Lane B worked around it by setting the two
 * sizes inline. Here the stylesheet is really loaded and the numbers are real
 * pixels, so the check has nothing to fall through to; every assertion below
 * also proves it read something, because a rule that cannot fail is not a rule.
 */

/** The token in the fixture, which is the shape the API issues: 22 url-safe characters. */
const TOKEN = fixture.token;

const ADVICE_PATH = `/advies/${TOKEN}/`;

/** Every route the site has, for the sweep that has to cover all of them. */
const ALL_PATHS = ["/", "/berekenen/", ADVICE_PATH, "/methodologie/"] as const;

/** The advice has arrived once its headline band is on the screen. */
async function openAdvice(page: Page): Promise<void> {
  await page.goto(ADVICE_PATH);
  // Nothing below auto-waits: evaluateAll and innerText read whatever is there
  // when they run, so without this they read the sentence that says the answer
  // is still coming and pass or fail on a race.
  await expect(page.locator('[data-band-kind="percentile"]')).toBeVisible();
}

async function serveFixture(page: Page, body: unknown = fixture): Promise<void> {
  // The API is not running in CI, and it should not need to be: these tests
  // are about what the page does with an answer, not about producing one.
  await page.route("**/api/advice/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(body),
    }),
  );
}

test.beforeEach(async ({ page }) => {
  await serveFixture(page);
});

/** The rendered font size in pixels, as the browser resolved it. */
function fontSize(locator: Locator): Promise<number> {
  return locator.evaluate((el) => Number.parseFloat(getComputedStyle(el).fontSize));
}

test("rule 1: no figure is drawn larger than its own band", async ({ page }) => {
  await openAdvice(page);
  const figures = page.locator("[data-band-kind]");
  const count = await figures.count();
  // The advice carries a headline band, a scenario band per fired rule and
  // four more in the battery block plus its curve. Zero figures would make
  // every loop below vacuous, which is exactly how this rule failed before.
  expect(count, "no banded figure was found on the advice page").toBeGreaterThan(1);

  for (let index = 0; index < count; index += 1) {
    const figure = figures.nth(index);
    const kind = await figure.getAttribute("data-band-kind");
    const middles = figure.locator('[data-role="band-middle"]');
    const ends = figure.locator('[data-role="band-end"]');
    if (kind === "none") {
      // A figure the model put no margin around shows the sentence that says
      // why, and no band at all.
      expect(await middles.count(), "a bandless figure drew a band middle").toBe(0);
      await expect(figure.locator('[data-role="basis-text"]')).not.toBeEmpty();
      continue;
    }
    const middleCount = await middles.count();
    const endCount = await ends.count();
    expect(middleCount, `figure ${index} (${kind}) has no middle`).toBe(1);
    expect(endCount, `figure ${index} (${kind}) has fewer than two ends`).toBeGreaterThan(1);

    const middleSize = await fontSize(middles.first());
    expect(middleSize, `figure ${index} (${kind}) middle has no measurable size`).toBeGreaterThan(0);
    for (let end = 0; end < endCount; end += 1) {
      const endSize = await fontSize(ends.nth(end));
      expect(endSize, `figure ${index} (${kind}) end ${end} has no measurable size`).toBeGreaterThan(
        0,
      );
      expect(
        middleSize,
        `figure ${index} (${kind}): middle ${middleSize}px is larger than end ${endSize}px`,
      ).toBeLessThanOrEqual(endSize);
    }
  }
});

test("rule 2: the confidence level is in the first viewport, on a phone and on a desktop", async ({
  page,
}) => {
  // The first viewport is not one size. 360x640 is a small phone and the one
  // that fails first when anything is added above the band.
  for (const viewport of [
    { width: 360, height: 640 },
    { width: 1280, height: 800 },
  ]) {
    await page.setViewportSize(viewport);
    await openAdvice(page);
    const label = page.getByText(fixture.confidence_label, { exact: true }).first();
    await expect(label).toBeVisible();
    const box = await label.boundingBox();
    expect(box, `${viewport.width}x${viewport.height}: the confidence label has no box`).not.toBeNull();
    const bottom = (box?.y ?? Number.POSITIVE_INFINITY) + (box?.height ?? 0);
    expect(
      bottom,
      `${viewport.width}x${viewport.height}: the confidence label ends at ${bottom}px, below the fold`,
    ).toBeLessThanOrEqual(viewport.height);
  }
});

test("rule 3: all three routes render, in the API's order, including an empty one", async ({
  page,
}) => {
  const withEmpty = {
    ...fixture,
    routes: fixture.routes.map((route, index) => (index === 1 ? { ...route, rules: [] } : route)),
  };
  await serveFixture(page, withEmpty);
  await openAdvice(page);
  const rendered = await page
    .locator("[data-route]")
    .evaluateAll((elements) => elements.map((element) => element.getAttribute("data-route")));
  expect(rendered).toEqual(["SHIFT_BEHAVIOUR", "SMART_CONTROL", "STORAGE"]);
  await expect(page.getByText(/niets meer te halen/i)).toBeVisible();
});

test("rule 4: the page carries no urgency, scarcity or social proof", async ({ page }) => {
  await openAdvice(page);
  const text = (await page.locator("body").innerText()).toLowerCase();
  // Non-vacuous: the advice text really is on the page, so an empty body
  // cannot make this pass.
  expect(text).toContain("saldering");
  for (const pattern of [
    "nog maar",
    "laatste kans",
    "huishoudens gingen",
    "mis niet",
    "actie loopt",
    "aftellen",
    "op is op",
  ]) {
    expect(text, `found "${pattern}" on the advice page`).not.toContain(pattern);
  }
});

test("rule 5: two kinds of call to action, and none of them leaves for a seller", async ({
  page,
}) => {
  await openAdvice(page);
  const hrefs = await page
    .locator("a[href]")
    .evaluateAll((elements) =>
      elements.map((element) => (element as HTMLAnchorElement).getAttribute("href") ?? ""),
    );
  expect(hrefs.length, "no links at all were found, so this proves nothing").toBeGreaterThan(0);
  const external = hrefs.filter((href) => /^https?:\/\//.test(href) && !href.includes("ampeer.nl"));
  expect(external, `external links on the advice page: ${external.join(", ")}`).toEqual([]);

  // The two that must be there, and the shape of the second: a link the
  // visitor keeps rather than a button that sends them somewhere.
  await expect(page.getByRole("link", { name: "Verfijn uw antwoord" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Kopieer deze link" })).toBeVisible();
});

test("every route passes axe", async ({ page }) => {
  for (const path of ALL_PATHS) {
    await page.goto(path);
    // Wait for the advice to have arrived, so axe scans the page a visitor
    // reads rather than the sentence that says it is loading.
    if (path === ADVICE_PATH) await expect(page.locator("[data-band-kind]").first()).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations,
      `${path}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
    ).toEqual([]);
  }
});
