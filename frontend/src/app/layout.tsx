import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteFooter } from "./_shell/SiteFooter";
import { SiteHeader } from "./_shell/SiteHeader";
import { THEME_BOOTSTRAP } from "./_shell/theme";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
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
        <a className="skip-link" href={`#${MAIN_ID}`}>
          Naar de inhoud
        </a>
        <SiteHeader />
        <main id={MAIN_ID} tabIndex={-1} className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
