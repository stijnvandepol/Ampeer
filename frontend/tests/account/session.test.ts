import { afterEach, describe, expect, it, vi } from "vitest";
import me from "../fixtures/me-response.json";
import { loadSession } from "@/app/_account/session";

afterEach(() => vi.unstubAllGlobals());

interface Answer {
  readonly status: number;
  readonly body?: unknown;
  readonly throws?: boolean;
}

/**
 * One answer per request, in order, and the URLs that were asked for.
 *
 * Counted on requests rather than on what ends up on the screen, because the
 * property under test is "exactly one exchange" and a screen cannot show the
 * difference between one refresh and three.
 */
function stubSequence(answers: readonly Answer[]): { readonly seen: string[] } {
  const seen: string[] = [];
  let index = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
      seen.push(String(input));
      const answer = answers[index];
      index += 1;
      if (answer === undefined) {
        throw new Error(
          `request ${index} was not planned for: ${String(input)}`,
        );
      }
      if (answer.throws === true) throw new TypeError("Failed to fetch");
      return answer.status === 204
        ? new Response(null, { status: answer.status })
        : new Response(JSON.stringify(answer.body ?? null), {
            status: answer.status,
            headers: { "content-type": "application/json" },
          });
    }),
  );
  return { seen };
}

describe("loading the account page", () => {
  it("shows the account when me/ answers 200, and asks nothing else", async () => {
    const { seen } = stubSequence([{ status: 200, body: me }]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_in", me });
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain("/api/auth/me/");
  });

  it("exchanges exactly once on a 401, and then shows the account", async () => {
    const { seen } = stubSequence([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 200, body: me },
    ]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_in", me });
    expect(seen).toHaveLength(3);
    expect(seen[1]).toContain("/api/auth/refresh/");
    expect(seen[2]).toContain("/api/auth/me/");
  });

  it("stops after a second 401, rather than rotating again", async () => {
    // A 401 after a successful rotation means the cookie the server just set
    // is not accepted, which no further attempt fixes. Going on would empty
    // the auth-refresh bucket and, once a spent token is offered again, ends
    // every session this account has. Counted on requests: a fourth would be
    // the bug and the screen would look the same either way.
    const { seen } = stubSequence([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_out", notice: null });
    expect(seen).toHaveLength(3);
  });

  it("stops when the exchange itself is refused", async () => {
    const { seen } = stubSequence([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
    ]);
    const state = await loadSession();
    expect(state).toEqual({ status: "signed_out", notice: null });
    expect(seen).toHaveLength(2);
  });

  it("says the connection failed and exchanges nothing at all", async () => {
    // Chapter 6.5. A request that never arrived is not a 401: nothing came
    // back, so nothing was said about who is signed in, and there is nothing
    // to exchange. e2e/privacy.spec.ts opens this page with no mock at all,
    // so this is the state that runs there.
    const { seen } = stubSequence([{ status: 0, throws: true }]);
    const state = await loadSession();
    expect(state.status).toBe("signed_out");
    expect(state).toHaveProperty(
      "notice",
      "Wij konden de server niet bereiken. Controleer uw verbinding en probeer het opnieuw.",
    );
    expect(seen).toHaveLength(1);
  });

  it("passes a throttle message through as the API wrote it", async () => {
    const { seen } = stubSequence([
      { status: 429, body: { detail: "Probeer het over een uur opnieuw." } },
    ]);
    const state = await loadSession();
    expect(state).toEqual({
      status: "signed_out",
      notice: "Probeer het over een uur opnieuw.",
    });
    expect(seen).toHaveLength(1);
  });

  it("says a server fault in its own words, because the API sent none", async () => {
    stubSequence([{ status: 500, body: {} }]);
    const state = await loadSession();
    expect(state).toEqual({
      status: "signed_out",
      notice: "De server had een storing. Probeer het straks opnieuw.",
    });
  });
});
