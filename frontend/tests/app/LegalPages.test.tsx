import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import PrivacyPage, {
  PrivacyStatement,
  metadata as privacyMetadata,
} from "@/app/privacy/page";
import OverOnsPage, {
  AboutAmpeer,
  metadata as overOnsMetadata,
} from "@/app/over-ons/page";
import {
  IDENTITY,
  IDENTITY_FIELDS,
  NOG_IN_TE_VULLEN,
  missingIdentityFields,
  requireCompleteIdentity,
  type CompleteIdentity,
  type Identity,
} from "@/app/privacy/identity";
import { SiteFooter } from "@/app/_shell/SiteFooter";
import { SITEMAP_ROUTES, SITE_ORIGIN } from "@/app/_shell/site";
import robots from "@/app/robots";
import sitemap from "@/app/sitemap";

/**
 * An identity with every fact supplied, so the pages can be rendered at all.
 *
 * Nothing in it resembles a real registration. `requireCompleteIdentity`
 * checks that a field is not the sentinel and nothing more, which is the whole
 * of what this repository can know: whether a KvK number is a KvK number is a
 * question for the person who types it in, and a test that pretended to answer
 * it would be asserting the shape of a fact it does not have.
 */
const FILLED: CompleteIdentity = {
  legalName: "TESTNAAM",
  kvkNumber: "TESTKVK",
  vatNumber: "TESTBTW",
  postalAddress: "TESTADRES",
  contactEmail: "test@example.invalid",
  legalBasis: "overeenkomst",
};

/** The same, on the other legal basis, so both paragraphs are rendered once. */
const FILLED_CONSENT: CompleteIdentity = {
  ...FILLED,
  legalBasis: "toestemming",
};

/** Rendered privacy statement text, on the basis the caller names. */
function privacyText(identity: CompleteIdentity = FILLED): string {
  const { container } = render(<PrivacyStatement identity={identity} />);
  return container.textContent ?? "";
}

/** Rendered about page text. */
function aboutText(identity: CompleteIdentity = FILLED): string {
  const { container } = render(<AboutAmpeer identity={identity} />);
  return container.textContent ?? "";
}

// ---------------------------------------------------------------------------
// The facts this repository does not have
// ---------------------------------------------------------------------------

