"use client";

import { useRef, type PointerEvent, type ReactNode } from "react";
import { useReducedMotion } from "@/design/motion";
import styles from "./magnetic.module.css";

/**
 * A wrapper that leans its child towards the pointer.
 *
 * WHERE TO TUNE IT. `PULL` below is the share of the distance from the middle
 * that the child travels, and `RANGE_PX` is how far outside the element the
 * pull still reaches. `magnetic.module.css` holds `--magnet-ease`, which is
 * only used on the way back: the follow itself is not eased, because an eased
 * follow lags the cursor and reads as a dropped frame.
 *
 * ONE NOTE ON WHERE THIS IS USED, because it is a judgement rather than a rule.
 * Chapter 2 of the frontend spec says motion may draw attention to uncertainty
 * and never to a purchase. Nothing on this site is a purchase, and the control
 * this wraps leads to four questions rather than to a seller, so it is inside
 * the rule as written. It is still the most persuasive thing on the page, and
 * it is used exactly once: on the way in. A second one turns a considered
 * detail into a technique.
 *
 * `transform` only, on one element, written straight to the style attribute. No
 * React state, so a pointer move is not a render.
 */

/** How far towards the cursor, as a share of the distance from the middle. */
const PULL = 0.22;

/** How far outside the element the pull still reaches, in pixels. */
const RANGE_PX = 44;

interface Props {
  readonly children: ReactNode;
  /*
   * `| undefined` spelled out because exactOptionalPropertyTypes is on. A CSS
   * module's export is typed `string | undefined`, so every caller passing one
   * of these through is a type error without it.
   */
  readonly className?: string | undefined;
}

export function Magnetic({ children, className }: Props) {
  const host = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();

  function lean(event: PointerEvent<HTMLSpanElement>) {
    const element = host.current;
    if (element === null) return;
    const box = element.getBoundingClientRect();
    const x = event.clientX - (box.left + box.width / 2);
    const y = event.clientY - (box.top + box.height / 2);
    // Outside the reach, sit still. Without this the child creeps whenever the
    // pointer is anywhere on the page, which is uncanny rather than pleasant.
    const outside =
      Math.abs(x) > box.width / 2 + RANGE_PX ||
      Math.abs(y) > box.height / 2 + RANGE_PX;
    if (outside) return release();
    element.dataset["leaning"] = "true";
    element.style.transform = `translate(${(x * PULL).toFixed(2)}px, ${(y * PULL).toFixed(2)}px)`;
  }

  function release() {
    const element = host.current;
    if (element === null) return;
    // The attribute is what turns the transition on, so the way back is eased
    // and the way there is not.
    element.dataset["leaning"] = "false";
    element.style.transform = "";
  }

  if (reduced) {
    return <span className={className}>{children}</span>;
  }

  return (
    <span
      ref={host}
      data-role="magnetic"
      data-leaning="false"
      className={`${styles.magnet} ${className ?? ""}`}
      onPointerMove={lean}
      onPointerLeave={release}
      // A keyboard visitor never moves a pointer, so the child would otherwise
      // sit still while focused. It stays still: there is nothing here for
      // focus to express, and a control that jumps when focused is worse than
      // one that does not move.
      onBlur={release}
    >
      {children}
    </span>
  );
}
