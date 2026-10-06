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
import { readFileSync, readdirSync } from "node:fs";
import { contrast as ratio, fromHex, luminance } from "./wcag";

const css = readFileSync("src/app/globals.css", "utf-8");

// --- WCAG 2.2 relative luminance and contrast, straight from the definition ---
//
// The formula lives in ./wcag.ts, because the plate's own contrast test asks
// the same question of colours that are never in this stylesheet. The two
// anchors at the bottom of this file are what prove it is the real formula,
// and they now prove it for both callers.

/** The shared ratio, over the hex strings this file reads out of the CSS. */
function contrast(a: string, b: string): number {
  return ratio(fromHex(a), fromHex(b));
}

/** Two opaque colours, blended. `share` of the first, the rest of the second. */
function mix(front: string, back: string, share: number): string {
  const [f, b] = [front.replace("#", ""), back.replace("#", "")];
  let out = "#";
  for (const at of [0, 2, 4]) {
    const one = Number.parseInt(f.slice(at, at + 2), 16);
    const two = Number.parseInt(b.slice(at, at + 2), 16);
    out += Math.round(share * one + (1 - share) * two)
      .toString(16)
      .padStart(2, "0");
  }
  return out;
}

// --- reading the four theme blocks out of the stylesheet ---

type Palette = Record<string, string>;

