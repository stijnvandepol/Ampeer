import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import ZelfVerbruikenPage, { metadata } from "@/app/zelf-verbruiken/page";
import { SITEMAP_ROUTES } from "@/app/_shell/site";

const PATH = "/zelf-verbruiken/";

function headings(container: HTMLElement): string[] {
  return [...container.querySelectorAll("h2")].map(
    (element) => element.textContent ?? "",
  );
}

describe("the page for the route that costs nothing", () => {
  it("has one first-level heading and six sections under it", () => {
    const { container } = render(<ZelfVerbruikenPage />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    // Six, counted rather than approximated: the outline is what a reader
    // scanning navigates by, and "Waar het ophoudt te helpen" is the section
    // that would quietly go first and the one that must not.
    expect(container.querySelectorAll("h2")).toHaveLength(6);
  });

  it("says in the first paragraph that this costs nothing", () => {
    // The answer to the query is that the cheapest step is free and is about
    // timing. A page that explains before it answers has lost the reader.
    const { container } = render(<ZelfVerbruikenPage />);
    const lead = container.querySelector("header p:last-of-type");
    expect(lead?.textContent).toMatch(/kost niets/);
  });

  it("says where this route stops helping", () => {
    // A tip list that only shows the good side is not advice, and this page
    // is the product's own first recommendation, which makes the limits the
    // part most worth protecting.
    const { container } = render(<ZelfVerbruikenPage />);
    expect(
      headings(container).some((text) => text.includes("ophoudt te helpen")),
    ).toBe(true);
  });

  it("sends somebody on to the battery page rather than ending there", () => {
    // The order of the three routes, expressed as navigation: this one first,
    // and the one that costs money only once this one runs out.
    const { container } = render(<ZelfVerbruikenPage />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    // The optional trailing slash for the same reason the calculator link
    // carries one: Next renders the href it was given and the route has one.
    expect(
      hrefs.filter((href) => /^\/thuisbatterij\/?$/.test(href ?? "")),
    ).toHaveLength(1);
  });

  it("puts no euro amount and no kilowatt-hour per appliance on the page", () => {
    // What a dryer uses depends on the dryer, and every euro figure this
    // product knows comes out of a simulation of one household with a band
    // around it. Either here would be a household nobody described.
    const { container } = render(<ZelfVerbruikenPage />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro|\d+\s*kWh/);
  });

  it("offers one way into the questions and no link off this site", () => {
    const { container } = render(<ZelfVerbruikenPage />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(
      hrefs.filter((href) => /^\/berekenen\/?$/.test(href ?? "")),
    ).toHaveLength(1);
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });

  it("marks up exactly the questions it shows, in the same words", () => {
    const { container } = render(<ZelfVerbruikenPage />);
    const scripts = [
      ...container.querySelectorAll('script[type="application/ld+json"]'),
    ].map((element) => JSON.parse(element.textContent ?? "{}"));
    const faq = scripts.find((data) => data["@type"] === "FAQPage");

    expect(faq).toBeDefined();
    expect(faq.mainEntity.map((entry: { name: string }) => entry.name)).toEqual(
      [...container.querySelectorAll("dt")].map(
        (element) => element.textContent ?? "",
      ),
    );
    expect(
      faq.mainEntity.map(
        (entry: { acceptedAnswer: { text: string } }) =>
          entry.acceptedAnswer.text,
      ),
    ).toEqual(
      [...container.querySelectorAll("dd")].map(
        (element) => element.textContent ?? "",
      ),
    );
  });

  it("is in the sitemap, because a page a search should find has to be", () => {
    expect(SITEMAP_ROUTES.map((entry) => entry.path)).toContain(PATH);
  });

  it("canonicalises to itself rather than to the site root", () => {
    expect(metadata.alternates?.canonical).toBe(PATH);
  });

  it("carries a title and a description a search result can show", () => {
    expect(typeof metadata.title).toBe("string");
    expect(String(metadata.description).length).toBeGreaterThan(50);
    expect(String(metadata.description).length).toBeLessThan(200);
  });
});