describe("the identity Ampeer cannot invent", () => {
  it("ships with every fact still unfilled, and says which", () => {
    // Not an assertion that the list is empty, because it is not, and it is
    // not supposed to be until somebody supplies six strings. What is asserted
    // is that the sentinel is the only thing standing in those fields, so the
    // build failure names a gap and never a typo.
    for (const field of missingIdentityFields(IDENTITY)) {
      expect(IDENTITY[field]).toBe(NOG_IN_TE_VULLEN);
    }
  });

  it("finds nothing missing in an identity that is complete", () => {
    expect(missingIdentityFields(FILLED)).toEqual([]);
    expect(missingIdentityFields(FILLED_CONSENT)).toEqual([]);
  });

  it("names every unfilled field, and not only the first", () => {
    // The instrument, shown to work. An implementation that returned after the
    // first gap would pass a test that only ever supplied one, and the person
    // filling this in would then get six build failures in a row instead of
    // one list.
    const empty = Object.fromEntries(
      IDENTITY_FIELDS.map((field) => [field, NOG_IN_TE_VULLEN]),
    ) as unknown as Identity;
    expect(missingIdentityFields(empty)).toEqual([...IDENTITY_FIELDS]);
    expect(
      missingIdentityFields({ ...FILLED, kvkNumber: NOG_IN_TE_VULLEN }),
    ).toEqual(["kvkNumber"]);
  });

  it("counts a blank value as unfilled, not as an answer", () => {
    // Deleting the sentinel is the obvious way to make the build error go
    // away, and it is not the same thing as supplying the fact. Without this
    // branch an empty string renders as a page with a name-shaped hole in it
    // and no marker left to find it by.
    expect(missingIdentityFields({ ...FILLED, postalAddress: "" })).toEqual([
      "postalAddress",
    ]);
    expect(missingIdentityFields({ ...FILLED, legalName: "   " })).toEqual([
      "legalName",
    ]);
  });

  it("refuses a legal basis that is not one of the two the DPIA leaves open", () => {
    // Chapter 10 point 2 of docs/dpia.md leaves the choice between performance
    // of a contract and consent to the controller. A third value would mean
    // the page renders neither paragraph, which is a privacy statement with a
    // hole in the one section that has to be right.
    const wrong = {
      ...FILLED,
      legalBasis: "gerechtvaardigd belang",
    } as unknown as Identity;
    expect(missingIdentityFields(wrong)).toEqual(["legalBasis"]);
  });

  it("throws rather than render, and the message is the list of what to supply", () => {
    let message = "";
    try {
      requireCompleteIdentity({ ...FILLED, legalName: NOG_IN_TE_VULLEN });
    } catch (error) {
      message = error instanceof Error ? error.message : String(error);
    }
    expect(message).toContain(NOG_IN_TE_VULLEN);
    expect(message).toContain("legalName");
    // The file to edit, spelled out, because a build error that says what is
    // wrong and not where is a build error somebody greps for.
    expect(message).toContain("src/app/privacy/identity.ts");
  });

  it("hands back the identity unchanged once it is complete", () => {
    expect(requireCompleteIdentity(FILLED)).toBe(FILLED);
  });

  it("puts both pages behind that guard rather than beside it", () => {
    // A source-level assertion, and deliberately so: what is being checked is
    // that neither route can be prerendered while a fact is missing, and the
    // only way to check that without a build is to read the call. The type of
    // CompleteIdentity closes the other half: `legalBasis` is a union of the
    // two accepted values there and includes the sentinel in `Identity`, so
    // the shipped IDENTITY does not typecheck where a page body wants one.
    for (const route of ["privacy", "over-ons"]) {
      const source = readFileSync(
        resolve(process.cwd(), "src/app", route, "page.tsx"),
        "utf-8",
      );
      expect(source, `${route} does not go through the guard`).toContain(
        "requireCompleteIdentity(IDENTITY)",
      );
    }
  });

  it("keeps the marker out of a page that is complete", () => {
    expect(privacyText()).not.toContain(NOG_IN_TE_VULLEN);
    expect(aboutText()).not.toContain(NOG_IN_TE_VULLEN);
    // And puts the facts it was given on the page, so the check above is not
    // passing because the fields are simply never rendered.
    for (const value of ["TESTNAAM", "TESTKVK", "TESTADRES"]) {
      expect(aboutText()).toContain(value);
    }
    expect(privacyText()).toContain("TESTNAAM");
    expect(privacyText()).toContain("test@example.invalid");
  });

  it("never lets the marker reach the built output", () => {
    // The second line, not the first. The first is the guard above, which
    // stops `next build` producing these two pages at all while a fact is
    // missing. This one reads what nginx would actually serve, so an edit that
    // renders a fact without going through the guard is caught by the artefact
    // rather than by an argument about the source.
    //
    // out/ is gitignored and CI runs `pnpm test` before `pnpm build`, so there
    // is nothing to read there. That is stated rather than hidden: this check
    // is worth what a local run after a build is worth, and the guard is worth
    // the rest.
    const out = resolve(process.cwd(), "out");
    if (!existsSync(out)) {
      expect(
        existsSync(resolve(process.cwd(), "src/app/privacy/page.tsx")),
      ).toBe(true);
      return;
    }
    const files = walk(out).filter((file) =>
      /\.(html|txt|js|json)$/.test(file),
    );
    // Non-vacuity, both halves. A walk that found nothing, or a search that
    // cannot find a string that is certainly there, would agree with any
    // output at all.
    expect(files.length, "no built files were read").toBeGreaterThan(10);
    const contents = files.map((file) => readFileSync(file, "utf-8"));
    expect(
      contents.filter((text) => text.includes("Ampeer")).length,
      "the search found nothing it should have found",
    ).toBeGreaterThan(0);
    const leaked = files.filter((file, index) =>
      (contents[index] ?? "").includes(NOG_IN_TE_VULLEN),
    );
    expect(leaked, "the placeholder shipped").toEqual([]);
  });
});

function walk(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const full = join(directory, entry.name);
    if (entry.isDirectory()) found.push(...walk(full));
    else found.push(full);
  }
  return found;
}

// ---------------------------------------------------------------------------
// The two routes
// ---------------------------------------------------------------------------

