import type { Metadata } from "next";
import Link from "next/link";

import { JsonLd } from "../_shell/JsonLd";
import { SITE_ORIGIN } from "../_shell/site";

/**
 * A layout that exists for two reasons: to give this route a title, and to
 * give it a body.
 *
 * The title half has the same reason and the same shape as
 * `advies/layout.tsx`. `page.tsx` beside it is a client component, because the
 * answers live in browser storage and the round comes off the query string,
 * and a client component cannot export `metadata`.
 *
 * Found on 2026-08-31 by measuring the built site rather than reading it: this
 * route shipped `<title>Ampeer</title>`, the root default. It is the page every
 * marketing link points at and the one a visitor is most likely to leave open
 * in a tab while they go and find their annual bill, so it was the worst route
 * on the site to have no name of its own.
 *
 * `e2e/rules.spec.ts` has a test that the four routes do not all answer to the
 * same title, and it passed: "Ampeer" is genuinely distinct from the other
 * three. The gate was green on the defect, which is the shape of a check that
 * measures difference where the thing that matters is meaning.
 *
 * THE BODY HALF, added 2026-09-02, is the same kind of finding one level
 * deeper. Measured on the built `out/berekenen/index.html`: 32 words of body
 * text and no `<h1>` at all, because everything on the route sat behind
 * hydration and the pre-hydration render is one sentence saying the questions
 * are on their way. Googlebot spends render budget to see anything here, and
 * the retrieval crawlers that decide what an AI answer cites (OAI-SearchBot,
 * PerplexityBot, Claude-SearchBot) largely do not run JavaScript at retrieval
 * time, so to them the one page a summary cannot answer away was blank.
 *
 * So the durable half of the page moved up here, where it is server rendered
 * for everybody and not only for a crawler: the heading, what the calculator
 * does, which questions it asks, and what nobody is being sold. The flow
 * renders between the two and is otherwise untouched. This is deliberately not
 * a `<noscript>` block and not a second page: a crawler that does run
 * JavaScript has to find the same words a visitor reads.
 */
const PATH = "/berekenen/";

/**
 * The name of this page, written once and used twice.
 *
 * The `<title>` and the `<h1>` disagreed until 2026-09-02: the tab said "Uw
 * situatie doorrekenen" and the heading said "Uw gegevens", so a screen reader
 * announced one name for the page on arrival and a different one at the first
 * heading. One constant, referenced by both, is the only arrangement in which
 * they cannot drift apart again.
 *
 * "Uw situatie doorrekenen" and not "Bereken wat de saldering u kost". This
 * page is read before anything has been computed, so a name that states a cost
 * presumes the answer, which is the rule the landing page's own title comment
 * states. It also has to hold for both rounds, and round two is a refinement
 * rather than a first calculation.
 */
const PAGE_TITLE = "Uw situatie doorrekenen";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  /*
   * Its own, rather than the site's. Until 2026-08-31 this route inherited the
   * root layout's description, which describes the product rather than this
   * page, so the one route a marketing link points at was described in a search
   * result by a sentence about something else.
   */
  description:
    "Vier vragen over uw dak en uw verbruik. Geen account, geen e-mailadres, en niets aan uw meterkast. U krijgt een bedrag met de bandbreedte erbij.",
  alternates: { canonical: PATH },
};

/**
 * The calculator, as a thing rather than as a page.
 *
 * `WebApplication` and NOT a rich result, and the difference is worth writing
 * down because somebody will otherwise try to close the gap. Google's Software
 * App result needs `aggregateRating` or `review` on top of what is here, and
 * this product has neither: nobody has rated it, and a rating a neutral
 * advisor supplied about itself is the first thing that would stop it being
 * neutral. So Search Console will report a missing rating for this markup
 * forever, and that warning is the correct state of it. If it proves too
 * tempting to silence, delete the type rather than acquire a rating.
 *
 * `offers` at zero is not a marketing claim. It is how schema.org says free,
 * and the page says the same thing in its own words.
 */
