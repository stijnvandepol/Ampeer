"use client";

import {
  EMPTY_ANSWERS,
  loadAnswers,
  saveAnswers,
  type Answers,
} from "./answers";

/**
 * sessionStorage as one store React can subscribe to.
 *
 * The answers live in the browser's storage and not in a component, which is
 * what makes this an external store rather than useState plus two effects. It
 * also removes the effect that wrote them back: there is one path that changes
 * an answer, and it is the one that saves it, so the two cannot get out of
 * step.
 *
 * The snapshot has to be the same object between renders or React's Object.is
 * check never settles, so the parsed answers are cached here and replaced only
 * when something is written. That cache is the whole reason this module exists
 * rather than a hook that calls loadAnswers.
 */

let cached: Answers | null = null;
const listeners = new Set<() => void>();

export function subscribeAnswers(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The answers in this tab, read once and kept. */
export function answersSnapshot(): Answers {
  if (cached === null) cached = loadAnswers(window.sessionStorage);
  return cached;
}

/**
 * Null, because the machine that builds the site has no half-filled form.
 *
 * Null and not EMPTY_ANSWERS: those are two different states and the page
 * shows different things for them. An empty form is a form; not knowing yet is
 * the moment before the browser has been asked, and rendering the first for
 * the second would put a form in the static HTML and replace it on hydration.
 */
export function answersDuringBuild(): Answers | null {
  return null;
}

export function updateAnswers(change: Partial<Answers>): void {
  cached = { ...answersSnapshot(), ...change };
  saveAnswers(window.sessionStorage, cached);
  for (const listener of listeners) listener();
}

/** Forgets the cache, so the next read goes back to storage. For tests. */
export function forgetCachedAnswers(): void {
  cached = null;
}

/** Exported so a caller can compare against the state where nothing is answered. */
export { EMPTY_ANSWERS };
