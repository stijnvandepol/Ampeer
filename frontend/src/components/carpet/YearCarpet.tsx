"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import type { YearSeries } from "@/lib/types";
import { useReducedMotion } from "@/design/motion";
import { cellAt, decodeYear } from "./decode";
import { buildPixels, cssColour, paletteFrom } from "./palette";
import {
  acrossOf,
  cellFromPointer,
  dayLabel,
  downOf,
  dutchQuantity,
  monthsOf,
  moveCursor,
  quarterLabel,
  type Cursor,
} from "./geometry";
import styles from "./carpet.module.css";

/**
 * How long the year takes to draw itself in, in milliseconds.
 *
 * The plate arrives 1 January to 31 December rather than all at once, because
 * chronological is the only order this object has and a reader who watches it
 * arrive has learned the horizontal axis without being told. It is the one
 * movement on the page and it says something the still plate does not, which is
 * exactly the case globals.css keeps `prefers-reduced-motion` for: under that
 * preference the plate is simply complete, not drawn faster.
 */
const REVEAL_MS = 1200;

/** The vertical axis, from midnight to midnight. */
const HOUR_LABELS = ["00", "06", "12", "18", "24"];

/**
 * What the plate is, for somebody who cannot see it.
 *
 * The three colour names have to be the colours actually drawn, so they are
 * written as the palette resolves them: own is the amber, offtake is the paler
 * grey blue and export is the deeper blue. A description naming a colour the
 * stylesheet no longer uses is worse than no description, because it reads as
 * information.
 */
const PLATE_DESCRIPTION =
  "Een jaar in kwartieren. Van links naar rechts de dagen van het jaar, van boven naar beneden het etmaal van middernacht tot middernacht. Geel staat voor een kwartier waarin u vooral uw eigen opwek gebruikte, lichtgrijsblauw voor een kwartier waarin u vooral stroom van het net haalde, en donkerblauw voor een kwartier waarin u vooral stroom teruggaf aan het net.";

/** What the readout says when nothing is under the pointer or the cursor. */
const READOUT_IDLE =
  "Beweeg over de plaat of gebruik de pijltjestoetsen om een kwartier te lezen.";

interface Props {
  readonly year: YearSeries;
}

/**
 * A household's year, one pixel per quarter of an hour.
 *
 * 365 columns by 96 rows, drawn on a canvas at exactly that size and scaled up
 * by the stylesheet with smoothing off, so nothing between the model and the
 * screen invents a value. Every other calculator in this market draws twelve
 * bars; the argument this product makes is that the quarter is the unit, and
 * this is that argument as a picture rather than as a sentence.
 *
 * WHAT IS NOT DRAWN HERE. No totals, no percentage, no euro figure. The
 * payload is quantised to one byte a quarter, so anything summed out of it in
 * the browser would be a second answer to a question the API has already
 * answered, differing from it in the third digit and carrying no band. The one
 * number this component puts on the screen is a single quarter, which is the
 * thing the plate is made of and is read back out of the picture rather than
 * computed from it.
 *
 * The provenance on the payload is not rendered either. There is no
 * `provenance_text` beside it, and the alternative is a Dutch word for a model
 * enum written in the browser, which is the second copy of the model's
 * vocabulary that `lib/types.ts` exists to keep out. What the answer rests on
 * is already on this page, in the API's own sentence, under "Waarmee gerekend
 * is".
 */
