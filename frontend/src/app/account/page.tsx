import type { Metadata } from "next";

import { AccountPage } from "../_account/AccountPage";

const PATH = "/account/";
const TITLE = "Uw account";
const DESCRIPTION =
  "Inloggen of een account aanmaken, uw toestemmingen bekijken en omzetten, uw gegevens downloaden of uw account verwijderen.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  // A string and not a URL instance, for the reason privacy/page.tsx gives:
  // Next treats a URL here as a base and canonicalises the page to the root.
  alternates: { canonical: PATH },
  /*
   * Not in any index, and not followed out of, the same tag advies/layout.tsx
   * carries and for a neighbouring reason.
   *
   * Leaving this route out of SITEMAP_ROUTES says which pages this product
   * wants found; it does not say anything a crawler has to obey. Nothing here
   * is an answer to a search: the whole page is a sign-in form, a
   * registration form and a visitor's own account, and a search result
   * leading to it is a result that helps nobody. Worse, the same address in an
   * index is where a phishing page wants to be, next to the real one.
   *
   * A meta tag and NOT a Disallow in robots.txt: a disallowed URL is never
   * fetched, so the noindex on it is never read, and a page can still be
   * indexed from an inbound link alone. The tag is the control a crawler has
   * to come in to obey.
   */
  robots: { index: false, follow: false },
};

/**
 * The account route, and the half of it that is in the file on disk.
 *
 * A server component, so the heading and the paragraph below are in
 * `out/account/index.html` whether or not any JavaScript runs. The three views
 * are underneath in a client component, because the only way to know who is
 * signed in is to ask the API, and the cookies that answer that are httpOnly.
 *
 * This route is deliberately absent from SITEMAP_ROUTES: a sign-in form is not
 * an answer to a search, and the sitemap is the list this product says it wants
 * indexed.
 */
export default function AccountRoute() {
  return (
    <div className="mx-auto w-full max-w-[var(--shell-max)] px-6 py-16">
      <div className="flex w-full max-w-2xl flex-col gap-10">
        <div className="flex flex-col gap-3">
          <h1 className="text-3xl">{TITLE}</h1>
          <p className="text-ink-muted">
            Hier logt u in of maakt u een account aan. In uw account ziet u
            welke toestemmingen u heeft gegeven, kunt u ze omzetten, uw gegevens
            downloaden en uw account verwijderen. Voor de rekenmachine is geen
            account nodig.
          </p>
        </div>
        <AccountPage />
      </div>
    </div>
  );
}
