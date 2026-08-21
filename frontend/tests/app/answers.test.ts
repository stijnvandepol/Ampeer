import { describe, expect, it } from "vitest";
import {
  ANSWERS_STORAGE_KEY,
  DEFAULT_AZIMUTH_DEG,
  DEFAULT_TILT_DEG,
  EMPTY_ANSWERS,
  clearAnswers,
  loadAnswers,
  postcodeText,
  saveAnswers,
  stepComplete,
  toEstimateInput,
  toRefineInput,
  type Answers,
} from "@/app/_flow/answers";

/** A storage that behaves like the real one, and one that refuses like Safari's. */
function memoryStorage(initial: Record<string, string> = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => void map.set(key, value),
    removeItem: (key: string) => void map.delete(key),
    map,
  };
}

function throwingStorage() {
  return {
    getItem: () => {
      throw new Error("storage is blocked");
    },
    setItem: () => {
      throw new Error("storage is blocked");
    },
    removeItem: () => {
      throw new Error("storage is blocked");
    },
  };
}

const ROUND_ONE: Answers = {
  ...EMPTY_ANSWERS,
  postcode4: 5401,
  peakPowerWp: 4200,
  azimuthDeg: 45,
  tiltDeg: 35,
  roofAnswered: true,
  annualConsumptionKwh: 3400,
};

const ROUND_TWO: Answers = {
  ...ROUND_ONE,
  daytimeOccupancy: false,
  ev: "SOLAR",
  heatPump: false,
  dynamicContract: true,
  battery: false,
};

describe("the answers, on their way to the API", () => {
  it("sends the postcode as the four digit string the RegexField wants", () => {
    expect(toEstimateInput(ROUND_ONE)?.postcode4).toBe("5401");
    expect(postcodeText(5401)).toBe("5401");
  });

  it("refuses a postcode that is not four digits rather than padding it", () => {
    expect(postcodeText(123)).toBeNull();
    expect(postcodeText(10000)).toBeNull();
    expect(postcodeText(5401.5)).toBeNull();
    expect(toEstimateInput({ ...ROUND_ONE, postcode4: 123 })).toBeNull();
  });

  it("will not send a roof the visitor never touched", () => {
    // The compass and the slider have to point somewhere before anybody has
    // answered, so "south at 35 degrees" is a starting position and not an
    // answer. Sending it as one would advise on a roof nobody described.
    expect(EMPTY_ANSWERS.azimuthDeg).toBe(DEFAULT_AZIMUTH_DEG);
    expect(EMPTY_ANSWERS.tiltDeg).toBe(DEFAULT_TILT_DEG);
    expect(toEstimateInput({ ...ROUND_ONE, roofAnswered: false })).toBeNull();
  });

  it("builds round one from the five values four questions collect", () => {
    expect(toEstimateInput(ROUND_ONE)).toEqual({
      postcode4: "5401",
      peak_power_wp: 4200,
      azimuth_deg: 45,
      tilt_deg: 35,
      annual_consumption_kwh: 3400,
    });
  });

  it("is null while round one is incomplete", () => {
    expect(toEstimateInput({ ...ROUND_ONE, peakPowerWp: null })).toBeNull();
    expect(toEstimateInput({ ...ROUND_ONE, annualConsumptionKwh: null })).toBeNull();
    expect(toEstimateInput(EMPTY_ANSWERS)).toBeNull();
  });

  it("turns the one car question into the two fields the serializer wants", () => {
    expect(toRefineInput(ROUND_TWO)).toMatchObject({ has_ev: true, ev_behaviour: "SOLAR" });
    expect(toRefineInput({ ...ROUND_TWO, ev: "NONE" })).toMatchObject({
      has_ev: false,
      ev_behaviour: null,
    });
  });

  it("refuses each yes that did not bring its detail, the way the serializer does", () => {
    expect(toRefineInput({ ...ROUND_TWO, heatPump: true })).toBeNull();
    expect(toRefineInput({ ...ROUND_TWO, battery: true })).toBeNull();
    expect(toRefineInput({ ...ROUND_TWO, heatPump: true, heatDemandKwh: 2400 })).toMatchObject({
      has_heat_pump: true,
      heat_demand_kwh: 2400,
    });
    expect(
      toRefineInput({ ...ROUND_TWO, battery: true, batteryCapacityKwh: 5 }),
    ).toMatchObject({ has_battery: true, battery_capacity_kwh: 5 });
  });

  it("never sends a detail without the flag that makes it legal", () => {
    // The serializer refuses a capacity without a battery, and it is right to:
    // two fields that disagree let whichever one is read first decide.
    expect(
      toRefineInput({ ...ROUND_TWO, battery: false, batteryCapacityKwh: 5 }),
    ).toMatchObject({ has_battery: false, battery_capacity_kwh: null });
    expect(
      toRefineInput({ ...ROUND_TWO, heatPump: false, heatDemandKwh: 2400 }),
    ).toMatchObject({ has_heat_pump: false, heat_demand_kwh: null });
  });

  it("is null when round two is short of an answer, and when round one is", () => {
    expect(toRefineInput({ ...ROUND_TWO, daytimeOccupancy: null })).toBeNull();
    expect(toRefineInput({ ...ROUND_TWO, ev: null })).toBeNull();
    expect(toRefineInput({ ...ROUND_TWO, dynamicContract: null })).toBeNull();
    expect(toRefineInput({ ...ROUND_TWO, roofAnswered: false })).toBeNull();
  });
});

