import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * The plate, in a real browser.
 *
 * Everything here needs one. The canvas is scaled by a stylesheet jsdom never
 * loads, the crosshair is positioned in percentages of a box jsdom measures as
 * zero, and the reveal runs on frames jsdom does not paint. A unit test can say
 * the component asked for the right things; only this can say the page a
 * visitor gets is the page that was meant.
 */

const TOKEN = fixture.token;
const ADVICE_PATH = `/advies/${TOKEN}/`;

async function serveFixture(
  page: Page,
  body: unknown = fixture,
): Promise<void> {
  await page.route("**/api/advice/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify(body),
    }),
  );
}

async function openAdvice(page: Page): Promise<void> {
  await page.goto(ADVICE_PATH);
  await expect(page.locator('[data-band-kind="percentile"]')).toBeVisible();
}

test.describe("the year carpet", () => {
  test.beforeEach(async ({ page }) => serveFixture(page));

  test("draws a year a reader can be told about", async ({ page }) => {
    await openAdvice(page);
    const plate = page.locator('[data-role="year-plate"]');
    await expect(plate).toBeVisible();

    // Its own size, not the stylesheet's: 365 columns and 96 rows is the claim
    // this picture makes, and a canvas of any other size is a different claim.
    await expect(plate).toHaveAttribute("width", "365");
    await expect(plate).toHaveAttribute("height", "96");

    const described = await plate.getAttribute("aria-label");
    expect(described).toContain("kwartieren");
    expect(described?.length ?? 0).toBeGreaterThan(120);

    // Non-vacuous: the plate really did draw, rather than sitting as an empty
    // element that every assertion above would still pass on.
    const painted = await plate.evaluate((element) => {
      const canvas = element as HTMLCanvasElement;
      const context = canvas.getContext("2d");
      if (context === null) return 0;
      const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
      const seen = new Set<string>();
      for (let at = 0; at < data.length; at += 4) {
        seen.add(`${data[at]},${data[at + 1]},${data[at + 2]}`);
      }
      return seen.size;
    });
    expect(painted).toBeGreaterThan(20);
  });

  test("says where the reader is, on the plate and in words", async ({
    page,
  }) => {
    await openAdvice(page);
    const plate = page.locator('[data-role="year-plate"]');
    const crosshair = page.locator('[data-role="year-crosshair"]');
    const readout = page.locator('[data-role="year-readout"]');

    await expect(crosshair).toHaveAttribute("data-reading", "false");
    await expect(readout).toContainText("Beweeg over de plaat");

    await plate.hover({ position: { x: 40, y: 30 } });
    await expect(crosshair).toHaveAttribute("data-reading", "true");
    await expect(readout).toContainText("kWh");

    // And by keyboard, which is the half a pointer test never reaches.
    await plate.focus();
    await page.keyboard.press("ArrowRight");
    await expect(readout).toContainText(":");
  });

  test("passes axe in both palettes", async ({ page }) => {
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await openAdvice(page);
      await expect(page.locator('[data-role="year-plate"]')).toBeVisible();
      const results = await new AxeBuilder({ page })
        .include('[data-role="year-carpet"]')
        .analyze();
      expect(results.violations, `axe in the ${scheme} palette`).toEqual([]);
      // Non-vacuous: axe really looked at something.
      expect(results.passes.length).toBeGreaterThan(0);
    }
  });

  test("does not push the page sideways on a narrow phone", async ({
    page,
  }) => {
    // The plate is 365 pixels wide by nature. A grid track defaults to
    // min-content, so without the minmax in the stylesheet this is exactly
    // where the whole page starts scrolling sideways.
    await page.setViewportSize({ width: 360, height: 780 });
    await openAdvice(page);
    await expect(page.locator('[data-role="year-plate"]')).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test("an advice without a year is the page it was before the field existed", async ({
    page,
  }) => {
    const { year: _dropped, ...without } = fixture as Record<string, unknown>;
    await serveFixture(page, without);
    await openAdvice(page);
    await expect(page.locator('[data-role="year-carpet"]')).toHaveCount(0);
    // And the rest of the answer is still all there, so this is an absent
    // picture rather than a broken page.
    await expect(page.locator('[data-band-kind="percentile"]')).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Verfijn uw antwoord" }),
    ).toBeVisible();
  });
});
