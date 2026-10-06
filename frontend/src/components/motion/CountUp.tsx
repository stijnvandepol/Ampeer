"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "@/design/motion";

/**
 * A whole number that counts up the first time it is scrolled to.
 *
 * WHERE TO TUNE IT. `DURATION_MS` and `THRESHOLD` below. The duration is the
 * whole run regardless of how large the number is, so 35040 and 3 take the same
 * time; counting per digit would make the large one interminable. `THRESHOLD`
 * is how much of the element has to be on screen before it starts.
 *
 * WHAT IT MAY NEVER BE USED ON. A euro amount. Rule one of the frontend spec
 * says no figure is drawn larger than its own band, and a ticking number has no
 * band; a euro figure that races upwards is drama applied to the one number
 * this product is most careful about. Everything this is used on is a count of
 * things that exist: quarters in a day, quarters in a year, routes on a page.
 * Those are facts about units and not claims about a household.
 *
 * WHAT A SCREEN READER GETS. The final number, once, and never the intermediate
 * values. The counting span is aria-hidden and the real figure sits beside it
 * in a visually hidden span, so nothing is announced 40 times.
 *
 * Under prefers-reduced-motion, and before the browser has run any script, the
 * final number is simply there. The count says nothing the number does not.
 */

/** The whole run, however large the number. */
const DURATION_MS = 1100;

/** How much of the element has to be visible before it starts. */
const THRESHOLD = 0.4;

/** Eased out, so it slows into its final value rather than stopping dead. */
function eased(through: number): number {
  return 1 - Math.pow(1 - through, 3);
}

interface Props {
  readonly to: number;
  /** Dutch thousands separators, for a number large enough to need them. */
  readonly grouped?: boolean;
}

export function CountUp({ to, grouped = false }: Props) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(to);
  const host = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const element = host.current;
    if (element === null || reduced) return;
    // Only when it can actually be watched. A browser without
    // IntersectionObserver keeps the final number, which is the correct
    // fallback rather than a number that never arrives.
    if (typeof IntersectionObserver === "undefined") return;

    let frame = 0;
    /*
     * null and not 0. A frame timestamp is legitimately 0 on the first frame
     * of a document, and with 0 as the sentinel the run then re-bases itself
     * on every frame and the number never moves off zero. Caught by the test
     * that drives the frames by hand with a first timestamp of 0.
     */
    let started: number | null = null;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        setShown(0);
        const step = (now: number) => {
          if (started === null) started = now;
          const through = Math.min(1, (now - started) / DURATION_MS);
          setShown(Math.round(to * eased(through)));
          if (through < 1) frame = window.requestAnimationFrame(step);
        };
        frame = window.requestAnimationFrame(step);
      },
      { threshold: THRESHOLD },
    );
    observer.observe(element);
    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
    };
  }, [to, reduced]);

  const format = (value: number) =>
    grouped ? value.toLocaleString("nl-NL") : String(value);

  return (
    <span ref={host} data-role="count-up">
      <span aria-hidden="true">{format(shown)}</span>
      <span className="sr-only">{format(to)}</span>
    </span>
  );
}
