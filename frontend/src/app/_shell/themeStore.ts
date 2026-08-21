"use client";

import {
  DEFAULT_THEME_CHOICE,
  applyChoice,
  readStoredChoice,
  writeStoredChoice,
  type ThemeChoice,
} from "./theme";

/**
 * localStorage and the root element, as one store React can subscribe to.
 *
 * The choice lives in the browser and not in React, which is what makes it an
 * external store rather than component state. Reading it in an effect and
 * calling setState would render the select with the wrong word first and the
 * right one a tick later, for no gain; here the first render says "Systeem"
 * because that is what the static HTML says, and the real value arrives in the
 * same commit React would have done the second render in.
 *
 * The snapshot is a string, so React's Object.is comparison settles after one
 * read. A store returning an object here would loop.
 */

const listeners = new Set<() => void>();

export function subscribeThemeChoice(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function themeChoiceSnapshot(): ThemeChoice {
  return readStoredChoice(window.localStorage);
}

/** What the built HTML contains, and what React hydrates against. */
export function themeChoiceDuringBuild(): ThemeChoice {
  return DEFAULT_THEME_CHOICE;
}

export function setThemeChoice(choice: ThemeChoice): void {
  writeStoredChoice(window.localStorage, choice);
  applyChoice(document.documentElement, choice);
  for (const listener of listeners) listener();
}
