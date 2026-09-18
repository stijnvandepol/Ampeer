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
      {/*
        Three things in a row that wraps, and the order of the wrap is the
        point. Measured on 2026-09-16 on a 390 by 664 viewport: the header
        stood 133 pixels tall, a fifth of the screen, because the theme
        control was the last item in the navigation and wrapped onto a row of
        its own under three links. Now the wordmark and the theme control
        share the first row on a phone and the links take the second; from
        `sm` up the three sit in one row as before. The control left the
        <nav> for that, which is also where it belongs: it is a setting, not
        a place to go.
      */}
      <div className="mx-auto flex w-full max-w-[var(--shell-max)] flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-3 sm:py-4">
        <Link
          href="/"
          className="flex items-center gap-2 font-medium tracking-tight text-ink"
        >
          {/*
            The band mark from icon.svg, inline so it takes the header's
            colour of nothing: it is the one colour on the site that does not
            follow the theme, for the reason the icon file gives. Decorative
            here, because the word beside it is the name.
          */}
          <svg
            aria-hidden="true"
            viewBox="0 0 32 32"
            width="24"
            height="24"
            className="shrink-0"
          >
            <rect width="32" height="32" rx="7" fill="#0b6e63" />
            <rect
              x="4"
              y="14"
              width="24"
              height="4"
              rx="2"
              fill="#ffffff"
              opacity="0.45"
            />
            <rect
              x="18.25"
              y="11"
              width="3.5"
              height="10"
              rx="1.75"
              fill="#ffffff"
            />
          </svg>
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
        <div className="order-2 sm:order-3">
          <ThemeToggle />
        </div>
        <nav
          aria-label="Hoofdnavigatie"
          className="order-3 flex w-full flex-wrap items-center gap-x-5 gap-y-2 sm:order-2 sm:w-auto"
        >
          <Link
            href="/einde-saldering/"
            className="text-sm text-ink-muted underline-offset-4 hover:underline"
          >
            Einde saldering
          </Link>
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
        </nav>
      </div>
    </header>
  );
}
