"use client";

import { useEffect, useRef } from "react";
import { useReducedMotion } from "@/design/motion";
import styles from "./cursor.module.css";

/**
 * A ring that follows the pointer and grows over anything interactive.
 *
 * WHERE TO TUNE IT. `cursor.module.css`: `--ring-size` at rest,
 * `--ring-grown` over a control, `--ring-ease` how long it takes to change
 * size, and `--ring-follow` how far behind the pointer it trails. Follow at 0
 * pins it exactly to the cursor; the shipped value gives it a little weight.
 *
 * IT DOES NOT REPLACE THE SYSTEM CURSOR, and that is deliberate rather than
 * unfinished. Hiding the real one takes away every setting a visitor has made
 * about it: size, contrast, the pointer trail, the shake-to-find. Those are
 * accessibility settings for people who need help finding a cursor, and a site
 * that hides theirs is removing the accommodation. This draws beside it.
 *
 * WHERE IT DOES NOT APPEAR. Any device without a fine pointer, checked in the
 * stylesheet with `(pointer: fine)` rather than by guessing from width: a touch
 * screen has no cursor to decorate, and a phone would paint a ring wherever the
 * last tap landed. Also not under prefers-reduced-motion, where a continuously
 * moving object with no end state has nothing to fall back to.
 *
 * The listener is passive and writes two custom properties on one element. No
 * React state, so a pointer move is not a render.
 */
export function Cursor() {
  const ring = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    const element = ring.current;
    if (element === null || reduced) return;
    // The same question the stylesheet asks, asked here too, so no listener is
    // attached on a touch device at all.
    if (!window.matchMedia("(pointer: fine)").matches) return;

    function move(event: PointerEvent) {
      element?.style.setProperty("--ring-x", `${event.clientX}px`);
      element?.style.setProperty("--ring-y", `${event.clientY}px`);
      const over = (event.target as Element | null)?.closest(
        "a, button, input, select, textarea, [tabindex]:not([tabindex='-1'])",
      );
      element?.style.setProperty("--ring-over", over === null ? "0" : "1");
    }

    function leave() {
      element?.style.setProperty("--ring-shown", "0");
    }

    function enter() {
      element?.style.setProperty("--ring-shown", "1");
    }

    window.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    document.addEventListener("pointerenter", enter);
    return () => {
      window.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
      document.removeEventListener("pointerenter", enter);
    };
  }, [reduced]);

  if (reduced) return null;

  return (
    <div
      ref={ring}
      className={styles.ring}
      aria-hidden="true"
      data-role="cursor"
    />
  );
}
