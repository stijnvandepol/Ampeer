import type { Metadata } from "next";
import { loadMethodology } from "@/lib/methodology";
import { Markdown } from "../_markdown/Markdown";
import { PageJsonLd } from "../_shell/JsonLd";

const PATH = "/methodologie/";
const TITLE = "Hoe Ampeer rekent";
const DESCRIPTION =
  "Welke verbruiksprofielen, welke instralingsreeks en welke tarieven wij gebruiken, met de aannames en de bandbreedtes erbij. Geschreven om nagerekend te worden.";

export const metadata: Metadata = {
  title: TITLE,
  /*
   * Its own, and it matters more here than anywhere else on the site. This is
   * the page most likely to earn a link from somebody writing about the
   * subject, because nobody else in this market publishes their method, and
   * until 2026-08-31 it was described in a search result by the sentence
   * written for the product as a whole.
   */
  description: DESCRIPTION,
  alternates: { canonical: PATH },
};

/**
 * The methodology, built from the file the Python tests guard.
 *
 * A server component with no client half at all: `loadMethodology()` reads the
 * repository at build time, and `next.config.ts` sets output: "export", so
 * this runs exactly once on the machine that builds the site and never in a
 * browser. Copying the document into the frontend instead would give the
 * published page a life of its own, and the first correction to the model
 * would leave the two disagreeing with nobody the wiser.
 *
 * This page writes no Dutch of its own. Every word on it comes out of
 * docs/methodologie.md.
 */
export default async function MethodologiePage() {
  const source = await loadMethodology();
  return (
    <article className="mx-auto w-full max-w-3xl px-6 py-16">
      <PageJsonLd path={PATH} name={TITLE} description={DESCRIPTION} />
      <Markdown source={source} />
    </article>
  );
}