export function YearCarpet({ year }: Props) {
  const decoded = useMemo(() => decodeYear(year), [year]);
  const reduced = useReducedMotion();
  const plate = useRef<HTMLCanvasElement>(null);
  const [cursor, setCursor] = useState<Cursor | null>(null);

  useEffect(() => {
    const element = plate.current;
    if (element === null || decoded === null) return;
    const context = element.getContext("2d");
    // A browser that hands back no 2d context draws nothing rather than
    // throwing on the whole advice page. The plate is the one thing here a
    // reader can do without.
    if (context === null) return;
    const palette = paletteFrom((name) =>
      window.getComputedStyle(document.documentElement).getPropertyValue(name),
    );
    // Same reasoning, and the reason there is no hardcoded fallback palette:
    // a colour that exists only in this file is a colour no contrast test can
    // see, which is how the band ended up drawn in an unmeasured blue.
    if (palette === null) return;

    const image = context.createImageData(decoded.days, decoded.quartersPerDay);
    image.data.set(buildPixels(decoded, palette));
    context.fillStyle = cssColour(palette.ground);
    context.fillRect(0, 0, decoded.days, decoded.quartersPerDay);

    const drawTo = (columns: number) => {
      if (columns > 0) {
        context.putImageData(
          image,
          0,
          0,
          0,
          0,
          columns,
          decoded.quartersPerDay,
        );
      }
    };

    if (reduced) {
      drawTo(decoded.days);
      return;
    }

    const started = performance.now();
    let frame = 0;
    const step = (now: number) => {
      // Eased out, so the year slows into December rather than stopping dead.
      const through = Math.min(1, (now - started) / REVEAL_MS);
      const columns = Math.round(decoded.days * through * (2 - through));
      drawTo(columns);
      // The edge the year is being written at, in the one saturated colour the
      // plate has. It is a single column on ground the next frame overwrites,
      // so it costs one fillRect and leaves nothing behind: at `through` of 1
      // the condition is false and the last column is data like every other.
      //
      // It is drawn rather than animated in CSS because it belongs to the
      // image. An element sliding over the canvas would be a second object
      // moving at its own speed, and this is the same object arriving.
      if (through < 1 && columns < decoded.days) {
        context.fillStyle = cssColour(palette.own);
        context.fillRect(columns, 0, 1, decoded.quartersPerDay);
      }
      if (through < 1) frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [decoded, reduced]);

  // A payload that does not describe a year draws nothing at all, and the page
  // around it is the page it was without this field. See decodeYear: every
  // refusal there is a payload that could only be drawn as a year that did not
  // happen.
  if (decoded === null) return null;

  const { days, quartersPerDay } = decoded;
  const reading =
    cursor === null ? null : cellAt(decoded, cursor.day, cursor.quarter);

  function readPointer(event: PointerEvent<HTMLCanvasElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    setCursor(
      cellFromPointer(
        (event.clientX - box.left) / box.width,
        (event.clientY - box.top) / box.height,
        days,
        quartersPerDay,
      ),
    );
  }

  function readKey(event: KeyboardEvent<HTMLCanvasElement>) {
    const next = moveCursor(cursor, event.key, days, quartersPerDay);
    // Only the four arrows are taken. Swallowing every key would take Tab and
    // Escape away from a visitor trying to leave the plate.
    if (next === null) return;
    event.preventDefault();
    setCursor(next);
  }

  return (
    <section
      aria-labelledby="jaar"
      data-role="year-carpet"
      className="flex flex-col gap-4"
    >
      <h2 id="jaar" className={styles.title}>
        Uw jaar in kwartieren
      </h2>
      <p className={styles.intro}>
        Elke kolom is een dag, van 1 januari links tot 31 december rechts. Elke
        rij is een kwartier, van middernacht boven tot middernacht onder.
      </p>

      <div className={styles.instrument}>
        <div className={styles.plate}>
          <div className={styles.hours} aria-hidden="true">
            {HOUR_LABELS.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
          <div className={styles.canvasCell}>
            <canvas
              ref={plate}
              width={days}
              height={quartersPerDay}
              role="img"
              tabIndex={0}
              aria-label={PLATE_DESCRIPTION}
              data-role="year-plate"
              className={styles.canvas}
              onPointerMove={readPointer}
              onPointerLeave={() => setCursor(null)}
              onKeyDown={readKey}
            />
            {/*
              Where the reader is, on the plate rather than only in the
              sentence below it. Hidden from the accessibility tree: the
              position it draws is already the words in the readout, and a
              second announcement of the same quarter would be read twice.
            */}
            <div
              aria-hidden="true"
              className={styles.crosshair}
              data-reading={cursor !== null}
              data-role="year-crosshair"
            >
              <span
                className={styles.day}
                style={{ left: acrossOf(cursor, days) }}
              />
              <span
                className={styles.quarter}
                style={{ top: downOf(cursor, quartersPerDay) }}
              />
              <span
                className={styles.mark}
                style={{
                  left: acrossOf(cursor, days),
                  top: downOf(cursor, quartersPerDay),
                }}
              />
            </div>
          </div>
          <div className={styles.months} aria-hidden="true">
            {monthsOf(days).map((month) => (
              <span
                key={month.label}
                className={styles.month}
                style={{ flexGrow: month.length }}
              >
                {month.label}
              </span>
            ))}
          </div>
        </div>

        <p className={styles.readout} data-role="year-readout">
          {reading === null ? (
            READOUT_IDLE
          ) : (
            <>
              <span className={styles.when}>
                {dayLabel(reading.day, days)} {quarterLabel(reading.quarter)}
              </span>
              <span>{dutchQuantity(reading.ownKwh, 2)} kWh zelf gebruikt</span>
              <span>
                {dutchQuantity(reading.meterKwh, 2)} kWh{" "}
                {reading.exported ? "teruggeleverd" : "van het net gehaald"}
              </span>
            </>
          )}
        </p>

        <ul className={styles.legend}>
          <li className={styles.entry}>
            <i
              aria-hidden="true"
              className={`${styles.swatch} ${styles.own}`}
            />
            zelf gebruikt
          </li>
          <li className={styles.entry}>
            <i
              aria-hidden="true"
              className={`${styles.swatch} ${styles.offtake}`}
            />
            van het net gehaald
          </li>
          <li className={styles.entry}>
            <i
              aria-hidden="true"
              className={`${styles.swatch} ${styles.export}`}
            />
            teruggeleverd
          </li>
        </ul>
      </div>
    </section>
  );
}
