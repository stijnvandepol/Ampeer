"use client";

import { useId, useSyncExternalStore } from "react";
import type { ThemeChoice } from "./theme";
import {
  setThemeChoice,
  subscribeThemeChoice,
  themeChoiceDuringBuild,
  themeChoiceSnapshot,
} from "./themeStore";

const CHOICES: readonly { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Systeem" },
  { value: "light", label: "Licht" },
  { value: "dark", label: "Donker" },
];

/**
 * The explicit light and dark choice, as a native select.
 *
 * Native because the keyboard and screen reader behaviour of a select is
 * behaviour nobody has to reimplement, and this control is worth none of the
 * code that reimplementing it would cost.
 *
 * The built HTML always says "Systeem", because the machine that built it has
 * no visitor to ask. That is not a flash of the wrong colours: the inline
 * script in the layout has already put the right palette on the page before
 * anything was painted. It is at most a select that says the wrong word until
 * React's first commit, which is the small half of the problem.
 */
export function ThemeToggle() {
  const id = useId();
  const choice = useSyncExternalStore(
    subscribeThemeChoice,
    themeChoiceSnapshot,
    themeChoiceDuringBuild,
  );

  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm text-ink-muted">
        Thema
      </label>
      <select
        id={id}
        value={choice}
        onChange={(event) => {
          const chosen = CHOICES.find((option) => option.value === event.target.value);
          if (chosen !== undefined) setThemeChoice(chosen.value);
        }}
        className="rounded-md border border-border-strong bg-surface px-2 py-1 text-sm text-ink"
      >
        {CHOICES.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
