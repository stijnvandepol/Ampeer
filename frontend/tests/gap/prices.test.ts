import { describe, expect, it } from "vitest";
import {
  EXPORTED_2027_CENTS,
  EXPORTED_NOW_CENTS,
  SCALE_BOTTOM_CENTS,
  SCALE_TOP_CENTS,
  SELF_USED_CENTS,
  boxOf,
  cents,
  downOf,
  exportedIn,
} from "@/components/gap/prices";

describe("the two regimes", () => {
  it("prices an exported hour exactly like a used one while saldering lasts", () => {
    // The rule, not a rounding of it. Saldering subtracts one from the other,
    // so the figure draws one band because there is one band.
    expect(exportedIn("nu")).toBe(SELF_USED_CENTS);
    expect(EXPORTED_NOW_CENTS).toBe(SELF_USED_CENTS);
  });

  it("drops it below zero from 2027", () => {
    expect(exportedIn("2027")).toBe(EXPORTED_2027_CENTS);
    expect(EXPORTED_2027_CENTS.low).toBeLessThan(0);
    expect(EXPORTED_2027_CENTS.high).toBeLessThan(SELF_USED_CENTS.low);
  });
});

describe("downOf", () => {
  it("puts the top of the scale at the top and the bottom at the bottom", () => {
    expect(downOf(SCALE_TOP_CENTS)).toBe(0);
    expect(downOf(SCALE_BOTTOM_CENTS)).toBe(100);
  });

  it("places zero where the scale says it is, not halfway", () => {
    // 32 above and 8 below, so the zero rule sits at 80 percent. Halfway would
    // be a scale with equal room on both sides, which this one does not have,
    // and the rule the lower band crosses would be drawn in the wrong place.
    expect(downOf(0)).toBeCloseTo(80, 10);
  });

  it("clamps rather than running off the plot", () => {
    expect(downOf(100)).toBe(0);
    expect(downOf(-100)).toBe(100);
  });
});

describe("boxOf", () => {
  it("measures a band from its high down to its low", () => {
    const box = boxOf({ low: 0, high: SCALE_TOP_CENTS });
    expect(box.top).toBe(0);
    expect(box.height).toBeCloseTo(80, 10);
  });

  it("never draws a band with no height", () => {
    // An invisible band reads as an absent one, which on this figure would say
    // a price is certain when it is not.
    expect(boxOf({ low: 5, high: 5 }).height).toBeGreaterThan(0);
  });
});

describe("cents", () => {
  it("writes a decimal comma and leaves whole numbers whole", () => {
    expect(cents(30)).toBe("30");
    expect(cents(-6.5)).toBe("-6,5");
    expect(cents(3.2)).toBe("3,2");
  });
});