function CalculatorJsonLd() {
  return (
    <JsonLd
      data={{
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "@id": `${SITE_ORIGIN}${PATH}#rekenmachine`,
        name: "Ampeer",
        url: `${SITE_ORIGIN}${PATH}`,
        applicationCategory: "UtilitiesApplication",
        operatingSystem: "Web",
        inLanguage: "nl-NL",
        isAccessibleForFree: true,
        offers: { "@type": "Offer", price: "0", priceCurrency: "EUR" },
        isPartOf: { "@id": `${SITE_ORIGIN}/#website` },
      }}
    />
  );
}

/**
 * What this page is, for a reader who has not pressed anything yet.
 *
 * Deliberately about the calculator and not about the end of netting. The long
 * explanation of the regulation is `/einde-saldering/`, 1418 words of it, and
 * repeating that here would be two pages competing for one query with half a
 * page each. What sits here is the part only this route can answer: which
 * questions it asks, what comes back, and what nobody is being sold.
 *
 * Below the flow rather than above it. A visitor who arrived to answer four
 * questions should meet the first question and not a page about questions; a
 * crawler reads the whole document and does not care in which order.
 */
function WhatThisCalculates() {
  return (
    <section
      aria-labelledby="over-de-rekenmachine"
      className="border-t border-current/15 pt-10"
    >
      {/*
        Folded shut since 2026-09-15, and the number is why. Measured on the
        built page at 400 pixels wide: this block was 1656 of the page's 2401
        pixels, sixty-nine per cent, and it sat under every one of the nine
        questions. Somebody answering question seven met two and a half screens
        of prose about a page they were already three quarters through.

        A disclosure rather than a deletion. Every word is still in the
        document, so a crawler reads all of it and the one visitor in twenty
        who wants to know what this thing is before typing a postcode is one
        click away. What changes is who pays for it: the reader who wanted it,
        rather than everybody.
      */}
      {/*
        CLOSED IN THE HTML, and with no script to close it.

        The first version shipped `open` and an inline script after the element
        that stripped the attribute, on the assumption that a script the parser
        meets inside the section runs before the first paint. Measured on
        2026-09-15 with a PerformanceObserver on the built page at 400 pixels
        wide: the browser painted the block open, ran the script at 126 ms, and
        recorded a layout shift of 0.073 for the section plus the footer under
        it. Lighthouse read the same page as CLS 0.095, the one number on the
        site above zero. An assumption about paint timing is not a measurement.

        Nothing is lost by shipping it shut. A disclosure is native HTML: a
        reader without JavaScript clicks the summary and gets every word, which
        is what e2e/form.spec.ts now does in its no-script run. Googlebot
        indexes the content of a collapsed disclosure since the switch to
        mobile-first indexing, and the retrieval crawlers read the document
        rather than the rendering. What the fold changes is who sees the prose
        first, not who can find it.
      */}
      <details id="over-de-rekenmachine-blok" className="flex flex-col gap-4">
        <summary
          id="over-de-rekenmachine"
          className="cursor-pointer text-2xl marker:text-ink-muted"
        >
          Wat u op deze pagina berekent
        </summary>
        <div className="flex flex-col gap-4 pt-4">
          <p className="text-ink-muted">
            De salderingsregeling stopt op 1 januari 2027. Wat dat u kost hangt
            niet af van hoeveel panelen u heeft, maar van hoeveel van uw eigen
            opwek u zelf gebruikt, en dat verschilt sterk per huishouden. Deze
            rekenmachine bouwt uit uw antwoorden een kwartierprofiel van een
            heel jaar op en rekent dat door op de tarieven van nu en die van
            2027.
          </p>

          <h3 className="text-lg font-medium">De vier vragen</h3>
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-ink-muted">
            <li>
              De eerste vier cijfers van uw postcode, voor de instraling in uw
              regio. Van uw postcode bewaren wij alleen die vier cijfers.
            </li>
            <li>Hoeveel wattpiek aan zonnepanelen er op uw dak ligt.</li>
            <li>
              Hoe het dak ligt: welke kant het op ligt en hoe schuin het staat.
            </li>
            <li>
              Hoeveel stroom u per jaar verbruikt, zonder het laden van een
              elektrische auto en zonder een warmtepomp. Naar die twee vragen
              wij apart.
            </li>
          </ol>
          <p className="text-ink-muted">
            Meer niet. Er is geen account, wij vragen geen e-mailadres en er
            hoeft niets aan uw meterkast te gebeuren. Weet u een getal niet
            precies, dan is een schatting genoeg.
          </p>

          <h3 className="text-lg font-medium">
            Vijf vragen die het antwoord scherper maken
          </h3>
          <p className="text-ink-muted">
            Na uw eerste antwoord kunt u verfijnen: of er op een doordeweekse
            dag overdag meestal iemand thuis is, wanneer een elektrische auto
            laadt, of er een warmtepomp is, of uw contract dynamisch is, en of
            er al een thuisbatterij staat. Vier vragen geeft een indicatief
            antwoord, negen vragen een goed antwoord.
          </p>

          <h3 className="text-lg font-medium">Wat u terugkrijgt</h3>
          <p className="text-ink-muted">
            Een bedrag per jaar met de bandbreedte eromheen, hoe zeker dat
            antwoord is, en drie routes in vaste volgorde: uw eigen ritme
            verschuiven, slimmer sturen met wat u al heeft, en stroom opslaan in
            een thuisbatterij. De routes die niets kosten staan altijd bovenaan,
            ook als er bij u aan een ervan niets te halen valt.
          </p>
          <p className="text-ink-muted">
            Ampeer verkoopt geen zonnepanelen, geen thuisbatterijen en geen
            energiecontract, en plaatst geen advertenties. Niemand betaalt ons
            voor de uitkomst die u krijgt. Daarom is nu geen batterij hier een
            geldige uitkomst.
          </p>
          <p className="text-ink-muted">
            Meer over{" "}
            <Link href="/einde-saldering/">
              wat er op 1 januari 2027 verandert
            </Link>
            , over <Link href="/methodologie/">hoe wij dit uitrekenen</Link>, en
            over{" "}
            <Link href="/privacy/">
              wat er met uw postcode en uw verbruik gebeurt
            </Link>
            .
          </p>
        </div>
      </details>
    </section>
  );
}

