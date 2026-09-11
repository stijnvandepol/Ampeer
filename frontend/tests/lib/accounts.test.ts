import { afterEach, describe, expect, it, vi } from "vitest";
import consentTexts from "../fixtures/consent-texts.json";
import me from "../fixtures/me-response.json";
import exportPayload from "../fixtures/export-response.json";
import { ApiError, postEstimate } from "@/lib/api";
import {
  confirmEmailVerification,
  confirmPasswordReset,
  deleteAccount,
  exportAccount,
  getConsentTexts,
  getMe,
  getMeterStatus,
  acceptConsumption,
  checkConsumption,
  linkMeter,
  login,
  logout,
  postConsent,
  refresh,
  register,
  requestEmailVerification,
  requestPasswordReset,
  unlinkMeter,
} from "@/lib/accounts";

const METER_STATUS = {
  may_link: true,
  linked: false,
  created_at: null,
  last_seen_at: null,
  last_seen_label: null,
};

const METER_KEY = {
  token: "a".repeat(43),
  push_path: "/api/meter/readings/",
  created_at: "2026-09-09T10:00:00Z",
};

const REGISTER_INPUT = {
  email: "iemand@voorbeeld.nl",
  password: "een-heel-lang-wachtwoord",
  consent_meter_link: false,
  consent_lead_generation: false,
  text_version: consentTexts.text_version,
};

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "csrftoken=; max-age=0";
});

/** A fresh Response per call: a body can only be read once. */
function stub(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(async () =>
    status === 204
      ? new Response(null, { status })
      : new Response(JSON.stringify(body), {
          status,
          headers: { "content-type": "application/json" },
        }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** The thirteen calls, each with the status and body its own route answers with. */
const CALLS: readonly {
  readonly name: string;
  readonly status: number;
  readonly body: unknown;
  readonly method: "GET" | "POST";
  readonly run: () => Promise<unknown>;
}[] = [
  {
    name: "consent-texts",
    status: 200,
    body: consentTexts,
    method: "GET",
    run: getConsentTexts,
  },
  {
    name: "register",
    status: 201,
    body: null,
    method: "POST",
    run: () => register(REGISTER_INPUT),
  },
  {
    name: "login",
    status: 200,
    body: null,
    method: "POST",
    run: () =>
      login({
        email: "iemand@voorbeeld.nl",
        password: "een-heel-lang-wachtwoord",
      }),
  },
  { name: "refresh", status: 200, body: null, method: "POST", run: refresh },
  { name: "me", status: 200, body: me, method: "GET", run: getMe },
  {
    name: "consent",
    status: 200,
    body: { kind: "METER_LINK", granted: true },
    method: "POST",
    run: () =>
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: consentTexts.text_version,
      }),
  },
  {
    name: "export",
    status: 200,
    body: exportPayload,
    method: "POST",
    run: exportAccount,
  },
  {
    name: "meter-status",
    status: 200,
    body: METER_STATUS,
    method: "GET",
    run: getMeterStatus,
  },
  {
    name: "meter-link",
    status: 201,
    body: METER_KEY,
    method: "POST",
    run: linkMeter,
  },
  {
    name: "meter-unlink",
    status: 204,
    body: null,
    method: "POST",
    run: unlinkMeter,
  },
  { name: "logout", status: 204, body: null, method: "POST", run: logout },
  {
    name: "delete",
    status: 204,
    body: null,
    method: "POST",
    run: () => deleteAccount("een-heel-lang-wachtwoord"),
  },
  {
    name: "reset-request",
    status: 202,
    body: {},
    method: "POST",
    run: () => requestPasswordReset({ email: "iemand@voorbeeld.nl" }),
  },
  {
    name: "reset-confirm",
    status: 204,
    body: null,
    method: "POST",
    run: () =>
      confirmPasswordReset({
        token: "a".repeat(43),
        password: "een-ander-wachtwoord",
      }),
  },
  {
    name: "verify-request",
    status: 202,
    body: {},
    method: "POST",
    run: requestEmailVerification,
  },
  {
    name: "advice-check",
    status: 200,
    body: { advice_token: null, check: null },
    method: "POST",
    run: checkConsumption,
  },
  {
    name: "advice-accept",
    status: 201,
    body: { token: "b".repeat(22) },
    method: "POST",
    run: () => acceptConsumption("b".repeat(22)),
  },
  {
    name: "verify-confirm",
    status: 204,
    body: null,
    method: "POST",
    run: () => confirmEmailVerification({ token: "a".repeat(43) }),
  },
];

describe("the account client", () => {
  it.each(CALLS)(
    "sends the session cookie on $name, without which every answer is a 401",
    async ({ status, body, run }) => {
      const fetchMock = stub(status, body);
      await run();
      const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
      expect(init.credentials).toBe("include");
    },
  );
});

describe("the CSRF header", () => {
  it.each(CALLS.filter((entry) => entry.method === "POST"))(
    "rides on $name, with the value out of the cookie",
    async ({ status, body, run }) => {
      document.cookie = "csrftoken=een-token-uit-de-cookie";
      const fetchMock = stub(status, body);
      await run();
      const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
      expect(new Headers(init.headers).get("X-CSRFToken")).toBe(
        "een-token-uit-de-cookie",
      );
    },
  );

  it.each(CALLS.filter((entry) => entry.method === "GET"))(
    "is not sent on $name, because a safe method does not need one",
    async ({ status, body, run }) => {
      document.cookie = "csrftoken=een-token-uit-de-cookie";
      const fetchMock = stub(status, body);
      await run();
      const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
      const headers = new Headers(init.headers);
      expect(headers.get("X-CSRFToken")).toBeNull();
      // api.ts:233-235 explains why: a content-type outside the CORS safelist
      // turns a simple cross-origin GET into a preflight, bought for a header
      // the request does not need. A GET here carries no body, so it must
      // carry no content-type either.
      expect(headers.has("content-type")).toBe(false);
    },
  );

  it("sends no header at all when there is no cookie yet", async () => {
    // The API then answers 403 with `csrf_failed`, whose sentence says to
    // reload. An empty header instead would be a request claiming to carry a
    // token, which is a different and less honest failure.
    const fetchMock = stub(200, null);
    await refresh();
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).has("X-CSRFToken")).toBe(false);
  });

  it("finds the token in a cookie jar that holds other cookies too", async () => {
    document.cookie = "ampeer-thema=dark";
    document.cookie = "csrftoken=tweede";
    const fetchMock = stub(204, null);
    await logout();
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("X-CSRFToken")).toBe("tweede");
  });
});

