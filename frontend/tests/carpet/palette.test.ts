import { describe, expect, it } from "vitest";
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
