import { describe, expect, it } from "vitest";
import type { YearSeries } from "@/lib/types";
import {
  EXPORT_FLAG,
  MAGNITUDE_MASK,
  OWN_FULL_SCALE,
  QUARTERS_PER_DAY,
  byteAt,
  cellAt,
  decodeYear,
} from "@/components/carpet/decode";

/**
 * The wire format, built here rather than borrowed from a fixture.
 *
 * A fixture would be a recording of what the encoder produced, and this file
 * is the only thing standing between that encoder and a picture. Building the
 * bytes from the format's own description is what makes a disagreement between
 * the two ends visible here instead of on the plate.
 */
const CEILINGS = { own: 0.2, export: 0.6, grid: 0.15 } as const;

function base64(bytes: readonly number[]): string {
  return btoa(String.fromCharCode(...bytes));
}

function seriesOf(
  own: readonly number[],
  meter: readonly number[],
  quarters = own.length,
): YearSeries {
  return {
    own: base64(own),
    meter: base64(meter),
    ceilings: CEILINGS,
    provenance: "SYNTHETIC",
    quarters,
  };
}

/** Two days of quarters, all zero, as the smallest thing that is a year. */
function twoDays(): { own: number[]; meter: number[] } {
  const size = QUARTERS_PER_DAY * 2;
  return {
    own: new Array<number>(size).fill(0),
    meter: new Array<number>(size).fill(0),
  };
}

describe("byteAt", () => {
  it("reads the byte that is there", () => {
    expect(byteAt(Uint8Array.from([7, 9]), 1)).toBe(9);
  });

  it("answers zero past the end rather than undefined", () => {
    // noUncheckedIndexedAccess makes every indexed read `number | undefined`,
    // and this is the one place that is resolved, so it is the one place worth
    // a test. A quarter off the end of the year is dark, not missing.
    expect(byteAt(Uint8Array.from([7]), 5)).toBe(0);
  });
});

describe("decodeYear", () => {
  it("unpacks a payload into days and quarters", () => {
    const { own, meter } = twoDays();
    const decoded = decodeYear(seriesOf(own, meter));
    expect(decoded).not.toBeNull();
    expect(decoded?.days).toBe(2);
    expect(decoded?.quartersPerDay).toBe(QUARTERS_PER_DAY);
    expect(decoded?.ceilings).toEqual(CEILINGS);
  });

  it("refuses a year of no quarters", () => {
    expect(decodeYear(seriesOf([], [], 0))).toBeNull();
  });

  it("refuses a count of quarters that is not whole days", () => {
    const own = new Array<number>(97).fill(0);
    expect(decodeYear(seriesOf(own, own, 97))).toBeNull();
  });

  it("refuses a payload that is not base64", () => {
    const { own, meter } = twoDays();
    const broken = { ...seriesOf(own, meter), own: "not base64 at all!" };
    expect(decodeYear(broken)).toBeNull();
  });

  it("refuses a payload whose length disagrees with its own count", () => {
    // The refusal that matters. base64 decodes happily to the wrong number of
    // bytes, and the plate would then be a year shifted by however many
    // quarters went missing, which reads as a household getting up earlier as
    // the year goes on.
    const { own, meter } = twoDays();
    expect(decodeYear(seriesOf(own.slice(0, -1), meter))).toBeNull();
    expect(decodeYear(seriesOf(own, meter.slice(0, -1)))).toBeNull();
  });
});

describe("cellAt", () => {
  const { own, meter } = twoDays();
  own[QUARTERS_PER_DAY + 3] = OWN_FULL_SCALE;
  // Day one, quarter three: exported, at full magnitude.
  meter[QUARTERS_PER_DAY + 3] = EXPORT_FLAG | MAGNITUDE_MASK;
  // Day one, quarter four: taken from the grid, at full magnitude.
  meter[QUARTERS_PER_DAY + 4] = MAGNITUDE_MASK;
  const year = decodeYear(seriesOf(own, meter));

  it("reads own use against its own ceiling", () => {
    expect(year).not.toBeNull();
    expect(cellAt(year!, 1, 3)?.ownKwh).toBeCloseTo(CEILINGS.own, 10);
  });

  it("reads an exported quarter against the export ceiling", () => {
    const cell = cellAt(year!, 1, 3);
    expect(cell?.exported).toBe(true);
    expect(cell?.meterKwh).toBeCloseTo(CEILINGS.export, 10);
  });

  it("reads an offtake quarter against the grid ceiling", () => {
    // The two ceilings are not interchangeable: on one household export peaks
    // about three times higher than offtake, which is why they travel apart. A
    // decoder that used one for both would draw a plausible plate and be wrong
    // by that factor on every quarter of one colour.
    const cell = cellAt(year!, 1, 4);
    expect(cell?.exported).toBe(false);
    expect(cell?.meterKwh).toBeCloseTo(CEILINGS.grid, 10);
  });

  it("answers nothing for a quarter outside the year", () => {
    expect(cellAt(year!, -1, 0)).toBeNull();
    expect(cellAt(year!, 2, 0)).toBeNull();
    expect(cellAt(year!, 0, -1)).toBeNull();
    expect(cellAt(year!, 0, QUARTERS_PER_DAY)).toBeNull();
  });
});
