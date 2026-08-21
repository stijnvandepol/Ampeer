"use client";

import { useSyncExternalStore } from "react";

import { DURATION } from "@/design/tokens";

/**
 * Motion is allowed to draw attention to uncertainty and never to a purchase.
 *
 * Re-exported so a component can import one module for everything about
 * movement. globals.css is the other half: it disables animation under
 * prefers-reduced-motion rather than shortening it, and flips the two
 * data-motion slots so a component that was saying something by moving says it
 * in words instead.
 */
export { DURATION };

/** The query, in one place, so the hook and any test agree on its spelling. */
export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  const query = window.matchMedia(REDUCED_MOTION_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function readPreference(): boolean {
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/**
 * The value during the static build, where there is no visitor to ask.
 *
 * False rather than true, because the alternative is worse in a way that is
 * easy to miss: rendering the reduced branch on the server and swapping to the
 * animated one on hydration would start a movement the visitor has just asked
 * not to have, on the machine of the one person who must not see it.
 */
function preferenceDuringBuild(): boolean {
  return false;
}

/**
 * True when the visitor asked for less movement.
 *
 * Used to choose a different presentation, never to shorten the same one.
 * Meaning that lives only in a movement is meaning this visitor does not get,
 * so the reduced branch has to say the thing rather than say it faster.
 *
 * useSyncExternalStore rather than useState plus useEffect: matchMedia is an
 * external store, and reading it in an effect means one render with the wrong
 * answer before the right one, which for this particular preference is one
 * render in which an animation may already have begun. Prefer the CSS route
 * where there is one; `[data-motion]` in globals.css needs no JavaScript at all
 * and therefore has no first paint to get wrong.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, readPreference, preferenceDuringBuild);
}

/**
 * The attribute that picks which half of a motion pair is shown.
 *
 * A component that carries information in a transition renders both halves and
 * marks them with this, so the CSS decides which one the visitor sees. Doing it
 * in CSS rather than in JavaScript means the right half is in the first paint,
 * with no flash of the wrong one while React hydrates.
 *
 *     <span {...motionSlot("animated")}>…the moving version…</span>
 *     <span {...motionSlot("static")}>…the same fact, written out…</span>
 */
export function motionSlot(slot: "animated" | "static"): { "data-motion": "animated" | "static" } {
  return { "data-motion": slot };
}
