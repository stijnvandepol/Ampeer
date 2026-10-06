import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import EindeSalderingPage from "@/app/einde-saldering/page";
import { metadata } from "@/app/einde-saldering/page";
import BerekenenLayout, {
  metadata as berekenenMetadata,
} from "@/app/berekenen/layout";
import { PageJsonLd, SiteJsonLd } from "@/app/_shell/JsonLd";
import { SITEMAP_ROUTES, SITE_ORIGIN } from "@/app/_shell/site";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";

describe("the product page", () => {
  it("has exactly one first-level heading and nine sections under it", () => {
    const { container } = render(<EindeSalderingPage />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    // Nine, and the count is not decoration: the outline is what a reader
    // scanning the page navigates by, and a section quietly lost is a claim
    // quietly dropped. "Wat wij niet weten" is the one most likely to go.
    expect(container.querySelectorAll("h2")).toHaveLength(9);
  });

  it("names what it does not know before it names what it does not sell", () => {
    // The order is the argument. Listing your blind spots before your virtues
    // is the thing this page says it does, and doing it the other way round
    // makes the honesty a footnote to the pitch.
    const { container } = render(<EindeSalderingPage />);
    const headings = [...container.querySelectorAll("h2")].map(
      (element) => element.textContent ?? "",
    );
    const unknown = headings.findIndex((text) => text.includes("niet weten"));
    const notSell = headings.findIndex((text) => text.includes("niet doen"));
    expect(unknown).toBeGreaterThan(-1);
    expect(notSell).toBeGreaterThan(unknown);
  });

  it("puts no euro amount on the page, because it has computed none", () => {
    // Same rule as the landing page. The figure's prices are per kilowatt hour
    // and are the tariff landscape; a euro total here would be a number nobody
    // computed for the person reading it.
    const { container } = render(<EindeSalderingPage />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro/);
  });

  it("offers the way into the questions twice and no third call to action", () => {
    // Two is the ceiling. The two calls to action the spec allows both refer to
    // something that does not exist yet on this page: an answer to refine and a
    // link to keep. A third entry, a sticky bar or a mid-scroll repeat is how a
    // way in becomes a funnel.
    const { container } = render(<EindeSalderingPage />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(
      hrefs.filter((href) => /^\/berekenen\/?$/.test(href ?? "")),
    ).toHaveLength(2);
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
    expect(screen.queryByText(/Verfijn uw antwoord/)).toBeNull();
    expect(screen.queryByText(/Bewaar deze link/i)).toBeNull();
  });

  it("carries no countdown and no scarcity", () => {
    const { container } = render(<EindeSalderingPage />);
    const text = (container.textContent ?? "").toLowerCase();
    for (const pattern of [
      "nog maar",
      "laatste kans",
      "mis niet",
      "aftellen",
    ]) {
      expect(text).not.toContain(pattern);
    }
  });

  it("says the 2029 tariff is a proposal it does not yet compute", () => {
    // Without both halves this section is a promise. It is the one place on the
    // site that describes something the engine cannot do.
    const { container } = render(<EindeSalderingPage />);
    const text = container.textContent ?? "";
    expect(text).toContain("nog geen regel");
    expect(text).toContain("rekent het nog niet door");
  });

  it("names itself as its own canonical, as a string", () => {
    // A URL instance here would be treated as a base and re-resolved against
    // the pathname, which canonicalises this page to the site root.
    expect(metadata.alternates?.canonical).toBe("/einde-saldering/");
    expect(typeof metadata.alternates?.canonical).toBe("string");
    // And no openGraph of its own: metadata merging is shallow, so any part of
    // it here would drop the root layout's siteName, locale and type.
    expect(metadata.openGraph).toBeUndefined();
  });
});

describe("the crawler files", () => {
  it("keeps the plain text payloads out of an index", () => {
    // out/ ships React Server Component payloads beside every page and nginx
    // serves them as text/plain: measured on 2026-08-31, /index.txt answers
    // 200. There is no meta tag you can put in a .txt file, so Disallow is the
    // only control that reaches them.
    const rules = robots().rules;
    const disallow = Array.isArray(rules) ? [] : (rules.disallow ?? []);
    expect(disallow).toContain("/*.txt$");
    expect(disallow).toContain("/__next");
  });

  it("does not disallow the advice pages, on purpose", () => {
    // A disallowed URL is never fetched, so the noindex on it is never read.
    // The meta tag in advies/layout.tsx is the control that works, and it only
    // works if a crawler is allowed in to see it.
    const rules = robots().rules;
    const disallow = Array.isArray(rules) ? [] : (rules.disallow ?? []);
    expect(disallow).not.toContain("/advies/");
    expect(robots().sitemap).toBe(`${SITE_ORIGIN}/sitemap.xml`);
  });

  it("lists every crawlable route absolutely and none of the advice pages", () => {
    const entries = sitemap();
    expect(entries).toHaveLength(SITEMAP_ROUTES.length);
    for (const entry of entries) {
      // Absolute, because metadataBase does not reach a metadata route.
      expect(entry.url.startsWith(`${SITE_ORIGIN}/`)).toBe(true);
      expect(entry.url.endsWith("/")).toBe(true);
      expect(entry.url).not.toContain("/advies/");
      // No lastModified: the honest value is when the content changed and the
      // build knows only when it ran.
      expect(entry.lastModified).toBeUndefined();
    }
    expect(entries.map((entry) => entry.url)).toContain(
      `${SITE_ORIGIN}/einde-saldering/`,
    );
  });
});

describe("the structured data", () => {
  it("claims nothing it cannot show on the page", () => {
    const { container } = render(<SiteJsonLd />);
    const blocks = [...container.querySelectorAll("script")].map(
      (element) => element.textContent ?? "",
    );
    expect(blocks).toHaveLength(2);
    const all = blocks.join(" ");
    // No rating, no review, no address, no telephone. Every one would be a
    // claim this product cannot support, and a rating on a neutral advisor is
    // the first thing that would stop it being one.
    for (const forbidden of [
      "aggregateRating",
      "review",
      "address",
      "telephone",
      "potentialAction",
    ]) {
      expect(all).not.toContain(forbidden);
    }
    for (const block of blocks) expect(JSON.parse(block)).toBeTruthy();
  });

  it("escapes every less-than sign, so no field can close the element", () => {
    const { container } = render(
      <PageJsonLd path="/x/" name="a<b" description="c</script>d" />,
    );
    const text = container.querySelector("script")?.textContent ?? "";
    expect(text).not.toContain("<");
    expect(text).toContain("\\u003c");
    // Still valid JSON that parses back to the original characters, which is
    // what makes the escape free rather than a corruption of the payload.
    expect(JSON.parse(text).name).toBe("a<b");
  });
});

describe("the questions route", () => {
  it("has a title of its own that does not presume the answer", () => {
    // It shipped the root default, "Ampeer", until 2026-08-31. The rules test
    // that the four routes do not all answer to the same title passed on it,
    // because "Ampeer" is genuinely distinct from the other three.
    expect(berekenenMetadata.title).toBe("Uw situatie doorrekenen");
    expect(String(berekenenMetadata.title)).not.toMatch(/kost|bespaar|verlies/);
    expect(berekenenMetadata.alternates?.canonical).toBe("/berekenen/");
    // Its own description too. It inherited the site's until 2026-08-31, so the
    // one route a marketing link points at was described in a search result by
    // a sentence about something else.
    expect(String(berekenenMetadata.description)).toContain("Vier vragen");
  });

  it("declares the calculator without claiming a rating nobody gave", () => {
    // WebApplication for entity understanding, and it will never produce a
    // rich result: Google's Software App result needs aggregateRating or review
    // on top of this, and a rating a neutral advisor supplied about itself is
    // the first thing that would stop it being neutral. The Search Console
    // warning about a missing rating is the correct state of this markup, and
    // this test is what stops somebody closing it.
    const { container } = render(
      BerekenenLayout({ children: null, params: Promise.resolve({}) }),
    );
    const block = container.querySelector("script")?.textContent ?? "";
    const data = JSON.parse(block) as Record<string, unknown>;
    expect(data["@type"]).toBe("WebApplication");
    expect(data["isAccessibleForFree"]).toBe(true);
    expect(block).not.toContain("aggregateRating");
    expect(block).not.toContain("review");
  });
});

describe("the questions a search engine is given", () => {
  it("marks up exactly the questions this page shows, in the same words", () => {
    // Six questions sat on this page as plain JSX with no FAQPage markup until
    // 2026-09-15, on the page most likely to be cited for the end of netting.
    // /thuisbatterij/ and /zelf-verbruiken/ had it from the start; this page is
    // older than the pattern.
    const { container } = render(<EindeSalderingPage />);
    const scripts = [
      ...container.querySelectorAll('script[type="application/ld+json"]'),
    ].map((element) => JSON.parse(element.textContent ?? "{}"));
    const faq = scripts.find((data) => data["@type"] === "FAQPage");

    expect(faq, "this page carries no FAQPage markup").toBeDefined();
    expect(faq.mainEntity.length).toBeGreaterThanOrEqual(5);
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
});
