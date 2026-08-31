import type { MetadataRoute } from "next";

import { SITE_ORIGIN } from "./_shell/site";

/**
 * Required by `output: "export"`, and the build says so rather than guessing.
 *
 * A metadata route is a route handler, and Next assumes a handler may be
 * dynamic. Without this the build fails with "export const dynamic =
 * force-static not configured on route", which is the right failure: a route
 * that could be dynamic has no meaning in a tree with no Node process behind
 * it.
 */
export const dynamic = "force-static";

/**
 * What a crawler may read, and the two things it may not.
 *
 * Until 2026-08-31 there was no robots.txt at all: `/robots.txt` answered 404.
 * That is not neutral, it is a site with no opinion about a URL space that
 * turns out to have two problems in it.
 *
 * THE PLAIN TEXT PAYLOADS. `output: "export"` writes React Server Component
 * prefetch payloads beside every page, and nginx serves them: `/index.txt`,
 * `/__next._full.txt`, `/__next._tree.txt` and one per route. Measured on the
 * running stack on 2026-08-31, they answer 200 with `text/plain` and they
 * contain the page's content in wire format. That is a complete plain text
 * duplicate of every page on this site, indexable, and there is no meta tag
 * you can put in a .txt file, so `Disallow` is the only control that reaches
 * them. This is the one case on this site where it is the right instrument.
 *
 * `/advies/` IS NOT DISALLOWED, AND THAT IS DELIBERATE. Every advice lives at a
 * bearer token URL and nginx answers 200 for any path under it, so the space is
 * unbounded. The instinct is to disallow it. That would be worse: a disallowed
 * URL cannot be crawled, so the `noindex` on it is never read, and a link
 * somebody shares publicly can still be indexed from the link alone. The
 * control that works is the meta tag in `advies/layout.tsx`, and it only works
 * if a crawler is allowed in to see it.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        // The RSC payloads. Both forms, because the per-route ones are
        // `/berekenen/index.txt` and the root ones are `/__next._full.txt`.
        "/*.txt$",
        "/__next",
      ],
    },
    // Absolute, and with the trailing slash written by hand. `metadataBase`
    // does not reach a metadata route: Next builds these before a base is
    // resolved, and says so in a comment in resolve-route-data.js. A relative
    // URL here ships a sitemap reference that resolves against whatever host
    // the crawler happens to be on.
    sitemap: `${SITE_ORIGIN}/sitemap.xml`,
  };
}
