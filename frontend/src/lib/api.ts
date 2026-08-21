import { ROUTE_ORDER, type Advice } from "@/lib/types";

/**
 * The browser talks to the advice API itself.
 *
 * Not a preference. The API throttles per IP (`advice-compute` is 20/hour,
 * `advice-read` 120/hour, see `backend/ampeer/settings/base.py`), so fetching
 * server-side would put every visitor into one bucket and turn a protection
 * into an outage for the twenty-first. And the answers are personal data,
 * which gain nothing from passing through one more process with one more
 * access log.
 *
 * THERE IS NO RETRY HERE, ON ANY STATUS. Read that again before adding one.
 * A 429 means slow down, and repeating the request is the single response
 * guaranteed to make it worse. A retried 400 asks the same wrong question
 * twice and gets the same answer. A retried 500 doubles the load on a server
 * that is already failing. If a request has to be made again, the person who
 * wanted the answer decides that, not this module.
 */
const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * The exact shape the API issues: 22 url-safe characters.
 *
 * `secrets.token_urlsafe(16)` emits base64url with the padding stripped, so
 * ceil(16 * 8 / 6) = 22 characters. `backend/advice/urls.py` derives the same
 * length from `TOKEN_BYTES` and routes on it, so anything else is already a
 * 404 there. Checking here means a typo or a probe never becomes a request.
 */
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{22}$/;

/**
 * A response the API refused to make into advice.
 *
 * `fields` mirrors DRF's `{field: [message, ...]}` error body, which is what a
 * 400 from `EstimateInputSerializer` or `RefineInputSerializer` looks like.
 * Other statuses have other bodies: a 429 sends `{"detail": "..."}` and a 404
 * sends nothing at all, so `fields` is empty for those and the sentence, if
 * there was one, is the message.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly fields: Record<string, string[]> = {},
    message = `advice API returned ${status}`,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * DRF's error bodies, reduced to one shape.
 *
 * `as_serializer_error` wraps every field message in a list, so the common
 * case is already `{field: [string]}`. A throttled request answers
 * `{"detail": string}` instead, and a body that is not an object at all is
 * something no endpoint here produces. Anything that does not fit is dropped
 * rather than guessed at: a caller that renders `fields` should never be
 * handed a value it cannot show.
 */
function readErrorBody(body: unknown): {
  fields: Record<string, string[]>;
  detail?: string;
} {
  if (typeof body !== "object" || body === null) return { fields: {} };
  const fields: Record<string, string[]> = {};
  let detail: string | undefined;
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    if (Array.isArray(value)) {
      const messages = value.filter(
        (entry): entry is string => typeof entry === "string",
      );
      if (messages.length > 0) fields[key] = messages;
    } else if (typeof value === "string") {
      if (key === "detail") detail = value;
      else fields[key] = [value];
    }
  }
  return detail === undefined ? { fields } : { fields, detail };
}

/**
 * The shape check, at the one place JSON becomes an Advice.
 *
 * There is no error boundary above the pages that render this, so a body with
 * a field missing or renamed does not produce a message: React unmounts the
 * tree and the visitor is left with a main element containing nothing at all.
 * That is the only failure on this site with nothing to read, and the two ways
 * in are ordinary: a proxy answering {"error": "upstream"} with a 200, and a
 * field renamed on the backend before this file learns about it.
 *
 * Every amount is checked for being a string, and that is the point rather
 * than a formality. JSON has no decimals, so an amount that travels as a
 * number has already been rounded by whichever parser touched it last, and
 * nothing downstream can tell: {"p10": 1} renders as a euro sign and a one,
 * cheerfully. lib/types.ts exists to keep those as strings and this is where
 * that promise is worth anything at runtime.
 *
 * A cast would be shorter. A cast is also the thing that turned a renamed
 * field into a blank page.
 */

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  // typeof [] is "object", which is exactly how an array reached a caller
  // expecting an advice and blanked the page.
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isStringList(value: unknown): boolean {
  return Array.isArray(value) && value.every(isString);
}

const CONFIDENCE_LEVELS = ["INDICATIVE", "GOOD", "PRECISE"];
const SIZING_BASES = [
  "CHOSEN_FROM_SIMULATED_CAPACITIES",
  "LIMITED_BY_LARGEST_SIMULATED_CAPACITY",
];

/** Three amounts as strings and the number of runs behind them. */
function isPercentileBand(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value["p10"]) &&
    isString(value["p50"]) &&
    isString(value["p90"]) &&
    isNumber(value["runs"])
  );
}

/** Narrower than a percentile band, and it carries the two lists that say so. */
function isScenarioBand(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value["low"]) &&
    isString(value["mid"]) &&
    isString(value["high"]) &&
    isStringList(value["varied"]) &&
    isStringList(value["pinned"]) &&
    isStringList(value["varied_text"]) &&
    isStringList(value["pinned_text"]) &&
    isNumber(value["combinations"])
  );
}

