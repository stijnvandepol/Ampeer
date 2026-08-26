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

async function serveFixture(
  page: Page,
  body: unknown = fixture,
): Promise<void> {
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
  return locator.evaluate((el) =>
    Number.parseFloat(getComputedStyle(el).fontSize),
  );
}

test("rule 1: no figure is drawn larger than its own band", async ({
  page,
}) => {
  await openAdvice(page);
  const figures = page.locator("[data-band-kind]");
  const count = await figures.count();
  // The advice carries a headline band, a scenario band per fired rule and
  // four more in the battery block plus its curve. Zero figures would make
  // every loop below vacuous, which is exactly how this rule failed before.
  expect(
    count,
    "no banded figure was found on the advice page",
  ).toBeGreaterThan(1);

  for (let index = 0; index < count; index += 1) {
    const figure = figures.nth(index);
    const kind = await figure.getAttribute("data-band-kind");
    const middles = figure.locator('[data-role="band-middle"]');
    const ends = figure.locator('[data-role="band-end"]');
    if (kind === "none") {
      // A figure the model put no margin around shows the sentence that says
      // why, and no band at all.
      expect(
        await middles.count(),
        "a bandless figure drew a band middle",
      ).toBe(0);
      await expect(figure.locator('[data-role="basis-text"]')).not.toBeEmpty();
      continue;
    }
    const middleCount = await middles.count();
    const endCount = await ends.count();
    expect(middleCount, `figure ${index} (${kind}) has no middle`).toBe(1);
    expect(
      endCount,
      `figure ${index} (${kind}) has fewer than two ends`,
    ).toBeGreaterThan(1);

    const middleSize = await fontSize(middles.first());
    expect(
      middleSize,
      `figure ${index} (${kind}) middle has no measurable size`,
    ).toBeGreaterThan(0);
    for (let end = 0; end < endCount; end += 1) {
      const endSize = await fontSize(ends.nth(end));
      expect(
        endSize,
        `figure ${index} (${kind}) end ${end} has no measurable size`,
      ).toBeGreaterThan(0);
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
    const label = page
      .getByText(fixture.confidence_label, { exact: true })
      .first();
    await expect(label).toBeVisible();
    const box = await label.boundingBox();
    expect(
      box,
      `${viewport.width}x${viewport.height}: the confidence label has no box`,
    ).not.toBeNull();
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
    routes: fixture.routes.map((route, index) =>
      index === 1 ? { ...route, rules: [] } : route,
    ),
  };
  await serveFixture(page, withEmpty);
  await openAdvice(page);
  const rendered = await page
    .locator("[data-route]")
    .evaluateAll((elements) =>
      elements.map((element) => element.getAttribute("data-route")),
    );
  expect(rendered).toEqual(["SHIFT_BEHAVIOUR", "SMART_CONTROL", "STORAGE"]);
  await expect(page.getByText(/niets meer te halen/i)).toBeVisible();
});

test("rule 4: the page carries no urgency, scarcity or social proof", async ({
  page,
}) => {
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
    expect(text, `found "${pattern}" on the advice page`).not.toContain(
      pattern,
    );
  }
});

