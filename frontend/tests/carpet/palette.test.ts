import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { contrast } from "../design/wcag";
import type { DecodedYear } from "@/components/carpet/decode";
import {
  EXPORT_FLAG,
  MAGNITUDE_MASK,
  OWN_FULL_SCALE,
  QUARTERS_PER_DAY,
} from "@/components/carpet/decode";
import {
  CARPET_TOKENS,
  buildPixels,
  cellColour,
  cssColour,
  paletteFrom,
  parseHex,
  stateOf,
  type CarpetState,
} from "@/components/carpet/palette";

const HEXES: Record<string, string> = {
  [CARPET_TOKENS.ground]: "#071019",
  [CARPET_TOKENS.own]: "#f5c64a",
  [CARPET_TOKENS.offtake]: "#5c7385",
  [CARPET_TOKENS.export]: "#16232e",
};

const PALETTE = paletteFrom((name) => HEXES[name] ?? "")!;

describe("parseHex", () => {
  it("reads six digits with or without surrounding space", () => {
    // getComputedStyle hands a custom property back with its leading space
    // intact, so trimming is not tidiness here, it is the format.
    expect(parseHex("#0a141e")).toEqual([10, 20, 30]);
    expect(parseHex("  #0A141E  ")).toEqual([10, 20, 30]);
  });

  it("refuses anything that is not six hex digits", () => {
    expect(parseHex("")).toBeNull();
    expect(parseHex("#fff")).toBeNull();
    expect(parseHex("rgb(1 2 3)")).toBeNull();
    expect(parseHex("#gggggg")).toBeNull();
  });
});

describe("paletteFrom", () => {
  it("reads all four tokens through whatever the caller looks them up with", () => {
    expect(PALETTE.ground).toEqual([7, 16, 25]);
    expect(PALETTE.own).toEqual([245, 198, 74]);
  });

  it("refuses to build a palette that is missing one colour", () => {
    // Three of four is not slightly off, it is a plate saying something
    // untrue: every quarter of the missing state would take another state's
    // colour and read as that state.
    for (const missing of Object.values(CARPET_TOKENS)) {
      const read = (name: string) =>
        name === missing ? "" : (HEXES[name] ?? "");
      expect(paletteFrom(read)).toBeNull();
    }
  });
});

describe("stateOf", () => {
  it("gives own use the saturated colour whenever it is the larger flow", () => {
    expect(stateOf(0.2, 0.1, false)).toBe("own");
    expect(stateOf(0.2, 0.1, true)).toBe("own");
  });

  it("shows which way the meter ran when it is not", () => {
    expect(stateOf(0.05, 0.2, true)).toBe("export");
    expect(stateOf(0.05, 0.2, false)).toBe("offtake");
  });

  it("treats an exact tie as the meter rather than as own use", () => {
    // The comparison is strict on purpose: a dark quarter has zero of both,
    // and calling that self consumption would light up every winter night.
    expect(stateOf(0, 0, false)).toBe("offtake");
  });
});

describe("cellColour", () => {
  it("lifts a colour towards white with magnitude, never towards the ground", () => {
    const floor = cellColour(PALETTE, "own", 0);
    const full = cellColour(PALETTE, "own", 1);
    expect(floor).toEqual(PALETTE.own);
    expect(full[0]).toBeGreaterThan(floor[0]);
    expect(full[2]).toBeGreaterThan(floor[2]);
  });

  it("bounds a magnitude that is out of range instead of overshooting white", () => {
    expect(cellColour(PALETTE, "own", 5)).toEqual(
      cellColour(PALETTE, "own", 1),
    );
    expect(cellColour(PALETTE, "own", -2)).toEqual(
      cellColour(PALETTE, "own", 0),
    );
  });
});

