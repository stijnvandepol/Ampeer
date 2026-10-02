import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import Zonnepanelen2027Page, { metadata } from "@/app/zonnepanelen-2027/page";
import { SITEMAP_ROUTES } from "@/app/_shell/site";

const PATH = "/zonnepanelen-2027/";

/**
 * The page for "ik heb zonnepanelen, wat moet ik doen". The checklists that
 * answer that question elsewhere end on a contract switch or a battery, and
 * the honest answer is that nothing has to happen before the date. These tests
 * keep the page saying that first and keep the last step taking the hurry out.
 */
describe("the page for what to do before 1 January", () => {
  it("has one first-level heading and five sections under it", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(container.querySelectorAll("h2")).toHaveLength(5);
  });

  it("answers the question in the first paragraph, and the answer is calm", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    const lead = container.querySelector("header p:last-of-type");
    expect(lead?.textContent).toContain("niets dat niet kan wachten");
    expect(lead?.textContent).toContain("blijven lonen");
  });

  it("lists the steps as a sequence, free ones before the battery", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    const steps = [
      ...container.querySelectorAll('section[aria-labelledby="stappen"] ol li'),
    ].map((element) => element.textContent ?? "");
    expect(steps).toHaveLength(5);
    // The battery is last and the step about it is a brake, not a push. A
    // checklist that put the purchase earlier, or phrased it as a task, would
    // be the seller's checklist this page exists to answer.
    const battery = steps.findIndex((step) => /thuisbatterij/i.test(step));
    expect(battery).toBe(steps.length - 1);
    expect(steps[battery]).toMatch(/niet haasten/);
    expect(steps[battery]).toMatch(/geen korting en geen subsidie/);
  });

  it("puts no euro amount on the page, because it has computed none", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro/);
  });

  it("names the date without counting down to it", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    const text = (container.textContent ?? "").toLowerCase();
    for (const pattern of [
      "nog maar",
      "laatste kans",
      "mis niet",
      "nog dagen",
      "wacht niet",
    ]) {
      expect(text).not.toContain(pattern);
    }
  });

  it("offers one way into the questions and links each sibling page once", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    for (const route of [
      "berekenen",
      "einde-saldering",
      "zelf-verbruiken",
      "thuisbatterij",
    ]) {
      expect(
        hrefs.filter((href) => new RegExp(`^/${route}/?$`).test(href ?? "")),
        `/${route}/`,
      ).toHaveLength(1);
    }
  });

  it("links out only from the sources, and there to named sources", () => {
    const { container } = render(<Zonnepanelen2027Page />);
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
    // What the regeling does after 2027 is the government's to say, and the
    // page's three claims about it are quoted from there.
    expect(
      external.some((link) =>
        (link.getAttribute("href") ?? "").includes("rijksoverheid.nl"),
      ),
    ).toBe(true);
  });

  it("dates every source, so a reader knows when it was true", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    const items = [
      ...container.querySelectorAll('section[aria-labelledby="bronnen"] li'),
    ];
    expect(items.length).toBeGreaterThanOrEqual(3);
    for (const item of items) {
      expect(item.textContent).toMatch(/gelezen op \d{1,2} \w+ 20\d\d/);
    }
  });

  it("marks up exactly the questions it shows, in the same words", () => {
    const { container } = render(<Zonnepanelen2027Page />);
    const scripts = [
      ...container.querySelectorAll('script[type="application/ld+json"]'),
    ].map((element) => JSON.parse(element.textContent ?? "{}"));
    const faq = scripts.find((data) => data["@type"] === "FAQPage");
    expect(faq).toBeDefined();
    const entries = faq.mainEntity as {
      name: string;
      acceptedAnswer: { text: string };
    }[];
    const shown = [...container.querySelectorAll("dt")].map(
      (element) => element.textContent ?? "",
    );
    const answered = [...container.querySelectorAll("dd")].map(
      (element) => element.textContent ?? "",
    );
    expect(entries.map((entry) => entry.name)).toEqual(shown);
    expect(entries.map((entry) => entry.acceptedAnswer.text)).toEqual(answered);
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
    expect(String(metadata.title)).toMatch(/zonnepanelen/i);
    expect(String(metadata.title)).toContain("2027");
    expect(String(metadata.description).length).toBeGreaterThan(50);
    expect(String(metadata.description).length).toBeLessThan(200);
  });
});
