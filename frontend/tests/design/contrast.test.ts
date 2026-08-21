/**
 * Every colour pair, measured rather than claimed.
 *
 * A palette is only accessible in the themes somebody checked. The dark theme
 * is the one that gets away with it, because whoever picked the colours was
 * looking at the light one, and a euro amount that has gone unreadable against
 * a background nobody compared it to still looks like a euro amount to the
 * person who shipped it.
 *
 * So this reads the real stylesheet, resolves each theme block on its own, and
 * computes the WCAG 2.2 contrast ratio for every pair the design actually
 * draws. Nothing here trusts a number written in a comment.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

const css = readFileSync("src/app/globals.css", "utf-8");

// --- WCAG 2.2 relative luminance and contrast, straight from the definition ---

function channel(eight: number): number {
  const c = eight / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function luminance(hex: string): number {
  const digits = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((at) => Number.parseInt(digits.slice(at, at + 2), 16));
  return 0.2126 * channel(r ?? 0) + 0.7152 * channel(g ?? 0) + 0.0722 * channel(b ?? 0);
}

function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)];
  const [lighter, darker] = x > y ? [x, y] : [y, x];
  return (lighter + 0.05) / (darker + 0.05);
}

// --- reading the four theme blocks out of the stylesheet ---

type Palette = Record<string, string>;

function paletteIn(block: string): Palette {
  const found: Palette = {};
  for (const [, name, value] of block.matchAll(/--colour-([a-z0-9-]+):\s*([^;]+);/g)) {
    if (name && value) found[name] = value.trim();
  }
  return found;
}

function blockAfter(pattern: RegExp): string {
  return css.match(pattern)?.[1] ?? "";
}

const BLOCKS = {
  "light (bare :root)": paletteIn(blockAfter(/^:root\s*\{([^}]*)\}/m)),
  "dark (prefers-color-scheme)": paletteIn(
    blockAfter(/prefers-color-scheme:\s*dark[^{]*\{\s*:root[^{]*\{([^}]*)\}/m),
  ),
  'light (explicit [data-theme="light"])': paletteIn(
    blockAfter(/^:root\[data-theme="light"\]\s*\{([^}]*)\}/m),
  ),
  'dark (explicit [data-theme="dark"])': paletteIn(
    blockAfter(/^:root\[data-theme="dark"\]\s*\{([^}]*)\}/m),
  ),
} as const;

/**
 * Text on a background. 4.5:1 is AA for body text; nothing in this product is
 * large enough to lean on the 3:1 exception, and a band whose ends only pass at
 * display size would fail the moment somebody set it smaller.
 */
const TEXT_PAIRS: readonly (readonly [string, string])[] = [
  ["ink", "surface"],
  ["ink", "surface-raised"],
  ["ink", "surface-sunken"],
  ["ink-muted", "surface"],
  ["ink-muted", "surface-raised"],
  ["ink-muted", "surface-sunken"],
  ["ink-subtle", "surface"],
  ["ink-subtle", "surface-raised"],
  ["ink-subtle", "surface-sunken"],
  ["accent", "surface"],
  ["accent", "surface-raised"],
  ["accent", "surface-sunken"],
  ["accent-hover", "surface"],
  ["accent-hover", "surface-raised"],
  ["accent-hover", "surface-sunken"],
  ["on-accent", "accent"],
  ["on-accent", "accent-hover"],
  ["confidence-indicative", "surface"],
  ["confidence-indicative", "surface-raised"],
  ["confidence-indicative", "surface-sunken"],
  ["confidence-good", "surface"],
  ["confidence-good", "surface-raised"],
  ["confidence-good", "surface-sunken"],
  ["confidence-precise", "surface"],
  ["confidence-precise", "surface-raised"],
  ["confidence-precise", "surface-sunken"],
  ["on-tone", "confidence-indicative"],
  ["on-tone", "confidence-good"],
  ["on-tone", "confidence-precise"],
  ["on-tone", "band-track"],
  ["danger", "surface"],
  ["danger", "surface-raised"],
  ["danger", "surface-sunken"],
  ["on-danger", "danger"],
];

/**
 * Graphics that carry meaning, and the boundaries of controls somebody has to
 * find. SC 1.4.11 asks 3:1 of these. The band's fill is on this list because
 * the band is the answer, not an ornament around it.
 */
