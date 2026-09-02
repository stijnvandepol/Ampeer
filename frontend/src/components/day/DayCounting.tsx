"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  cellColour,
  cssColour,
  paletteFrom,
} from "@/components/carpet/palette";
import {
  QUARTERS,
  blockSizes,
  illustrativeDay,
  placeAt,
  sortedOrder,
} from "./shape";
import styles from "./day.module.css";

/**
 * The landing page's figure: the same day, in the two orders the rules put it.
 *
 * WHY IT IS A SORT AND NOT A COUNTDOWN. The one thing this page must not do is
 * manufacture urgency out of a calendar, and a landing page about a date is
 * where that gets added. So the figure carries the rule instead of the date:
 * saldering nets what crossed the meter over a whole year, which throws the
 * order in time away, and the quarters a household used itself never crossed
 * the meter at all. Moving the cells into blocks is that sentence as a
 * movement. Nothing here counts down to anything, and `.semgrep/frontend.yml`
 * forbids this tree from reading a clock so that it cannot start.
 *
 * WHY THE COLOURS COME FROM THE PLATE. `cellColour` is the advice page's own
 * function, reading the advice page's own tokens. A second lift rule here
 * would be a second set of colours outside the bands
 * `tests/carpet/palette.test.ts` measures, on a page where the same three
 * states mean the same three things. One rule, one measurement, and a reader
 * who arrives at the plate has already learned this vocabulary.
 *
 * WHAT A READER WITHOUT JAVASCRIPT GETS. Every cell carries its state as a
 * class, and the stylesheet paints it in that state's token, which is the FLOOR
 * of its band. The lift below is an upgrade on a picture that already says the
 * true thing, not the only thing that makes it appear.
 */

/** The two orders, as the control names them. */
type Order = "time" | "meter";

const LABELS: Readonly<Record<Order, string>> = {
  time: "Op tijd",
  meter: "Zoals salderen telt",
};

/** What the figure is, for somebody who cannot see it. */
const FIGURE_LABEL =
  "Een voorbeelddag van 96 kwartieren, van middernacht links tot middernacht rechts. Hoe hoger een staaf, hoe meer stroom er in dat kwartier omging. Geel is een kwartier waarin het huishouden vooral zijn eigen opwek gebruikte, lichtgrijsblauw een kwartier waarin het stroom van het net haalde, en donkerblauw een kwartier waarin het stroom teruggaf aan het net.";

export function DayCounting() {
  const day = useMemo(() => illustrativeDay(), []);
  const places = useMemo(() => sortedOrder(day), [day]);
  const counts = useMemo(() => blockSizes(day), [day]);
  const [order, setOrder] = useState<Order>("time");
  const strip = useRef<HTMLDivElement>(null);

  /*
   * The lift, applied after paint rather than during render.
   *
   * getComputedStyle needs a document, and this component is prerendered into
   * static HTML where there is none. Rendering the floor colour on the server
   * and lifting here means the markup React hydrates against is the markup it
   * produced, and the picture is correct at every moment in between.
   */
  useEffect(() => {
    const root = strip.current;
    if (root === null) return;
    const palette = paletteFrom((name) =>
      window.getComputedStyle(document.documentElement).getPropertyValue(name),
    );
    // No hardcoded fallback, for the reason palette.ts gives: a colour that
    // exists only in a component is a colour no contrast test can see.
    if (palette === null) return;
    for (const [index, quarter] of day.entries()) {
      const cell = root.children[index];
      if (!(cell instanceof HTMLElement)) continue;
      cell.style.background = cssColour(
        cellColour(palette, quarter.state, quarter.magnitude),
      );
    }
  }, [day]);

  return (
    <figure className={styles.figure}>
      <div
        className={styles.strip}
        data-order={order}
        role="img"
        aria-label={FIGURE_LABEL}
        ref={strip}
      >
        {day.map((quarter) => (
          <span
            key={quarter.at}
            className={`${styles.cell} ${styles[quarter.state]}`}
            style={{
              // Two positions on one element. The stylesheet picks between
              // them by [data-order], so the movement is a transition on a
              // custom property rather than a re-render, and React never sees
              // the intermediate frames.
              ["--at-time" as string]: placeAt(quarter.at, QUARTERS),
              ["--size" as string]: quarter.magnitude.toFixed(4),
              ["--at-meter" as string]: placeAt(
                places[quarter.at] ?? quarter.at,
                QUARTERS,
              ),
            }}
          />
        ))}
      </div>

      {/*
        The axis changes with the order, because in the sorted view a clock
        would be a lie: the cells are no longer in time. Watching 00:00 to
        24:00 be replaced by three block names is the figure's whole argument
        in its smallest form, so this is not a detail that could be left as a
        static row of times.

        Both rows are hidden from the accessibility tree. The times are the
        axis of a picture that is already described in one sentence on the
        strip itself, and the three counts are in the caption below as prose.
      */}
      {order === "time" ? (
        <div className={styles.axis} aria-hidden="true">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      ) : (
        <div className={styles.blocks} aria-hidden="true">
          {(
            [
              ["own", "zelf gebruikt"],
              ["offtake", "van het net"],
              ["export", "teruggeleverd"],
            ] as const
          ).map(([state, name]) => (
            <span
              key={state}
              className={styles.block}
              style={{ flexGrow: counts[state] }}
            >
              {name} {counts[state]}
            </span>
          ))}
        </div>
      )}

      <div className={styles.control} role="group" aria-label="Volgorde">
        {(["time", "meter"] as const).map((option) => (
          <button
            key={option}
            type="button"
            className={styles.choice}
            aria-pressed={order === option}
            onClick={() => setOrder(option)}
          >
            {LABELS[option]}
          </button>
        ))}
      </div>

      <figcaption className={styles.caption}>
        {order === "time" ? (
          <>
            Een voorbeelddag, geen berekening. {counts.own} van de 96 kwartieren
            gebruikte dit huishouden zijn eigen opwek, {counts.export} gaf het
            terug aan het net en {counts.offtake} haalde het eruit.
          </>
        ) : (
          <>
            Salderen kijkt alleen naar wat door de meter ging en telt dat over
            een heel jaar op. De volgorde in de tijd valt daarbij weg, en de{" "}
            {counts.own} gele kwartieren zaten er nooit in: die kwamen nooit
            langs de meter. Vanaf 2027 zijn dat juist de kwartieren die tellen.
          </>
        )}
      </figcaption>
    </figure>
  );
}
