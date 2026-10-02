import { expect, test } from "@playwright/test";

/**
 * The numbered lists on the content pages, measured in a browser.
 *
 * Most pages render a step as two spans, a name and a text, with no space
 * between them. Until 2026-10-01 both were inline, so on a phone a step read
 * "Zoek op hoeveel stroom u teruglevertOp uw jaarafrekening": one line, the
 * margin between them never applied, and a screen reader joined the two words
 * as well. jsdom loads no stylesheet and cannot see this, so it is measured
 * here, in pixels. /einde-saldering/ uses a heading and a paragraph, which
 * were always blocks; it is swept anyway, so a change to spans there is
 * caught, and so is the 404 page, which uses the same list for its way back.
 */
const PAGES = [
  "/einde-saldering/",
  "/zonnepanelen-2027/",
  "/thuisbatterij/",
  "/thuisbatterij-btw/",
  "/zelf-verbruiken/",
  "/deze-pagina-bestaat-niet/",
] as const;

for (const path of PAGES) {
  test(`${path} puts every step's text on a line below its name`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(path);
    const gaps = await page
      .locator('li > [class*="routeName"] + [class*="routeText"]')
      .evaluateAll((texts) =>
        texts.map((text) => {
          const name = text.previousElementSibling as Element;
          return (
            text.getBoundingClientRect().top -
            name.getBoundingClientRect().bottom
          );
        }),
      );
    // Proves the selector found something: a list of zero gaps passes every
    // comparison below and measures nothing.
    expect(gaps.length).toBeGreaterThan(0);
    for (const gap of gaps) {
      expect(gap).toBeGreaterThanOrEqual(0);
    }
  });
}