describe("the shape checks", () => {
  it("refuses consent texts that are missing one of the two kinds", async () => {
    stub(200, { text_version: "2026-09-04", texts: { METER_LINK: "een zin" } });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent text that is present and empty", async () => {
    // The plausible wrong body: a key that exists and says nothing, which
    // would put a blank label beside a checkbox somebody then ticks.
    stub(200, {
      text_version: "2026-09-04",
      texts: { LEAD_GENERATION: "", METER_LINK: "een zin" },
    });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an account whose consents are strings rather than booleans", async () => {
    // "false" is truthy, so this is the body that turns a refusal into a row
    // that says yes.
    stub(200, {
      email: "iemand@voorbeeld.nl",
      consents: { LEAD_GENERATION: "false", METER_LINK: "true" },
    });
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent answer about the other kind", async () => {
    // The quietest wrong body on this API: a 200 that updates the wrong row on
    // the screen, with every value of the right type.
    stub(200, { kind: "LEAD_GENERATION", granted: true });
    await expect(
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: "2026-09-04",
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export whose consent rows have lost the version", async () => {
    stub(200, {
      ...exportPayload,
      consents: [
        {
          kind: "METER_LINK",
          action: "GRANTED",
          occurred_at: "2026-09-05T09:12:44Z",
        },
      ],
    });
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  it("hands back the export as the exact text the API sent", async () => {
    // Byte for byte, because this string becomes the file. A parse and a
    // re-serialise would round every amount inside an advice.
    const text = JSON.stringify(exportPayload);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async () => new Response(text, { status: 200 })),
    );
    await expect(exportAccount()).resolves.toBe(text);
  });

  it("accepts an export carrying an advice it knows nothing about", async () => {
    stub(200, {
      ...exportPayload,
      advices: [{ inputs: { postcode4: "5401" }, advice: { iets_nieuws: 1 } }],
    });
    await expect(exportAccount()).resolves.toContain("iets_nieuws");
  });

  it("refuses an export that is not JSON at all", async () => {
    // A proxy's error page with a 200 on it, which is the way this arrives in
    // practice.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>oeps</html>", { status: 200 }),
      ),
    );
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });
});

