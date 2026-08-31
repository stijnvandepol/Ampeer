import type { Metadata } from "next";

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
export const metadata: Metadata = {
  title: "Uw situatie doorrekenen",
};

export default function BerekenenLayout({
  children,
}: LayoutProps<"/berekenen">) {
  return children;
}