describe("buildPixels", () => {
  const days = 2;
  const rows = QUARTERS_PER_DAY;
  const own = new Uint8Array(days * rows);
  const meter = new Uint8Array(days * rows);
  // Day one, quarter two: own use is the larger flow.
  own[rows + 2] = OWN_FULL_SCALE;
  meter[rows + 2] = 1;
  // Day one, quarter three: exported, and nothing used.
  meter[rows + 3] = EXPORT_FLAG | MAGNITUDE_MASK;

  const year: DecodedYear = {
    days,
    quartersPerDay: rows,
    own,
    meter,
    ceilings: { own: 0.2, export: 0.6, grid: 0.15 },
  };
  const pixels = buildPixels(year, PALETTE);

  function at(day: number, quarter: number): readonly number[] {
    const start = (quarter * days + day) * 4;
    return Array.from(pixels.slice(start, start + 4));
  }

  it("draws one opaque pixel per quarter and nothing more", () => {
    expect(pixels).toHaveLength(days * rows * 4);
    expect(at(0, 0)[3]).toBe(255);
  });

  it("transposes the payload, which runs by day, into a picture that runs by hour", () => {
    // The one that would look almost right if it were wrong: a plate drawn
    // untransposed is still a rectangle of plausible colours.
    // Read through `red` rather than indexed inline: noUncheckedIndexedAccess
    // makes every element `number | undefined`, and a comparison against
    // undefined is not a comparison. The fallback is out of range for a
    // channel, so a pixel that is not there fails rather than passes.
    const red = (day: number, quarter: number): number =>
      at(day, quarter)[0] ?? -1;
    expect(red(1, 2)).toBeGreaterThan(red(1, 3));
    expect(red(0, 2)).toBeLessThan(red(1, 2));
  });

  it("draws a dark quarter in the offtake colour at its floor", () => {
    expect(at(0, 0).slice(0, 3)).toEqual([...PALETTE.offtake]);
  });
});

describe("cssColour", () => {
  it("writes something the canvas takes, from numbers rather than from text", () => {
    expect(cssColour([7.4, 16.6, 25])).toBe("rgb(7 17 25)");
  });
});

/**
 * Every colour this plate can draw, measured against the instrument it is
 * drawn on.
 *
 * The pairs in `tests/design/contrast.test.ts` measure three tokens out of the
 * stylesheet. Three tokens are not three states: `cellColour` lifts each one
 * towards white by its magnitude, so what a reader actually sees is a band of
 * colours per state and the token is only one end of it. The claim the design
 * rests on is about the whole band, and until this existed it was a sentence
 * in two source comments and nothing more. Both of those sentences were also
 * wrong, by 11 percent on the top of the export band, which is what a claim
 * nobody re-derives does.
 *
 * The palette is read out of `globals.css` rather than written here, for the
 * same reason the contrast test reads it: a copy is a second stylesheet that
 * agrees with itself.
 */
