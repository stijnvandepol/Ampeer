import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * The landing page's figure, in a real browser.
 *
 * The unit tests can say the component asked for two positions and that the
 * stylesheet is told which one to use. Whether a cell actually moves is a fact
 * about a stylesheet jsdom never loads and a box it measures as zero, so the
 * one claim the whole figure rests on can only be checked here.
 */

const STRIP = '[role="img"][aria-label*="voorbeelddag"]';

async function cellLefts(page: Page): Promise<number[]> {
  return page
    .locator(`${STRIP} > span`)
    .evaluateAll((cells) =>
      cells.map((cell) => cell.getBoundingClientRect().left),
    );
}

test.describe("the day figure", () => {
  test("moves every cell out of time order and back", async ({ page }) => {
    await page.goto("/");
    const strip = page.locator(STRIP);
    await expect(strip).toBeVisible();

    const inTime = await cellLefts(page);
    expect(inTime).toHaveLength(96);
    // Non-vacuous: the cells are spread across a strip that has a width, so a
    // collapsed or unstyled figure cannot make the comparison below pass.
    expect(Math.max(...inTime) - Math.min(...inTime)).toBeGreaterThan(200);

    await page.getByRole("button", { name: "Zoals salderen telt" }).click();
    // The transition is 320ms, and reading mid-flight would compare two
    // positions that are both wrong.
    await page.waitForTimeout(600);
    const sorted = await cellLefts(page);

    const moved = sorted.filter(
      (left, at) => Math.abs(left - (inTime[at] ?? left)) > 1,
    );
    // Most of the day changes place. Not all of it: the first cells of the
    // first block were already at the left edge and have nowhere to go.
    expect(moved.length).toBeGreaterThan(60);

    await page.getByRole("button", { name: "Op tijd" }).click();
    await page.waitForTimeout(600);
    const back = await cellLefts(page);
    for (const [at, left] of back.entries()) {
      expect(Math.abs(left - (inTime[at] ?? -1))).toBeLessThan(1);
    }
  });

  test("replaces the clock with the blocks it sorted into", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByText("12:00")).toBeVisible();
    await page.getByRole("button", { name: "Zoals salderen telt" }).click();
    // A clock under cells that are no longer in time is a lie, and it is the
    // smallest form of what this figure argues.
    await expect(page.getByText("12:00")).toHaveCount(0);
    await expect(page.getByText(/^zelf gebruikt \d+$/)).toBeVisible();
  });

  test("paints each cell with the plate's own colours", async ({ page }) => {
    await page.goto("/");
    // Polled rather than read once, because the thing being measured is
    // applied in an effect. DayCounting renders the three floor colours on the
    // server on purpose, so the markup React hydrates against is the markup it
    // produced, and lifts each cell to its own magnitude after paint. A single
    // read right after goto is therefore a race against hydration, and it lost
    // one in CI on 2026-09-02: run 33599078353 reported 3 shades, which is the
    // floor and exactly what the comment below calls the lift not running.
    // The product was fine; the measurement was early.
    await expect
      .poll(
        async () =>
          page
            .locator(`${STRIP} > span`)
            .evaluateAll(
              (cells) =>
                new Set(
                  cells.map((cell) => getComputedStyle(cell).backgroundColor),
                ).size,
            ),
        {
          // Three states, each lifted by its own magnitude. One flat colour
          // would be a strip that lost the day's shape, and three would be the
          // lift not running at all.
          message: "the cells never lifted past the three floor colours",
        },
      )
      .toBeGreaterThan(20);
  });

  test("passes axe in both palettes", async ({ page }) => {
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto("/");
      await expect(page.locator(STRIP)).toBeVisible();
      const results = await new AxeBuilder({ page })
        .include("figure")
        .analyze();
      expect(results.violations, `axe in the ${scheme} palette`).toEqual([]);
      expect(results.passes.length).toBeGreaterThan(0);
    }
  });
});
