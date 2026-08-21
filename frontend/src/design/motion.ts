"use client";

import { useSyncExternalStore } from "react";

import { DURATION } from "@/design/tokens";

/**
 * Motion is allowed to draw attention to uncertainty and never to a purchase.
 *
 * Re-exported so a component can import one module for everything about
 * movement. globals.css is the other half: it disables animation under
 * prefers-reduced-motion rather than shortening it, so a component that would
 * have said something by moving has to say it some other way.
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
 * render in which an animation may already have begun. Prefer a CSS route
 * where there is one: it needs no JavaScript at all and therefore has no first
 * paint to get wrong.
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, readPreference, preferenceDuringBuild);
}
