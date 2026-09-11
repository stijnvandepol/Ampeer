import { ApiError } from "@/lib/api";

/**
 * The account API, which is the opposite of the advice API in the one way that
 * matters.
 *
 * `api.ts` sets `credentials: "omit"` and says why: there is no session there,
 * so there is nothing to send and nothing to steal. Here there is a session, it
 * lives in two httpOnly cookies, and every single call has to carry them, the
 * GETs included. That is why this is a second module rather than an option on
 * the first: an option is something a caller can get wrong.
 *
 * THERE IS NO RETRY HERE EITHER, ON ANY STATUS. The one exchange the design
 * allows, a 401 on `me/` at page load followed by one `refresh/` and one more
 * `me/`, is not in this file. It lives in `app/_account/session.ts`, so there
 * is exactly one place where it can happen and it is the load function.
 *
 * Every answer is checked for shape before it becomes a value, for the reason
 * `isAdvice` gives one module over: there is no error boundary above this page,
 * so a renamed field produces no message, it produces an empty screen.
 */
/**
 * Exported for `_account/AccountPage.tsx`, which needs it to show the full
 * push address (`apiBase + push_path`) beside the one-time meter key. Nothing
 * else outside this file has a reason to read it: every other call already
 * carries this prefix internally.
 */
export const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * The two kinds, in the order the API sends them.
 *
 * `sorted(Consent.KINDS)` on the Python side, and
 * `tests/test_frontend_contract.py` compares this list with that one, so a
 * third kind falls over on the side where it was added rather than becoming a
 * row the browser silently never shows.
 */
export const CONSENT_KINDS = ["LEAD_GENERATION", "METER_LINK"] as const;

export type ConsentKind = (typeof CONSENT_KINDS)[number];
export type ConsentAction = "GRANTED" | "WITHDRAWN";

export interface ConsentTexts {
  readonly text_version: string;
  readonly texts: Readonly<Record<ConsentKind, string>>;
  /**
   * The heading each consent is shown under, from the same answer and under
   * the same version as the sentence it heads. Decision 38: a label edit is
   * caught the way a text edit is, and no label lives in this tree.
   */
  readonly labels: Readonly<Record<ConsentKind, string>>;
}

export interface Me {
  readonly email: string;
  readonly consents: Readonly<Record<ConsentKind, boolean>>;
  /** ISO 8601, or null for an address nobody has confirmed yet. */
  readonly email_verified_at: string | null;
}

export interface ConsentResult {
  readonly kind: ConsentKind;
  readonly granted: boolean;
}

/**
 * What `GET /api/auth/meter/` answers with. No reason is carried alongside
 * `may_link`: the backend knows why linking is blocked (an unconfirmed
 * address, a missing consent, or both), and this shape does not repeat that
 * distinction, so the frontend shows one requirement sentence rather than
 * guessing which half of it still needs doing.
 */
export interface MeterStatus {
  readonly may_link: boolean;
  readonly linked: boolean;
  /** ISO 8601, or null when there is no active link. */
  readonly created_at: string | null;
  /** ISO 8601, or null when a link exists but nothing has arrived yet. */
  readonly last_seen_at: string | null;
  /**
   * The same moment as words, in Europe/Amsterdam, built by the API.
   *
   * The page may not build this itself: `.semgrep/frontend.yml`'s
   * ampeer-no-reading-the-clock forbids `new Date(...)` here, and says a date
   * the visitor should see comes from the API, which computed it. Keeping
   * both means anything that needs the value still has the ISO.
   */
  readonly last_seen_label: string | null;
}

/**
 * What this household's own meter says about the annual consumption it typed.
 *
 * A band and not a number. Ampeer puts this in front of a household only when
 * their own figure falls outside it, so the band is both the answer and the
 * reason there is one: a figure inside it is a figure the measurements do not
 * contradict, and then nothing is shown at all.
 */
export interface ConsumptionCheck {
  readonly typed_kwh: number;
  readonly p10_kwh: number;
  readonly p50_kwh: number;
  readonly p90_kwh: number;
  /** How many refits the band was measured over, each with a week withheld. */
  readonly runs: number;
  readonly quarters_used: number;
  /** The Dutch sentence, from the API. No wording is built here. */
  readonly message: string;
  /**
   * Set when the modelled feed-in does not match the meter's either.
   *
   * The fit matched offtake, so a disagreeing feed-in points at the
   * description of the installation rather than at the consumption, and a
   * household should hear that before accepting a figure that carries it.
   */
  readonly installation_note: string | null;
}

export interface ConsumptionCheckAnswer {
  /** The advice the correction applies to, or null when there is nothing. */
  readonly advice_token: string | null;
  readonly check: ConsumptionCheck | null;
}

