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
        {/*
          The wordmark, its mark, and one line saying what the name means.
          The owner's brief on 2026-09-18: the logo has to say what Ampeer
          does, fast, to somebody who has never heard of it. The mark is the
          day in three bars, the same figure the first screen and every
          advice draw (see icon.svg for the reasoning). The line under the
          name is the one sentence the site would keep if it could keep one.
          It sits outside the link so that the link's accessible name stays
          "Ampeer", which is what a screen reader should hear for the way
          home.
        */}
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 font-medium tracking-tight text-ink"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 32 32"
              width="28"
              height="28"
              className="shrink-0"
            >
              <rect width="32" height="32" rx="7" fill="#071019" />
              <rect
                x="5.5"
                y="15"
                width="6"
                height="11"
                rx="1.5"
                fill="#8b9ba8"
              />
              <rect
                x="13"
                y="6"
                width="6"
                height="20"
                rx="1.5"
                fill="#f5c64a"
              />
              <rect
                x="20.5"
                y="11"
                width="6"
                height="15"
                rx="1.5"
                fill="#3f6489"
              />
            </svg>
            Ampeer
          </Link>
          <span
            className="hidden text-sm leading-tight text-ink-muted sm:block"
            aria-hidden="true"
          >
            Rekent uit wat het einde van saldering u kost
          </span>
        </div>
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
