import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { CONFIDENCE_TONE, DURATION } from "@/design/tokens";

const css = readFileSync("src/app/globals.css", "utf-8");

describe("the design tokens", () => {
  it("defines every colour twice, so a dark theme cannot inherit a light one", () => {
    const light = css.match(/^:root\s*\{([^}]*)\}/m)?.[1] ?? "";
    const declared = [...light.matchAll(/--([a-z0-9-]+):/g)].map((m) => m[1] ?? "");
    expect(declared.length).toBeGreaterThan(0);
    const dark = css.match(/prefers-color-scheme:\s*dark[^{]*\{\s*:root[^{]*\{([^}]*)\}/m)?.[1] ?? "";
    for (const name of declared.filter((n) => n.startsWith("colour-"))) {
      expect(dark, `--${name} has no dark value`).toContain(`--${name}:`);
    }
  });

  it("names a tone for every confidence level the API can send", () => {
    expect(Object.keys(CONFIDENCE_TONE).sort()).toEqual(["GOOD", "INDICATIVE", "PRECISE"]);
    for (const variable of Object.values(CONFIDENCE_TONE)) {
      expect(css).toContain(`${variable}:`);
    }
  });

  it("keeps every duration short enough not to be in the way", () => {
    // A transition a reader waits for is a transition that reads as slowness.
    for (const ms of Object.values(DURATION)) expect(ms).toBeLessThanOrEqual(400);
  });

  it("disables motion rather than shortening it under prefers-reduced-motion", () => {
    // Shortening keeps the meaning in the movement, which is the thing the
    // preference exists to remove.
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(css).toMatch(/animation-duration:\s*0\.01ms/);
  });
});
