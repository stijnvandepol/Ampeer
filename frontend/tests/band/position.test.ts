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
  LABEL_ANCHOR_PROPERTY,
  labelAnchor,
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

describe("how a label is put over the point it names", () => {
  it("hands the stylesheet the point, as a percentage of the track", () => {
    // The stylesheet sets left to this and translates the label by the same
    // percentage of its own width, so a label at 0 is flush left, one at 100 is
    // flush right, and one in between has its own 40% mark over the axis's 40%
    // mark. That is what makes a label cover its value at every width without
    // anything having to know what either measures.
    expect(labelAnchor(0)).toEqual({ [LABEL_ANCHOR_PROPERTY]: "0%" });
    expect(labelAnchor(100)).toEqual({ [LABEL_ANCHOR_PROPERTY]: "100%" });
    expect(labelAnchor(40)).toEqual({ [LABEL_ANCHOR_PROPERTY]: "40%" });
  });

  it("returns one number and not a pair of CSS strings", () => {
    // One value, so the offset along the track and the offset into the label
    // cannot be written apart. A custom property rather than a translate
    // literal because the language boundary walk in e2e/language.spec.ts reads
    // a returned string as text the visitor might see, and CSS in
    // tests/ui-strings.txt is noise in the one file that has to stay readable.
    expect(LABEL_ANCHOR_PROPERTY.startsWith("--")).toBe(true);
    for (const at of [0, 12.5, 50, 70.375, 99.9, 100]) {
      const anchor = labelAnchor(at);
      expect(Object.keys(anchor)).toEqual([LABEL_ANCHOR_PROPERTY]);
      expect(anchor[LABEL_ANCHOR_PROPERTY]).toBe(`${at}%`);
    }
  });

  it("refuses to place a label off the track", () => {
    // A percentage outside the axis would push the page sideways, which is a
    // reflow failure on the phone this site is mostly read on.
    expect(labelAnchor(140)).toEqual({ [LABEL_ANCHOR_PROPERTY]: "100%" });
    expect(labelAnchor(-20)).toEqual({ [LABEL_ANCHOR_PROPERTY]: "0%" });
  });
});