describe("the privacy statement", () => {
  it("has one first-level heading and a title and description of its own", () => {
    const { container } = render(<PrivacyStatement identity={FILLED} />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(
      screen.getByRole("heading", { level: 1, name: "Privacyverklaring" }),
    ).toBeInTheDocument();
    expect(privacyMetadata.title).toBe("Privacyverklaring");
    expect(String(privacyMetadata.description).length).toBeGreaterThan(50);
    expect(privacyMetadata.alternates?.canonical).toBe("/privacy/");
    expect(typeof privacyMetadata.alternates?.canonical).toBe("string");
    // No openGraph of its own: metadata merging is shallow, so any part of it
    // here would drop the root layout's siteName, locale and type.
    expect(privacyMetadata.openGraph).toBeUndefined();
  });

  it("says everything article 13 has to say, in the visitor's own words", () => {
    const text = privacyText();
    for (const claim of [
      // Who, and how to reach them.
      "verantwoordelijk",
      // What, and when.
      "vier cijfers",
      "jaarverbruik",
      // Why, and on what basis.
      "grondslag",
      // How long, and what happens to the link.
      "werkt de link niet meer",
      // Who else sees it.
      "Cloudflare",
      "verwerker",
      // What does not happen.
      "advertenties",
      "cookies",
      "profiel",
      // Rights, and the regulator.
      "Autoriteit Persoonsgegevens",
    ]) {
      expect(text, `the statement never says "${claim}"`).toContain(claim);
    }
  });

  it("points at the regulator that can actually take the complaint", () => {
    render(<PrivacyStatement identity={FILLED} />);
    const link = screen.getByRole("link", {
      name: /Autoriteit Persoonsgegevens/,
    });
    expect(link.getAttribute("href")).toBe(
      "https://www.autoriteitpersoonsgegevens.nl/",
    );
  });

  it("renders one legal basis paragraph, and the one it was given", () => {
    const contract = privacyText(FILLED);
    const consent = privacyText(FILLED_CONSENT);
    expect(contract).toContain("uitvoering van de overeenkomst");
    expect(contract).not.toContain("uw toestemming intrekken");
    expect(consent).toContain("uw toestemming intrekken");
    expect(consent).not.toContain("uitvoering van de overeenkomst");
  });

  it("names the retention the backend actually implements", () => {
    // Read from the code and never written here. docs/methodologie.md has
    // already gone stale against the model once, silently, because a document
    // cannot fail a build. A privacy statement is the worst place for that to
    // happen: the retention window is the sentence somebody would hold this
    // service to.
    const models = readFileSync(
      resolve(process.cwd(), "../backend/advice/models.py"),
      "utf-8",
    );
    // The window is derived from the setting and is not a literal in the
    // model, which is what makes the setting the single place that decides it.
    expect(models).toContain("timedelta(days=settings.AMPEER_ADVICE_TTL_DAYS)");
    const settings = readFileSync(
      resolve(process.cwd(), "../backend/ampeer/settings/base.py"),
      "utf-8",
    );
    const match = /^AMPEER_ADVICE_TTL_DAYS = (\d+)$/m.exec(settings);
    expect(match, "the setting is no longer a plain integer").not.toBeNull();
    const days = Number(match?.[1]);
    expect(days).toBeGreaterThan(0);
    expect(
      privacyText(),
      `the backend deletes after ${days} days and the page does not say so`,
    ).toContain(`${days} dagen`);
  });

  it("offers the way to the questions and to the page about Ampeer", () => {
    const { container } = render(<PrivacyStatement identity={FILLED} />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(hrefs.some((href) => /^\/over-ons\/?$/.test(href ?? ""))).toBe(true);
    // Exactly one link off this site, and it is the regulator.
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([
      "https://www.autoriteitpersoonsgegevens.nl/",
    ]);
  });

  it("carries no em-dash, anywhere a visitor reads", () => {
    expect(privacyText()).not.toContain("—");
    expect(aboutText()).not.toContain("—");
  });
});

describe("the page about Ampeer", () => {
  it("has one first-level heading and a title and description of its own", () => {
    const { container } = render(<AboutAmpeer identity={FILLED} />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(
      screen.getByRole("heading", { level: 1, name: "Over Ampeer" }),
    ).toBeInTheDocument();
    expect(overOnsMetadata.title).toBe("Over Ampeer");
    expect(String(overOnsMetadata.description).length).toBeGreaterThan(50);
    expect(overOnsMetadata.alternates?.canonical).toBe("/over-ons/");
    expect(typeof overOnsMetadata.alternates?.canonical).toBe("string");
    expect(overOnsMetadata.openGraph).toBeUndefined();
  });

  it("says what it does not sell before it says anything else", () => {
    // The order is the argument. A trust page that explains itself first and
    // discloses second has buried the disclosure, and the disclosure is the
    // only part a reader cannot get anywhere else.
    const { container } = render(<AboutAmpeer identity={FILLED} />);
    const headings = [...container.querySelectorAll("h2")].map(
      (element) => element.textContent ?? "",
    );
    expect(headings[0]).toContain("niet");
    const paid = headings.findIndex((text) => text.includes("betaald"));
    const why = headings.findIndex((text) => text.includes("bestaat"));
    expect(paid).toBeGreaterThan(-1);
    expect(why).toBeGreaterThan(paid);
  });

  it("names the outcome no competitor can offer, and what it earns", () => {
    const text = aboutText();
    expect(text).toContain("nu geen batterij");
    expect(text).toContain("verdienen");
  });

  it("lists every route Ampeer does not take to make money", () => {
    const text = aboutText();
    for (const claim of [
      "zonnepanelen",
      "thuisbatterijen",
      "energiecontract",
      "advertenties",
      "leads",
    ]) {
      expect(text, `the page never says "${claim}"`).toContain(claim);
    }
  });

  it("links to the method and to the privacy statement and nowhere off site", () => {
    const { container } = render(<AboutAmpeer identity={FILLED} />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(hrefs.some((href) => /^\/methodologie\/?$/.test(href ?? ""))).toBe(
      true,
    );
    expect(hrefs.some((href) => /^\/privacy\/?$/.test(href ?? ""))).toBe(true);
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });

  it("puts no euro amount on the page, because it has computed none", () => {
    expect(aboutText()).not.toMatch(/€|\d+\s*euro/);
    expect(privacyText()).not.toMatch(/€|\d+\s*euro/);
  });
});

// ---------------------------------------------------------------------------
// Where the two routes are announced
// ---------------------------------------------------------------------------

describe("the crawler files, once the legal pages exist", () => {
  it("names both routes in the sitemap, absolutely", () => {
    const urls = sitemap().map((entry) => entry.url);
    expect(urls).toContain(`${SITE_ORIGIN}/privacy/`);
    expect(urls).toContain(`${SITE_ORIGIN}/over-ons/`);
    expect(sitemap()).toHaveLength(SITEMAP_ROUTES.length);
    // And leaves out the one route that is not an answer to a search. The
    // account page's own file says it is deliberately absent; a comment is
    // not a check, and this is the line that would go red if somebody added
    // it. The tag in that file's metadata is the other half: this list says
    // which pages the product wants found, the tag is what a crawler that
    // arrived by an inbound link has to obey.
    expect(urls).not.toContain(`${SITE_ORIGIN}/account/`);
    for (const entry of sitemap()) {
      expect(entry.url.endsWith("/")).toBe(true);
      expect(entry.lastModified).toBeUndefined();
    }
  });

  it("lets a crawler read them, which is the point of writing them", () => {
    // E-E-A-T on a YMYL subject is the reason these two pages exist at all. A
    // Disallow on either would be the site publishing an identity nobody can
    // read.
    const rules = robots().rules;
    const disallow = Array.isArray(rules) ? [] : (rules.disallow ?? []);
    expect(disallow).not.toContain("/privacy/");
    expect(disallow).not.toContain("/over-ons/");
    expect(Array.isArray(rules) ? "" : rules.allow).toBe("/");
  });
});

describe("the footer, which is where a visitor looks for these", () => {
  it("still says what Ampeer does not sell", () => {
    render(<SiteFooter />);
    expect(screen.getByText(/verkoopt geen panelen/)).toBeInTheDocument();
  });

  it("reaches all four pages that explain the product rather than sell it", () => {
    const { container } = render(<SiteFooter />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    for (const path of [
      /^\/methodologie\/?$/,
      /^\/over-ons\/?$/,
      /^\/privacy\/?$/,
      // The one entrance to the account, and the only one: the site header
      // does not change and nothing goes on the advice page.
      /^\/account\/?$/,
    ]) {
      expect(hrefs.some((href) => path.test(href ?? ""))).toBe(true);
    }
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// The routes themselves, as Next will call them
// ---------------------------------------------------------------------------

describe("the two default exports", () => {
  it("refuse to render while a fact is missing", () => {
    // This is what makes `next build` fail rather than publish a page with a
    // hole in it. It stops being a failure the moment somebody fills the six
    // fields in, and at that point both calls below return an element instead,
    // which is what the two branches here allow for. Either way, one of the
    // two must hold: a page that neither throws nor renders is a page that
    // slipped past the guard.
    for (const page of [PrivacyPage, OverOnsPage]) {
      const missing = missingIdentityFields(IDENTITY);
      if (missing.length > 0) {
        expect(() => page()).toThrow(NOG_IN_TE_VULLEN);
      } else {
        expect(page()).toBeTruthy();
      }
    }
  });
});