/** A figure with no margin, and the sentence that says why it has none. */
function isBandlessFigure(value: unknown): boolean {
  return (
    isObject(value) &&
    isNumber(value["value"]) &&
    value["band"] === null &&
    isString(value["basis"]) &&
    SIZING_BASES.includes(value["basis"]) &&
    isString(value["basis_text"])
  );
}

function isFiredRule(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value["rule_id"]) &&
    isString(value["text"]) &&
    (value["saving_eur"] === null || isScenarioBand(value["saving_eur"]))
  );
}

function isRouteBlock(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value["route"]) &&
    (ROUTE_ORDER as readonly string[]).includes(value["route"]) &&
    isString(value["title"]) &&
    Array.isArray(value["rules"]) &&
    value["rules"].every(isFiredRule)
  );
}

/** A capacity and the band that came out of the simulation at it, in that order. */
function isCurvePoint(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    isNumber(value[0]) &&
    isScenarioBand(value[1])
  );
}

function isBatteryAdvice(value: unknown): boolean {
  return (
    isObject(value) &&
    isString(value["verdict"]) &&
    isBandlessFigure(value["sized_capacity_kwh"]) &&
    isScenarioBand(value["annual_saving_eur"]) &&
    isScenarioBand(value["payback_years"]) &&
    isScenarioBand(value["break_even_cost_per_kwh"]) &&
    Array.isArray(value["curve"]) &&
    value["curve"].every(isCurvePoint)
  );
}

function isAdvice(value: unknown): value is Advice {
  return (
    isObject(value) &&
    isString(value["token"]) &&
    isString(value["confidence"]) &&
    CONFIDENCE_LEVELS.includes(value["confidence"]) &&
    isString(value["confidence_label"]) &&
    isPercentileBand(value["headline"]) &&
    Array.isArray(value["routes"]) &&
    value["routes"].every(isRouteBlock) &&
    (value["battery"] === null || isBatteryAdvice(value["battery"])) &&
    isString(value["engine_version"]) &&
    isString(value["advice_version"]) &&
    isString(value["production_source"]) &&
    isString(value["production_source_text"]) &&
    isNumber(value["profile_year"]) &&
    isNumber(value["weather_year"])
  );
}

async function call(path: string, body?: unknown): Promise<Advice> {
  const response = await fetch(`${BASE}${path}`, {
    // A GET carries no content-type on purpose. A content-type outside the
    // CORS safelist turns a simple cross-origin GET into a preflight, which
    // is a second round trip bought for a header the request does not need.
    ...(body === undefined
      ? { method: "GET" }
      : {
          method: "POST",
          body: JSON.stringify(body),
          headers: { "content-type": "application/json" },
        }),
    // No cookies, in either direction. There is no session on this API, so
    // there is nothing to send and nothing to steal. Set after the spread so
    // no caller can turn it back on by accident.
    credentials: "omit",
  });
  if (!response.ok) {
    // No retry. See the note at the top of this file.
    const { fields, detail } = readErrorBody(
      await response.json().catch(() => null),
    );
    throw new ApiError(response.status, fields, detail);
  }
  const advice = await response.json().catch(() => null);
  if (!isAdvice(advice)) {
    // A 200 whose body is not an advice is a proxy, an error page, or a
    // backend that renamed a field. Raising an ApiError keeps every failure
    // from this module one type, so a caller that catches ApiError does not
    // also need a catch-all, and every one of them has a sentence to show.
    throw new ApiError(
      response.status,
      {},
      "advice API returned a body that is not an advice",
    );
  }
  return advice;
}

export interface EstimateInput {
  readonly postcode4: string;
  readonly peak_power_wp: number;
  readonly azimuth_deg: number;
  readonly tilt_deg: number;
  readonly annual_consumption_kwh: number;
}

export interface RefineInput extends EstimateInput {
  readonly daytime_occupancy: boolean;
  readonly has_ev: boolean;
  /** The names of `ampeer_sim.types.EVChargingBehaviour`, which the serializer derives its choices from. */
  readonly ev_behaviour: "NIGHT" | "ARRIVAL" | "SOLAR" | null;
  readonly has_heat_pump: boolean;
  readonly heat_demand_kwh: number | null;
  readonly dynamic_contract: boolean;
  readonly has_battery: boolean;
  readonly battery_capacity_kwh: number | null;
}

/** Round one: four questions, five values. Answers 201 with the advice. */
export const postEstimate = (input: EstimateInput): Promise<Advice> =>
  call("/api/advice/estimate/", input);

/** Round two: nine questions. Answers 201 with a new advice and a new token. */
export const postRefine = (input: RefineInput): Promise<Advice> =>
  call("/api/advice/refine/", input);

/**
 * The shareable link, read back.
 *
 * A token that is not the shape the API issues never becomes a request. The
 * router would answer 404 anyway, so the round trip could only tell the
 * visitor something they already know, at the cost of one call against a
 * budget of 120 an hour.
 */
export function getAdvice(token: string): Promise<Advice> {
  if (!TOKEN_PATTERN.test(token)) {
    return Promise.reject(new ApiError(400, {}, "not a token this API issues"));
  }
  return call(`/api/advice/${token}/`);
}