describe("the question the visitor is looking at", () => {
  it("knows which of round one is answered", () => {
    expect(stepComplete(EMPTY_ANSWERS, 1, 0)).toBe(false);
    expect(stepComplete(ROUND_ONE, 1, 0)).toBe(true);
    expect(stepComplete(ROUND_ONE, 1, 1)).toBe(true);
    expect(stepComplete(ROUND_ONE, 1, 2)).toBe(true);
    expect(stepComplete(ROUND_ONE, 1, 3)).toBe(true);
    expect(stepComplete({ ...ROUND_ONE, roofAnswered: false }, 1, 2)).toBe(false);
  });

  it("checks the three pairs of round two as pairs", () => {
    expect(stepComplete(ROUND_TWO, 2, 0)).toBe(true);
    expect(stepComplete(ROUND_TWO, 2, 1)).toBe(true);
    expect(stepComplete(ROUND_TWO, 2, 2)).toBe(true);
    expect(stepComplete(ROUND_TWO, 2, 3)).toBe(true);
    expect(stepComplete(ROUND_TWO, 2, 4)).toBe(true);
    expect(stepComplete({ ...ROUND_TWO, heatPump: true }, 2, 2)).toBe(false);
    expect(stepComplete({ ...ROUND_TWO, battery: true }, 2, 4)).toBe(false);
    expect(stepComplete(EMPTY_ANSWERS, 2, 3)).toBe(false);
  });
});

describe("the half filled form, across a reload", () => {
  it("comes back the way it went in", () => {
    const storage = memoryStorage();
    saveAnswers(storage, ROUND_TWO);
    expect(loadAnswers(storage)).toEqual(ROUND_TWO);
  });

  it("goes in sessionStorage under a name a visitor can recognise", () => {
    const storage = memoryStorage();
    saveAnswers(storage, ROUND_ONE);
    expect([...storage.map.keys()]).toEqual([ANSWERS_STORAGE_KEY]);
  });

  it("keeps nothing it cannot check, because a browser wrote it", () => {
    // A cast of JSON.parse would put a string where a number belongs and the
    // failure would arrive as a 400 naming a field the visitor never saw.
    const storage = memoryStorage({
      [ANSWERS_STORAGE_KEY]: JSON.stringify({
        postcode4: "5401",
        peakPowerWp: 4200,
        ev: "ROCKET",
        roofAnswered: "yes",
        heatPump: null,
      }),
    });
    expect(loadAnswers(storage)).toEqual({
      ...EMPTY_ANSWERS,
      peakPowerWp: 4200,
    });
  });

  it("survives a storage that is empty, broken, or not there at all", () => {
    expect(loadAnswers(undefined)).toEqual(EMPTY_ANSWERS);
    expect(loadAnswers(memoryStorage())).toEqual(EMPTY_ANSWERS);
    expect(loadAnswers(memoryStorage({ [ANSWERS_STORAGE_KEY]: "{" }))).toEqual(EMPTY_ANSWERS);
    expect(loadAnswers(memoryStorage({ [ANSWERS_STORAGE_KEY]: "[1,2]" }))).toEqual(EMPTY_ANSWERS);
    expect(loadAnswers(memoryStorage({ [ANSWERS_STORAGE_KEY]: "null" }))).toEqual(EMPTY_ANSWERS);
    expect(loadAnswers(throwingStorage())).toEqual(EMPTY_ANSWERS);
  });

  it("keeps working when the browser refuses to store anything", () => {
    // A visitor with storage blocked keeps a working form and loses only the
    // ability to reload without retyping.
    expect(() => saveAnswers(throwingStorage(), ROUND_ONE)).not.toThrow();
    expect(() => clearAnswers(throwingStorage())).not.toThrow();
    expect(() => saveAnswers(undefined, ROUND_ONE)).not.toThrow();
    expect(() => clearAnswers(undefined)).not.toThrow();
  });

  it("is gone once it is cleared", () => {
    const storage = memoryStorage();
    saveAnswers(storage, ROUND_ONE);
    clearAnswers(storage);
    expect(loadAnswers(storage)).toEqual(EMPTY_ANSWERS);
  });
});
