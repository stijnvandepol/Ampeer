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
};

export default function AdviesLayout({ children }: LayoutProps<"/advies">) {
  return children;
}
