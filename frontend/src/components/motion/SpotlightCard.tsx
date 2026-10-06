"use client";

import { useRef, type PointerEvent, type ReactNode } from "react";
import { useReducedMotion } from "@/design/motion";
import styles from "./spotlight.module.css";

/**
 * A card that lights where the pointer is, with a border that turns with it.
 *
 * WHERE TO TUNE IT. `spotlight.module.css`, on `.card`: `--spot-size` is the
 * radius of the light, `--spot-strength` its opacity, `--edge-strength` the
 * opacity of the rotating border, and `--spot-ease` how long the light takes
 * to fade in and out when the pointer arrives and leaves. The position itself
 * is not eased: a lagging spotlight reads as a dropped frame rather than as
 * smoothness.
 *
 * WHY IT WRITES CUSTOM PROPERTIES AND NOT STATE. Every pointer move would
 * otherwise be a React render of the whole card. Here the handler sets two
 * custom properties on one element, the browser recomputes one gradient, and
 * React is not involved at all. That is the difference between this holding
 * 60fps and this being the reason a page drops frames.
 *
 * WHAT IT IS WITHOUT A POINTER. Everything. The card is a bordered card with
 * its content; the light and the turning edge are the only things that go, and
 * neither carries information. Under prefers-reduced-motion no listener is
 * attached at all, because a spotlight has no end state to jump to.
 */

interface Props {
  readonly children: ReactNode;
  /*
   * `| undefined` spelled out because exactOptionalPropertyTypes is on. A CSS
   * module's export is typed `string | undefined`, so every caller passing one
   * of these through is a type error without it.
   */
  readonly className?: string | undefined;
}

export function SpotlightCard({ children, className }: Props) {
  const reduced = useReducedMotion();
  const card = useRef<HTMLDivElement>(null);

  function follow(event: PointerEvent<HTMLDivElement>) {
    const element = card.current;
    if (element === null) return;
    const box = element.getBoundingClientRect();
    const x = event.clientX - box.left;
    const y = event.clientY - box.top;
    element.style.setProperty("--spot-x", `${x}px`);
    element.style.setProperty("--spot-y", `${y}px`);
    // The angle the border gradient is turned to: where the pointer sits
    // relative to the middle. So the bright part of the edge is the part
    // nearest the cursor, which is what makes it read as light rather than as
    // a rotating decoration.
    const angle =
      (Math.atan2(y - box.height / 2, x - box.width / 2) * 180) / Math.PI;
    element.style.setProperty("--spot-angle", `${angle.toFixed(1)}deg`);
  }

  const handlers = reduced
    ? {}
    : {
        onPointerMove: follow,
        onPointerEnter: (event: PointerEvent<HTMLDivElement>) => {
          card.current?.style.setProperty("--spot-lit", "1");
          follow(event);
        },
        onPointerLeave: () => {
          card.current?.style.setProperty("--spot-lit", "0");
        },
      };

  return (
    <div
      ref={card}
      className={`${styles.card} ${className ?? ""}`}
      data-role="spotlight-card"
      {...handlers}
    >
      {children}
    </div>
  );
}