/**
 * What `POST /api/auth/meter/link/` answers with, once, per design chapter 3:
 * the key is shown exactly here and never again, so nothing in this file
 * offers a second way to read it back.
 */
export interface MeterKey {
  readonly token: string;
  readonly push_path: string;
  readonly created_at: string;
}

export interface SignInInput {
  readonly email: string;
  readonly password: string;
}

export interface RegisterInput extends SignInInput {
  readonly consent_meter_link: boolean;
  readonly consent_lead_generation: boolean;
  /** The version whose sentences were on the screen. Never a constant here. */
  readonly text_version: string;
}

export interface ConsentInput {
  readonly kind: ConsentKind;
  readonly action: ConsentAction;
  /** Sent on GRANTED, absent on WITHDRAWN. Chapter 5.2 of the design. */
  readonly text_version?: string | undefined;
}

export interface ResetRequestInput {
  readonly email: string;
}

export interface ResetConfirmInput {
  /** Off the fragment of the link in the mail. Never typed, never shown. */
  readonly token: string;
  readonly password: string;
}

export interface VerifyConfirmInput {
  readonly token: string;
}

/**
 * DRF's error bodies, reduced to one shape.
 *
 * A deliberate copy of the function of the same name in `api.ts`, which does
 * not export it. Chapter 4.1 of the design weighs the three options and takes
 * this one: exporting it would edit the file frontend/CLAUDE.md puts under
 * lock, and a third module both read from would do the same. The copy is not
 * kept in step by a promise but by a test, "the duplicated error reduction" in
 * tests/lib/accounts.test.ts, which runs one table of bodies through both.
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
 * The double submit token, read from the cookie the API set.
 *
 * `CSRF_COOKIE_HTTPONLY = False` is what makes this possible, and that is not
 * a weakening: a token JavaScript cannot read is a token JavaScript cannot
 * send back. Null when there is none, in which case nothing is sent and the
 * API answers 403 with a sentence saying to reload, which is the truth.
 */
function csrfToken(): string | null {
  for (const entry of document.cookie.split(";")) {
    const [name, ...rest] = entry.trim().split("=");
    if (name === "csrftoken") return decodeURIComponent(rest.join("="));
  }
  return null;
}

interface CallOptions {
  readonly method: "GET" | "POST";
  readonly body?: unknown;
}

/**
 * One request, and the error it raises when the answer is not a success.
 *
 * The `ApiError` this throws carries the API's own sentence as its message, and
 * an empty message when the API sent none. `_account/messages.ts` reads that
 * difference, because `ApiError`'s own default message is English ("advice API
 * returned 401") and showing that to a household would be the language
 * boundary crossed from the wrong side.
 */
async function call(path: string, options: CallOptions): Promise<Response> {
  const token = options.method === "GET" ? null : csrfToken();
  const response = await fetch(`${BASE}${path}`, {
    method: options.method,
    ...(options.body === undefined
      ? {}
      : { body: JSON.stringify(options.body) }),
    headers: {
      ...(options.body === undefined
        ? {}
        : { "content-type": "application/json" }),
      ...(token === null ? {} : { "X-CSRFToken": token }),
    },
    // The session, in both directions, on every call including the GETs. Set
    // after the spread so no caller can turn it off by accident, which is the
    // same placement and the same argument as `omit` in api.ts.
    credentials: "include",
  });
  if (!response.ok) {
    // No retry. See the note at the top of this file.
    const { fields, detail } = readErrorBody(
      await response.json().catch(() => null),
    );
    throw new ApiError(response.status, fields, detail ?? "");
  }
  return response;
}

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

/** Both kinds present under `texts` and under `labels`, none empty. A further key is left alone. */
function isConsentTexts(value: unknown): value is ConsentTexts {
  if (!isObject(value)) return false;
  const version = value["text_version"];
  if (!isString(version) || version.length === 0) return false;
  const texts = value["texts"];
  const labels = value["labels"];
  if (!isObject(texts) || !isObject(labels)) return false;
  return CONSENT_KINDS.every((kind) => {
    const sentence = texts[kind];
    const label = labels[kind];
    return (
      isString(sentence) &&
      sentence.length > 0 &&
      isString(label) &&
      label.length > 0
    );
  });
}

function isMe(value: unknown): value is Me {
  if (!isObject(value) || !isString(value["email"])) return false;
  const consents = value["consents"];
  if (!isObject(consents)) return false;
  if (!("email_verified_at" in value)) return false;
  const verified = value["email_verified_at"];
  if (verified !== null && !isString(verified)) return false;
  return CONSENT_KINDS.every((kind) => typeof consents[kind] === "boolean");
}