function paletteIn(block: string): Palette {
  const found: Palette = {};
  for (const [, name, value] of block.matchAll(
    /--colour-([a-z0-9-]+):\s*([^;]+);/g,
  )) {
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
  // The plate's own labels: hour and month axes, legend and readout, all drawn
  // on the instrument rather than on the page.
  ["on-carpet", "carpet-ground"],
  ["on-ground", "carpet-ground"],
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
  /*
   * The three states of the year plate, against the instrument they are drawn
   * on. Colour is the entire encoding there: a cell is one pixel and carries no
   * label, no shape and no position of its own, so if two states are not
   * distinguishable the picture says nothing.
   *
   * Each name is the FLOOR of its state and not a representative of it.
   * src/components/carpet/palette.ts only lightens a state towards white, so
   * the dimmest cell it can draw is exactly the token measured here. That is
   * the property tests/carpet/palette.test.ts pins by walking every cell the
   * wire format can hold; without it these three rows would measure a colour
   * that happens to be in the stylesheet rather than the worst one on screen.
   */
  ["carpet-own", "carpet-ground"],
  ["carpet-offtake", "carpet-ground"],
  ["carpet-export", "carpet-ground"],
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
      expect(
        keys,
        `${theme} does not declare the same colours as ${first?.[0]}`,
      ).toEqual(first?.[1]);
    }
  });

  it("gives the explicit choice exactly the colours it overrides", () => {
    // Four copies of a palette is a maintenance hazard unless something checks
    // they still say the same thing. This is that something.
    expect(BLOCKS['light (explicit [data-theme="light"])']).toEqual(
      BLOCKS["light (bare :root)"],
    );
    expect(BLOCKS['dark (explicit [data-theme="dark"])']).toEqual(
      BLOCKS["dark (prefers-color-scheme)"],
    );
  });

  it("states every colour as a literal hex, so a ratio can be computed from it", () => {
    // A var() here would make every assertion below measure an empty string
    // and pass, which is the shape of a check that has quietly stopped working.
    for (const [theme, palette] of Object.entries(BLOCKS)) {
      for (const [name, value] of Object.entries(palette)) {
        expect(
          value,
          `${theme}: --colour-${name} is not a literal hex`,
        ).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
  });

  it("leaves no colour without a check", () => {
    // A token added without a pair is a token nobody measured.
    const checked = new Set(
      [...TEXT_PAIRS, ...GRAPHIC_PAIRS]
        .flatMap(([a, b]) => [a, b])
        .concat([...EXEMPT]),
    );
    const declared = Object.keys(BLOCKS["light (bare :root)"]);
    expect(declared.filter((name) => !checked.has(name))).toEqual([]);
  });

  it.each(Object.entries(BLOCKS))(
    "reaches AA for every text pair in %s",
    (theme, palette) => {
      const failures: string[] = [];
      for (const [fg, bg] of TEXT_PAIRS) {
        const [front, back] = [palette[fg], palette[bg]];
        expect(front, `${theme}: no --colour-${fg}`).toBeDefined();
        expect(back, `${theme}: no --colour-${bg}`).toBeDefined();
        const ratio = contrast(front ?? "#000000", back ?? "#000000");
        if (ratio < 4.5) failures.push(`${fg} on ${bg}: ${ratio.toFixed(2)}:1`);
      }
      expect(failures, `${theme} is below WCAG 2.2 AA (4.5:1)`).toEqual([]);
    },
  );

  it.each(Object.entries(BLOCKS))(
    "reaches 3:1 for every meaningful graphic in %s",
    (theme, palette) => {
      const failures: string[] = [];
      for (const [fg, bg] of GRAPHIC_PAIRS) {
        const ratio = contrast(
          palette[fg] ?? "#000000",
          palette[bg] ?? "#000000",
        );
        if (ratio < 3) failures.push(`${fg} vs ${bg}: ${ratio.toFixed(2)}:1`);
      }
      expect(failures, `${theme} is below WCAG 2.2 SC 1.4.11 (3:1)`).toEqual(
        [],
      );
    },
  );

  it("draws every colour it declares, somewhere other than the @theme block", () => {
    // Seven tokens were declared, measured by the pairs above, and rendered by
    // no route: ink-subtle, surface-raised, surface-sunken, band-track, on-tone,
    // on-danger and accent-hover. Nothing could see it, because @theme inline
    // hands every one of them to Tailwind with a var() reference, so a naive
    // search for the name finds a "use" for a token no page draws.
    //
    // So the @theme block is cut out before looking. What counts as a use is a
    // var() in a real rule, in this file or in a component stylesheet, or the
    // token's name in TypeScript for the maps that select between them. A
    // Tailwind utility class does not count: it would put the check back where
    // it started.
    const withoutTheme = css.replace(/@theme[^{]*\{[\s\S]*?\n\}/m, "");
    expect(withoutTheme.length, "the @theme block was not found").toBeLessThan(
      css.length,
    );
    const elsewhere = readdirSync("src", { recursive: true, encoding: "utf-8" })
      .filter(
        (name) => /\.(css|ts|tsx)$/.test(name) && !name.endsWith("globals.css"),
      )
      .map((name) => readFileSync(`src/${name}`, "utf-8"))
      .join("\n");
    const unused = Object.keys(BLOCKS["light (bare :root)"]).filter((name) => {
      const reference = `var(--colour-${name}`;
      return (
        !withoutTheme.includes(reference) &&
        !elsewhere.includes(reference) &&
        !elsewhere.includes(`"--colour-${name}"`)
      );
    });
    expect(unused, "declared, measured, and drawn by nothing").toEqual([]);
  });

  it("lets no component stylesheet state a colour of its own", () => {
    // band.module.css used to carry a hex fallback beside every var(), and one
    // of them, #5b8def, was in neither palette. A confidence level this build
    // did not know produced var(undefined), React dropped the property, and the
    // band was drawn in that colour: never measured, never in a theme, and
    // close enough to the PRECISE navy to read as more certain than PRECISE.
    //
    // Every module rather than that one file, as of 2026-08-27. The old form
    // named `src/components/band/band.module.css` and nothing else, so the
    // second component stylesheet in this tree would have been free to carry
    // exactly the literal the first one was forbidden. A rule that holds for
    // one named path is not a rule about the codebase.
    const modules = readdirSync("src", {
      recursive: true,
      encoding: "utf-8",
    }).filter((name) => name.endsWith(".module.css"));
    // Non-vacuous: a glob that matched nothing would agree with every
    // stylesheet in the tree, including one written entirely in hex.
    expect(
      modules.length,
      "no component stylesheet was found to check",
    ).toBeGreaterThan(1);
    const offenders: string[] = [];
    for (const name of modules) {
      const source = readFileSync(`src/${name}`, "utf-8").replace(
        /\/\*[\s\S]*?\*\//g,
        "",
      );
      for (const found of source.matchAll(
        /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g,
      )) {
        offenders.push(`${name}: ${found[0]}`);
      }
    }
    expect(offenders, "a colour with one definition, in one theme").toEqual([]);
  });

  it("keeps every point of the band's gradient above 3:1 against the page", () => {
    // The gradient is a background-image, which is the blind spot two correct
    // checks share: this file parses tokens and never looks at a component, and
    // axe's colour-contrast rule is text-only and ignores background-image
    // entirely. Measured at the ends the old gradient composited to about 2:1
    // while the middle sat at 6:1, so colour said the opposite of what the type
    // sizes said.
    //
    // This computes it from the tokens; e2e/rules.spec.ts samples the pixels of
    // the built page, which is the check that cannot be fooled by a stylesheet
    // that says one thing and renders another. Both are here because this one
    // fails in a second and names the token.
    const band = readFileSync("src/components/band/band.module.css", "utf-8");
    const mixed = band.match(
      /color-mix\(\s*in srgb,\s*var\(--tone[\s\S]*?(\d+)%,\s*var\(--colour-surface\)/,
    );
    expect(
      mixed,
      "the gradient no longer mixes the tone with the surface",
    ).not.toBeNull();
    const share = Number(mixed?.[1] ?? 0) / 100;
    expect(share).toBeGreaterThan(0);

    const failures: string[] = [];
    for (const [theme, palette] of Object.entries(BLOCKS)) {
      const surface = palette["surface"] ?? "#000000";
      for (const tone of [
        "confidence-indicative",
        "confidence-good",
        "confidence-precise",
      ]) {
        const full = palette[tone] ?? "#000000";
        for (const [where, colour] of [
          ["end", full],
          ["middle", mix(full, surface, share)],
        ] as const) {
          const ratio = contrast(colour, surface);
          if (ratio < 3)
            failures.push(
              `${theme}: ${tone} at the ${where}: ${ratio.toFixed(2)}:1`,
            );
        }
      }
    }
    expect(
      failures,
      "below WCAG 2.2 SC 1.4.11 (3:1) somewhere along the band",
    ).toEqual([]);
  });

  it("computes the same ratio for a pair the specification names", () => {
    // Guards the arithmetic itself. WCAG's own worked example: #FFFFFF on
    // #000000 is exactly 21:1, and mid grey #767676 on white is 4.54:1, the
    // pair the specification uses to mark the AA boundary.
    expect(contrast("#ffffff", "#000000")).toBeCloseTo(21, 5);
    expect(contrast("#767676", "#ffffff")).toBeCloseTo(4.54, 2);
  });
});

/**
 * A well is a lighter panel in the dark, and a darker one in the light.
 *
 * The first dark palette translated "sunken" literally: a shade below white
 * became a shade below near-black, #080b0d on #0c1013, a contrast of 1.03.
 * Measured on 2026-09-15 with a scan over every page: the band's track, the
 * pressed toggle on the home page and on /einde-saldering/, and the hover of
 * the quiet buttons were black on black and simply gone. The scan is not a
 * test; this is, and it asks the one question the scan reduced to: on which
 * side of the page does the well sit, and is it far enough from it to see.
 */
describe("the sunken surface", () => {
  const WELL = 1.15;

  for (const [name, palette] of Object.entries(BLOCKS)) {
    const dark = name.startsWith("dark");
    it(`is ${dark ? "lighter" : "darker"} than the page in ${name}, and visibly so`, () => {
      const page = palette["surface"] ?? "";
      const well = palette["surface-sunken"] ?? "";
      expect(page).toMatch(/^#/);
      expect(well).toMatch(/^#/);
      const up = luminance(fromHex(well)) > luminance(fromHex(page));
      expect(
        up,
        `the well sits on the wrong side of the page: ${well} on ${page}`,
      ).toBe(dark);
      expect(
        contrast(well, page),
        `the well is ${well} on ${page}, which cannot be told from the page`,
      ).toBeGreaterThanOrEqual(WELL);
    });
  }
});