export default function BerekenenLayout({
  children,
}: LayoutProps<"/berekenen">) {
  return (
    <>
      <CalculatorJsonLd />
      {/*
        The frame moved here from `page.tsx`, which carried a copy of it in each
        of its three branches. The site's width on the outside and a form's
        width on the inside: both were max-w-2xl and centred once, so the
        questions sat 176 pixels to the right of the wordmark above them on a
        1440 wide screen, because two centred columns of different widths never
        share an edge.
      */}
      <div className="mx-auto w-full max-w-[var(--shell-max)] px-6 py-16">
        <div className="flex w-full max-w-2xl flex-col gap-10">
          <div className="flex flex-col gap-3">
            <h1 className="text-3xl">{PAGE_TITLE}</h1>
            <p className="text-ink-muted">
              Vier vragen over uw dak en uw verbruik, en u ziet wat het einde
              van de salderingsregeling u per jaar gaat kosten. Met de
              bandbreedte erbij, want een enkel getal zou meer zekerheid
              suggereren dan er is.
            </p>
          </div>
          {/*
            The floor under the flow is a measured number and the reason the
            page stopped moving. Before hydration the flow is one line, "De
            vragen worden klaargezet.", 26 pixels tall; after it the first
            question stands 279 pixels tall at 400 wide, 314 at 1280 and 341
            at 320. Everything below, the explainer and the footer, moved by
            the difference, which Lighthouse read as CLS 0.095 and a
            PerformanceObserver on 2026-09-15 pinned to that swap at 310 ms.
            First suspected was the explainer's fold; measured with the fold
            shipped shut, the shift was identical, so the suspect was
            innocent and the placeholder was not.

            20rem is 320 pixels: at or above the first question at every
            width but 320, where the remaining shift is 21 pixels. It goes on
            the wrapper and not on the placeholder, because a floor on one
            state only moves the shift to the moment the other state arrives.
          */}
          <div className="min-h-[20rem]">{children}</div>
          <WhatThisCalculates />
        </div>
      </div>
    </>
  );
}