/**
 * The three categories `isObject` and its neighbours exist to catch, proven
 * rather than assumed.
 *
 * Every guard above rejects `null` and an array by construction (`isObject`
 * excludes both), and rejects a body missing one of its required top-level
 * keys because the missing key reads as `undefined`, which fails every
 * `isString` / `typeof ... === "boolean"` check. Until now nothing sent any of
 * the three: coverage showed the early `return false` in `isConsentTexts`,
 * `isMe` and `isExport` as unreached. Loosening any one of those guards to
 * drop its `isObject` check (leaving the rest of the function unchanged) lets
 * the `null` case below resolve a value instead of rejecting, which is the
 * red-proof for this block.
 */
describe("the shape checks refuse a body that is not even the right kind of value", () => {
  it("refuses consent texts when the body is null", async () => {
    stub(200, null);
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses consent texts when the body is an array", async () => {
    stub(200, []);
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses consent texts missing a required top-level key", async () => {
    const { text_version: _version, ...withoutVersion } = consentTexts;
    stub(200, withoutVersion);
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an account when the body is null", async () => {
    stub(200, null);
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an account when the body is an array", async () => {
    stub(200, []);
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an account missing a required top-level key", async () => {
    const { email: _email, ...withoutEmail } = me;
    stub(200, withoutEmail);
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent answer when the body is null", async () => {
    stub(200, null);
    await expect(
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: "2026-09-04",
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent answer when the body is an array", async () => {
    stub(200, []);
    await expect(
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: "2026-09-04",
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a consent answer missing a required top-level key", async () => {
    stub(200, { kind: "METER_LINK" });
    await expect(
      postConsent({
        kind: "METER_LINK",
        action: "GRANTED",
        text_version: "2026-09-04",
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export when the body is null", async () => {
    stub(200, null);
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export when the body is an array", async () => {
    stub(200, []);
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export missing a required top-level key", async () => {
    const { email: _email, ...withoutEmail } = exportPayload;
    stub(200, withoutEmail);
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  // The finer-grained partner of the three above: each function guards more
  // than one required key, and a body missing the *first* key it checks never
  // reaches the guard for the second. These pick the second (or third) key on
  // purpose, so every `return false` in accounts.ts has a body that reaches it.

  it("refuses consent texts whose texts object is missing entirely", async () => {
    stub(200, { text_version: consentTexts.text_version });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an account whose consents object is missing entirely", async () => {
    stub(200, { email: me.email });
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export missing date_joined", async () => {
    const { date_joined: _dateJoined, ...withoutDateJoined } = exportPayload;
    stub(200, withoutDateJoined);
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export whose consents is not an array", async () => {
    stub(200, { ...exportPayload, consents: {} });
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses an export whose advices is not an array", async () => {
    stub(200, { ...exportPayload, advices: {} });
    await expect(exportAccount()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("what this module refuses to do", () => {
  it("makes exactly one request on a 500", async () => {
    const fetchMock = stub(500, {});
    await getMe().catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("makes exactly one request on a 401, because the exchange is not here", async () => {
    const fetchMock = stub(401, { detail: "u bent niet ingelogd" });
    await getMe().catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reads no body on a 204, which would throw", async () => {
    stub(204, null);
    await expect(logout()).resolves.toBeUndefined();
    stub(204, null);
    await expect(
      deleteAccount("een-heel-lang-wachtwoord"),
    ).resolves.toBeUndefined();
  });

  it("carries the API's own sentence as the message", async () => {
    stub(429, {
      detail: "Request was throttled. Expected available in 1800 seconds.",
    });
    // rejects.toMatchObject, not a bare .catch(cb): if the promise ever
    // resolved instead of rejecting, this assertion fails loudly rather than
    // the callback quietly never running.
    await expect(getMe()).rejects.toMatchObject({
      status: 429,
      message: expect.stringContaining("throttled"),
    });
  });

  it("leaves the message empty when the API sent no sentence of its own", async () => {
    // The difference `_account/messages.ts` reads. ApiError's own default
    // message is English, and a household never sees it.
    stub(400, { text_version: ["de toestemmingstekst is gewijzigd"] });
    await expect(register(REGISTER_INPUT)).rejects.toMatchObject({
      message: "",
      fields: { text_version: ["de toestemmingstekst is gewijzigd"] },
    });
  });

  it("still raises an ApiError when a failing response has no JSON body at all", async () => {
    // A proxy's 502 with an HTML error page, which is not the shape any
    // endpoint here answers with. response.json() rejects, and the catch on
    // that call is what keeps this from crashing the caller instead of
    // handing it an ApiError.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>bad gateway</html>", { status: 502 }),
      ),
    );
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>bad gateway</html>", { status: 502 }),
      ),
    );
    await expect(getMe()).rejects.toMatchObject({ status: 502, fields: {} });
  });
});

/**
 * The two reductions, on one table.
 *
 * `readErrorBody` exists twice on purpose and this is the whole of what keeps
 * the copies together: the same bodies go through `postEstimate` from api.ts
 * and through `getMe` from this module, and the `fields` that come out have to
 * be equal. If one drifts, this is red.
 */
const ERROR_BODIES: readonly unknown[] = [
  { email: ["geen geldig e-mailadres"] },
  { colour: "onbekend veld" },
  { detail: "Request was throttled." },
  { password: ["te kort", "te simpel"] },
  { nested: { niet: "een lijst" } },
  { empty: [] },
  { mixed: ["een zin", 4, null] },
  null,
  "een string",
  [1, 2, 3],
];

const ESTIMATE_INPUT = {
  postcode4: "5401",
  peak_power_wp: 3500,
  azimuth_deg: 0,
  tilt_deg: 35,
  annual_consumption_kwh: 3500,
};

describe("the duplicated error reduction", () => {
  it.each(ERROR_BODIES.map((body, index) => ({ index, body })))(
    "agrees with the one in api.ts on body $index",
    async ({ body }) => {
      stub(400, body);
      const fromAdvice = (await postEstimate(ESTIMATE_INPUT).catch(
        (error: ApiError) => error,
      )) as ApiError;
      stub(400, body);
      const fromAccounts = (await getMe().catch(
        (error: ApiError) => error,
      )) as ApiError;
      // Both calls really did reject, and rejected with the class this
      // comparison is about. Without these two lines a pair of calls that
      // resolved would put `undefined` on both sides and the comparison
      // below would hold, which is the shape of a parity check that has
      // stopped reading anything.
      expect(fromAdvice).toBeInstanceOf(ApiError);
      expect(fromAccounts).toBeInstanceOf(ApiError);
      expect(fromAccounts.fields).toEqual(fromAdvice.fields);
    },
  );
});

describe("the three meter calls", () => {
  it("calls the right path with the right method", async () => {
    const fetchMock = stub(200, METER_STATUS);
    await getMeterStatus();
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "GET" });
    expect(new URL(String(fetchMock.mock.calls[0]?.[0])).pathname).toBe(
      "/api/auth/meter/",
    );

    const linkFetch = stub(201, METER_KEY);
    await linkMeter();
    expect(linkFetch.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
    expect(new URL(String(linkFetch.mock.calls[0]?.[0])).pathname).toBe(
      "/api/auth/meter/link/",
    );

    const unlinkFetch = stub(204, null);
    await unlinkMeter();
    expect(unlinkFetch.mock.calls[0]?.[1]).toMatchObject({ method: "POST" });
    expect(new URL(String(unlinkFetch.mock.calls[0]?.[0])).pathname).toBe(
      "/api/auth/meter/unlink/",
    );
  });

  /**
   * `isMeterStatus` refuses `may_link` missing, checked by weakening the
   * guard to `return true;` unconditionally: that mutation turns this test
   * red, because `getMeterStatus` then resolves with the malformed body
   * instead of throwing.
   */
  it("refuses a meter status missing may_link", async () => {
    const { may_link: _dropped, ...withoutMayLink } = METER_STATUS;
    stub(200, withoutMayLink);
    await expect(getMeterStatus()).rejects.toMatchObject({ message: "" });
  });

  /**
   * A response where `created_at` is missing rather than `null`.
   *
   * Red-proofed by removing the `"created_at" in value` guard AND widening
   * the type check on the same field to also accept `undefined`. Either
   * mutation alone leaves this test green (the other line still catches a
   * missing key), which is exactly why the guard is written as the two
   * lines it is: dropping only the `in` check is not, on its own, provable
   * to fail here, since the type check below it treats `undefined` the same
   * as "not null and not a string". Both together let a missing key through
   * and turn this test red.
   */
  it("refuses a meter status where created_at is missing rather than null", async () => {
    const { created_at: _dropped, ...withoutCreatedAt } = METER_STATUS;
    stub(200, withoutCreatedAt);
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status when the body is null", async () => {
    stub(200, null);
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status whose linked is not a boolean", async () => {
    stub(200, { ...METER_STATUS, linked: "false" });
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status whose created_at is neither null nor a string", async () => {
    stub(200, { ...METER_STATUS, created_at: 1725580800 });
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status where last_seen_at is missing rather than null", async () => {
    const { last_seen_at: _dropped, ...withoutLastSeenAt } = METER_STATUS;
    stub(200, withoutLastSeenAt);
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status whose last_seen_at is neither null nor a string", async () => {
    stub(200, { ...METER_STATUS, last_seen_at: 1725580800 });
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status where last_seen_label is missing rather than null", async () => {
    const { last_seen_label: _dropped, ...withoutLabel } = METER_STATUS;
    stub(200, withoutLabel);
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status whose last_seen_label is neither null nor a string", async () => {
    stub(200, { ...METER_STATUS, last_seen_label: 1725580800 });
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("accepts a meter status that is linked and has a last-seen moment", async () => {
    stub(200, {
      may_link: true,
      linked: true,
      created_at: "2026-09-09T09:00:00Z",
      last_seen_at: "2026-09-09T10:15:00Z",
      last_seen_label: "9 september 2026 12:15",
    });
    const status = await getMeterStatus();
    expect(status.linked).toBe(true);
  });

  it("refuses a meter key missing its push_path", async () => {
    const { push_path: _dropped, ...withoutPushPath } = METER_KEY;
    stub(201, withoutPushPath);
    await expect(linkMeter()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter status whose 200 body is not JSON at all", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>oeps</html>", { status: 200 }),
      ),
    );
    await expect(getMeterStatus()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a meter key whose 201 body is not JSON at all", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>oeps</html>", { status: 201 }),
      ),
    );
    await expect(linkMeter()).rejects.toBeInstanceOf(ApiError);
  });

  it("carries the API's own Dutch sentence on a 403 from the meter status route", async () => {
    stub(403, { detail: "geen toestemming voor deze koppeling" });
    await expect(getMeterStatus()).rejects.toMatchObject({
      status: 403,
      message: "geen toestemming voor deze koppeling",
    });
  });
});

describe("the two shape guards that grew a key", () => {
  it("refuses a me/ that does not say whether the address is confirmed", async () => {
    const { email_verified_at: _dropped, ...withoutIt } = me;
    stub(200, withoutIt);
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses a me/ whose confirmation timestamp is not a string", async () => {
    stub(200, { ...me, email_verified_at: 1725580800 });
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });

  it("accepts a me/ whose address is confirmed at a time", async () => {
    stub(200, { ...me, email_verified_at: "2026-09-06T10:00:00+00:00" });
    const answer = await getMe();
    expect(answer.email_verified_at).toBe("2026-09-06T10:00:00+00:00");
  });

  it("refuses consent texts without the labels, and labels without a kind", async () => {
    const { labels: _dropped, ...withoutLabels } = consentTexts;
    stub(200, withoutLabels);
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
    stub(200, {
      ...consentTexts,
      labels: { METER_LINK: consentTexts.labels.METER_LINK },
    });
    await expect(getConsentTexts()).rejects.toBeInstanceOf(ApiError);
  });

  it("sends the three recovery bodies exactly as the API reads them, and none for a resend", async () => {
    const fetchMock = stub(202, {});
    await requestPasswordReset({ email: "iemand@voorbeeld.nl" });
    await confirmPasswordReset({ token: "t".repeat(43), password: "pw" });
    await confirmEmailVerification({ token: "v".repeat(43) });
    await requestEmailVerification();
    const bodies = fetchMock.mock.calls.map(
      (call) => (call[1] as RequestInit).body,
    );
    expect(bodies.slice(0, 3).map((body) => JSON.parse(String(body)))).toEqual([
      { email: "iemand@voorbeeld.nl" },
      { token: "t".repeat(43), password: "pw" },
      { token: "v".repeat(43) },
    ]);
    expect(bodies[3]).toBeUndefined();
    const paths = fetchMock.mock.calls.map(
      (call) => new URL(String(call[0])).pathname,
    );
    expect(paths).toEqual([
      "/api/auth/reset/request/",
      "/api/auth/reset/confirm/",
      "/api/auth/verify/confirm/",
      "/api/auth/verify/request/",
    ]);
  });
});

describe("what the meter says about the typed figure", () => {
  const CHECK = {
    advice_token: "b".repeat(22),
    check: {
      typed_kwh: 2800,
      p10_kwh: 3600,
      p50_kwh: 4000,
      p90_kwh: 4400,
      runs: 8,
      quarters_used: 5376,
      message: "een zin uit de API",
      installation_note: null,
    },
  };

  it("reads a whole answer back", async () => {
    stub(200, CHECK);
    await expect(checkConsumption()).resolves.toEqual(CHECK);
  });

  it("reads the silent answer back, which is the common one", async () => {
    stub(200, { advice_token: null, check: null });
    await expect(checkConsumption()).resolves.toEqual({
      advice_token: null,
      check: null,
    });
  });

  it("carries the note about the installation when the API sends one", async () => {
    const withNote = {
      ...CHECK,
      check: { ...CHECK.check, installation_note: "kijk naar uw panelen" },
    };
    stub(200, withNote);
    await expect(checkConsumption()).resolves.toEqual(withNote);
  });

  it.each([
    ["a band missing a figure", { ...CHECK.check, p50_kwh: undefined }],
    ["a figure that is not a number", { ...CHECK.check, p50_kwh: "4000" }],
    ["a message that is not a string", { ...CHECK.check, message: 12 }],
    [
      "a note that is neither null nor text",
      { ...CHECK.check, installation_note: 7 },
    ],
    [
      "a body that dropped the note key entirely",
      {
        typed_kwh: 2800,
        p10_kwh: 3600,
        p50_kwh: 4000,
        p90_kwh: 4400,
        runs: 8,
        quarters_used: 5376,
        message: "een zin uit de API",
      },
    ],
  ])("refuses %s rather than showing it", async (_name, check) => {
    stub(200, { advice_token: "b".repeat(22), check });
    await expect(checkConsumption()).rejects.toThrow();
  });

  it.each([
    ["a token that is not text", { advice_token: 12, check: null }],
    ["a check that is not an object", { advice_token: null, check: 5 }],
    ["an answer with neither key", {}],
    ["an answer that is not an object", 7],
  ])("refuses %s rather than showing it", async (_name, body) => {
    stub(200, body);
    await expect(checkConsumption()).rejects.toThrow();
  });

  it("hands back the new token when a figure is accepted", async () => {
    stub(201, { token: "c".repeat(22) });
    await expect(acceptConsumption("b".repeat(22))).resolves.toBe(
      "c".repeat(22),
    );
  });

  it("refuses an acceptance with no token in it", async () => {
    stub(201, {});
    await expect(acceptConsumption("b".repeat(22))).rejects.toThrow();
  });

  it("puts the advice token in the path it posts to", async () => {
    const fetchMock = stub(201, { token: "c".repeat(22) });
    await acceptConsumption("b".repeat(22));
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/auth/advice/${"b".repeat(22)}/accept/`,
    );
  });
});

describe("an answer about the meter that is not JSON at all", () => {
  it("is refused when asking what the meter says", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>oeps</html>", { status: 200 }),
      ),
    );
    await expect(checkConsumption()).rejects.toBeInstanceOf(ApiError);
  });

  it("is refused when accepting the measured figure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(
        async () => new Response("<html>oeps</html>", { status: 201 }),
      ),
    );
    await expect(acceptConsumption("b".repeat(22))).rejects.toBeInstanceOf(
      ApiError,
    );
  });
});
