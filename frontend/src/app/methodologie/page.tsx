import type { Metadata } from "next";
import { loadMethodology } from "@/lib/methodology";
import { Markdown } from "../_markdown/Markdown";

export const metadata: Metadata = {
  title: "Hoe Ampeer rekent",
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
      <Markdown source={source} />
    </article>
  );
}
