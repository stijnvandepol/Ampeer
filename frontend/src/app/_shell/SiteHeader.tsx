import Link from "next/link";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Navigation, and nothing that sells.
 *
 * Every label here is interface text written by the frontend, which is the one
 * category of Dutch this codebase is allowed to write. There is no third call
 * to action hiding in a navigation bar: these are the names of pages that
 * exist, and the methodology is one of them because the document this product
 * is judged on should be one click away from the answer it produced.
 */
export function SiteHeader() {
  return (
    <header className="border-b border-hairline">
      <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <Link href="/" className="font-medium tracking-tight text-ink">
          Ampeer
        </Link>
        {/*
         * flex-wrap, and it is load bearing rather than tidy. The outer div
         * wrapped and this nav did not, so it was one flex item 341px wide that
         * could not break, and every page of the site had a horizontal
         * scrollbar below about 390px: measured at 360x640, scrollWidth 366
         * against clientWidth 360, on all four routes, and 365 against 320 at
         * 400% zoom. 360 is the most common Android viewport in the
         * Netherlands. WCAG 2.2 AA 1.4.10, and axe cannot see it at all, so
         * e2e/rules.spec.ts measures the document instead.
         */}
        <nav
          aria-label="Hoofdnavigatie"
          className="flex flex-wrap items-center gap-x-5 gap-y-2"
        >
          <Link
            href="/berekenen/"
            className="text-sm text-ink-muted underline-offset-4 hover:underline"
          >
            Berekenen
          </Link>
          <Link
            href="/methodologie/"
            className="text-sm text-ink-muted underline-offset-4 hover:underline"
          >
            Methodologie
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
