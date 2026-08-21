/**
 * The geometry that makes the width of a band mean something.
 *
 * Until this existed the fill was `width: 100%` on every band, so a rule with a
 * spread of 60 euro and one with a spread of 383 euro were drawn as the same
 * object, and the only visual variable on the page was the marker, which
 * encodes skew. A sighted reader learned the uncertainty by reading the
 * numbers, which is the one thing the page was built not to require.
 *
 * The axis runs from zero to the band's own upper end. Both are real numbers
 * the model produced, so there is no invented reference constant anywhere in
 * this: the width of a band is the share of that axis it covers, which is the
 * uncertainty as a fraction of the largest value the model thinks plausible.
 */

import { describe, expect, it } from "vitest";
import {
  axisPercentage,
  bandOffsetFraction,
  bandSpanFraction,
} from "@/components/band/position";

describe("the width of a band", () => {
  it("is wider for a wider spread, on the same axis", () => {
    // The two amounts from the fixture the audit measured: 105.08 to 165.51
    // against 269.56 to 652.74. Drawn identically until now.
    const narrow = bandSpanFraction("105.08", "165.51");
    const wide = bandSpanFraction("269.56", "652.74");
    expect(narrow).toBeCloseTo(0.3651, 3);
    expect(wide).toBeCloseTo(0.587, 3);
    expect(wide).toBeGreaterThan(narrow);
  });

  it("is zero when there is no spread, so a point is not drawn as a rail", () => {
    // The picture of a range where there is none was the exact failure: the
    // marker fell back to the middle of a full-width track and the reader saw
    // a band the model never produced.
    expect(bandSpanFraction("100.00", "100.00")).toBe(0);
    expect(bandOffsetFraction("100.00", "100.00")).toBe(1);
  });

  it("is the whole axis when the band reaches from zero", () => {
    expect(bandSpanFraction("0", "500")).toBe(1);
    expect(bandOffsetFraction("0", "500")).toBe(0);
  });

  it("never exceeds the axis, whichever side of zero the band is on", () => {
    // A band that straddles zero covers everything between its own ends, so it
    // is the whole axis and cannot be more. A band entirely below zero is
    // measured against the same axis from the other side.
    expect(bandSpanFraction("-100", "300")).toBe(1);
    expect(bandSpanFraction("-300", "-100")).toBeCloseTo(0.6667, 3);
    expect(bandOffsetFraction("-300", "-100")).toBe(0);
    for (const [low, high] of [
      ["-100", "300"],
      ["-300", "-100"],
      ["12.5", "12.5"],
      ["1", "1000000"],
    ] as const) {
      const span = bandSpanFraction(low, high);
      const offset = bandOffsetFraction(low, high);
      expect(span).toBeGreaterThanOrEqual(0);
      expect(offset + span).toBeLessThanOrEqual(1.000001);
    }
  });

  it("refuses to draw anything for an amount it cannot read", () => {
    // A width computed from a value that is not a number would be a shape
    // asserting something about an answer nobody has.
    expect(bandSpanFraction("onbekend", "300")).toBe(0);
    expect(bandOffsetFraction("100", "onbekend")).toBe(0);
    expect(bandSpanFraction("0", "0")).toBe(0);
  });
});

describe("where the middle sits", () => {
  it("is the middle's own place on the axis, not the centre of the track", () => {
    // 1684.85 on an axis that runs to 1979.54.
    expect(axisPercentage("1395.51", "1684.85", "1979.54")).toBeCloseTo(
      85.11,
      2,
    );
  });

  it("lands inside the band it belongs to", () => {
    const low = 105.08;
    const high = 165.51;
    const at = axisPercentage("105.08", "126.09", "165.51") / 100;
    expect(at).toBeGreaterThanOrEqual(low / high);
    expect(at).toBeLessThanOrEqual(1);
  });

  it("says the middle is the whole answer when the band has no width", () => {
    expect(axisPercentage("100", "100", "100")).toBe(100);
  });

  it("falls back to the centre only when it has nothing to compute from", () => {
    expect(axisPercentage("onbekend", "1", "2")).toBe(50);
  });
});
