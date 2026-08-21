/**
 * Light and dark, with an explicit choice that beats the system preference.
 *
 * `globals.css` defines four complete palettes: bare `:root` for light, a
 * `prefers-color-scheme: dark` block, and `[data-theme="light"]` and
 * `[data-theme="dark"]` for the explicit choice. Nothing sets that attribute
 * on its own, so this module is the half that makes the choice real.
 *
 * The choice is a display preference and not household data, so it lives in
 * `localStorage` and survives the tab. The answers to the questions do not:
 * they are consumption data about a household and go in `sessionStorage`. The
 * two storages are used for two different things on purpose, and the
 * difference is the point rather than an inconsistency.
 */

/** The two palettes, which are the two values `data-theme` may hold. */
export type Theme = "light" | "dark";

/** What the visitor picked. "system" means: do not set the attribute at all. */
export type ThemeChoice = Theme | "system";

/** The attribute `globals.css` selects on. */
export const THEME_ATTRIBUTE = "data-theme";

/** Dutch because a visitor may read it in their own developer tools. */
export const THEME_STORAGE_KEY = "ampeer-thema";

/** The default: follow the operating system, which is what most people want. */
export const DEFAULT_THEME_CHOICE: ThemeChoice = "system";

function isTheme(value: string | null): value is Theme {
  return value === "light" || value === "dark";
}

/**
 * The stored choice, or "system" for anything else.
 *
 * Storage can throw rather than return null: Safari in private browsing and a
 * cookie-blocking setting both raise on access. A theme that cannot be read is
 * not an error worth telling anybody about, so it falls back to the system
 * preference, which is the state the page was already in.
 */
export function readStoredChoice(
  storage: Pick<Storage, "getItem"> | undefined,
): ThemeChoice {
  if (storage === undefined) return DEFAULT_THEME_CHOICE;
  try {
    const stored = storage.getItem(THEME_STORAGE_KEY);
    return isTheme(stored) ? stored : DEFAULT_THEME_CHOICE;
  } catch {
    return DEFAULT_THEME_CHOICE;
  }
}

/** Writes the choice, or removes it when the visitor goes back to the system. */
export function writeStoredChoice(
  storage: Pick<Storage, "setItem" | "removeItem"> | undefined,
  choice: ThemeChoice,
): void {
  if (storage === undefined) return;
  try {
    if (choice === "system") storage.removeItem(THEME_STORAGE_KEY);
    else storage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // A visitor who blocks storage still gets the theme they clicked for this
    // page load. Refusing to switch because the choice cannot be remembered
    // would be worse than forgetting it.
  }
}

/** Puts the choice on the root element, where the CSS can see it. */
export function applyChoice(root: Element, choice: ThemeChoice): void {
  if (choice === "system") root.removeAttribute(THEME_ATTRIBUTE);
  else root.setAttribute(THEME_ATTRIBUTE, choice);
}

/**
 * The same three lines again, as source, to run before the first paint.
 *
 * This is duplication and it is deliberate. React sets the attribute after
 * hydration, which is several hundred milliseconds after the browser has
 * already painted the page in whichever palette the system preference asked
 * for. A visitor whose system says light and who chose dark would watch the
 * page flash white first, every single time. The only place that can be fixed
 * is before any framework code runs.
 *
 * It is rendered as the children of a plain `<script>`, which React 19 renders
 * as inline source. Not `dangerouslySetInnerHTML`: `.semgrep/frontend.yml`
 * fails the build on that prop and it is right to, because the prop's other
 * uses in a page like this one are the dangerous ones.
 *
 * The only two values interpolated are the two constants above, both literals
 * written in this file, so that the script and the TypeScript cannot drift on
 * the name of the key. Nothing else may ever be spliced in: a value from
 * storage, from the URL or from the API would turn this string into the script
 * injection the semgrep rule exists to prevent.
 */
export const THEME_BOOTSTRAP = `try{var c=localStorage.getItem("${THEME_STORAGE_KEY}");if(c==="light"||c==="dark"){document.documentElement.setAttribute("${THEME_ATTRIBUTE}",c)}}catch(e){}`;
