import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/*
 * Required, not decorative. next.config.ts sets `output: "export"`, and an
 * image route is a route: without this Next refuses the build outright with
 * "export const dynamic = force-static not configured on route
 * /opengraph-image". It is the right answer rather than a way past the error,
 * because this picture depends on nothing per request. There is no Node
 * process in production to render it in.
 */
export const dynamic = "force-static";

/**
 * The accessible name of the picture, which is what a screen reader announces
 * when somebody shares the link into a timeline or a chat.
 *
 * It describes the picture and not the product, because that is what alt text
 * is for and because a sales line read aloud in place of an image is the kind
 * of thing this site does not do.
 */
export const alt = "Ampeer, met een bandbreedte in plaats van een enkel getal";

/**
 * The one sentence on the card, which is the site description in
 * app/layout.tsx and is already in frontend/tests/ui-strings.txt.
 *
 * A share card is the last place to invent a new claim. Written here as a
 * constant so it is one string rather than a text node JSX may reflow.
 */
const SITE_LINE =
  "Reken uit wat het einde van de salderingsregeling uw huishouden kost, met de marge erbij.";

/** The palette, read off globals.css rather than invented here. */
const SURFACE = "#ffffff";
const INK = "#0e1519";
const INK_MUTED = "#45535f";
const ACCENT = "#0b6e63";
const TRACK = "#e8ecf0";
const BAND = "#1f7c70";

/**
 * The picture every share of this site shows.
 *
 * WHY THERE IS ONE AT ALL. Measured on the built site on 2026-09-13: no page
 * carried an `og:image`, so every link pasted into WhatsApp, LinkedIn or Slack
 * rendered as text on a blank card. That is not a ranking factor and it is a
 * real cost per share on a site whose whole distribution plan is somebody
 * sending it to somebody else.
 *
 * WHY A BAND AND NO NUMBER. The first of the five rules in frontend/CLAUDE.md
 * is that no figure is ever drawn larger than its own band, and it calls that
 * one stylistic decision the whole difference between a range and a big number
 * with decoration. A share card is where that rule is under the most pressure,
 * because a number is what would make somebody click. So the band is here and
 * the number is not: the track, the span and the midpoint marker, with nothing
 * written on any of them. There is nothing to read off it, which is the point.
 * Every euro figure this product knows comes out of a simulation of one
 * household, and a figure here would be a household nobody described.
 *
 * WHY THE WORDS ARE BORROWED. Both lines already exist: the second is the site
 * description in app/layout.tsx and is in frontend/tests/ui-strings.txt
 * already. A share card is the last place to invent a new claim, and reusing
 * the sentence the site already makes means this file cannot drift away from
 * it.
 *
 * ONE IMAGE FOR EVERY ROUTE, deliberately. Next resolves this file for the
 * whole tree, so /thuisbatterij/ and /zelf-verbruiken/ inherit it along with
 * their own og:title and og:description, which are the parts that differ. A
 * per route picture would be four more things to keep true.
 */
export default function OpengraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: SURFACE,
        padding: "72px 80px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        {/* The mark: a band in miniature, so the motif reads before the words. */}
        <div
          style={{
            display: "flex",
            width: 26,
            height: 26,
            borderRadius: 13,
            background: ACCENT,
          }}
        />
        <div style={{ fontSize: 40, fontWeight: 700, color: INK }}>Ampeer</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
        <div
          style={{
            display: "flex",
            fontSize: 58,
            lineHeight: 1.18,
            color: INK,
            // NO width AND NO maxWidth. Satori ignores `maxWidth` on a flex
            // node, measured on 2026-09-13: 940 and 1040 produced a
            // byte-identical PNG. So the wrap is the parent's 1040, which is
            // 1200 less this block's padding, and that is the three line
            // setting that reads best. An explicit `width: 900` does work and
            // gives four lines, which is worse.
            //
            // A KNOWN BLEMISH, left alone deliberately: Satori renders a
            // wider space after the two longest words, "salderingsregeling"
            // and "huishouden". The string itself is clean, checked byte by
            // byte, so it is text shaping in the renderer and not the copy.
            // Fixing it means shipping a font file for Satori to use instead
            // of its bundled fallback, and the site's own face comes from
            // next/font/google at build time with nothing on disk to hand
            // over. At the size a card renders in a chat window it is not
            // visible. Written down so the next person does not spend the
            // afternoon on it that this took.
          }}
        >
          {/*
              One expression and not a wrapped text node. Satori keeps the
              newline and the indentation that JSX would normally collapse, and
              the rendered picture showed a double space between
              "salderingsregeling" and "uw". Seen on 2026-09-13 by looking at
              the PNG the running stack served, which is the only place it is
              visible at all.
            */}
          {SITE_LINE}
        </div>

        {/* The band. A track, the span it covers, and where the middle sits. */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div
            style={{
              display: "flex",
              width: 1040,
              height: 22,
              borderRadius: 11,
              background: TRACK,
              alignItems: "center",
            }}
          >
            <div
              style={{
                display: "flex",
                marginLeft: 208,
                width: 520,
                height: 22,
                borderRadius: 11,
                background: BAND,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  display: "flex",
                  width: 6,
                  height: 38,
                  borderRadius: 3,
                  background: INK,
                }}
              />
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", fontSize: 30, color: INK_MUTED }}>
        ampeer.nl
      </div>
    </div>,
    size,
  );
}
