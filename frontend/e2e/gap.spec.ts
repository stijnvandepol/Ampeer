import { expect, test, type Page } from "@playwright/test";

/**
 * The price gap, in a real browser.
 *
 * The unit tests read the inline percentages the component writes. Whether
 * those percentages become a band that actually sits lower and taller on the
 * screen is a fact about a stylesheet jsdom never loads and a box it measures
 * as zero, and it is the whole figure.
 */

const PLOT = '[role="img"][aria-label*="kilowattuur waard is"]';

/**
 * Each band's top and height, measured from the top of the plot.
 *
 * Relative and not viewport coordinates. Clicking the control scrolls it into
 * view, so a viewport `top` read before the click and one read after it are
 * distances to two different scroll positions: the first version of this test
 * saw the self-used band "move" 1101 pixels while standing perfectly still.
 */
async function boxes(page: Page): Promise<{ top: number; height: number }[]> {
  return page.locator(PLOT).evaluate((plot) => {
    const origin = plot.getBoundingClientRect().top;
    return [...plot.querySelectorAll('span[style*="height"]')].map((band) => {
      const box = band.getBoundingClientRect();
      return { top: box.top - origin, height: box.height };
    });
  });
}

test.describe("the price gap", () => {
  test("drops the exported band through zero and widens it", async ({
    page,
  }) => {
    await page.goto("/einde-saldering/");
    await expect(page.locator(PLOT)).toBeVisible();

    const before = await boxes(page);
    expect(before).toHaveLength(2);
    // While saldering lasts the two are the same band. Not approximately: the
    // rule subtracts one from the other, so they are one price.
    expect(before[0]?.top).toBeCloseTo(before[1]?.top ?? -1, 1);
    expect(before[0]?.height).toBeCloseTo(before[1]?.height ?? -1, 1);
    // Non-vacuous: the plot has a real height, so a collapsed figure cannot
    // make the comparison below pass.
    expect(before[0]?.height ?? 0).toBeGreaterThan(20);

    await page.getByRole("button", { name: "Vanaf 2027" }).click();
    await page.waitForTimeout(600);
    const after = await boxes(page);

    // The self-used band did not move. The change is not that using your own
    // power became worth more.
    expect(after[0]?.top).toBeCloseTo(before[0]?.top ?? -1, 1);
    // The exported one fell, and got taller, because the price stopped being
    // known. What moves is the uncertainty, which is the only motion the
    // frontend spec allows here.
    expect(after[1]?.top ?? 0).toBeGreaterThan(before[1]?.top ?? 0);
    expect(after[1]?.height ?? 0).toBeGreaterThan(after[0]?.height ?? 0);

    // And it really crosses the dashed rule at zero, which is the fact the
    // whole figure exists to carry. Measured against the rule's own position
    // rather than against a percentage, because the crossing is what a reader
    // sees.
    const zero = await page.locator(PLOT).evaluate((plot) => {
      const origin = plot.getBoundingClientRect().top;
      const rule = plot.querySelector('span[class*="zeroLine"]');
      return (rule?.getBoundingClientRect().top ?? 0) - origin;
    });
    expect(after[1]?.top ?? 0).toBeLessThan(zero);
    expect((after[1]?.top ?? 0) + (after[1]?.height ?? 0)).toBeGreaterThan(
      zero,
    );
  });

  test("keeps the page inside its own width on a narrow phone", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto("/einde-saldering/");
    await expect(page.locator(PLOT)).toBeVisible();
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
