import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import ThuisbatterijBtwPage, { metadata } from "@/app/thuisbatterij-btw/page";
import { SITEMAP_ROUTES } from "@/app/_shell/site";

const PATH = "/thuisbatterij-btw/";

/**
 * The page Search Console asked for. Four of the first seven impressions
 * were "btw thuisbatterij" in three spellings, landing on a page titled
 * with a different question and clicked by nobody. This one answers the
 * tax question in its first sentence, and these tests keep it doing that.
 */
describe("the page for the btw question", () => {
  it("has one first-level heading and seven sections under it", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(container.querySelectorAll("h2")).toHaveLength(7);
  });

  it("answers with the rate in the title and the first paragraph", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    expect(container.querySelector("h1")?.textContent).toContain("21 procent");
    const lead = container.querySelector("header p:last-of-type");
    expect(lead?.textContent).toContain("21 procent");
    // And says in the same breath that the exception people hope for does
    // not exist: this is the claim that makes the page worth landing on.
    expect(lead?.textContent).toMatch(/ook niet als u hem tegelijk/);
  });

  it("names what happened in Den Haag as a sequence, with the outcome last", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    const steps = [
      ...container.querySelectorAll(
        'section[aria-labelledby="den-haag"] ol li',
      ),
    ].map((element) => element.textContent ?? "");
    expect(steps).toHaveLength(3);
    expect(steps[0]).toContain("2023");
    expect(steps[1]).toContain("10 juni 2026");
    expect(steps[2]).toContain("Prinsjesdag");
    expect(steps[2]).toContain("21 procent");
  });

  it("puts no euro amount on the page, because it has computed none", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro/);
  });

  it("offers one way into the questions and links the sibling page once", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(
      hrefs.filter((href) => /^\/berekenen\/?$/.test(href ?? "")),
    ).toHaveLength(1);
    expect(
      hrefs.filter((href) => /^\/thuisbatterij\/?$/.test(href ?? "")),
    ).toHaveLength(1);
  });

  it("links out only from the sources, and there to named sources", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    const external = [...container.querySelectorAll("a[href]")].filter(
      (element) => /^https?:/.test(element.getAttribute("href") ?? ""),
    );
    expect(external.length).toBeGreaterThanOrEqual(3);
    for (const link of external) {
      expect(link.getAttribute("href")).toMatch(/^https:/);
      expect(
        link.closest("section")?.getAttribute("aria-labelledby"),
        `${link.getAttribute("href")} links out from outside the sources`,
      ).toBe("bronnen");
    }
    // The rule itself comes from the Belastingdienst and nowhere else; a
    // page about tax whose only sources were sellers would be a page about
    // what sellers say.
    expect(
      external.some((link) =>
        (link.getAttribute("href") ?? "").includes("belastingdienst.nl"),
      ),
    ).toBe(true);
  });

  it("dates every source, so a reader knows when it was true", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    const items = [
      ...container.querySelectorAll('section[aria-labelledby="bronnen"] li'),
    ];
    expect(items.length).toBeGreaterThanOrEqual(3);
    for (const item of items) {
      expect(item.textContent).toMatch(/gelezen op \d{1,2} \w+ 20\d\d/);
    }
  });

  it("marks up exactly the questions it shows, in the same words", () => {
    const { container } = render(<ThuisbatterijBtwPage />);
    const scripts = [
      ...container.querySelectorAll('script[type="application/ld+json"]'),
    ].map((element) => JSON.parse(element.textContent ?? "{}"));
    const faq = scripts.find((data) => data["@type"] === "FAQPage");
    expect(faq).toBeDefined();
    const asked = faq.mainEntity.map(
      (entry: { name: string }) => entry.name,
    ) as string[];
    const shown = [...container.querySelectorAll("dt")].map(
      (element) => element.textContent ?? "",
    );
    expect(asked).toEqual(shown);
    const page = scripts.find((data) => data["@type"] === "WebPage");
    expect(page?.dateModified).toMatch(/^20\d\d-\d\d-\d\d$/);
  });

  it("is in the sitemap, because a page a search should find has to be", () => {
    expect(SITEMAP_ROUTES.map((entry) => entry.path)).toContain(PATH);
  });

  it("canonicalises to itself rather than to the site root", () => {
    expect(metadata.alternates?.canonical).toBe(PATH);
  });

  it("carries a title and a description a search result can show", () => {
    expect(String(metadata.title)).toContain("Btw");
    expect(String(metadata.description).length).toBeGreaterThan(50);
    expect(String(metadata.description).length).toBeLessThan(200);
  });
});
