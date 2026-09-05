import { afterEach, describe, expect, it, vi } from "vitest";
import consentTexts from "../fixtures/consent-texts.json";
import me from "../fixtures/me-response.json";
import exportPayload from "../fixtures/export-response.json";
import { ApiError, postEstimate } from "@/lib/api";
import {
  deleteAccount,
  exportAccount,
  getConsentTexts,
  getMe,
  login,
  logout,
  postConsent,
  refresh,
  register,
} from "@/lib/accounts";

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

/** The nine calls, each with the status and body its own route answers with. */
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
  { name: "logout", status: 204, body: null, method: "POST", run: logout },
  {
    name: "delete",
    status: 204,
    body: null,
    method: "POST",
    run: () => deleteAccount("een-heel-lang-wachtwoord"),
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
      expect(new Headers(init.headers).get("X-CSRFToken")).toBeNull();
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
    await getMe().catch((error: ApiError) => {
      expect(error.message).toContain("throttled");
      expect(error.status).toBe(429);
    });
  });

  it("leaves the message empty when the API sent no sentence of its own", async () => {
    // The difference `_account/messages.ts` reads. ApiError's own default
    // message is English, and a household never sees it.
    stub(400, { text_version: ["de toestemmingstekst is gewijzigd"] });
    await register(REGISTER_INPUT).catch((error: ApiError) => {
      expect(error.message).toBe("");
      expect(error.fields["text_version"]).toEqual([
        "de toestemmingstekst is gewijzigd",
      ]);
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
    await getMe().catch((error: ApiError) => {
      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(502);
      expect(error.fields).toEqual({});
    });
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
      expect(fromAccounts.fields).toEqual(fromAdvice.fields);
    },
  );
});
