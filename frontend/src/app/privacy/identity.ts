/**
 * The six facts about Ampeer as an entity that this repository does not know.
 *
 * WHY THIS FILE EXISTS AT ALL. `/privacy/` and `/over-ons/` are the two pages
 * whose whole subject is who is behind this site. A privacy statement without
 * a named controller does not satisfy article 13 and a trust page without a
 * registration is a claim about neutrality made by nobody. Every other page on
 * this site can be written from the repository. These two cannot: the legal
 * name, the KvK number, the VAT number, the postal address, the contact
 * address and the legal basis are decisions and registrations that live
 * outside it.
 *
 * WHY A SENTINEL RATHER THAN A PLAUSIBLE PLACEHOLDER. "Ampeer B.V., KvK
 * 12345678" would render, would pass every test, would look finished in a
 * review, and would be a false statement about a legal entity on the one page
 * of the site whose job is to be true. A value that cannot be mistaken for an
 * answer is the only kind that is safe to leave in.
 *
 * WHAT STOPS IT SHIPPING. `requireCompleteIdentity` throws, and both page
 * components call it. `next build` prerenders every route, so a missing fact
 * fails the build and `out/` is never written. That is the gate, and it is
 * deliberately the build rather than a test: CI runs `pnpm test` before
 * `pnpm build`, `out/` is gitignored, and a test over an artefact that does
 * not exist yet is a test that agrees with anything. The build is the only
 * thing that stands between this source tree and the directory nginx serves.
 *
 * `tests/app/LegalPages.test.tsx` is the second line: it reads `out/` when a
 * local build has produced one and fails on the sentinel there, which catches
 * a future edit that renders a fact without going through the guard.
 *
 * WHERE IT LIVES. Under `privacy/` rather than in a shared folder, because the
 * article 13 obligation is what forces these facts to exist at all;
 * `over-ons/` reuses them rather than restating them, so the two pages cannot
 * name two different entities.
 */

/**
 * The one value that means "not supplied yet".
 *
 * Spelled in Dutch because the person who has to fill it in reads Dutch, and
 * spelled in capitals with underscores because it has to survive a grep, a
 * diff and a glance at a rendered page without being mistaken for content.
 */
export const NOG_IN_TE_VULLEN = "NOG_IN_TE_VULLEN";

/**
 * The two lawful bases that are actually open here, and no third.
 *
 * Chapter 10 point 2 of `docs/dpia.md` leaves the choice between performance
 * of a contract at the data subject's request and consent to the controller,
 * and says in the same breath that the choice also decides what the privacy
 * statement says. So it is a fact this file is missing rather than a wording
 * detail, and the page renders a different paragraph for each. Legitimate
 * interest is not in this union on purpose: nothing in the assessment supports
 * it, and a union that accepted it would let it be chosen by a typo.
 */
export const LEGAL_BASES = ["overeenkomst", "toestemming"] as const;

export type LegalBasis = (typeof LEGAL_BASES)[number];

/** The identity as it stands, with the gaps still in it. */
export interface Identity {
  readonly legalName: string;
  readonly kvkNumber: string;
  readonly vatNumber: string;
  readonly postalAddress: string;
  readonly contactEmail: string;
  readonly legalBasis: LegalBasis | typeof NOG_IN_TE_VULLEN | string;
}

/**
 * The identity a page is allowed to render.
 *
 * `legalBasis` is narrowed to the union here and widened in `Identity`, which
 * is what makes this a compile time barrier and not only a runtime one: the
 * exported `IDENTITY` below does not typecheck where a page body wants one of
 * these. The only way to obtain a `CompleteIdentity` is `requireCompleteIdentity`.
 */
export interface CompleteIdentity {
  readonly legalName: string;
  readonly kvkNumber: string;
  readonly vatNumber: string;
  readonly postalAddress: string;
  readonly contactEmail: string;
  readonly legalBasis: LegalBasis;
}

/**
 * Every field, in the order the build error lists them.
 *
 * A written list rather than `Object.keys`, so a field that somebody adds to
 * the interface and forgets here is a type error rather than a fact that
 * silently stops being checked.
 */
