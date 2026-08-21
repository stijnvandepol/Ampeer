import type { Advice } from "@/lib/types";

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
function readErrorBody(body: unknown): { fields: Record<string, string[]>; detail?: string } {
  if (typeof body !== "object" || body === null) return { fields: {} };
  const fields: Record<string, string[]> = {};
  let detail: string | undefined;
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    if (Array.isArray(value)) {
      const messages = value.filter((entry): entry is string => typeof entry === "string");
      if (messages.length > 0) fields[key] = messages;
    } else if (typeof value === "string") {
      if (key === "detail") detail = value;
      else fields[key] = [value];
    }
  }
  return detail === undefined ? { fields } : { fields, detail };
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
    const { fields, detail } = readErrorBody(await response.json().catch(() => null));
    throw new ApiError(response.status, fields, detail);
  }
  const advice = await response.json().catch(() => null);
  if (typeof advice !== "object" || advice === null) {
    // A 200 whose body is not JSON is a proxy or an error page, not an answer.
    // Raising an ApiError keeps every failure from this module one type, so a
    // caller that catches ApiError does not also need a catch-all.
    throw new ApiError(response.status, {}, "advice API returned a body that is not JSON");
  }
  return advice as Advice;
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
