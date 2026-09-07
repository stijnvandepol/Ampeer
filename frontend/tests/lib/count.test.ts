import { afterEach, describe, expect, it, vi } from "vitest";
import { count } from "@/lib/count";

afterEach(() => vi.unstubAllGlobals());

describe("the counter", () => {
  it("sends the name to the counting route and nothing else", async () => {
    const answer = new Response("{}", {
      status: 202,
      headers: { "content-type": "application/json" },
    });
    const fetchMock = vi.fn<typeof fetch>(async () => answer);
    vi.stubGlobal("fetch", fetchMock);

    count("funnel_question_2");

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toMatch(/\/api\/advice\/count\/$/);
    expect(init?.method).toBe("POST");
    expect(init?.keepalive).toBe(true);
    expect(JSON.parse(String(init?.body))).toEqual({
      name: "funnel_question_2",
    });
  });

  it("swallows a rejected request instead of letting it reach the caller", async () => {
    // The failure path is the whole reason this module has a `.catch`, and it
    // is the one branch no other test drives: every component test that fires
    // a counter answers it. Without this test the arrow inside `.catch` is a
    // function V8 counts only when teardown happens to reach it first, which
    // makes the functions figure of the whole suite differ between runs.
    const failure = Promise.reject(new Error("the network is gone"));
    const fetchMock = vi.fn<typeof fetch>(() => failure);
    vi.stubGlobal("fetch", fetchMock);

    expect(() => count("funnel_started")).not.toThrow();

    // `count` attached its own handler to this promise before we attach this
    // one, and a promise runs its handlers in the order they were attached,
    // so awaiting here resolves only once the silencing `.catch` has run.
    // A rejection that escaped it would arrive as this line rejecting.
    await expect(failure.catch(() => "silenced")).resolves.toBe("silenced");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
