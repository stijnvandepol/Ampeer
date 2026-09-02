import type { MetadataRoute } from "next";

import { SITE_ORIGIN, SITEMAP_ROUTES } from "./_shell/site";

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
 * The four routes worth crawling.
 *
 * There is no `lastModified`, and leaving it out is deliberate rather than
 * lazy. The honest value is the date the page's content changed, and this
 * build knows only the date it ran. `new Date()` here would stamp every route
 * with the moment of the last deploy, telling a crawler that four pages
 * changed when a dependency was bumped, which is a claim that costs its
 * credibility the third time it is wrong. It is also a clock read, and
 * `ampeer-no-reading-the-clock` in `.semgrep/frontend.yml` forbids this tree
 * one for a related reason: a date this site knows is a date it can be tempted
 * to count down from.
 *
 * `output: "export"` writes this to `out/sitemap.xml` at the root, unaffected
 * by `trailingSlash`, because Next returns from copying a metadata route
 * before the branch that turns `/berekenen` into `berekenen/index.html`.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  return SITEMAP_ROUTES.map(({ path, changeFrequency, priority }) => ({
    url: `${SITE_ORIGIN}${path}`,
    changeFrequency,
    priority,
  }));
}
