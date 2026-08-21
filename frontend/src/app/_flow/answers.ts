import type { EstimateInput, RefineInput } from "@/lib/api";

/**
 * The answers, while they are still incomplete.
 *
 * Every field is nullable because a half-filled form is the normal state of
 * this page, and `null` here means "not answered yet" rather than zero. The
 * API's input types have no room for that, which is why they are built at the
 * end by `toEstimateInput` and `toRefineInput` and not filled in as we go: a
 * partial object cast to `EstimateInput` is a lie the compiler would believe.
 */
export interface Answers {
  readonly postcode4: number | null;
  readonly peakPowerWp: number | null;
  readonly azimuthDeg: number;
  readonly tiltDeg: number;
  readonly roofAnswered: boolean;
  readonly annualConsumptionKwh: number | null;
  readonly daytimeOccupancy: boolean | null;
  /** "NONE" and a charging behaviour, in one answer, because it is one question. */
  readonly ev: EvAnswer | null;
  readonly heatPump: boolean | null;
  readonly heatDemandKwh: number | null;
  readonly dynamicContract: boolean | null;
  readonly battery: boolean | null;
  readonly batteryCapacityKwh: number | null;
}

/**
 * The `EVChargingBehaviour` names the serializer derives its choices from,
 * plus the answer "no car", which is not a behaviour and so is not in the enum.
 */
export type EvAnswer = "NONE" | "NIGHT" | "ARRIVAL" | "SOLAR";

/**
 * A south-facing roof at 35 degrees, which is where the pickers start.
 *
 * These two are not null like everything else, because a slider and a compass
 * have to point somewhere the moment they are drawn. `roofAnswered` carries
 * what the nulls carry elsewhere: whether the visitor has touched it. Without
 * that flag a visitor who skipped the question would have answered "south, 35
 * degrees" without ever saying so.
 */
export const DEFAULT_AZIMUTH_DEG = 0;
export const DEFAULT_TILT_DEG = 35;

export const EMPTY_ANSWERS: Answers = {
  postcode4: null,
  peakPowerWp: null,
  azimuthDeg: DEFAULT_AZIMUTH_DEG,
  tiltDeg: DEFAULT_TILT_DEG,
  roofAnswered: false,
  annualConsumptionKwh: null,
  daytimeOccupancy: null,
  ev: null,
  heatPump: null,
  heatDemandKwh: null,
  dynamicContract: null,
  battery: null,
  batteryCapacityKwh: null,
};

/**
 * Where a half-filled form survives a reload.
 *
 * sessionStorage and not localStorage. This is consumption data about a
 * household, from which it can be read when somebody is home, and it should
 * not outlive the tab it was typed into.
 */
export const ANSWERS_STORAGE_KEY = "ampeer-antwoorden";

