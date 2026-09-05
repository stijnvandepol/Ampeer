import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import me from "../fixtures/me-response.json";
import consentTexts from "../fixtures/consent-texts.json";
import { AccountPage } from "@/app/_account/AccountPage";

afterEach(() => vi.unstubAllGlobals());

/** One answer per request, in order, plus the addresses that were asked for. */
function stub(
  answers: readonly { status: number; body?: unknown; throws?: boolean }[],
) {
  const seen: string[] = [];
  let index = 0;
  const fetchMock = vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
    seen.push(String(input));
    const answer = answers[index];
    index += 1;
    if (answer === undefined)
      throw new Error(`request ${index} was not planned for`);
    if (answer.throws === true) throw new TypeError("Failed to fetch");
    return answer.status === 204
      ? new Response(null, { status: answer.status })
      : new Response(JSON.stringify(answer.body ?? null), {
          status: answer.status,
          headers: { "content-type": "application/json" },
        });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, seen };
}

describe("which of the three views is on the screen", () => {
  it("says the data is being fetched, rather than showing an empty element", () => {
    // Chapter 3. `/berekenen/` shipped zero headings and 32 words of body text
    // on 2026-09-02, all of it header and footer, and a blank `main` is the
    // wrong answer for a visitor on a slow connection as well as for a crawler.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => new Promise(() => {})),
    );
    render(<AccountPage />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Uw gegevens worden opgehaald.",
    );
  });

  it("shows the account when me/ answers 200", async () => {
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText(me.email)).toBeInTheDocument();
  });

  it("shows the sign-in view when me/ answers 401 twice around one exchange", async () => {
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByRole("button", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(me.email)).not.toBeInTheDocument();
  });

  it("shows the sign-in view with a message when nothing came back at all", async () => {
    // Chapter 6.5, and this is not a hypothetical: e2e/privacy.spec.ts opens
    // every page a visitor can reach without an advice and mocks nothing, so
    // this is the state this route is in there.
    stub([{ status: 0, throws: true }]);
    render(<AccountPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Wij konden de server niet bereiken.",
    );
    expect(
      screen.getByRole("button", { name: "Inloggen" }),
    ).toBeInTheDocument();
  });

  it("switches to the registration view and back without leaving the route", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Nog geen account? Account aanmaken",
      }),
    );
    expect(
      await screen.findByRole("heading", { name: "Account aanmaken" }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Ik heb al een account. Inloggen" }),
    );
    expect(
      screen.getByRole("heading", { name: "Inloggen" }),
    ).toBeInTheDocument();
  });
});

describe("focus, so a keyboard user is not left on a control the view just removed", () => {
  it("moves focus into the new view when switching between sign-in and registration", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Nog geen account? Account aanmaken",
      }),
    );
    // The heading itself belongs to `RegisterForm`, task 6's file, so this
    // route cannot put a ref on it directly. It focuses the labelled wrapper
    // around the form instead, which is why the assertion below is exact
    // identity and not "contains": `document.body` also contains the
    // heading, and that would pass even with no focus management at all.
    const registerHeading = await screen.findByRole("heading", {
      name: "Account aanmaken",
    });
    const registerRegion = registerHeading.closest('[role="group"]');
    expect(registerRegion).not.toBeNull();
    expect(document.activeElement).toBe(registerRegion);

    await userEvent.click(
      screen.getByRole("button", { name: "Ik heb al een account. Inloggen" }),
    );
    const signInHeading = screen.getByRole("heading", { name: "Inloggen" });
    const signInRegion = signInHeading.closest('[role="group"]');
    expect(signInRegion).not.toBeNull();
    expect(document.activeElement).toBe(signInRegion);
  });

  it("moves focus to the account heading once signing in succeeds", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 200, body: me },
    ]);
    render(<AccountPage />);
    await userEvent.type(
      await screen.findByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(
      screen.getByLabelText("Wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    expect(
      await screen.findByRole("heading", { name: "Uw gegevens" }),
    ).toHaveFocus();
  });
});
