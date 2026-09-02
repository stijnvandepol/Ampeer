import type { Metadata } from "next";

/**
 * A layout that exists for one reason: to give this route a title.
 *
 * `page.tsx` next to it is a client component, because the token is read from
 * the address bar and the request goes out from the browser. A client component
 * cannot export `metadata`, so without this file the advice page took the root
 * layout's default and every shared link opened a tab called "Ampeer", the same
 * as the landing page and the same as the questions.
 *
 * It renders its children and nothing else. Adding markup here would put it on
 * a page whose own file is the one that decides what the page looks like.
 */
export const metadata: Metadata = {
  title: "Uw advies",
  /*
   * Not in any index, and not followed out of.
   *
   * Every advice lives at a bearer token URL, and nginx answers 200 for any
   * path under /advies/, so the space is unbounded: measured on 2026-08-31,
   * /advies/dit-bestaat-niet/ returns the advice shell with a 200. Two things
   * follow. A crawler would map an endless set of soft 404s, and a token
   * somebody pastes in public would be indexed, which undoes from the other
   * side the care nginx.conf takes to keep tokens out of its own access log.
   *
   * A meta tag and NOT a Disallow in robots.txt, and the difference decides
   * whether this works. A disallowed URL is never fetched, so the noindex on it
   * is never read, and a page can still be indexed from an inbound link alone.
   * The tag is the control that a crawler has to come in to obey.
   */
  robots: { index: false, follow: false },
};

export default function AdviesLayout({ children }: LayoutProps<"/advies">) {
  return children;
}