/**
 * Five keys of the right type, `created_at`, `last_seen_at` and
 * `last_seen_label` as a string or
 * `null`, both checked with `"key" in value` first for the same reason `isMe`
 * checks `email_verified_at` that way: a missing key is not the same claim as
 * a `null` one, and a body that dropped the key silently is not a body this
 * screen can render a state from.
 */
function isConsumptionCheck(value: unknown): value is ConsumptionCheck {
  if (!isObject(value)) return false;
  for (const key of [
    "typed_kwh",
    "p10_kwh",
    "p50_kwh",
    "p90_kwh",
    "runs",
    "quarters_used",
  ]) {
    if (typeof value[key] !== "number") return false;
  }
  if (!isString(value["message"])) return false;
  if (!("installation_note" in value)) return false;
  const note = value["installation_note"];
  if (note !== null && !isString(note)) return false;
  return true;
}

function isConsumptionCheckAnswer(
  value: unknown,
): value is ConsumptionCheckAnswer {
  if (!isObject(value)) return false;
  if (!("advice_token" in value) || !("check" in value)) return false;
  const token = value["advice_token"];
  if (token !== null && !isString(token)) return false;
  const check = value["check"];
  return check === null || isConsumptionCheck(check);
}

function isMeterStatus(value: unknown): value is MeterStatus {
  if (!isObject(value)) return false;
  if (typeof value["may_link"] !== "boolean") return false;
  if (typeof value["linked"] !== "boolean") return false;
  if (!("created_at" in value)) return false;
  const createdAt = value["created_at"];
  if (createdAt !== null && !isString(createdAt)) return false;
  if (!("last_seen_at" in value)) return false;
  const lastSeenAt = value["last_seen_at"];
  if (lastSeenAt !== null && !isString(lastSeenAt)) return false;
  if (!("last_seen_label" in value)) return false;
  const lastSeenLabel = value["last_seen_label"];
  if (lastSeenLabel !== null && !isString(lastSeenLabel)) return false;
  return true;
}

/**
 * A non-empty `token`, a `push_path` that starts with `/` (the address a
 * device pushes to, always a path on this same API), and a `created_at`.
 */
function isMeterKey(value: unknown): value is MeterKey {
  return (
    isObject(value) &&
    isString(value["token"]) &&
    value["token"].length > 0 &&
    isString(value["push_path"]) &&
    value["push_path"].startsWith("/") &&
    isString(value["created_at"])
  );
}

/** The answer is about the kind that was sent, or it is about nothing. */
function isConsentResult(
  value: unknown,
  kind: ConsentKind,
): value is ConsentResult {
  return (
    isObject(value) &&
    value["kind"] === kind &&
    typeof value["granted"] === "boolean"
  );
}

/**
 * The export, checked no deeper than "an object with inputs and advice".
 *
 * A second copy of `isAdvice` here could refuse a valid export because this
 * file does not yet know about a field the engine started sending, and that is
 * the wrong side to drop that error on: the download is the visitor's own data
 * and the frontend renders none of it.
 */
function isExport(value: unknown): boolean {
  if (!isObject(value) || !isString(value["email"])) return false;
  if (!isString(value["date_joined"])) return false;
  const consents = value["consents"];
  const advices = value["advices"];
  if (!Array.isArray(consents) || !Array.isArray(advices)) return false;
  return (
    consents.every(
      (row) =>
        isObject(row) &&
        isString(row["kind"]) &&
        isString(row["action"]) &&
        isString(row["occurred_at"]) &&
        isString(row["text_version"]),
    ) &&
    advices.every((row) => isObject(row) && "inputs" in row && "advice" in row)
  );
}

/**
 * A success whose body is not what this route answers with.
 *
 * The message is EMPTY, and that is the contract the docstring on `call()`
 * above states: an `ApiError` from this file carries the API's own sentence or
 * nothing at all. `describeAuthError` shows a non-empty message word for word,
 * because almost every one of them is Dutch and came from the API, so an
 * English sentence put here would be printed at a household unchanged. The
 * guard that refused the body has no Dutch to offer anyway: it is the frontend
 * saying it could not read something, and `messages.ts` already holds the one
 * sentence for exactly that.
 *
 * `what` is not thrown away. It goes on `cause`, where a developer reading a
 * console or a stack trace finds which guard refused which route, and where
 * nothing that renders will ever look for it.
 */
function unreadable(response: Response, what: string): ApiError {
  const error = new ApiError(response.status, {}, "");
  error.cause = `auth API returned ${what}`;
  return error;
}

export async function getConsentTexts(): Promise<ConsentTexts> {
  const response = await call("/api/auth/consent-texts/", { method: "GET" });
  const body: unknown = await response.json().catch(() => null);
  if (!isConsentTexts(body)) throw unreadable(response, "no consent texts");
  return body;
}

