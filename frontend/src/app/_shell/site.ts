/**
 * Where this site lives, spelled once.
 *
 * Three things need an absolute origin and none of them can be given a
 * relative one. `metadataBase` in the root layout resolves canonicals and
 * `og:image` against it, and without it an exported page ships an `og:image`
 * pointing at `http://localhost:3000`, which is silent apart from a build time
 * warning. `sitemap.ts` and `robots.ts` are metadata routes, which Next builds
 * before any base is resolved, so every URL in them has to be absolute and
 * carry its own trailing slash.
 *
 * A constant and not an environment variable. The one variable this frontend
 * reads, `NEXT_PUBLIC_API_BASE`, exists because the API's host genuinely
 * differs between a developer machine and production. This does not: the
 * canonical origin of ampeer.nl is ampeer.nl in every build, and making it
 * configurable would mean a mis-set variable ships canonicals pointing at
 * somewhere else, which is the failure mode that takes a site out of an index
 * without anything turning red.
 *
 * No trailing slash on the origin itself, so every use reads `${SITE_ORIGIN}/pad/`
 * and the slash is visible at the call site rather than hidden in here.
 */
export const SITE_ORIGIN = "https://ampeer.nl";

/**
 * Every route a crawler should be told about, with how often its content
 * actually changes.
 *
 * `/advies/` is absent, and that is the whole reason this list is written by
 * hand rather than discovered from the route tree. An advice lives at a bearer
 * token and there is one per visitor, so there is nothing there a sitemap
 * could name that should be named.
 *
 * `changeFrequency` is a hint crawlers have largely stopped acting on. It is
 * here because it costs a word and because it is true: the product page and
 * the methodology move when the model does, and the form does not move at all.
 *
 * `/over-ons/` and `/privacy/` are here rather than left out, and both halves
 * of that are deliberate. They are the two pages that say which entity is
 * making the claims on the rest of the site, which is the thing a search
 * engine assessing a page about somebody's money has no other way to find.
 * Their priority is low because they are not what anybody arrives for; their
 * presence is not optional, because a site that names no entity is a site that
 * has not answered the question.
 */
export const SITEMAP_ROUTES: readonly {
  readonly path: string;
  readonly changeFrequency: "monthly" | "yearly";
  readonly priority: number;
}[] = [
  { path: "/", changeFrequency: "monthly", priority: 1 },
  { path: "/einde-saldering/", changeFrequency: "monthly", priority: 0.9 },
  { path: "/thuisbatterij/", changeFrequency: "monthly", priority: 0.9 },
  { path: "/thuisbatterij-btw/", changeFrequency: "monthly", priority: 0.8 },
  { path: "/zelf-verbruiken/", changeFrequency: "monthly", priority: 0.9 },
  { path: "/berekenen/", changeFrequency: "yearly", priority: 0.8 },
  { path: "/methodologie/", changeFrequency: "monthly", priority: 0.6 },
  { path: "/over-ons/", changeFrequency: "yearly", priority: 0.5 },
  { path: "/privacy/", changeFrequency: "yearly", priority: 0.3 },
  { path: "/voorwaarden/", changeFrequency: "yearly", priority: 0.3 },
];
