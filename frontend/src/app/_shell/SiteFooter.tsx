import Link from "next/link";

/**
 * What this is, what it is not, and who is saying so.
 *
 * The sentence about selling nothing is the one claim on the page that is
 * about Ampeer rather than about the visitor's house, and it belongs at the
 * bottom rather than in a banner. It is interface text: it says what this site
 * is, not what the household should do.
 *
 * The links under it are the pages that back that sentence up. Until
 * 2026-09-02 there was only one, to the methodology, and the two that were
 * missing were the two a visitor goes looking for in a footer: who is behind
 * this, and what happens to what I typed in. A site that collects a postcode
 * and a consumption figure and offers neither is a site whose claim about
 * neutrality is made by nobody.
 *
 * There are now five, and the fifth is the only entrance to the account: the
 * site header does not change, and nothing goes on the advice page, because a
 * footer is where a visitor looks for an account and an account in phase 1 is
 * a facility rather than an offer.
 *
 * A nav landmark rather than a list of paragraphs, so a screen reader can jump
 * to it and skip it. It carries its own label because the header already has
 * one: two unlabelled navigation landmarks on a page are announced identically
 * and neither can be told from the other.
 */
export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-hairline">
      <div className="mx-auto flex w-full max-w-[var(--shell-max)] flex-col gap-3 px-6 py-8 text-sm text-ink-muted">
        <p>
          Ampeer verkoopt geen panelen, geen batterijen en geen energiecontract,
          en plaatst geen advertenties. Niemand betaalt ons voor de uitkomst die
          u krijgt.
        </p>
        <nav
          aria-label="Over Ampeer"
          className="flex flex-wrap items-center gap-x-5 gap-y-2"
        >
          <Link href="/methodologie/" className="underline underline-offset-4">
            Hoe Ampeer rekent
          </Link>
          <Link href="/over-ons/" className="underline underline-offset-4">
            Over ons
          </Link>
          <Link href="/privacy/" className="underline underline-offset-4">
            Privacy
          </Link>
          <Link href="/voorwaarden/" className="underline underline-offset-4">
            Voorwaarden
          </Link>
          {/*
            No link to /account/ since 2026-09-15, on the owner's decision.
            The account exists for the meter link, and the meter link hands a
            household a key and a URL and nothing that sends readings there:
            no HomeWizard or Home Assistant integration, no script, no page
            that explains it. A door to a room with nothing in it is worse
            than no door. The route still answers for whoever has an account,
            it carries noindex and is not in the sitemap; the link comes back
            when the room has something in it.
          */}
        </nav>
      </div>
    </footer>
  );
}
