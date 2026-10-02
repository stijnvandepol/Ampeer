import Link from "next/link";

/**
 * Navigation, and nothing that sells.
 *
 * Every label here is interface text written by the frontend, which is the one
 * category of Dutch this codebase is allowed to write. There is no third call
 * to action hiding in a navigation bar: these are the names of pages that
 * exist, and the methodology is one of them because the document this product
 * is judged on should be one click away from the answer it produced.
 */
/** Where the header goes, in the order a worried visitor would ask. */
const NAV: readonly (readonly [string, string])[] = [
  ["/einde-saldering/", "Einde saldering"],
  ["/zonnepanelen-2027/", "Wat moet ik doen?"],
  ["/thuisbatterij/", "Thuisbatterij"],
  ["/berekenen/", "Berekenen"],
];

export function SiteHeader() {
  return (
    <header className="border-b border-hairline">
      {/*
        Two things in a row that wraps: the wordmark, and the navigation under
        it on a phone or beside it from `sm` up. Measured on 2026-09-16 on a
        390 by 664 viewport, the header stood 133 pixels tall with the theme
        control in it; that control now lives in the footer.
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
            Onafhankelijk advies over uw zonnepanelen
          </span>
        </div>
        {/*
         * The four questions a visitor arrives with, in their words, since
         * 2026-10-01. "Methodologie" stood here before: the right page for a
         * reviewer and a word the people this site is for do not use. It is
         * still one click away, in the footer, as "Hoe Ampeer rekent". The
         * theme control moved to the footer the same day; it is a setting
         * that almost nobody changes and it took a third of the header.
         *
         * flex-wrap, and it is load bearing rather than tidy: an unwrapping
         * nav gave every page a horizontal scrollbar below about 390px
         * (measured at 360x640 on 2026-09-02), which fails WCAG 2.2 AA 1.4.10
         * and which axe cannot see, so e2e/rules.spec.ts measures it.
         */}
        <nav
          aria-label="Hoofdnavigatie"
          className="flex w-full flex-wrap items-center gap-x-5 gap-y-2 sm:w-auto"
        >
          {NAV.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className="text-sm font-medium text-ink underline-offset-4 hover:underline sm:text-base"
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