export async function register(input: RegisterInput): Promise<void> {
  await call("/api/auth/register/", { method: "POST", body: input });
}

export async function login(input: SignInInput): Promise<void> {
  await call("/api/auth/login/", { method: "POST", body: input });
}

export async function refresh(): Promise<void> {
  await call("/api/auth/refresh/", { method: "POST" });
}

export async function getMe(): Promise<Me> {
  const response = await call("/api/auth/me/", { method: "GET" });
  const body: unknown = await response.json().catch(() => null);
  if (!isMe(body)) throw unreadable(response, "no account");
  return body;
}

export async function postConsent(input: ConsentInput): Promise<ConsentResult> {
  const response = await call("/api/auth/consent/", {
    method: "POST",
    body: input,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!isConsentResult(body, input.kind)) {
    throw unreadable(response, "an answer about another consent");
  }
  return body;
}

/**
 * Ask what the meter says about the most recent advice on this account.
 *
 * A POST for a question, which is unusual and deliberate: answering runs the
 * engine several times over the measured window, so it sits behind the same
 * rate as the routes that write, and nothing between here and the API should
 * treat it as cacheable.
 */
export async function checkConsumption(): Promise<ConsumptionCheckAnswer> {
  const response = await call("/api/auth/advice/check/", { method: "POST" });
  const body: unknown = await response.json().catch(() => null);
  if (!isConsumptionCheckAnswer(body)) {
    throw unreadable(response, "no consumption check");
  }
  return body;
}

/**
 * Take the meter's figure and recompute that advice on it.
 *
 * Answers with a fresh advice under a new token: the old one keeps the answer
 * the household's own figure produced, which is what makes accepting a choice
 * rather than an overwrite.
 */
export async function acceptConsumption(token: string): Promise<string> {
  const response = await call(`/api/auth/advice/${token}/accept/`, {
    method: "POST",
  });
  const body: unknown = await response.json().catch(() => null);
  if (!isObject(body) || !isString(body["token"])) {
    throw unreadable(response, "no advice");
  }
  return body["token"];
}

export async function getMeterStatus(): Promise<MeterStatus> {
  const response = await call("/api/auth/meter/", { method: "GET" });
  const body: unknown = await response.json().catch(() => null);
  if (!isMeterStatus(body)) throw unreadable(response, "no meter status");
  return body;
}

export async function linkMeter(): Promise<MeterKey> {
  const response = await call("/api/auth/meter/link/", { method: "POST" });
  const body: unknown = await response.json().catch(() => null);
  if (!isMeterKey(body)) throw unreadable(response, "no meter key");
  return body;
}

export async function unlinkMeter(): Promise<void> {
  // 204, so there is no body, the same contract as logout() below.
  await call("/api/auth/meter/unlink/", { method: "POST" });
}

/**
 * The export, as the text the API sent.
 *
 * Read once, as text, and handed to the download unchanged. Not parsed and
 * re-serialised: every amount inside an advice is a string because JSON has
 * only floats, and a second trip through a parser is exactly the mistake this
 * project avoids everywhere else. The shape check runs on `JSON.parse` of that
 * same text, and the parsed value is then thrown away.
 */
export async function exportAccount(): Promise<string> {
  const response = await call("/api/auth/export/", { method: "POST" });
  const text = await response.text();
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw unreadable(response, "an export that is not JSON");
  }
  if (!isExport(parsed)) throw unreadable(response, "no export");
  return text;
}

export async function logout(): Promise<void> {
  // 204, so there is no body. `response.json()` throws on one.
  await call("/api/auth/logout/", { method: "POST" });
}

export async function deleteAccount(password: string): Promise<void> {
  await call("/api/auth/delete/", { method: "POST", body: { password } });
}

/**
 * The four recovery calls. All four answer with an empty body (202 with `{}`,
 * or 204), so there is no shape to check and nothing to return: a success is
 * the absence of an `ApiError`, and a failure carries the API's own Dutch
 * sentence, under `token` or `password` or as `detail`, like every other call
 * in this file.
 */
export async function requestPasswordReset(
  input: ResetRequestInput,
): Promise<void> {
  await call("/api/auth/reset/request/", { method: "POST", body: input });
}

export async function confirmPasswordReset(
  input: ResetConfirmInput,
): Promise<void> {
  await call("/api/auth/reset/confirm/", { method: "POST", body: input });
}

export async function requestEmailVerification(): Promise<void> {
  await call("/api/auth/verify/request/", { method: "POST" });
}

export async function confirmEmailVerification(
  input: VerifyConfirmInput,
): Promise<void> {
  await call("/api/auth/verify/confirm/", { method: "POST", body: input });
}