function readNumber(source: Record<string, unknown>, key: string): number | null {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readBoolean(source: Record<string, unknown>, key: string): boolean | null {
  const value = source[key];
  return typeof value === "boolean" ? value : null;
}

function readEv(source: Record<string, unknown>): EvAnswer | null {
  const value = source["ev"];
  return value === "NONE" || value === "NIGHT" || value === "ARRIVAL" || value === "SOLAR"
    ? value
    : null;
}

/**
 * Reads back what was stored, field by field, keeping nothing it cannot check.
 *
 * Not a cast of JSON.parse to Answers. This string came out of storage, which
 * is to say out of the browser, where anything at all may have written it. A
 * cast would put a string where a number belongs and the failure would surface
 * as a 400 from the API naming a field the visitor never saw.
 */
export function loadAnswers(storage: Pick<Storage, "getItem"> | undefined): Answers {
  if (storage === undefined) return EMPTY_ANSWERS;
  let parsed: unknown;
  try {
    const raw = storage.getItem(ANSWERS_STORAGE_KEY);
    if (raw === null) return EMPTY_ANSWERS;
    parsed = JSON.parse(raw);
  } catch {
    return EMPTY_ANSWERS;
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return EMPTY_ANSWERS;
  }
  const source = parsed as Record<string, unknown>;
  return {
    postcode4: readNumber(source, "postcode4"),
    peakPowerWp: readNumber(source, "peakPowerWp"),
    azimuthDeg: readNumber(source, "azimuthDeg") ?? DEFAULT_AZIMUTH_DEG,
    tiltDeg: readNumber(source, "tiltDeg") ?? DEFAULT_TILT_DEG,
    roofAnswered: readBoolean(source, "roofAnswered") ?? false,
    annualConsumptionKwh: readNumber(source, "annualConsumptionKwh"),
    daytimeOccupancy: readBoolean(source, "daytimeOccupancy"),
    ev: readEv(source),
    heatPump: readBoolean(source, "heatPump"),
    heatDemandKwh: readNumber(source, "heatDemandKwh"),
    dynamicContract: readBoolean(source, "dynamicContract"),
    battery: readBoolean(source, "battery"),
    batteryCapacityKwh: readNumber(source, "batteryCapacityKwh"),
  };
}

export function saveAnswers(storage: Pick<Storage, "setItem"> | undefined, answers: Answers): void {
  if (storage === undefined) return;
  try {
    storage.setItem(ANSWERS_STORAGE_KEY, JSON.stringify(answers));
  } catch {
    // A visitor with storage blocked keeps a working form and loses only the
    // ability to reload without retyping. Not worth an error message.
  }
}

export function clearAnswers(storage: Pick<Storage, "removeItem"> | undefined): void {
  if (storage === undefined) return;
  try {
    storage.removeItem(ANSWERS_STORAGE_KEY);
  } catch {
    // Same reason as above.
  }
}

/**
 * Four digits as a string, which is what the API's RegexField wants.
 *
 * The form collects a number so that the bounds check can name the end that
 * was passed, and String() of an integer between 1000 and 9999 is always four
 * ASCII digits. This returns null outside that range rather than padding,
 * because a padded 123 is a postcode the visitor never typed.
 */
export function postcodeText(value: number): string | null {
  if (!Number.isInteger(value) || value < 1000 || value > 9999) return null;
  return String(value);
}

/**
 * Whether the question at this position has an answer the API could use.
 *
 * One question per screen means one of these per screen, and the flow refuses
 * to advance past a question that is not answered rather than disabling the
 * button. A disabled button says nothing about why it is disabled, and the
 * visitor who cannot see the field they missed is exactly the visitor a
 * disabled button strands.
 *
 * The three pairs in round two are checked as pairs, because the serializer
 * checks them as pairs: a heat pump without a demand is refused there, and
 * finding that out three screens later is finding it out too late.
 */
export function stepComplete(answers: Answers, round: 1 | 2, index: number): boolean {
  if (round === 1) {
    if (index === 0) return answers.postcode4 !== null;
    if (index === 1) return answers.peakPowerWp !== null;
    if (index === 2) return answers.roofAnswered;
    return answers.annualConsumptionKwh !== null;
  }
  if (index === 0) return answers.daytimeOccupancy !== null;
  if (index === 1) return answers.ev !== null;
  if (index === 2) return answers.heatPump !== null && (!answers.heatPump || answers.heatDemandKwh !== null);
  if (index === 3) return answers.dynamicContract !== null;
  return answers.battery !== null && (!answers.battery || answers.batteryCapacityKwh !== null);
}

/** Round one is complete when all five values are present and the roof was set. */
export function toEstimateInput(answers: Answers): EstimateInput | null {
  const { postcode4, peakPowerWp, annualConsumptionKwh, roofAnswered } = answers;
  if (postcode4 === null || peakPowerWp === null || annualConsumptionKwh === null) return null;
  if (!roofAnswered) return null;
  const postcode = postcodeText(postcode4);
  if (postcode === null) return null;
  return {
    postcode4: postcode,
    peak_power_wp: peakPowerWp,
    azimuth_deg: answers.azimuthDeg,
    tilt_deg: answers.tiltDeg,
    annual_consumption_kwh: annualConsumptionKwh,
  };
}

/**
 * Round two, built only when every yes brought the detail that makes it usable.
 *
 * The serializer refuses has_ev without ev_behaviour, a heat pump without a
 * demand and a battery without a capacity, and reports all three together.
 * Building the same three pairs here means the visitor is stopped by a
 * disabled button on the question they are looking at, rather than by a 400
 * naming a field three screens back.
 */
export function toRefineInput(answers: Answers): RefineInput | null {
  const base = toEstimateInput(answers);
  if (base === null) return null;
  const { daytimeOccupancy, ev, heatPump, heatDemandKwh, dynamicContract, battery } = answers;
  if (daytimeOccupancy === null || ev === null) return null;
  if (heatPump === null || dynamicContract === null || battery === null) return null;
  if (heatPump && heatDemandKwh === null) return null;
  if (battery && answers.batteryCapacityKwh === null) return null;
  return {
    ...base,
    daytime_occupancy: daytimeOccupancy,
    has_ev: ev !== "NONE",
    ev_behaviour: ev === "NONE" ? null : ev,
    has_heat_pump: heatPump,
    heat_demand_kwh: heatPump ? heatDemandKwh : null,
    dynamic_contract: dynamicContract,
    has_battery: battery,
    battery_capacity_kwh: battery ? answers.batteryCapacityKwh : null,
  };
}