const GRAPHIC_PAIRS: readonly (readonly [string, string])[] = [
  ["border-strong", "surface"],
  ["border-strong", "surface-raised"],
  ["border-strong", "surface-sunken"],
  ["focus", "surface"],
  ["focus", "surface-raised"],
  ["focus", "surface-sunken"],
  ["band-track", "surface"],
  ["band-track", "surface-raised"],
  ["confidence-indicative", "surface"],
  ["confidence-indicative", "surface-raised"],
  ["confidence-good", "surface"],
  ["confidence-good", "surface-raised"],
  ["confidence-precise", "surface"],
  ["confidence-precise", "surface-raised"],
];

/** Never drawn against text or used as a control boundary. */
const EXEMPT = new Set(["border"]);

describe("the palette", () => {
  it("defines the same colour names in all four theme blocks", () => {
    const names = Object.entries(BLOCKS).map(
      ([theme, palette]) => [theme, Object.keys(palette).sort()] as const,
    );
    const [first, ...rest] = names;
    expect(first?.[1].length ?? 0).toBeGreaterThan(0);
    for (const [theme, keys] of rest) {
      expect(keys, `${theme} does not declare the same colours as ${first?.[0]}`).toEqual(first?.[1]);
    }
  });

  it("gives the explicit choice exactly the colours it overrides", () => {
    // Four copies of a palette is a maintenance hazard unless something checks
    // they still say the same thing. This is that something.
    expect(BLOCKS['light (explicit [data-theme="light"])']).toEqual(BLOCKS["light (bare :root)"]);
    expect(BLOCKS['dark (explicit [data-theme="dark"])']).toEqual(
      BLOCKS["dark (prefers-color-scheme)"],
    );
  });

  it("states every colour as a literal hex, so a ratio can be computed from it", () => {
    // A var() here would make every assertion below measure an empty string
    // and pass, which is the shape of a check that has quietly stopped working.
    for (const [theme, palette] of Object.entries(BLOCKS)) {
      for (const [name, value] of Object.entries(palette)) {
        expect(value, `${theme}: --colour-${name} is not a literal hex`).toMatch(
          /^#[0-9a-f]{6}$/,
        );
      }
    }
  });

  it("leaves no colour without a check", () => {
    // A token added without a pair is a token nobody measured.
    const checked = new Set(
      [...TEXT_PAIRS, ...GRAPHIC_PAIRS].flatMap(([a, b]) => [a, b]).concat([...EXEMPT]),
    );
    const declared = Object.keys(BLOCKS["light (bare :root)"]);
    expect(declared.filter((name) => !checked.has(name))).toEqual([]);
  });

  it.each(Object.entries(BLOCKS))("reaches AA for every text pair in %s", (theme, palette) => {
    const failures: string[] = [];
    for (const [fg, bg] of TEXT_PAIRS) {
      const [front, back] = [palette[fg], palette[bg]];
      expect(front, `${theme}: no --colour-${fg}`).toBeDefined();
      expect(back, `${theme}: no --colour-${bg}`).toBeDefined();
      const ratio = contrast(front ?? "#000000", back ?? "#000000");
      if (ratio < 4.5) failures.push(`${fg} on ${bg}: ${ratio.toFixed(2)}:1`);
    }
    expect(failures, `${theme} is below WCAG 2.2 AA (4.5:1)`).toEqual([]);
  });

  it.each(Object.entries(BLOCKS))("reaches 3:1 for every meaningful graphic in %s", (theme, palette) => {
    const failures: string[] = [];
    for (const [fg, bg] of GRAPHIC_PAIRS) {
      const ratio = contrast(palette[fg] ?? "#000000", palette[bg] ?? "#000000");
      if (ratio < 3) failures.push(`${fg} vs ${bg}: ${ratio.toFixed(2)}:1`);
    }
    expect(failures, `${theme} is below WCAG 2.2 SC 1.4.11 (3:1)`).toEqual([]);
  });

  it("computes the same ratio for a pair the specification names", () => {
    // Guards the arithmetic itself. WCAG's own worked example: #FFFFFF on
    // #000000 is exactly 21:1, and mid grey #767676 on white is 4.54:1, the
    // pair the specification uses to mark the AA boundary.
    expect(contrast("#ffffff", "#000000")).toBeCloseTo(21, 5);
    expect(contrast("#767676", "#ffffff")).toBeCloseTo(4.54, 2);
  });
});