export const IDENTITY_FIELDS = [
  "legalName",
  "kvkNumber",
  "vatNumber",
  "postalAddress",
  "contactEmail",
  "legalBasis",
] as const satisfies readonly (keyof Identity)[];

export type IdentityField = (typeof IDENTITY_FIELDS)[number];

/**
 * What each field is, for the person filling it in.
 *
 * English, because this text reaches a build log and never a visitor.
 * `CLAUDE.md` puts log messages on the English side of the language boundary.
 */
export const IDENTITY_FIELD_HELP: Readonly<Record<IdentityField, string>> = {
  legalName:
    "the registered name of the controller, including its legal form, or the full name of the natural person",
  kvkNumber: "the Chamber of Commerce number, eight digits",
  vatNumber: "the VAT identification number, NL followed by twelve characters",
  postalAddress: "a postal address a letter can reach",
  contactEmail: "the address that answers questions about personal data",
  legalBasis: `either "${LEGAL_BASES[0]}" or "${LEGAL_BASES[1]}"; see chapter 10 point 2 of docs/dpia.md`,
};

/**
 * THE SIX FACTS. Fill these in and both pages build.
 *
 * Nothing else in this repository has to change. Replace each sentinel with
 * the real value, run `pnpm build`, and the failure below goes away.
 */
export const IDENTITY: Identity = {
  // An eenmanszaak, so the controller is the natural person behind it and
  // "Stijn IT" is the registered trade name. Both are stated, because a
  // visitor exercising a right needs the name a letter can be addressed to
  // and the name they saw on the site, and for this legal form those differ.
  legalName: "Stijn IT, eenmanszaak",
  kvkNumber: "42015984",
  vatNumber: NOG_IN_TE_VULLEN,
  postalAddress: "Snavelbiesstraat 8, 5445 NV Landhorst",
  contactEmail: NOG_IN_TE_VULLEN,
  // Chosen on 2026-09-02, from the two the DPIA leaves open in chapter 10.
  // Article 6(1)(b): the visitor asks for a calculation and these answers are
  // what makes one possible, so the processing is the service rather than
  // something done alongside it. Consent was the alternative and is worse here
  // in both directions: it has to be as easy to withdraw as to give, and
  // withdrawing it after an advice has been computed leaves a question nobody
  // has a good answer to, while asking for it at all implies that saying no
  // still leaves something to calculate, which it does not.
  legalBasis: "overeenkomst",
};

/** True when a field still holds nothing a page may print. */
function isUnfilled(identity: Identity, field: IdentityField): boolean {
  const value = identity[field];
  if (field === "legalBasis") {
    return !(LEGAL_BASES as readonly string[]).includes(value);
  }
  return value === NOG_IN_TE_VULLEN || value.trim().length === 0;
}

/**
 * Every field still standing open, in order, and never only the first.
 *
 * All of them, because somebody supplying these should get one list and not
 * six consecutive build failures.
 */
export function missingIdentityFields(
  identity: Identity,
): readonly IdentityField[] {
  return IDENTITY_FIELDS.filter((field) => isUnfilled(identity, field));
}

/**
 * The identity, or a build that stops here.
 *
 * The message names every gap, says what each one is, and says which file to
 * edit. A build error that says what is wrong and not where is a build error
 * somebody greps for.
 */
export function requireCompleteIdentity(identity: Identity): CompleteIdentity {
  const missing = missingIdentityFields(identity);
  if (missing.length === 0) return identity as CompleteIdentity;
  const lines = missing.map(
    (field) => `  - ${field}: ${IDENTITY_FIELD_HELP[field]}`,
  );
  throw new Error(
    [
      `${NOG_IN_TE_VULLEN}: /privacy/ and /over-ons/ name the entity behind`,
      "Ampeer, and this repository does not know it yet. These pages are not",
      "publishable until every field below is supplied in",
      "src/app/privacy/identity.ts:",
      ...lines,
    ].join("\n"),
  );
}