test("rule 5: two kinds of call to action, and none of them leaves for a seller", async ({
  page,
}) => {
  await openAdvice(page);
  const hrefs = await page
    .locator("a[href]")
    .evaluateAll((elements) =>
      elements.map(
        (element) => (element as HTMLAnchorElement).getAttribute("href") ?? "",
      ),
    );
  expect(
    hrefs.length,
    "no links at all were found, so this proves nothing",
  ).toBeGreaterThan(0);
  const external = hrefs.filter(
    (href) => /^https?:\/\//.test(href) && !href.includes("ampeer.nl"),
  );
  expect(
    external,
    `external links on the advice page: ${external.join(", ")}`,
  ).toEqual([]);

  // The two that must be there, and the shape of the second: a link the
  // visitor keeps rather than a button that sends them somewhere.
  await expect(
    page.getByRole("link", { name: "Verfijn uw antwoord" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Kopieer deze link" }),
  ).toBeVisible();
});

test("every route passes axe", async ({ page }) => {
  for (const path of ALL_PATHS) {
    await page.goto(path);
    // Wait for the advice to have arrived, so axe scans the page a visitor
    // reads rather than the sentence that says it is loading.
    if (path === ADVICE_PATH)
      await expect(page.locator("[data-band-kind]").first()).toBeVisible();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations,
      `${path}: ${JSON.stringify(results.violations.map((violation) => violation.id))}`,
    ).toEqual([]);
  }
});

/*
 * ---------------------------------------------------------------------------
 * The four things nothing above could see
 *
 * Each of these was measured on the built site and each sat in a blind spot two
 * correct checks shared. axe's colour-contrast rule is text-only and ignores
 * background-image, and tests/design/contrast.test.ts parses globals.css and
 * never looks at a component, so a gradient carrying meaning was checked by
 * neither. axe cannot see reflow at all. Nothing measured how much of the page
 * one section took, so "free routes first" as DOM order let the paid route take
 * 2.2 times their space. And page-has-heading-one is a best-practice rule, which
 * the tag list above filters out, so the heading check was green because the
 * rule was excluded rather than because the pages passed.
 */

/** WCAG 2.2 relative luminance and contrast, from the definition. */
function channel(eight: number): number {
  const c = eight / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function contrastOf(a: readonly number[], b: readonly number[]): number {
  const luminance = (rgb: readonly number[]) =>
    0.2126 * channel(rgb[0] ?? 0) +
    0.7152 * channel(rgb[1] ?? 0) +
    0.0722 * channel(rgb[2] ?? 0);
  const [x, y] = [luminance(a), luminance(b)];
  const [lighter, darker] = x > y ? [x, y] : [y, x];
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Every column of a rendered element, as the pixels the browser painted.
 *
 * A screenshot rather than a computed style, because the thing being measured is
 * a gradient: getComputedStyle hands back the linear-gradient source text, which
 * says nothing about what any point along it composited to. The decode happens
 * inside the page, through an Image and a canvas, so this needs no image library
 * and no dependency that a required check would then rest on.
 *
 * Every column rather than three, because the marker is drawn on top of the band
 * and a sample that happens to land on it measures solid ink and passes. A sweep
 * cannot be fooled that way: the worst column is the worst column.
 */
async function sampleColumns(
  page: Page,
  clip: { x: number; y: number; width: number; height: number },
): Promise<number[][]> {
  const shot = await page.screenshot({ clip });
  return page.evaluate(async (encoded: string) => {
    const image = new Image();
    image.src = `data:image/png;base64,${encoded}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext("2d");
    if (context === null) throw new Error("no 2d context");
    context.drawImage(image, 0, 0);
    const row = Math.floor(image.height / 2);
    const columns: number[][] = [];
    for (let x = 0; x < image.width; x += 1) {
      const pixel = context.getImageData(x, row, 1, 1).data;
      columns.push([pixel[0] ?? 0, pixel[1] ?? 0, pixel[2] ?? 0]);
    }
    return columns;
  }, shot.toString("base64"));
}

test("the band's colour never says less than its type sizes say", async ({
  page,
}) => {
  // Measured before this existed, on the built page: the gradient faded to 30%
  // alpha at both ends and those ends composited to about 2:1 against the page
  // in both themes, below the 3:1 that SC 1.4.11 asks of a graphic that carries
  // meaning, while the middle sat at 6.33:1 light and 10.25:1 dark with a 3px
  // solid marker on it. Type sizes obeyed rule 1, 28px at the ends against 20px
  // in the middle, and colour undid it: the eye landed on the centre and the
  // band faded out towards its own answer.
  for (const theme of ["light", "dark"] as const) {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(ADVICE_PATH);
    await page.evaluate(
      (chosen) => document.documentElement.setAttribute("data-theme", chosen),
      theme,
    );
    await expect(page.locator('[data-band-kind="percentile"]')).toBeVisible();
    // The fill animates to its width; measuring before it settles measures a
    // sliver of a rounded corner rather than the band.
    await page.waitForTimeout(600);

    const box = await page.locator('[data-role="band-fill"]').boundingBox();
    expect(box, `${theme}: the band has no box`).not.toBeNull();
    expect(
      box?.width ?? 0,
      `${theme}: the band is too narrow to sample`,
    ).toBeGreaterThan(20);

    const columns = await sampleColumns(page, {
      x: box?.x ?? 0,
      y: box?.y ?? 0,
      width: box?.width ?? 0,
      height: box?.height ?? 0,
    });
    const background = await page.evaluate(() => {
      const found =
        getComputedStyle(document.body).backgroundColor.match(/[0-9]+/g) ?? [];
      return found.slice(0, 3).map(Number);
    });
    expect(
      background,
      `${theme}: no page background to measure against`,
    ).toHaveLength(3);
    expect(columns.length, `${theme}: nothing was sampled`).toBeGreaterThan(20);

    // The rounded cap is antialiased against whatever is behind it, so the
    // outermost pixel of each end is the shape's edge rather than its colour.
    const inside = columns.slice(2, -2);
    const ratios = inside.map((pixel) => contrastOf(pixel, background));
    const worst = Math.min(...ratios);
    const at = ratios.indexOf(worst);
    expect(
      worst,
      `${theme}: the band is ${worst.toFixed(2)}:1 against the page at column ${at} of ` +
        `${ratios.length}, below SC 1.4.11's 3:1`,
    ).toBeGreaterThanOrEqual(3);

    // And in the direction rule 1 asks for: the ends are the answer, so they may
    // not be the faintest part of the figure. The median rather than the centre
    // column, because the marker is drawn on top of the band and a sample that
    // lands on it measures solid ink.
    const sorted = [...ratios].sort((one, two) => one - two);
    const median = sorted[Math.floor(sorted.length / 2)] ?? 0;
    const ends = Math.min(ratios[0] ?? 0, ratios[ratios.length - 1] ?? 0);
    expect(
      ends,
      `${theme}: the ends are ${ends.toFixed(2)}:1 against a median of ${median.toFixed(2)}:1, ` +
        `so the band fades out towards its own answer`,
    ).toBeGreaterThanOrEqual(median * 0.95);
  }
});

test("the width of a band is the width of its band", async ({ page }) => {
  // Two figures whose spreads differ by a factor of six were drawn as two
  // identical 416px objects, and the five capacities of the battery curve were
  // the same picture five times. The only visual variable was the marker, which
  // encodes skew, so a sighted reader learned the uncertainty by reading the
  // numbers: the one thing this page was built not to require.
  await page.setViewportSize({ width: 1280, height: 900 });
  await openAdvice(page);
  await page.locator("[data-role='battery-detail']").click();
  await page.waitForTimeout(600);

  const drawn = await page.locator("[data-band-span]").evaluateAll((figures) =>
    figures.map((figure) => {
      const axis = figure.querySelector(
        "[data-band-part='axis']",
      ) as HTMLElement;
      const band = figure.querySelector(
        "[data-band-part='band']",
      ) as HTMLElement;
      return {
        span: Number(figure.getAttribute("data-band-span")),
        width: band.getBoundingClientRect().width,
        axis: axis.getBoundingClientRect().width,
      };
    }),
  );
  expect(drawn.length, "no banded figure was found").toBeGreaterThan(1);

  for (const figure of drawn) {
    expect(
      figure.axis,
      "a band was drawn on an axis of no width",
    ).toBeGreaterThan(0);
    expect(
      Math.abs(figure.width - figure.span * figure.axis),
      `a band declaring a span of ${figure.span} was drawn ${figure.width}px wide on a ` +
        `${figure.axis}px axis`,
    ).toBeLessThanOrEqual(1.5);
  }

  // And the encoding actually varies. If every figure came out the same width
  // this test would pass on the very layout it exists to forbid.
  const widths = new Set(drawn.map((figure) => Math.round(figure.width)));
  expect(
    widths.size,
    "every band on the page is still the same width",
  ).toBeGreaterThan(2);
});

test("no route pushes the page sideways at 360px or at 400% zoom", async ({
  page,
}) => {
  // 360x640 is the most common Android viewport in the Netherlands, and 320 CSS
  // pixels is what 1280 becomes at the 400% zoom SC 1.4.10 asks about. Measured
  // before the fix: scrollWidth 366 against clientWidth 360 on all four routes,
  // and 365 against 320, every time because of one nav that could not wrap. axe
  // cannot see reflow at all, which is why this is here and not in the sweep
  // above.
  for (const viewport of [
    { width: 360, height: 640 },
    { width: 320, height: 256 },
  ]) {
    await page.setViewportSize(viewport);
    for (const path of ALL_PATHS) {
      await page.goto(path);
      if (path === ADVICE_PATH)
        await expect(page.locator("[data-band-kind]").first()).toBeVisible();
      const overflow = await page.evaluate(() => {
        const root = document.documentElement;
        const offenders: string[] = [];
        for (const element of document.querySelectorAll("body *")) {
          const box = element.getBoundingClientRect();
          // Anything inside its own scroller is allowed to be wider than the
          // page: that is what the scroller is for.
          const scroller = element.closest("[tabindex='0'][role='group']");
          if (scroller === null && box.right > root.clientWidth + 1) {
            offenders.push(
              `${element.tagName}.${element.className}`.slice(0, 80),
            );
          }
        }
        return {
          scrollWidth: root.scrollWidth,
          clientWidth: root.clientWidth,
          offenders,
        };
      });
      expect(
        overflow.scrollWidth,
        `${path} at ${viewport.width}px scrolls sideways: ${overflow.scrollWidth} against ` +
          `${overflow.clientWidth}, because of ${overflow.offenders.slice(0, 3).join(", ")}`,
      ).toBeLessThanOrEqual(overflow.clientWidth);
    }
  }
});

test("the paid route never outweighs the free ones the model put first", async ({
  page,
}) => {
  // The fixture's verdict is one the model does not recommend on. Measured at
  // 1280x900 before this: headline 345px, the two free routes 313px each, the
  // storage route 219px, and the battery block 1365px, which is 38.5% of the
  // page and 2.2x the free routes together, with a five-capacity table of what
  // each size earns inside it. It passed all five rules above, because "free
  // routes first" was DOM order and order is the weakest form of precedence
  // there is.
  //
  // On the property rather than on one id, for the reason
  // tests/app/AdviesPage.test.tsx gives beside the same guard: the fixture
  // household moved from BATTERY_DOES_NOT_PAY_BACK to BATTERY_DEPENDS_ON_PRICE
  // on 2026-08-26 without the page's behaviour moving at all.
  expect(["BATTERY_DOES_NOT_PAY_BACK", "BATTERY_DEPENDS_ON_PRICE"]).toContain(
    fixture.battery.verdict,
  );
  await page.setViewportSize({ width: 1280, height: 900 });
  await openAdvice(page);

  const height = async (selector: string) => {
    const box = await page.locator(selector).boundingBox();
    expect(box, `${selector} has no box`).not.toBeNull();
    return box?.height ?? 0;
  };
  const free =
    (await height("[data-route='SHIFT_BEHAVIOUR']")) +
    (await height("[data-route='SMART_CONTROL']"));
  const battery = await height("section[aria-labelledby='batterij']");
  expect(free, "the free routes drew nothing").toBeGreaterThan(0);
  expect(
    battery,
    `the battery block is ${Math.round(battery)}px against ${Math.round(free)}px of free routes, ` +
      `on a household the model told not to buy one`,
  ).toBeLessThanOrEqual(free);

  // Nothing was hidden: it is one click away and it opens.
  await page.locator("[data-role='battery-detail']").click();
  await expect(page.locator("[data-role='battery-detail']")).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  expect(await height("section[aria-labelledby='batterij']")).toBeGreaterThan(
    battery,
  );
});

test("every route has exactly one first-level heading", async ({ page }) => {
  // page-has-heading-one is one of axe's best-practice rules, and the tag list
  // this project passes to AxeBuilder is wcag2a, wcag2aa and wcag22aa, so the
  // rule was filtered out and /berekenen/ went green with no h1 at all. A gate
  // that is green because the rule was excluded is not a gate.
  for (const path of ALL_PATHS) {
    await page.goto(path);
    if (path === ADVICE_PATH)
      await expect(page.locator("[data-band-kind]").first()).toBeVisible();
    const headings = await page.locator("h1").allTextContents();
    expect(
      headings,
      `${path} has ${headings.length} first-level headings`,
    ).toHaveLength(1);
    expect(
      headings[0]?.trim().length ?? 0,
      `${path}: its h1 is empty`,
    ).toBeGreaterThan(0);
  }
});

test("the four routes do not all answer to the same title", async ({
  page,
}) => {
  // /, /berekenen/ and /advies/<token>/ all carried <title>Ampeer</title>, so
  // three of the four were indistinguishable in a tab strip, in a history list,
  // and to a screen reader announcing the page on arrival.
  const titles: string[] = [];
  for (const path of ALL_PATHS) {
    await page.goto(path);
    titles.push(await page.title());
  }
  expect(new Set(titles).size, `titles: ${titles.join(" / ")}`).toBe(
    titles.length,
  );
});
