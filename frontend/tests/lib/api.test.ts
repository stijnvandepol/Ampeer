import { afterEach, describe, expect, it, vi } from "vitest";
import fixture from "../fixtures/advice-response.json";
import { ApiError, getAdvice, postEstimate, postRefine } from "@/lib/api";

const input = {
  postcode4: "5401",
  peak_power_wp: 3500,
  azimuth_deg: 0,
  tilt_deg: 35,
  annual_consumption_kwh: 3500,
};

/** 22 url-safe characters, the shape secrets.token_urlsafe(16) produces. */
const TOKEN = "abcdefghijklmnopqrstuv";

afterEach(() => vi.unstubAllGlobals());

// A fresh Response per call, not one shared instance. A body can only be
// read once, so a mock that resolves the same Response twice makes the second
// call look like a request that came back empty.
function stub(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("the api client", () => {
  it("returns the advice on success", async () => {
    stub(201, fixture);
    await expect(postEstimate(input)).resolves.toMatchObject({
      token: expect.any(String),
    });
  });

  it("turns a 400 into an error that names the fields", async () => {
    stub(400, { postcode4: ["geen Nederlandse postcode"] });
    await expect(postEstimate(input)).rejects.toBeInstanceOf(ApiError);
    await postEstimate(input).catch((error: ApiError) => {
      expect(error.status).toBe(400);
      expect(error.fields.postcode4).toContain("geen Nederlandse postcode");
    });
  });

  it("keeps an unknown field's message, which the API sends as a bare string", async () => {
    // StrictSerializer answers {"colour": "onbekend veld"} and DRF's
    // as_serializer_error wraps it, but a body that arrives unwrapped must
    // still reach a caller that only knows how to read lists.
    stub(400, { colour: "onbekend veld" });
    await postEstimate(input).catch((error: ApiError) => {
      expect(error.fields.colour).toEqual(["onbekend veld"]);
    });
  });

  it("does not lose a throttle message that has no field to hang on", async () => {
    // A 429 answers {"detail": "Request was throttled..."}, which is a
    // sentence about the request rather than about one of its fields.
    stub(429, {
      detail: "Request was throttled. Expected available in 1800 seconds.",
    });
    await postEstimate(input).catch((error: ApiError) => {
      expect(error.message).toContain("throttled");
      expect(error.fields).toEqual({});
    });
  });

  it("survives an error response with no body at all", async () => {
    // The 404 from StoredAdviceView sends nothing, on purpose: an unknown
    // token and an expired one have to answer identically.
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response(null, { status: 404 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(getAdvice(TOKEN)).rejects.toBeInstanceOf(ApiError);
    await getAdvice(TOKEN).catch((error: ApiError) => {
      expect(error.status).toBe(404);
      expect(error.fields).toEqual({});
    });
  });

  it("does not retry a 4xx", async () => {
    // A 429 means slow down. Retrying it is the one response guaranteed to
    // make it worse, and a client that retries a 400 asks the same wrong
    // question twice.
    const fetchMock = stub(429, {});
    await postEstimate(input).catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a 5xx either, because there is no status that earns one", async () => {
    const fetchMock = stub(500, {});
    await postEstimate(input).catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry a refused connection", async () => {
    // The one failure a retry loop is usually written for. It is still one
    // request: whether to ask again is the visitor's decision, not this
    // module's, and a silent second attempt hides that the first one failed.
    const fetchMock = vi.fn<typeof fetch>(async () => {
      throw new TypeError("Failed to fetch");
    });
    vi.stubGlobal("fetch", fetchMock);
    await postEstimate(input).catch(() => {});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends no credentials, because there is no session to send", async () => {
    const fetchMock = stub(201, fixture);
    await postEstimate(input);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.credentials).toBe("omit");
  });

  it("sends no credentials on a read either", async () => {
    const fetchMock = stub(200, fixture);
    await getAdvice(TOKEN);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.credentials).toBe("omit");
  });

  it("refuses a token that is not the shape the API issues", async () => {
    // 22 url-safe characters. Anything else is a typo or a probe, and asking
    // the API about it is a request nobody needed to make.
    await expect(getAdvice("../../etc/passwd")).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("makes no request at all for a token of the wrong shape", async () => {
    // The point of the check. A 404 from the router would cost a call against
    // a budget of 120 an hour and tell the visitor nothing new.
    const fetchMock = stub(200, fixture);
    for (const bad of [
      "",
      "short",
      `${TOKEN}x`,
      "abcdefghijklmnopqrstu/",
      "../../etc/passwd",
    ]) {
      await getAdvice(bad).catch(() => {});
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("accepts every character secrets.token_urlsafe can emit", async () => {
    const fetchMock = stub(200, fixture);
    await getAdvice("-_0123456789AZazbcde").catch(() => {});
    expect(fetchMock).not.toHaveBeenCalled(); // 20 characters, not 22
    await getAdvice("-_0123456789AZazbcdefg");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("posts each round to its own endpoint, with the answers as JSON", async () => {
    const fetchMock = stub(201, fixture);
    await postEstimate(input);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toMatch(/\/api\/advice\/estimate\/$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual(input);
  });

  it("posts round two to refine, which is a different endpoint", async () => {
    const fetchMock = stub(201, fixture);
    await postRefine({
      ...input,
      daytime_occupancy: false,
      has_ev: true,
      ev_behaviour: "NIGHT",
      has_heat_pump: false,
      heat_demand_kwh: null,
      dynamic_contract: false,
      has_battery: false,
      battery_capacity_kwh: null,
    });
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toMatch(/\/api\/advice\/refine\/$/);
  });

  it("asks for a stored advice with GET and no content-type", async () => {
    // A content-type outside the CORS safelist turns a simple cross-origin
    // GET into a preflight: a second round trip for a header a GET with no
    // body has no use for.
    const fetchMock = stub(200, fixture);
    await getAdvice(TOKEN);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/api/advice/${TOKEN}/$`));
    expect(init.method).toBe("GET");
    expect(init.headers).toBeUndefined();
  });

  it("raises an ApiError rather than a SyntaxError when a 200 is not JSON", async () => {
    // A proxy error page served with a 200 is the realistic case. Every
    // failure out of this module being one type is what lets a caller catch
    // ApiError and be done.
    const fetchMock = vi.fn<typeof fetch>(
      async () => new Response("<html>oops</html>", { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(getAdvice(TOKEN)).rejects.toBeInstanceOf(ApiError);
  });
});

/**
 * A 200 whose body is JSON but is not an advice.
 *
 * There is no error boundary above these callers, so a body that reaches a
 * renderer without the fields it promises unmounts the whole tree and leaves a
 * main element with nothing in it and nothing to read. A proxy answering
 * {"error": "upstream"} with a 200, or one field renamed on the backend, does
 * that to every visitor at once. So the shape is checked here, at the one
 * place the JSON becomes an Advice, and a wrong one becomes the same named
 * failure as every other refusal from this module.
 */
interface Loose {
  [key: string]: unknown;
}

function copyFixture(): Loose {
  return JSON.parse(JSON.stringify(fixture)) as Loose;
}

function looseAt(source: Loose, key: string): Loose {
  return source[key] as Loose;
}

function firstOf(source: Loose, key: string): Loose {
  const list = source[key];
  return Array.isArray(list) ? (list[0] as Loose) : ({} as Loose);
}

function mutated(change: (advice: Loose) => void): Loose {
  const advice = copyFixture();
  change(advice);
  return advice;
}

const WRONG_SHAPES: readonly (readonly [string, unknown])[] = [
  ["an array, which typeof calls an object", []],
  ["a proxy's own error body", { error: "upstream" }],
  ["no token", mutated((advice) => delete advice["token"])],
  ["a token that is a number", mutated((advice) => (advice["token"] = 1))],
  [
    "a confidence level that is not one of the three",
    mutated((a) => (a["confidence"] = "MAYBE")),
  ],
  [
    "no confidence label",
    mutated((advice) => delete advice["confidence_label"]),
  ],
  ["no headline at all", mutated((advice) => delete advice["headline"])],
  [
    "a headline amount that arrived as a JSON number",
    mutated((advice) => (looseAt(advice, "headline")["p10"] = 1)),
  ],
  [
    "a headline with no run count",
    mutated((advice) => delete looseAt(advice, "headline")["runs"]),
  ],
  ["routes that are not a list", mutated((advice) => (advice["routes"] = {}))],
  [
    "a route name the renderer has no section for",
    mutated(
      (advice) => (firstOf(advice, "routes")["route"] = "SOMETHING_ELSE"),
    ),
  ],
  [
    "a rule with no id to trace it back by",
    mutated(
      (advice) => delete firstOf(firstOf(advice, "routes"), "rules")["rule_id"],
    ),
  ],
  [
    "a saving band missing the Dutch it is rendered from",
    mutated(
      (advice) =>
        delete looseAt(
          firstOf(firstOf(advice, "routes"), "rules"),
          "saving_eur",
        )["varied_text"],
    ),
  ],
  [
    "a saving amount that arrived as a JSON number",
    mutated(
      (advice) =>
        (looseAt(firstOf(firstOf(advice, "routes"), "rules"), "saving_eur")[
          "mid"
        ] = 126.09),
    ),
  ],
  [
    "a battery that is not an object",
    mutated((advice) => (advice["battery"] = "geen")),
  ],
  [
    "a sized capacity carrying a band it says it has not got",
    mutated(
      (advice) =>
        (looseAt(looseAt(advice, "battery"), "sized_capacity_kwh")["band"] =
          0.5),
    ),
  ],
  [
    "a sizing basis that is not one of the two",
    mutated(
      (advice) =>
        (looseAt(looseAt(advice, "battery"), "sized_capacity_kwh")["basis"] =
          "GUESSED"),
    ),
  ],
  [
    "a payback figure with no band around it",
    mutated((advice) => delete looseAt(advice, "battery")["payback_years"]),
  ],
  [
    "a curve point that is not a capacity and a band",
    mutated((advice) => (looseAt(advice, "battery")["curve"] = [[3.0]])),
  ],
  [
    "a curve capacity that arrived as a string",
    mutated(
      (advice) => (looseAt(advice, "battery")["curve"] = [["3.0", null]]),
    ),
  ],
  [
    "no engine version to log the answer against",
    mutated((a) => delete a["engine_version"]),
  ],
  ["no advice version", mutated((advice) => delete advice["advice_version"])],
  [
    "no production source",
    mutated((advice) => delete advice["production_source"]),
  ],
  [
    "a production source with no sentence beside it",
    mutated((advice) => delete advice["production_source_text"]),
  ],
  [
    "a profile year that arrived as a string",
    mutated((a) => (a["profile_year"] = "2025")),
  ],
  ["no weather year", mutated((advice) => delete advice["weather_year"])],
];

describe("a 200 that is not an advice", () => {
  it.each(WRONG_SHAPES)(
    "is refused when the body has %s",
    async (_what, body) => {
      stub(200, body);
      await expect(getAdvice(TOKEN)).rejects.toBeInstanceOf(ApiError);
    },
  );

  it("is refused on the way out of a computation too, not only on a read", async () => {
    stub(201, { error: "upstream" });
    await expect(postEstimate(input)).rejects.toBeInstanceOf(ApiError);
  });

  it("says which kind of failure it was rather than throwing something nameless", async () => {
    // Every failure out of this module is one type, so a caller that catches
    // ApiError has covered this one as well and has a sentence to show.
    stub(200, { error: "upstream" });
    await getAdvice(TOKEN).catch((error: ApiError) => {
      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(200);
      expect(error.message).toMatch(/advice/i);
    });
    expect.assertions(3);
  });

  it("accepts the advice the API actually sends", async () => {
    stub(200, fixture);
    await expect(getAdvice(TOKEN)).resolves.toMatchObject({
      token: fixture.token,
    });
  });

  it("accepts an advice with no battery block, which is a valid answer", async () => {
    // "Nu geen batterij" is an outcome the model is allowed to reach, and the
    // API sends null for it. Refusing that would refuse a correct answer.
    stub(
      200,
      mutated((advice) => (advice["battery"] = null)),
    );
    await expect(getAdvice(TOKEN)).resolves.toMatchObject({ battery: null });
  });

  it("accepts a rule that saves nothing measurable, which sends a null band", async () => {
    stub(
      200,
      mutated(
        (advice) =>
          (firstOf(firstOf(advice, "routes"), "rules")["saving_eur"] = null),
      ),
    );
    await expect(getAdvice(TOKEN)).resolves.toMatchObject({
      token: fixture.token,
    });
  });
});
