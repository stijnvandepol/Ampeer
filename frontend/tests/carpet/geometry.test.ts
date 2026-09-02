import { describe, expect, it } from "vitest";
import {
  acrossOf,
  cellFromPointer,
  dayLabel,
  downOf,
  dutchQuantity,
  monthsOf,
  moveCursor,
  quarterLabel,
} from "@/components/carpet/geometry";

const COMMON = 365;
const LEAP = 366;
const ROWS = 96;

describe("monthsOf", () => {
  it("gives twelve months that add up to the year", () => {
    const total = monthsOf(COMMON).reduce(
      (sum, month) => sum + month.length,
      0,
    );
    expect(monthsOf(COMMON)).toHaveLength(12);
    expect(total).toBe(COMMON);
  });

  it("makes February one wider in a leap year", () => {
    // The plate is as wide as the year is long, so twelve equal columns would
    // put every label after February up to two days off its own block.
    expect(monthsOf(LEAP)[1]?.length).toBe(29);
    expect(monthsOf(LEAP).reduce((sum, month) => sum + month.length, 0)).toBe(
      LEAP,
    );
  });
});

describe("dayLabel", () => {
  it("names the first and the last day of a common year", () => {
    expect(dayLabel(0, COMMON)).toBe("1 jan");
    expect(dayLabel(COMMON - 1, COMMON)).toBe("31 dec");
  });

  it("counts the leap day rather than stepping over it", () => {
    expect(dayLabel(59, COMMON)).toBe("1 mrt");
    expect(dayLabel(59, LEAP)).toBe("29 feb");
    expect(dayLabel(60, LEAP)).toBe("1 mrt");
  });

  it("says nothing for a day outside the year", () => {
    expect(dayLabel(COMMON, COMMON)).toBe("");
  });
});

describe("quarterLabel", () => {
  it("reads the grid's own clock", () => {
    expect(quarterLabel(0)).toBe("00:00");
    expect(quarterLabel(55)).toBe("13:45");
    expect(quarterLabel(ROWS - 1)).toBe("23:45");
  });
});

describe("cellFromPointer", () => {
  it("takes fractions of the box rather than pixels", () => {
    expect(cellFromPointer(0, 0, COMMON, ROWS)).toEqual({ day: 0, quarter: 0 });
    expect(cellFromPointer(0.5, 0.5, COMMON, ROWS)).toEqual({
      day: 182,
      quarter: 48,
    });
  });

  it("clamps a pointer that has left the plate", () => {
    expect(cellFromPointer(1.4, -0.2, COMMON, ROWS)).toEqual({
      day: COMMON - 1,
      quarter: 0,
    });
  });

  it("answers nothing when the box has no size", () => {
    // A zero width box divides to Infinity or NaN, and clamping that lands
    // silently on 31 December. A plate that reports the last day of the year
    // for every hover is worse than one that reports nothing.
    expect(cellFromPointer(Number.NaN, 0.5, COMMON, ROWS)).toBeNull();
    expect(
      cellFromPointer(0.5, Number.POSITIVE_INFINITY, COMMON, ROWS),
    ).toBeNull();
  });
});

describe("moveCursor", () => {
  it("steps a day sideways and a quarter up or down", () => {
    const at = { day: 10, quarter: 10 };
    expect(moveCursor(at, "ArrowRight", COMMON, ROWS)).toEqual({
      day: 11,
      quarter: 10,
    });
    expect(moveCursor(at, "ArrowLeft", COMMON, ROWS)).toEqual({
      day: 9,
      quarter: 10,
    });
    expect(moveCursor(at, "ArrowUp", COMMON, ROWS)).toEqual({
      day: 10,
      quarter: 9,
    });
    expect(moveCursor(at, "ArrowDown", COMMON, ROWS)).toEqual({
      day: 10,
      quarter: 11,
    });
  });

  it("starts at the origin of both axes", () => {
    expect(moveCursor(null, "ArrowRight", COMMON, ROWS)).toEqual({
      day: 1,
      quarter: 0,
    });
  });

  it("stops at the edges instead of wrapping", () => {
    expect(
      moveCursor({ day: 0, quarter: 0 }, "ArrowLeft", COMMON, ROWS),
    ).toEqual({
      day: 0,
      quarter: 0,
    });
    expect(
      moveCursor(
        { day: COMMON - 1, quarter: ROWS - 1 },
        "ArrowDown",
        COMMON,
        ROWS,
      ),
    ).toEqual({ day: COMMON - 1, quarter: ROWS - 1 });
  });

  it("refuses a key that is not one of the four", () => {
    // Null rather than the cursor unchanged, because the caller decides from
    // it whether to swallow the key. A plate that consumed every keystroke
    // would take Tab and Escape from a visitor trying to leave it.
    expect(moveCursor({ day: 1, quarter: 1 }, "Tab", COMMON, ROWS)).toBeNull();
    expect(
      moveCursor({ day: 1, quarter: 1 }, "Escape", COMMON, ROWS),
    ).toBeNull();
  });
});

describe("acrossOf and downOf", () => {
  it("place a cursor at the middle of its own column and row", () => {
    expect(acrossOf({ day: 0, quarter: 0 }, 4)).toBe("12.5000%");
    expect(downOf({ day: 0, quarter: 1 }, 4)).toBe("37.5000%");
  });

  it("answer the centre when there is no cursor", () => {
    // Never seen, because the crosshair is transparent then. What it avoids is
    // a glide in from a corner the first time a reader arrives, which is the
    // one moment the transition would be visible.
    expect(acrossOf(null, COMMON)).toBe("50%");
    expect(downOf(null, ROWS)).toBe("50%");
  });

  it("answer the centre rather than dividing by nothing", () => {
    expect(acrossOf({ day: 0, quarter: 0 }, 0)).toBe("50%");
    expect(downOf({ day: 0, quarter: 0 }, 0)).toBe("50%");
  });
});

describe("dutchQuantity", () => {
  it("writes a decimal comma", () => {
    expect(dutchQuantity(0.125, 2)).toBe("0,13");
    expect(dutchQuantity(0, 2)).toBe("0,00");
  });
});
