import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { CONFIDENCE_TONE, DURATION, confidenceTone } from "@/design/tokens";

const css = readFileSync("src/app/globals.css", "utf-8");

describe("the design tokens", () => {
  it("defines every colour twice, so a dark theme cannot inherit a light one", () => {
    const light = css.match(/^:root\s*\{([^}]*)\}/m)?.[1] ?? "";
    const declared = [...light.matchAll(/--([a-z0-9-]+):/g)].map(
      (m) => m[1] ?? "",
    );
    expect(declared.length).toBeGreaterThan(0);
    const dark =
      css.match(
        /prefers-color-scheme:\s*dark[^{]*\{\s*:root[^{]*\{([^}]*)\}/m,
      )?.[1] ?? "";
    for (const name of declared.filter((n) => n.startsWith("colour-"))) {
      expect(dark, `--${name} has no dark value`).toContain(`--${name}:`);
    }
  });

  it("names a tone for every confidence level the API can send", () => {
    expect(Object.keys(CONFIDENCE_TONE).sort()).toEqual([
      "GOOD",
      "INDICATIVE",
      "PRECISE",
    ]);
    for (const variable of Object.values(CONFIDENCE_TONE)) {
      expect(css).toContain(`${variable}:`);
    }
  });

  it("answers a level it has never heard of with the least certain tone", () => {
    // The map used to be indexed directly, with a comment saying a fourth level
    // "should fail the type check here". It does not: Advice is a description
    // of JSON and nothing checks JSON at runtime. A fourth level produced
    // var(undefined), React dropped the property, and band.module.css fell
    // through to a hard-coded #5b8def, a colour in neither palette, never
    // measured against anything, and close enough to the PRECISE navy to read
    // as more certain than PRECISE.
    for (const [level, token] of Object.entries(CONFIDENCE_TONE)) {
      expect(confidenceTone(level)).toBe(token);
    }
    for (const unknown of ["EXACT", "", "constructor", "toString"]) {
      expect(confidenceTone(unknown)).toBe(CONFIDENCE_TONE.INDICATIVE);
    }
    // And the fallback is a token both palettes define, so it is a colour the
    // contrast test has measured rather than a literal nobody has looked at.
    expect(css).toContain(`${CONFIDENCE_TONE.INDICATIVE}:`);
  });

  it("keeps every duration short enough not to be in the way", () => {
    // A transition a reader waits for is a transition that reads as slowness.
    for (const ms of Object.values(DURATION))
      expect(ms).toBeLessThanOrEqual(400);
  });

  it("disables motion rather than shortening it under prefers-reduced-motion", () => {
    // Shortening keeps the meaning in the movement, which is the thing the
    // preference exists to remove.
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(css).toMatch(/animation-duration:\s*0\.01ms/);
  });
});
