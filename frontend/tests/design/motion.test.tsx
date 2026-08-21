/**
 * Reduced motion, checked as a removal rather than as a reduction.
 *
 * The plan's tokens test checks that `animation-duration: 0.01ms` is present.
 * That is the visible half. This is the other half: nothing in the block may
 * still be moving, the durations TypeScript passes must be the durations the
 * stylesheet holds, and the hook has to keep listening after mount, because a
 * visitor can turn the preference on while the page is open.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { act, renderHook } from "@testing-library/react";

import { DURATION, REDUCED_MOTION_QUERY, useReducedMotion } from "@/design/motion";
import { CONFIDENCE_TONE, TYPE_SCALE } from "@/design/tokens";

const css = readFileSync("src/app/globals.css", "utf-8");

/**
 * The body of the first at-rule whose prelude matches, found by balancing
 * braces rather than by a lazy regex. A regex either stops at the first nested
 * closing brace or runs to the end of the file, and both mistakes produce a
 * block that still looks plausible enough to assert against.
 */
function atRuleBody(prelude: RegExp): string {
  const start = css.search(prelude);
  if (start < 0) return "";
  const open = css.indexOf("{", start);
  if (open < 0) return "";
  let depth = 0;
  for (let at = open; at < css.length; at += 1) {
    if (css[at] === "{") depth += 1;
    else if (css[at] === "}") {
      depth -= 1;
      if (depth === 0) return css.slice(open + 1, at);
    }
  }
  return "";
}

const reducedBlock = atRuleBody(/@media[^{]*prefers-reduced-motion:\s*reduce/);
const rootBlock = css.match(/^:root\s*\{([^}]*)\}/m)?.[1] ?? "";

describe("the reduced-motion block", () => {
  it("exists and was found by the parser", () => {
    expect(reducedBlock.length).toBeGreaterThan(0);
    expect(rootBlock.length).toBeGreaterThan(0);
  });

  it("leaves no duration or delay that still moves", () => {
    // 0.01ms is below one frame, so no intermediate state is ever painted.
    // Anything larger is a shortened animation, which still carries its meaning
    // inside the movement, which is the thing the preference exists to remove.
    const offenders: string[] = [];
    for (const [declaration, , amount, unit] of reducedBlock.matchAll(
      /((?:animation|transition)-(?:duration|delay)):\s*([\d.]+)(ms|s)/g,
    )) {
      const ms = Number.parseFloat(amount ?? "0") * (unit === "s" ? 1000 : 1);
      if (ms > 0.01) offenders.push(`${declaration?.trim()} is ${ms}ms`);
    }
    expect(offenders, "these still move under prefers-reduced-motion").toEqual([]);
  });

  it("zeroes the duration tokens as well, for anything reading them at runtime", () => {
    for (const token of ["--duration-quick", "--duration-considered"]) {
      expect(reducedBlock, `${token} is not zeroed`).toMatch(new RegExp(`${token}:\\s*0m?s`));
    }
    expect(reducedBlock).toMatch(/--motion-enabled:\s*0/);
  });

  it("swaps in a still version rather than only removing the moving one", () => {
    // Removing the animation and leaving nothing behind loses whatever the
    // animation was saying. Both slots have to change hands.
    expect(reducedBlock).toMatch(/\[data-motion="animated"\][\s\S]*?display:\s*none/);
    expect(reducedBlock).toMatch(/\[data-motion="static"\][\s\S]*?display:\s*revert/);
  });
});

describe("the duration tokens", () => {
  it("says the same thing in TypeScript as in the stylesheet", () => {
    // Two copies of a number with nothing comparing them is how they drift.
    for (const [name, ms] of Object.entries(DURATION)) {
      const token = `--duration-${name}`;
      const declared = rootBlock.match(new RegExp(`${token}:\\s*(\\d+)ms`))?.[1];
      expect(declared, `${token} is not declared in :root`).toBeDefined();
      expect(Number(declared), `${token} disagrees with DURATION.${name}`).toBe(ms);
    }
  });
});

describe("the token maps", () => {
  it("names only custom properties the stylesheet actually declares", () => {
    for (const variable of [...Object.values(CONFIDENCE_TONE), ...Object.values(TYPE_SCALE)]) {
      expect(css, `${variable} is named in TypeScript but not declared in CSS`).toContain(
        `${variable}:`,
      );
    }
  });

  it("keeps the band's middle no larger than its ends", () => {
    // Rule 1, expressed in the tokens rather than only in the component that
    // uses them. The middle is a marking inside the band; the ends are the
    // answer. If these two ever swap, the page has become a big number with
    // decoration, and no component test would have to notice.
    const step = (token: string) =>
      rootBlock.match(new RegExp(`${token}:\\s*var\\((--text-[a-z0-9-]+)\\)`))?.[1];
    const order = [
      "--text-xs",
      "--text-sm",
      "--text-base",
      "--text-lg",
      "--text-xl",
      "--text-2xl",
      "--text-3xl",
    ];
    const middle = step("--text-band-middle");
    const end = step("--text-band-end");
    expect(middle, "--text-band-middle is not a step of the scale").toBeDefined();
    expect(end, "--text-band-end is not a step of the scale").toBeDefined();
    expect(order.indexOf(middle ?? "")).toBeLessThanOrEqual(order.indexOf(end ?? ""));
  });
});

describe("useReducedMotion", () => {
  /**
   * A matchMedia stub whose answer can change, because that is the case worth
   * testing: a stub that is fixed at mount cannot tell a hook that reads the
   * preference once from a hook that keeps watching it.
   */
  const listeners: (() => void)[] = [];
  const preference = { reduced: false };

  function stubMatchMedia(reduced: boolean) {
    listeners.length = 0;
    preference.reduced = reduced;
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({
        get matches() {
          return query === REDUCED_MOTION_QUERY ? preference.reduced : false;
        },
        media: query,
        addEventListener: (_: string, fn: () => void) => {
          listeners.push(fn);
        },
        removeEventListener: (_: string, fn: () => void) => {
          const at = listeners.indexOf(fn);
          if (at >= 0) listeners.splice(at, 1);
        },
      })),
    );
  }

  /** What the operating system does when the visitor flips the setting. */
  function changePreferenceTo(reduced: boolean) {
    preference.reduced = reduced;
    act(() => {
      for (const notify of [...listeners]) notify();
    });
  }

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reports the preference on the first render, not one render later", () => {
    // The gap matters here more than it usually does: a render with the wrong
    // answer is a render in which an animation may already have started, on the
    // machine of the one visitor who asked not to see one.
    stubMatchMedia(true);
    const { result, unmount } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
    unmount();
  });

  it("is false when the visitor has not asked for less movement", () => {
    stubMatchMedia(false);
    const { result, unmount } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    unmount();
  });

  it("keeps watching, because the setting can change while the page is open", () => {
    stubMatchMedia(false);
    const { result, unmount } = renderHook(() => useReducedMotion());
    expect(listeners.length).toBeGreaterThan(0);
    changePreferenceTo(true);
    expect(result.current).toBe(true);
    unmount();
  });

  it("stops watching when the component goes away", () => {
    stubMatchMedia(false);
    const { unmount } = renderHook(() => useReducedMotion());
    unmount();
    expect(listeners).toHaveLength(0);
  });
});
