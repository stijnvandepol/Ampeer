import type { Metadata } from "next";

import { JsonLd } from "../_shell/JsonLd";
import { SITE_ORIGIN } from "../_shell/site";

/**
 * A layout that exists for one reason: to give this route a title.
 *
 * The same reason and the same shape as `advies/layout.tsx`. `page.tsx` beside
 * it is a client component, because the answers live in browser storage and
 * the round comes off the query string, and a client component cannot export
 * `metadata`.
 *
 * Found on 2026-08-31 by measuring the built site rather than reading it: this
 * route shipped `<title>Ampeer</title>`, the root default. It is the page every
 * marketing link points at and the one a visitor is most likely to leave open
 * in a tab while they go and find their annual bill, so it was the worst route
 * on the site to have no name of its own.
 *
 * `e2e/rules.spec.ts` has a test that the four routes do not all answer to the
 * same title, and it passed: "Ampeer" is genuinely distinct from the other
 * three. The gate was green on the defect, which is the shape of a check that
 * measures difference where the thing that matters is meaning.
 *
 * "Uw situatie doorrekenen" and not "Bereken wat de saldering u kost". This
 * page is read before anything has been computed, so a title naming a cost
 * presumes the answer, which is the same rule the landing page's own title
 * comment states. It also has to hold for both rounds, and round two is a
 * refinement rather than a first calculation.
 */
const PATH = "/berekenen/";

export const metadata: Metadata = {
  title: "Uw situatie doorrekenen",
  /*
   * Its own, rather than the site's. Until 2026-08-31 this route inherited the
   * root layout's description, which describes the product rather than this
   * page, so the one route a marketing link points at was described in a search
   * result by a sentence about something else.
   */
  description:
    "Vier vragen over uw dak en uw verbruik. Geen account, geen e-mailadres, en niets aan uw meterkast. U krijgt een bedrag met de bandbreedte erbij.",
  alternates: { canonical: PATH },
};

/**
 * The calculator, as a thing rather than as a page.
 *
 * `WebApplication` and NOT a rich result, and the difference is worth writing
 * down because somebody will otherwise try to close the gap. Google's Software
 * App result needs `aggregateRating` or `review` on top of what is here, and
 * this product has neither: nobody has rated it, and a rating a neutral
 * advisor supplied about itself is the first thing that would stop it being
 * neutral. So Search Console will report a missing rating for this markup
 * forever, and that warning is the correct state of it. If it proves too
 * tempting to silence, delete the type rather than acquire a rating.
 *
 * `offers` at zero is not a marketing claim. It is how schema.org says free,
 * and the page says the same thing in its own words.
 */
function CalculatorJsonLd() {
  return (
    <JsonLd
      data={{
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "@id": `${SITE_ORIGIN}${PATH}#rekenmachine`,
        name: "Ampeer",
        url: `${SITE_ORIGIN}${PATH}`,
        applicationCategory: "UtilitiesApplication",
        operatingSystem: "Web",
        inLanguage: "nl-NL",
        isAccessibleForFree: true,
        offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
        isPartOf: { "@id": `${SITE_ORIGIN}/#website` },
      }}
    />
  );
}

export default function BerekenenLayout({
  children,
}: LayoutProps<"/berekenen">) {
  return (
    <>
      <CalculatorJsonLd />
      {children}
    </>
  );
}
