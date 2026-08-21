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
    await expect(postEstimate(input)).resolves.toMatchObject({ token: expect.any(String) });
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
    stub(429, { detail: "Request was throttled. Expected available in 1800 seconds." });
    await postEstimate(input).catch((error: ApiError) => {
      expect(error.message).toContain("throttled");
      expect(error.fields).toEqual({});
    });
  });

  it("survives an error response with no body at all", async () => {
    // The 404 from StoredAdviceView sends nothing, on purpose: an unknown
    // token and an expired one have to answer identically.
    const fetchMock = vi.fn<typeof fetch>(async () => new Response(null, { status: 404 }));
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
    await expect(getAdvice("../../etc/passwd")).rejects.toBeInstanceOf(ApiError);
  });

  it("makes no request at all for a token of the wrong shape", async () => {
    // The point of the check. A 404 from the router would cost a call against
    // a budget of 120 an hour and tell the visitor nothing new.
    const fetchMock = stub(200, fixture);
    for (const bad of ["", "short", `${TOKEN}x`, "abcdefghijklmnopqrstu/", "../../etc/passwd"]) {
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
