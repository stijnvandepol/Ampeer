import { SITE_ORIGIN } from "./site";

/**
 * Structured data, without the construct semgrep forbids.
 *
 * Next's own guide for this renders JSON-LD with `dangerouslySetInnerHTML`,
 * which is an ERROR under `ampeer-no-dangerously-set-inner-html` in
 * `.semgrep/frontend.yml` and would fail the required `sast` check. It does not
 * need to: React treats `<script>` as a raw text element and does not escape
 * its text children, which this project already relies on for the theme
 * bootstrap in `layout.tsx`. Verified against the built artifact rather than
 * against that claim: `out/index.html` carries the bootstrap with its double
 * quotes intact and not entity encoded.
 *
 * Every less-than sign is still escaped to its six character unicode form.
 * That is a valid escape inside a JSON string, it parses back to the same
 * character, and it is the only thing stopping a stray closing script tag in
 * some future data driven field from ending the element early. One call, and
 * it removes this construct's only injection shape.
 */
export function JsonLd({ data }: { readonly data: Record<string, unknown> }) {
  return <script type="application/ld+json">{emit(data)}</script>;
}

function emit(data: Record<string, unknown>): string {
  return JSON.stringify(data).replaceAll("<", "\\u003c");
}

/**
 * Who publishes this site, and the site itself.
 *
 * WHAT IS DELIBERATELY ABSENT. No `aggregateRating`, no `review`, no
 * `address`, no `telephone`. Google's own guidelines say not to mark up
 * content that is not visible on the page and not to use structured data to
 * mislead, and every one of those would be a claim this product cannot support:
 * there are no reviewers, there is no counter, and a rating on a neutral
 * advisor would be the first thing to stop it being one.
 *
 * No `potentialAction` either. The sitelinks search box it feeds was retired in
 * November 2024, and there is no search on this site to point it at.
 *
 * `description` names what Ampeer does not sell, which is not marketing here:
 * ampeer.nl previously carried a service that arranged Dutch energy contracts,
 * and an index that still remembers it is the single most confusing fact a
 * visitor searching the brand can meet. The page says the same thing in its own
 * words under "Wat wij niet doen", which is what makes this markup a
 * description of visible content rather than a claim of its own.
 */
export function SiteJsonLd() {
  const organisation = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE_ORIGIN}/#organisatie`,
    name: "Ampeer",
    url: `${SITE_ORIGIN}/`,
    description:
      "Neutrale energie-adviseur voor Nederlandse huishoudens met zonnepanelen. Verkoopt geen panelen, geen batterijen en geen energiecontract, en plaatst geen advertenties.",
    knowsLanguage: "nl",
  };
  const website = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE_ORIGIN}/#website`,
    name: "Ampeer",
    url: `${SITE_ORIGIN}/`,
    inLanguage: "nl-NL",
    publisher: { "@id": `${SITE_ORIGIN}/#organisatie` },
  };
  return (
    <>
      <script type="application/ld+json">{emit(organisation)}</script>
      <script type="application/ld+json">{emit(website)}</script>
    </>
  );
}

/** One page, named and placed inside the site. Nothing here is a claim. */
export function PageJsonLd({
  path,
  name,
  description,
  dateModified,
}: {
  readonly path: string;
  readonly name: string;
  readonly description: string;
  /**
   * ISO date of the last change to what the page says, written by hand in
   * the page beside the visible "laatst bijgewerkt" line so the two cannot
   * disagree. Optional, because a date nobody maintains is worse than none:
   * Google reads it as freshness and a stale one is a claim.
   */
  readonly dateModified?: string | undefined;
}) {
  const page = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${SITE_ORIGIN}${path}#pagina`,
    url: `${SITE_ORIGIN}${path}`,
    name,
    description,
    inLanguage: "nl-NL",
    isPartOf: { "@id": `${SITE_ORIGIN}/#website` },
    ...(dateModified === undefined ? {} : { dateModified }),
    /*
     * Two crumbs, home and this page, nested in the WebPage rather than a
     * script of their own: the site is flat, so a breadcrumb says only
     * where a page sits under the root, and that is what Google draws in
     * a result in place of the raw URL.
     */
    ...(path === "/"
      ? {}
      : {
          breadcrumb: {
            "@type": "BreadcrumbList",
            itemListElement: [
              {
                "@type": "ListItem",
                position: 1,
                name: "Ampeer",
                item: `${SITE_ORIGIN}/`,
              },
              { "@type": "ListItem", position: 2, name },
            ],
          },
        }),
  };
  return <script type="application/ld+json">{emit(page)}</script>;
}

/**
 * The questions a page answers, for the machines that read pages.
 *
 * Not for a Google rich result, because there is none any more: FAQ rich
 * results were limited to government and health sites in August 2023 and
 * retired altogether on 7 May 2026. What still reads this markup is Google's
 * own understanding of the page and the retrieval crawlers behind AI answers,
 * which cite a page that states a question and its answer as one unit. That
 * is the only return on it, and it is the one this site is after.
 *
 * Every question and every answer here must already be on the page in the same
 * words. Google's guidelines say not to mark up content a visitor cannot see,
 * and this project has a second reason: an answer that exists only in the
 * markup is an answer nobody proofread, on a page whose whole argument is that
 * it says what it means.
 *
 * The caller passes the same array it renders, so the two cannot drift.
 */
export function FaqJsonLd({
  questions,
}: {
  readonly questions: readonly (readonly [string, string])[];
}) {
  const faq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    inLanguage: "nl-NL",
    mainEntity: questions.map(([question, answer]) => ({
      "@type": "Question",
      name: question,
      acceptedAnswer: { "@type": "Answer", text: answer },
    })),
  };
  return <script type="application/ld+json">{emit(faq)}</script>;
}
