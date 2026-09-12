import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import ThuisbatterijPage, { metadata } from "@/app/thuisbatterij/page";
import { SITEMAP_ROUTES } from "@/app/_shell/site";

const PATH = "/thuisbatterij/";

function headings(container: HTMLElement): string[] {
  return [...container.querySelectorAll("h2")].map(
    (element) => element.textContent ?? "",
  );
}

describe("the page a search brings somebody to", () => {
  it("has one first-level heading and seven sections under it", () => {
    const { container } = render(<ThuisbatterijPage />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    // Seven, counted rather than approximated for the reason the sibling page
    // gives: the outline is what a reader scanning navigates by, and a section
    // quietly lost is a claim quietly dropped. "Wanneer hij dat niet doet" is
    // the one that would go first and the one that must not.
    expect(container.querySelectorAll("h2")).toHaveLength(7);
  });

  it("answers the question in the first paragraph", () => {
    // The whole reason this page exists in this shape. Somebody typed a
    // question; a page that introduces itself first has already lost them.
    const { container } = render(<ThuisbatterijPage />);
    const lead = container.querySelector("header p:last-of-type");
    expect(lead?.textContent).toMatch(/\bnee\b|\bniet\b/);
  });

  it("puts the free routes before the battery", () => {
    // The order is the argument, and it is the same order the advice itself
    // uses. A battery credited with savings that shifting a washing machine
    // would also have produced looks better than it is, and that is the
    // easiest way to make this product dishonest.
    const { container } = render(<ThuisbatterijPage />);
    const outline = headings(container);
    const free = outline.findIndex((text) => text.includes("r een batterij"));
    const works = outline.findIndex((text) =>
      text.includes("wel kan uitkomen"),
    );
    expect(free).toBeGreaterThan(-1);
    expect(works).toBeGreaterThan(free);
  });

  it("says when a battery does not pay off, on the page and not in a footnote", () => {
    const { container } = render(<ThuisbatterijPage />);
    expect(headings(container).some((text) => text.includes("niet doet"))).toBe(
      true,
    );
  });

  it("puts no euro amount on the page, because it has computed none", () => {
    // Every euro figure this product knows comes out of a simulation of one
    // household with a band around it. A figure here would be a household
    // nobody described.
    const { container } = render(<ThuisbatterijPage />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro/);
  });

  it("offers one way into the questions and no second call to action", () => {
    const { container } = render(<ThuisbatterijPage />);
    // The same shape the sibling page's test uses, including the optional
    // trailing slash: Next renders the href it was given and the route has one.
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(
      hrefs.filter((href) => /^\/berekenen\/?$/.test(href ?? "")),
    ).toHaveLength(1);
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });

  it("marks up exactly the questions it shows, in the same words", () => {
    // Google's guidelines say not to mark up content a visitor cannot see, and
    // this project has a second reason: an answer that exists only in the
    // markup is an answer nobody proofread.
    const { container } = render(<ThuisbatterijPage />);
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

    const answered = faq.mainEntity.map(
      (entry: { acceptedAnswer: { text: string } }) =>
        entry.acceptedAnswer.text,
    ) as string[];
    const visible = [...container.querySelectorAll("dd")].map(
      (element) => element.textContent ?? "",
    );
    expect(answered).toEqual(visible);
  });

  it("is in the sitemap, because a page a search should find has to be", () => {
    expect(SITEMAP_ROUTES.map((entry) => entry.path)).toContain(PATH);
  });

  it("canonicalises to itself rather than to the site root", () => {
    // A URL instance here would be treated as a base and resolved against the
    // pathname, which is how a route canonicalises itself away.
    expect(metadata.alternates?.canonical).toBe(PATH);
  });

  it("carries a title and a description a search result can show", () => {
    expect(typeof metadata.title).toBe("string");
    expect(String(metadata.description).length).toBeGreaterThan(50);
    expect(String(metadata.description).length).toBeLessThan(200);
  });
});
