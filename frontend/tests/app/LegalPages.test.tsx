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
import VoorwaardenPage, {
  TermsPage,
  metadata as voorwaardenMetadata,
} from "@/app/voorwaarden/page";
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
  privacyEmail: "privacy@example.invalid",
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
  it("ships with both addresses filled and consent as the legal basis", () => {
    // Since 2026-09-03 this list stood empty and the old version of this
    // test ran its own loop zero times, which the red-proof rule forbids: a
    // check that reads green because it reads nothing. Turned around to what
    // is true today.
    expect(missingIdentityFields(IDENTITY)).toEqual([]);
    expect(IDENTITY.contactEmail).toBe("info@ampeer.nl");
    expect(IDENTITY.privacyEmail).toBe("privacy@ampeer.nl");
    expect(IDENTITY.legalBasis).toBe("toestemming");
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
    for (const route of ["privacy", "over-ons", "voorwaarden"]) {
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

  it("says what changed since fase 1 shipped accounts", () => {
    const text = privacyText();
    for (const claim of ["Resend", "Argon2id", "dertien", "7 september 2026"]) {
      expect(text, `the statement never says "${claim}"`).toContain(claim);
    }
    // The two session cookies, named by function rather than by name: the
    // page never spells out ampeer_access or ampeer_refresh, it says what
    // they are for.
    expect(text).toContain("kwartier");
    expect(text).toContain("veertien dagen");
    expect(text).toContain("geen cookiemelding");
    // The third cookie, CSRF, named by function: what it protects against.
    expect(text).toContain("verzoeken die niet van u komen");
    // The privacy address from FILLED, and not only the general one.
    expect(text).toContain("privacy@example.invalid");
    // The old claims are gone.
    expect(text).not.toContain("Er is geen account");
    expect(text).not.toContain("Wij plaatsen geen cookies");
    expect(text).not.toContain(
      "Er is nog geen knop waarmee u uw advies zelf weggooit",
    );
  });

  it("says a household can delete its own account, not only wait for a link to expire", () => {
    const text = privacyText();
    expect(text).toContain(
      "Op uw accountpagina staat een knop die uw account verwijdert.",
    );
    expect(text).toContain("Hij vraagt uw wachtwoord opnieuw.");
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

  it("adds two paragraphs about the account to the consent branch only", () => {
    const consent = privacyText(FILLED_CONSENT);
    const contract = privacyText(FILLED);
    expect(consent).toContain(
      "Wij verwerken ook uw account met uw toestemming",
    );
    expect(contract).not.toContain(
      "Wij verwerken ook uw account met uw toestemming",
    );
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

/** Rendered terms page text, on the identity the caller names. */
function termsText(identity: CompleteIdentity = FILLED): string {
  const { container } = render(<TermsPage identity={identity} />);
  return container.textContent ?? "";
}

describe("the terms page", () => {
  it("has one first-level heading and a title and description of its own", () => {
    const { container } = render(<TermsPage identity={FILLED} />);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(
      screen.getByRole("heading", { level: 1, name: "Gebruiksvoorwaarden" }),
    ).toBeInTheDocument();
    expect(voorwaardenMetadata.title).toBe("Gebruiksvoorwaarden");
    expect(String(voorwaardenMetadata.description).length).toBeGreaterThan(50);
    expect(voorwaardenMetadata.alternates?.canonical).toBe("/voorwaarden/");
    expect(voorwaardenMetadata.openGraph).toBeUndefined();
  });

  it("says what a reader needs before trusting the advice", () => {
    const text = termsText();
    for (const claim of [
      "schatting",
      "bandbreedte",
      "geen financieel",
      "verkopen geen",
      "Niemand betaalt ons",
      "account per e-mailadres",
      "Nederlands recht",
      "Autoriteit Persoonsgegevens",
    ]) {
      expect(text, `the terms page never says "${claim}"`).toContain(claim);
    }
  });

  it("carries exactly one external link, the regulator", () => {
    const { container } = render(<TermsPage identity={FILLED} />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([
      "https://www.autoriteitpersoonsgegevens.nl/",
    ]);
  });

  it("carries no em-dash and no euro amount", () => {
    expect(termsText()).not.toContain("—");
    expect(termsText()).not.toMatch(/€|\d+\s*euro/);
  });

  it("says 7 september 2026", () => {
    expect(termsText()).toContain("7 september 2026");
  });

  it("refuses to render while a fact is missing", () => {
    const missing = missingIdentityFields(IDENTITY);
    if (missing.length > 0) {
      expect(() => VoorwaardenPage()).toThrow(NOG_IN_TE_VULLEN);
    } else {
      expect(VoorwaardenPage()).toBeTruthy();
    }
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
    expect(urls).toContain(`${SITE_ORIGIN}/voorwaarden/`);
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

  it("reaches all five pages that explain the product rather than sell it", () => {
    const { container } = render(<SiteFooter />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    for (const path of [
      /^\/methodologie\/?$/,
      /^\/over-ons\/?$/,
      /^\/privacy\/?$/,
      /^\/voorwaarden\/?$/,
      // The one entrance to the account, and the only one: the site header
      // does not change and nothing goes on the advice page.
      /^\/account\/?$/,
    ]) {
      expect(hrefs.some((href) => path.test(href ?? ""))).toBe(true);
    }
    // Five, and a sixth is a finding rather than a detail: the fifth is the
    // page that says what Ampeer does not stand behind, and it stands next
    // to the page that says what Ampeer keeps, because a reader looking for
    // one wants the other too.
    expect(hrefs).toHaveLength(5);
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
    for (const page of [PrivacyPage, OverOnsPage, VoorwaardenPage]) {
      const missing = missingIdentityFields(IDENTITY);
      if (missing.length > 0) {
        expect(() => page()).toThrow(NOG_IN_TE_VULLEN);
      } else {
        expect(page()).toBeTruthy();
      }
    }
  });
});

// ---------------------------------------------------------------------------
// The two hand-written route lists, laid against the route tree
// ---------------------------------------------------------------------------

/** Every array literal string this file's own regex can find, in order. */
function stringArrayNamed(source: string, name: string): string[] {
  const match = new RegExp(`const ${name}[^=]*=\\s*\\[([\\s\\S]*?)\\]`).exec(
    source,
  );
  if (!match) throw new Error(`${name} was not found`);
  return [...match[1]!.matchAll(/"([^"]+)"/g)].map((found) => found[1]!);
}

describe("the hand-written e2e route lists stay complete", () => {
  it("names every route under src/app/, or the token template that stands for it", () => {
    const appDir = resolve(process.cwd(), "src/app");
    const routes = readdirSync(appDir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !entry.name.startsWith("_"))
      .filter((entry) => existsSync(join(appDir, entry.name, "page.tsx")))
      .map((entry) => `/${entry.name}/`)
      .sort();

    // The route tree, minus the one entry the e2e lists write differently:
    // /advies/ is a bearer-token page and both lists name the templated
    // ADVICE_PATH instead of the bare directory.
    const expected = routes.filter((route) => route !== "/advies/");

    // Deliberate exceptions to the sitemap, named so a reader does not have
    // to guess why these two routes are in the e2e lists but not in
    // SITEMAP_ROUTES: /advies/ has one URL per visitor and nothing a search
    // engine could usefully index, /account/ carries a noindex tag of its own.
    const NOT_IN_SITEMAP = ["/advies/", "/account/"];
    for (const route of routes) {
      if (NOT_IN_SITEMAP.includes(route)) continue;
      expect(
        SITEMAP_ROUTES.map((entry) => entry.path),
        `${route} is a real route, is not one of the two named exceptions, and is missing from SITEMAP_ROUTES`,
      ).toContain(route);
    }

    // `ALL_PATHS` moved out of rules.spec.ts on 2026-09-11 into
    // frontend/e2e/routes.ts, which the light sweep and the dark sweep now
    // share. Before that they were two lists and the dark one was three
    // routes short, which is the drift this check is here to catch; reading
    // the shared file means adding a route to one sweep and not the other is
    // no longer possible at all.
    for (const [file, name] of [
      ["frontend/e2e/privacy.spec.ts", "PAGES"],
      ["frontend/e2e/routes.ts", "ALL_PATHS"],
    ] as const) {
      const source = readFileSync(resolve(process.cwd(), "..", file), "utf-8");
      const listed = stringArrayNamed(source, name);
      for (const route of expected) {
        expect(
          listed.some(
            (entry) => entry === route || entry.startsWith("/advies/"),
          ),
          `${file}'s ${name} does not name ${route}`,
        ).toBe(true);
      }
    }
  });
});