describe("every colour the plate can draw", () => {
  const css = readFileSync("src/app/globals.css", "utf-8");
  const root = css.match(/^:root\s*\{([^}]*)\}/m)?.[1] ?? "";
  // `\\s` and not `\s`: a template literal eats the backslash, and the pattern
  // would become `name:s*(...)`, which matches only because `s*` is allowed to
  // match nothing. Green by luck, and it would swallow the first character of
  // any value that began with an s.
  const SHIPPING = paletteFrom(
    (name) => root.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1]?.trim() ?? "",
  );

  /** Every magnitude the wire format can express, per state. */
  const STEPS: Readonly<Record<CarpetState, number>> = {
    own: OWN_FULL_SCALE,
    offtake: MAGNITUDE_MASK,
    export: MAGNITUDE_MASK,
  };

  function bandOf(state: CarpetState): readonly number[] {
    const ground = SHIPPING!.ground;
    const steps = STEPS[state];
    return Array.from({ length: steps + 1 }, (_, at) =>
      contrast(cellColour(SHIPPING!, state, at / steps), ground),
    );
  }

  it("reads the shipping stylesheet, not a copy of it", () => {
    // Everything below is vacuous without this: paletteFrom answers null when
    // a token is missing, and `null!` would then throw rather than assert.
    expect(SHIPPING).not.toBeNull();
    expect(SHIPPING?.ground).toEqual([7, 16, 25]);
  });

  it.each([
    ["export", 3.0947, 4.0683, 128],
    ["offtake", 6.7005, 7.5855, 128],
    ["own", 11.9023, 13.5738, 256],
  ] as const)(
    "keeps %s inside the band it was measured at",
    (state, low, high, steps) => {
      const band = bandOf(state);
      expect(band).toHaveLength(steps);
      expect(Math.min(...band)).toBeCloseTo(low, 3);
      expect(Math.max(...band)).toBeCloseTo(high, 3);
      // The lift does something. A band whose ends are equal is a state drawn
      // in one flat colour, and every other assertion here would still pass.
      expect(high - low).toBeGreaterThan(0.5);
    },
  );

  it("puts the token at the floor of its own state, never inside it", () => {
    // The property the whole arrangement rests on. `contrast.test.ts` measures
    // three tokens and calls the result the worst case; that is only true
    // while `cellColour` lightens and never darkens. The moment it blends
    // towards the ground instead, as the prototype did, the measured token
    // stays green and the dimmest cell on screen goes to 1,2:1.
    for (const state of ["own", "offtake", "export"] as const) {
      const token = contrast(SHIPPING![state], SHIPPING!.ground);
      const dimmest = Math.min(...bandOf(state));
      expect(
        dimmest,
        `${state} is drawn below its own token`,
      ).toBeGreaterThanOrEqual(token - 1e-9);
    }
  });

  it("clears the 3:1 that SC 1.4.11 asks of a graphic that carries meaning", () => {
    for (const state of ["own", "offtake", "export"] as const) {
      expect(Math.min(...bandOf(state)), state).toBeGreaterThanOrEqual(3);
    }
  });

  it("leaves the three bands apart, so no cell reads as another state", () => {
    // Not 3:1 between neighbours, and that is arithmetic rather than a corner
    // cut: three states each 3:1 above a ground of luminance 0,0049 would need
    // relative luminances of 0,115, 0,444 and 1,432, and 1 is the ceiling. So
    // the states are told apart by hue and by not overlapping, and this is the
    // half of that claim a test can hold.
    const bands = (["export", "offtake", "own"] as const).map((state) => {
      const band = bandOf(state);
      return { state, low: Math.min(...band), high: Math.max(...band) };
    });
    const gaps = bands
      .slice(1)
      .map((band, at) => band.low / (bands[at]?.high ?? 1));
    for (const gap of gaps) expect(gap).toBeGreaterThan(1);
    expect(Math.min(...gaps)).toBeCloseTo(1.5691, 3);
  });

  it("draws nothing outside those bands over all 65536 cells the format holds", () => {
    // The bands above are computed from magnitudes. This walks the wire format
    // itself: both bytes, every value, through the same arithmetic buildPixels
    // uses, and asks whether any pair lands somewhere the bands do not cover.
    const bounds = Object.fromEntries(
      (["own", "offtake", "export"] as const).map((state) => {
        const band = bandOf(state);
        return [state, [Math.min(...band), Math.max(...band)] as const];
      }),
    ) as Record<CarpetState, readonly [number, number]>;

    const ceilings = { own: 0.2, export: 0.6, grid: 0.15 };
    const reached = new Set<CarpetState>();
    let cells = 0;
    let outside = 0;
    for (let ownByte = 0; ownByte <= OWN_FULL_SCALE; ownByte += 1) {
      for (let meterByte = 0; meterByte <= 0xff; meterByte += 1) {
        const exported = (meterByte & EXPORT_FLAG) !== 0;
        const ownShare = ownByte / OWN_FULL_SCALE;
        const meterShare = (meterByte & MAGNITUDE_MASK) / MAGNITUDE_MASK;
        const state = stateOf(
          ownShare * ceilings.own,
          meterShare * (exported ? ceilings.export : ceilings.grid),
          exported,
        );
        reached.add(state);
        cells += 1;
        const ratio = contrast(
          cellColour(SHIPPING!, state, state === "own" ? ownShare : meterShare),
          SHIPPING!.ground,
        );
        const [low, high] = bounds[state];
        if (ratio < low - 1e-9 || ratio > high + 1e-9) outside += 1;
      }
    }
    expect(cells).toBe(65536);
    // All three, or this walked one state 65536 times and proved nothing about
    // the other two.
    expect([...reached].sort()).toEqual(["export", "offtake", "own"]);
    expect(outside).toBe(0);
  });
});
