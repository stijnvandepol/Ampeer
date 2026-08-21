import { describe, expect, it } from "vitest";
import {
  DEFAULT_THEME_CHOICE,
  THEME_ATTRIBUTE,
  THEME_BOOTSTRAP,
  THEME_STORAGE_KEY,
  applyChoice,
  readStoredChoice,
  writeStoredChoice,
} from "@/app/_shell/theme";
import { ADVICE_BASE_PATH, advicePath, tokenFromPath } from "@/app/_advice/link";

function memoryStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    removeItem: (key: string) => void map.delete(key),
    map,
  };
}

function throwingStorage() {
  const raise = () => {
    throw new Error("storage is blocked");
  };
  return { getItem: raise, setItem: raise, removeItem: raise };
}

describe("the explicit light and dark choice", () => {
  it("follows the system until somebody says otherwise", () => {
    expect(readStoredChoice(memoryStorage())).toBe(DEFAULT_THEME_CHOICE);
    expect(readStoredChoice(undefined)).toBe("system");
    expect(readStoredChoice(memoryStorage({ [THEME_STORAGE_KEY]: "solarized" }))).toBe("system");
  });

  it("reads back a stored choice", () => {
    expect(readStoredChoice(memoryStorage({ [THEME_STORAGE_KEY]: "dark" }))).toBe("dark");
    expect(readStoredChoice(memoryStorage({ [THEME_STORAGE_KEY]: "light" }))).toBe("light");
  });

  it("stores a choice and removes it again when the visitor goes back to the system", () => {
    const storage = memoryStorage();
    writeStoredChoice(storage, "dark");
    expect(storage.map.get(THEME_STORAGE_KEY)).toBe("dark");
    writeStoredChoice(storage, "system");
    expect(storage.map.has(THEME_STORAGE_KEY)).toBe(false);
  });

  it("survives a browser that refuses storage entirely", () => {
    expect(readStoredChoice(throwingStorage())).toBe("system");
    expect(() => writeStoredChoice(throwingStorage(), "dark")).not.toThrow();
    expect(() => writeStoredChoice(undefined, "dark")).not.toThrow();
  });

  it("puts the choice where the stylesheet can see it, and takes it away again", () => {
    const root = document.createElement("html");
    applyChoice(root, "dark");
    expect(root.getAttribute(THEME_ATTRIBUTE)).toBe("dark");
    applyChoice(root, "system");
    expect(root.hasAttribute(THEME_ATTRIBUTE)).toBe(false);
  });

  it("bootstraps the same decision, and can only ever set a palette that exists", () => {
    // The script runs before React exists, so it cannot import any of the
    // above. What it can do is agree with it, which is what this checks: the
    // key and the attribute are the same two strings, and the only values it
    // will write are the two the stylesheet defines. That it actually runs and
    // actually beats the first paint is checked in a real browser, in
    // e2e/theme.spec.ts, because that is the only place the question is real.
    expect(THEME_BOOTSTRAP).toContain(`"${THEME_STORAGE_KEY}"`);
    expect(THEME_BOOTSTRAP).toContain(`"${THEME_ATTRIBUTE}"`);
    expect(THEME_BOOTSTRAP).toContain('c==="light"||c==="dark"');
    // Storage can throw rather than return null, and an exception here would
    // stop the page before anything else ran.
    expect(THEME_BOOTSTRAP.startsWith("try{")).toBe(true);
    expect(THEME_BOOTSTRAP).toContain("catch");
    // Nothing that would close the script element it is rendered inside.
    expect(THEME_BOOTSTRAP).not.toContain("</script");
  });
});

describe("the shareable link", () => {
  it("puts the token in the path, with the trailing slash next.config.ts produces", () => {
    expect(advicePath("FIXTUREfixture00000000")).toBe("/advies/FIXTUREfixture00000000/");
    expect(advicePath("x").startsWith(`${ADVICE_BASE_PATH}/`)).toBe(true);
  });

  it("reads the token back out of a pathname", () => {
    expect(tokenFromPath("/advies/FIXTUREfixture00000000/")).toBe("FIXTUREfixture00000000");
    expect(tokenFromPath("/advies/FIXTUREfixture00000000")).toBe("FIXTUREfixture00000000");
  });

  it("says there is none rather than guessing", () => {
    expect(tokenFromPath("/advies/")).toBeNull();
    expect(tokenFromPath("/advies")).toBeNull();
    expect(tokenFromPath("/")).toBeNull();
  });

  it("does not decide whether the token is one the API issued", () => {
    // getAdvice owns the shape, in one place. Two definitions of a token is
    // how the two end up disagreeing.
    expect(tokenFromPath("/advies/nietEenToken/")).toBe("nietEenToken");
  });
});
