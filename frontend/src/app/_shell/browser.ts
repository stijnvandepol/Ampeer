"use client";

import { useSyncExternalStore } from "react";

/**
 * The three things about the browser this site needs, read the way React 19
 * wants them read.
 *
 * The site is statically built, so the first render happens on a machine that
 * has no URL, no storage and no visitor. Reading any of that in an effect and
 * calling setState is a cascading render and the lint rule that says so is
 * right: it renders once with an answer nobody wants, then again with the real
 * one. useSyncExternalStore is React's answer, and it is the same one
 * `src/design/motion.ts` already uses for matchMedia. The server snapshot is
 * what the built HTML contains, so a page that cannot know yet renders the
 * state that says it does not know yet, rather than a state that is wrong.
 *
 * Every snapshot below returns a primitive. That is not a coincidence: React
 * calls getSnapshot on every render and compares with Object.is, so a snapshot
 * that builds a fresh object each time is an infinite loop. Anything with a
 * shape has to be cached by the store that owns it, which is what
 * `_flow/store.ts` does.
 */

/**
 * A URL does not change under a page. It changes by navigating, and a
 * navigation renders again anyway, so there is nothing to subscribe to.
 */
const NOTHING_TO_SUBSCRIBE_TO = () => () => {};

/** The full URL, or the empty string while it is not known. */
export function useLocationHref(): string {
  return useSyncExternalStore(
    NOTHING_TO_SUBSCRIBE_TO,
    () => window.location.href,
    () => "",
  );
}

/** The path, or undefined while it is not known. Undefined is not "no path". */
export function useLocationPath(): string | undefined {
  return useSyncExternalStore(
    NOTHING_TO_SUBSCRIBE_TO,
    () => window.location.pathname,
    () => undefined,
  );
}

/**
 * One query parameter: its value, null when the URL has none, and undefined
 * while the URL is not known.
 *
 * Three states rather than two, because a page that renders the absent case
 * during the build would put the wrong screen in the static HTML and swap it
 * out on hydration. Not `useSearchParams` from next/navigation: that one asks
 * for a Suspense boundary under `output: "export"`, which is a lot of
 * machinery for a value this page reads once.
 */
export function useSearchParam(name: string): string | null | undefined {
  return useSyncExternalStore(
    NOTHING_TO_SUBSCRIBE_TO,
    () => new URLSearchParams(window.location.search).get(name),
    () => undefined,
  );
}
