import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { BOUNDS, POSTCODE4_PATTERN } from "@/lib/validation";

/** The authority. This file is the copy. */
// Resolved from the working directory, which vitest sets to frontend/.
// `import.meta.url` is not a file URL under the jsdom environment.
const SERIALIZERS = readFileSync(
  resolve(process.cwd(), "../backend/advice/serializers.py"),
  "utf-8",
);
const VALIDATION = readFileSync(
  resolve(process.cwd(), "src/lib/validation.ts"),
  "utf-8",
);

/** Every module-level `NAME = number` in the serializer, as a number. */
function pythonConstants(source: string): Record<string, number> {
  const constants: Record<string, number> = {};
  for (const [, name, literal] of source.matchAll(
    /^([A-Z][A-Z0-9_]*)\s*=\s*(-?[\d_]+(?:\.\d+)?)$/gm,
  )) {
    constants[name as string] = Number((literal as string).replaceAll("_", ""));
  }
  return constants;
}

/** Which pair of Python constants each entry in BOUNDS claims to mirror. */
const MIRRORS: Readonly<Record<string, readonly [string, string]>> = {
  postcode4: ["MIN_POSTCODE4", "MAX_POSTCODE4"],
  peak_power_wp: ["MIN_PEAK_POWER_WP", "MAX_PEAK_POWER_WP"],
  azimuth_deg: ["MIN_AZIMUTH_DEG", "MAX_AZIMUTH_DEG"],
  tilt_deg: ["MIN_TILT_DEG", "MAX_TILT_DEG"],
  annual_consumption_kwh: [
    "MIN_ANNUAL_CONSUMPTION_KWH",
    "MAX_ANNUAL_CONSUMPTION_KWH",
  ],
  heat_demand_kwh: ["MIN_HEAT_DEMAND_KWH", "MAX_HEAT_DEMAND_KWH"],
  battery_capacity_kwh: [
    "MIN_BATTERY_CAPACITY_KWH",
    "MAX_BATTERY_CAPACITY_KWH",
  ],
};

describe("the input bounds", () => {
  it("covers every numeric field the form asks about", () => {
    for (const field of [
      "peak_power_wp",
      "annual_consumption_kwh",
      "tilt_deg",
      "azimuth_deg",
      "heat_demand_kwh",
      "battery_capacity_kwh",
    ]) {
      expect(BOUNDS[field], `no bound for ${field}`).toBeDefined();
    }
  });

  it("matches the bounds the API enforces", () => {
    // These exist so a visitor is told before the round trip, not so the
    // frontend decides. The API refuses out-of-range input regardless; if the
    // two ever disagree, the API wins and this is the copy that is wrong.
    expect(BOUNDS.tilt_deg).toEqual({ min: 0, max: 90 });
    expect(BOUNDS.azimuth_deg).toEqual({ min: -180, max: 180 });
  });

  it("matches every constant it names, read out of serializers.py", () => {
    // The comments beside each entry say which constant it mirrors. A comment
    // cannot go red, so this reads the Python and compares. Without it, the
    // day somebody raises MAX_PEAK_POWER_WP is the day the form starts
    // refusing input the API would have accepted, silently and only for the
    // households at the edge.
    const constants = pythonConstants(SERIALIZERS);
    const disagreements: string[] = [];
    for (const [field, [minName, maxName]] of Object.entries(MIRRORS)) {
      const bound = BOUNDS[field];
      expect(bound, `no bound for ${field}`).toBeDefined();
      expect(
        constants[minName],
        `${minName} is not a constant in serializers.py`,
      ).toBeDefined();
      expect(
        constants[maxName],
        `${maxName} is not a constant in serializers.py`,
      ).toBeDefined();
      if (bound?.min !== constants[minName]) {
        disagreements.push(
          `${field}.min is ${bound?.min}, ${minName} is ${constants[minName]}`,
        );
      }
      if (bound?.max !== constants[maxName]) {
        disagreements.push(
          `${field}.max is ${bound?.max}, ${maxName} is ${constants[maxName]}`,
        );
      }
    }
    expect(disagreements, "the API wins; fix validation.ts").toEqual([]);
  });

  it("names, per entry, the constant it mirrors, so the next person can check", () => {
    for (const [minName, maxName] of Object.values(MIRRORS)) {
      expect(VALIDATION, `${minName} is not named in validation.ts`).toContain(
        minName,
      );
      expect(VALIDATION, `${maxName} is not named in validation.ts`).toContain(
        maxName,
      );
    }
    expect(VALIDATION).toContain("backend/advice/serializers.py");
  });

  it("says in its docstring which side wins", () => {
    expect(VALIDATION).toMatch(
      /API WINS AND THIS FILE IS THE ONE THAT IS\s+\*\s+WRONG/,
    );
  });

  it("has a lower bound below its upper bound everywhere", () => {
    for (const [field, bound] of Object.entries(BOUNDS)) {
      expect(bound.min, `${field} is an empty range`).toBeLessThan(bound.max);
    }
  });
});

describe("the postcode pattern", () => {
  it("accepts four ASCII digits and nothing else", () => {
    expect(POSTCODE4_PATTERN.test("5401")).toBe(true);
    for (const bad of ["540", "54011", "54o1", " 5401", "5401\n", "٥٤٠١"]) {
      expect(
        POSTCODE4_PATTERN.test(bad),
        `accepted ${JSON.stringify(bad)}`,
      ).toBe(false);
    }
  });

  it("is the same regex the serializer uses, minus Python's trailing-newline quirk", () => {
    expect(SERIALIZERS).toContain(
      String.raw`POSTCODE4_PATTERN = r"^[0-9]{4}\Z"`,
    );
  });

  it("does not pretend to know a postcode from a four digit string", () => {
    // "0123" has the shape and is not a place. BOUNDS.postcode4 is what
    // catches it, which is why both exist.
    expect(POSTCODE4_PATTERN.test("0123")).toBe(true);
    expect(Number("0123")).toBeLessThan(BOUNDS.postcode4?.min ?? 0);
  });
});
