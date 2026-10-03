import type { Metadata } from "next";
import { Atkinson_Hyperlegible_Next, Fraunces } from "next/font/google";
import "./globals.css";
import { ConsentBanner } from "./_shell/ConsentBanner";
import { SiteFooter } from "./_shell/SiteFooter";
import { SiteHeader } from "./_shell/SiteHeader";
import { SiteJsonLd } from "./_shell/JsonLd";
import { SITE_ORIGIN } from "./_shell/site";
import { THEME_BOOTSTRAP } from "./_shell/theme";

/*
 * The two faces, chosen on 2026-10-01 to stop the site reading as a system.
 *
 * Until then it was Geist and Geist Mono, a pair drawn for developer tools,
 * and the mono face set every small label and axis. The owner's brief that day
 * was that the site felt abstract and impersonal to the people it is for:
 * homeowners with panels, mostly past forty-five, mostly on a phone.
 *
 * The body is Atkinson Hyperlegible Next, drawn by the Braille Institute for
 * readers with low vision: letters that are easy to tell apart (I, l and 1;
 * O and 0) and open shapes at small sizes. It also sets every figure, with
 * tabular numerals where they line up, so there is no third face.
 *
 * The headings are Fraunces with its SOFT axis at the maximum: a serif with
 * round terminals and gentle contrast, which reads as a person talking rather
 * than a heading in a dashboard. Both are variable, so every weight costs one
 * file each.
 */
const body = Atkinson_Hyperlegible_Next({
  variable: "--font-body",
  subsets: ["latin"],
});

const display = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
  axes: ["SOFT", "opsz"],
});

/** The id the skip link jumps to. Every page renders its content inside it. */
export const MAIN_ID = "hoofdinhoud";

export const metadata: Metadata = {
  /*
   * A default and a template rather than one string. Measured on the built
   * site: /, /berekenen/ and /advies/<token>/ all carried <title>Ampeer</title>,
   * so three of the four routes were indistinguishable in a tab strip, in a
   * history list, in a bookmark, and to a screen reader announcing the page on
   * arrival. Each route that can set its own now does; the default is what is
   * left for the ones that cannot.
   */
  title: { default: "Ampeer", template: "%s | Ampeer" },
  description:
    "Reken uit wat het einde van de salderingsregeling uw huishouden kost, met de marge erbij.",
  /*
   * Without this every relative URL Next resolves stays relative, and the one
   * that matters is `og:image`: a statically exported page ships it pointing at
   * http://localhost:3000, and the only sign is a warnOnce during the build.
   * It also decides whether `canonical` gains the trailing slash from
   * `trailingSlash: true`, which it does only once the URL is absolute and
   * same origin.
   */
  metadataBase: new URL(SITE_ORIGIN),
  /*
   * An `openGraph` key has to EXIST before Next copies `title` and
   * `description` into it. Measured on the built site on 2026-08-31:
   * out/index.html carried a title, a description, a favicon link and not one
   * og: or twitter: tag, because this object was absent and the inheritance in
   * resolve-metadata.js is guarded by `if (target)`. An empty object would be
   * enough to trigger it; these three fields are the ones inheritance cannot
   * supply.
   *
   * NOTHING BELOW THIS MAY BE PARTIALLY OVERRIDDEN. Metadata merging is
   * shallow: a route that sets `openGraph: { title }` replaces this whole
   * object and silently drops siteName, locale and type for that route. A
   * route either restates all of it or touches none of it, and every one of
   * them currently touches none.
   */
  openGraph: {
    siteName: "Ampeer",
    locale: "nl_NL",
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // lang="nl": the interface, the advice and the methodology are all Dutch,
    // and a screen reader that reads Dutch with an English voice is unusable.
    //
    // suppressHydrationWarning is here for one attribute and one only. The
    // inline script below writes data-theme on this element before React
    // exists, so the markup React hydrates against is not byte-for-byte the
    // markup it produced. This is React's documented answer for exactly that
    // case; it suppresses a warning about the server and client disagreeing on
    // this element's own attributes, not about anything inside it.
    <html
      lang="nl"
      suppressHydrationWarning
      className={`${body.variable} ${display.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-surface text-ink">
        {/*
         * Before anything is painted, so a visitor who chose dark on a light
         * system never watches the page flash white first. Rendered as the
         * children of a plain script element, which React 19 emits as inline
         * source; dangerouslySetInnerHTML is refused by .semgrep/frontend.yml
         * and this needs no exception to it.
         */}
        <script>{THEME_BOOTSTRAP}</script>
        {/*
          Who publishes this site, once, on every page. Plain script children
          rather than dangerouslySetInnerHTML, which .semgrep/frontend.yml
          forbids and which Next's own guide for this uses; see the note in
          _shell/JsonLd.tsx.
        */}
        <SiteJsonLd />
        <a className="skip-link" href={`#${MAIN_ID}`}>
          Naar de inhoud
        </a>
        <SiteHeader />
        <main id={MAIN_ID} tabIndex={-1} className="flex-1">
          {children}
        </main>
        <SiteFooter />
        {/*
          The question about measuring, on every page and after everything
          else: it is fixed to the viewport, so its place in the document
          only decides tab order, and a visitor should reach the content
          before the question about it. Renders nothing at all in a build
          without a measurement ID; see _shell/analytics.ts.
        */}
        <ConsentBanner />
      </body>
    </html>
  );
}
