import { describe, expect, it } from "vitest";
import {
  QUARTERS,
  blockSizes,
  consumption,
  illustrativeDay,
  placeAt,
  production,
  sortedOrder,
  type DayState,
} from "@/components/day/shape";

const DAY = illustrativeDay();

describe("the drawn curves", () => {
  it("makes nothing at midnight and most at solar noon", () => {
    expect(production(0)).toBe(0);
    expect(production(QUARTERS - 1)).toBe(0);
    const peak = Math.max(
      ...Array.from({ length: QUARTERS }, (_, at) => production(at)),
    );
    // Half past one, which is where the curve was centred. Not a measurement
    // of anything: this asserts the figure is the figure that was drawn.
    expect(production(54)).toBeCloseTo(peak, 10);
  });

  it("uses more in the evening than at four in the morning", () => {
    expect(consumption(76)).toBeGreaterThan(consumption(16));
    // A base that never reaches zero: a household that used nothing all night
    // would draw a day nobody has.
    expect(consumption(8)).toBeGreaterThan(0.1);
  });
});

describe("the day", () => {
  it("is ninety six quarters in order", () => {
    expect(DAY).toHaveLength(QUARTERS);
    expect(DAY.map((quarter) => quarter.at)).toEqual(
      Array.from({ length: QUARTERS }, (_, at) => at),
    );
  });

  it("reaches all three states, so the figure has something to sort", () => {
    // Without this the two views below could be identical and every other
    // assertion here would still pass.
    expect(new Set(DAY.map((quarter) => quarter.state))).toEqual(
      new Set(["own", "offtake", "export"]),
    );
  });

  it("keeps every magnitude inside the range the stylesheet expects", () => {
    // day.module.css computes `12% + 88% * var(--size)`. A magnitude above one
    // is a bar taller than the strip, and a negative one is a bar that is not
    // there.
    for (const quarter of DAY) {
      expect(quarter.magnitude).toBeGreaterThanOrEqual(0);
      expect(quarter.magnitude).toBeLessThanOrEqual(1);
    }
  });

  it("puts the night on the grid and the middle of the day on the meter", () => {
    // The figure has to be a day a reader recognises, or it teaches nothing.
    expect(DAY[4]?.state).toBe("offtake");
    expect(DAY[54]?.state).toBe("export");
    expect(DAY[90]?.state).toBe("offtake");
  });
});

describe("sortedOrder", () => {
  const places = sortedOrder(DAY);

  it("is a permutation, so no quarter is lost or drawn twice", () => {
    // The one that would look almost right if it were wrong. Two cells sharing
    // a place stack exactly on top of each other, and the strip would be
    // missing a quarter with nothing on the screen saying so.
    expect([...places].sort((a, b) => a - b)).toEqual(
      Array.from({ length: QUARTERS }, (_, at) => at),
    );
  });

  it("puts the three states in contiguous blocks, own first", () => {
    const inOrder: DayState[] = new Array<DayState>(QUARTERS).fill("own");
    for (const quarter of DAY) {
      inOrder[places[quarter.at] ?? 0] = quarter.state;
    }
    const runs = inOrder.filter((state, at) => state !== inOrder[at - 1]);
    expect(runs).toEqual(["own", "offtake", "export"]);
  });

  it("keeps the day's own order inside each block", () => {
    // Stable, because a cell that jumped its neighbours would read as movement
    // in time, and time is the thing this figure shows being removed.
    for (const first of DAY) {
      for (const second of DAY) {
        if (first.state !== second.state || first.at >= second.at) continue;
        expect(places[first.at] ?? 0).toBeLessThan(places[second.at] ?? 0);
      }
    }
  });
});

describe("blockSizes", () => {
  it("counts every quarter exactly once", () => {
    const counts = blockSizes(DAY);
    expect(counts.own + counts.offtake + counts.export).toBe(QUARTERS);
    expect(counts.own).toBeGreaterThan(0);
  });
});

describe("placeAt", () => {
  it("gives a percentage of the strip rather than a pixel", () => {
    expect(placeAt(0, 96)).toBe("0.0000%");
    expect(placeAt(48, 96)).toBe("50.0000%");
  });

  it("answers the left edge rather than dividing by nothing", () => {
    expect(placeAt(3, 0)).toBe("0%");
  });
});
