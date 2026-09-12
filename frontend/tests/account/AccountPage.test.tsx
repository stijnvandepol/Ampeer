import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import me from "../fixtures/me-response.json";
import consentTexts from "../fixtures/consent-texts.json";
import exportPayload from "../fixtures/export-response.json";
import { AccountPage } from "@/app/_account/AccountPage";
import AccountRoute, { metadata } from "@/app/account/page";

afterEach(() => vi.unstubAllGlobals());

/**
 * What `stub()` below answers `GET /api/auth/meter/` with, unless a test
 * overrides it.
 *
 * Task B3 adds this call to every mount of the signed-in view (a second
 * effect beside the one that fetches `consentTexts`), which would otherwise
 * have forced an update to every one of the two dozen `stub([...])` arrays
 * already in this file: each would need a third entry inserted at the exact
 * position this new fetch fires, and every action-specific answer after it
 * would need to shift down by one. Answering the meter route out of band,
 * by path rather than by position, keeps every existing array meaning
 * exactly what it said before this task, and is what the tests below that
 * DO care about the meter section override for.
 */
const DEFAULT_METER_STATUS = {
  may_link: false,
  linked: false,
  created_at: null,
  last_seen_at: null,
  last_seen_label: null,
};

interface StubAnswer {
  status: number;
  body?: unknown;
  /**
   * The literal response text, when a test needs to control the exact bytes
   * on the wire rather than whatever `JSON.stringify(body)` would produce.
   * Without this, `body` is re-serialised fresh for every answer, which
   * means it can never differ from a caller's own `JSON.stringify` of the
   * same value, and a test built that way could never catch a reparse.
   */
  text?: string;
  throws?: boolean;
}

/**
 * One answer per request, in order, plus the addresses that were asked for.
 *
 * `meterStatus`, when given, answers `GET /api/auth/meter/` instead of the
 * default above; it never consumes a slot from `answers`, for the reason the
 * comment on `DEFAULT_METER_STATUS` gives. A single answer repeats for every
 * call; an array is consumed one per call and its last entry repeats once
 * exhausted, the same convention `e2e/account.spec.ts`'s own `Plan` type uses
 * for a path called more than once (a link, then the refreshed status after
 * it, answer differently).
 */
function stub(
  answers: readonly StubAnswer[],
  options?: {
    readonly meterStatus?: StubAnswer | readonly StubAnswer[];
    readonly consumptionCheck?: unknown;
  },
) {
  const seen: string[] = [];
  let index = 0;
  let meterCalls = 0;
  const fetchMock = vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
    seen.push(String(input));
    if (new URL(String(input)).pathname === "/api/auth/meter/") {
      const planned = options?.meterStatus ?? {
        status: 200,
        body: DEFAULT_METER_STATUS,
      };
      const sequence = Array.isArray(planned) ? planned : [planned];
      const answer = sequence[Math.min(meterCalls, sequence.length - 1)];
      meterCalls += 1;
      return new Response(JSON.stringify(answer?.body ?? null), {
        status: answer?.status ?? 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (new URL(String(input)).pathname === "/api/auth/advice/check/") {
      // Answered outside the queue, like the meter status above. The account
      // page asks this whenever a link exists, so leaving it in the queue
      // would shift every planned answer by one in any test that happens to
      // have a linked meter. Silence is the default because most of these
      // tests are not about the correction at all; the ones that are plan it
      // through `consumptionCheck`.
      return new Response(
        JSON.stringify(
          options?.consumptionCheck ?? { advice_token: null, check: null },
        ),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    const answer = answers[index];
    index += 1;
    if (answer === undefined)
      throw new Error(`request ${index} was not planned for`);
    if (answer.throws === true) throw new TypeError("Failed to fetch");
    return answer.status === 204
      ? new Response(null, { status: answer.status })
      : new Response(answer.text ?? JSON.stringify(answer.body ?? null), {
          status: answer.status,
          headers: { "content-type": "application/json" },
        });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, seen };
}

/**
 * A promise a test can settle from outside its own executor, for a request
 * that must stay pending until the test says otherwise.
 *
 * Not a bare `let settle: (() => void) | null = null;` reassigned inside the
 * executor: TypeScript's control-flow narrowing does not follow an assignment
 * made only inside a nested closure, so a later `settle?.()` sees the
 * variable's type as the value it held at declaration, `null`, and narrows
 * the optional call to `never`. The definite-assignment assertion below
 * (`!`) gives `resolve`/`reject` their real, always-callable type from the
 * start, so there is nothing nullable left to narrow.
 */
function deferred<T = void>(): {
  readonly promise: Promise<T>;
  readonly resolve: (value: T) => void;
  readonly reject: (reason: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
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

  it("leaves focus at the top of the document when the page has only just loaded", async () => {
    // Nobody has done anything yet: `me/` answered, the form replaced the
    // loading sentence, and that is the page arriving rather than a view the
    // visitor asked for. Focus moved down into the form here would carry a
    // keyboard or screen reader visitor past the skip link, the navigation,
    // the h1 and the paragraph saying what this page is.
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      {
        status: 401,
        body: { detail: "uw sessie is verlopen, log opnieuw in" },
      },
    ]);
    render(<AccountPage />);
    await screen.findByRole("heading", { name: "Inloggen" });
    expect(document.activeElement).toBe(document.body);
  });

  it("leaves focus at the top when a valid cookie lands on the account view", async () => {
    // The same moment on the other branch: this visitor was still signed in,
    // so the account view is the first thing they see rather than the answer
    // to a form they submitted.
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await screen.findByText(me.email);
    expect(
      screen.getByRole("heading", { name: "Uw gegevens" }),
    ).not.toHaveFocus();
    expect(document.activeElement).toBe(document.body);
  });
});

describe("the account view", () => {
  it("shows both consent rows with the sentence from the API beside them, the meter link first", async () => {
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    const { container } = render(<AccountPage />);
    expect(
      await screen.findByText(consentTexts.texts.METER_LINK),
    ).toBeInTheDocument();
    expect(
      screen.getByText(consentTexts.texts.LEAD_GENERATION),
    ).toBeInTheDocument();
    // Ruling 50: the consent that improves the advice renders above the
    // commercial one, on the one screen where this product's neutrality is
    // visible. Checked by DOM position, not by presence, because presence
    // alone cannot tell the two render orders apart.
    const html = container.innerHTML;
    expect(html.indexOf(consentTexts.texts.METER_LINK)).toBeLessThan(
      html.indexOf(consentTexts.texts.LEAD_GENERATION),
    );
  });

  it("updates one row from the answer, without asking me/ again", async () => {
    // The API has just answered this question. A second me/ would spend an
    // auth-read and could fill the row with an answer that has caught up with
    // a change made somewhere else.
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen, fetchMock } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 200, body: { kind: "LEAD_GENERATION", granted: true } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Toestemming geven" }),
    );
    expect(await screen.findAllByText("Toestemming gegeven")).toHaveLength(2);
    expect(seen.filter((url) => url.includes("/api/auth/me/"))).toHaveLength(1);
    // Chapter 5.2: a grant carries the version whose sentence was on the
    // screen, so the recorded consent can never drift from what was shown.
    //
    // Found by path rather than by a fixed index: the meter status effect
    // added in task B3 fires its own request on the same mount, and `stub()`
    // still records it in `fetchMock.mock.calls` even though it answers that
    // request out of band, so a plain positional index is no longer stable.
    const consentCall = fetchMock.mock.calls.find(
      (call) => new URL(String(call[0])).pathname === "/api/auth/consent/",
    );
    expect(consentCall).toBeDefined();
    const body = JSON.parse(String((consentCall?.[1] as RequestInit).body));
    expect(body).toEqual({
      kind: "LEAD_GENERATION",
      action: "GRANTED",
      text_version: consentTexts.text_version,
    });
  });

  it("sends the version with a grant and nothing with a withdrawal", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { fetchMock } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 200, body: { kind: "METER_LINK", granted: false } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Toestemming intrekken" }),
    );
    const consentCall = fetchMock.mock.calls.find(
      (call) => new URL(String(call[0])).pathname === "/api/auth/consent/",
    );
    expect(consentCall).toBeDefined();
    const body = JSON.parse(String((consentCall?.[1] as RequestInit).body));
    expect(body).toEqual({ kind: "METER_LINK", action: "WITHDRAWN" });
  });

  it("lets a consent be withdrawn but not granted when the text is missing", async () => {
    // Chapter 6.3, and it is article 7(3) on the screen: granting with no
    // sentence in front of the reader would be consent to something nobody
    // read; refusing a withdrawal for the same reason would make taking it
    // back harder than giving it.
    stub([
      { status: 200, body: me },
      { status: 500, body: {} },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByRole("button", { name: "Toestemming intrekken" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Toestemming geven" }),
    ).toBeDisabled();
  });

  it("leaves a failed grant unflipped and re-enables the row", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      {
        status: 429,
        body: { detail: "u vraagt dit te vaak, probeer het later opnieuw" },
      },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Toestemming geven" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "u vraagt dit te vaak, probeer het later opnieuw",
    );
    // No optimistic flip: the row still reads what it read before the click,
    // under the same accessible name, and the button works again.
    expect(screen.getByText("Geen toestemming gegeven")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Toestemming geven" }),
    ).toBeEnabled();
  });

  it("shows the network sentence and re-enables the row when a toggle cannot reach the server", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 0, throws: true },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Toestemming geven" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Wij konden de server niet bereiken.",
    );
    expect(screen.getByText("Geen toestemming gegeven")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Toestemming geven" }),
    ).toBeEnabled();
  });

  it("keeps the account view and re-enables the buttons when signing out fails", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      {
        status: 429,
        body: { detail: "u vraagt dit te vaak, probeer het later opnieuw" },
      },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Uitloggen" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "u vraagt dit te vaak, probeer het later opnieuw",
    );
    expect(screen.getByText(me.email)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Uitloggen" })).toBeEnabled();
    // No confirmation appeared: this account was never signed out.
    expect(
      screen.queryByText("Uw account is verwijderd."),
    ).not.toBeInTheDocument();
  });

  it("keeps the view and re-enables export after a 429 on the export", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      {
        status: 429,
        body: { detail: "u vraagt dit te vaak, probeer het later opnieuw" },
      },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Gegevens exporteren" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "u vraagt dit te vaak, probeer het later opnieuw",
    );
    expect(screen.getByText(me.email)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Gegevens exporteren" }),
    ).toBeEnabled();
  });

  it("keeps a toggle busy after an unrelated export finishes", async () => {
    // Property: one action's completion must never clear another's busy
    // state. The export starts first; while it is still in flight, the
    // toggle button is not disabled by it (it reads only its own kind), so a
    // visitor can start it. Once the export resolves, the toggle's own row
    // must still read busy.
    const userEvent = (await import("@testing-library/user-event")).default;
    const exportRequest = deferred<void>();
    const toggleRequest = deferred<void>();
    const fetchMock = vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
      const url = String(input);
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "content-type": "application/json" },
        });
      if (url.includes("/api/auth/me/")) return json(me);
      if (url.includes("/api/auth/consent-texts/")) return json(consentTexts);
      if (url.includes("/api/auth/export/")) {
        await exportRequest.promise;
        return json(exportPayload);
      }
      if (url.includes("/api/auth/consent/")) {
        await toggleRequest.promise;
        return json({ kind: "LEAD_GENERATION", granted: true });
      }
      throw new Error(`request to ${url} was not planned for`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = () => "blob:een-url";
    URL.revokeObjectURL = () => {};
    try {
      render(<AccountPage />);
      await userEvent.click(
        await screen.findByRole("button", { name: "Gegevens exporteren" }),
      );
      // The export is now in flight and its own button is disabled, but that
      // does not touch `ConsentRow`, which reads only its own kind, so the
      // toggle can still be started here.
      await userEvent.click(
        screen.getByRole("button", { name: "Toestemming geven" }),
      );
      // Two live regions: the export's own and the toggling row's own.
      expect(screen.getAllByRole("status")).toHaveLength(2);
      exportRequest.resolve();
      // The export's own `finally` clears only its own entry: one live
      // region left, the toggling row's, not two and not zero.
      await waitFor(() =>
        expect(screen.getAllByRole("status")).toHaveLength(1),
      );
      // Nothing re-enables while the toggle is still in flight, including
      // the button whose own request has already finished.
      expect(
        screen.getByRole("button", { name: "Gegevens exporteren" }),
      ).toBeDisabled();
      expect(
        screen.getByRole("button", { name: "Toestemming geven" }),
      ).toBeDisabled();
    } finally {
      toggleRequest.resolve();
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    }
  });

  it("clears the deletion confirmation once the visitor switches to another view", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 204 },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(
      screen.getByLabelText("Uw wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Verwijderen bevestigen" }),
    );
    await screen.findByRole("status");
    await userEvent.click(
      screen.getByRole("button", {
        name: "Nog geen account? Account aanmaken",
      }),
    );
    expect(
      screen.queryByText("Uw account is verwijderd."),
    ).not.toBeInTheDocument();
  });

  it("ignores a second delete submission while the first is still in flight", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const deleteRequest = deferred<void>();
    const fetchMock = vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
      const url = String(input);
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "content-type": "application/json" },
        });
      if (url.includes("/api/auth/me/")) return json(me);
      if (url.includes("/api/auth/consent-texts/")) return json(consentTexts);
      if (url.includes("/api/auth/delete/")) {
        await deleteRequest.promise;
        return new Response(null, { status: 204 });
      }
      throw new Error(`request to ${url} was not planned for`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(
      screen.getByLabelText("Uw wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    const submit = screen.getByRole("button", {
      name: "Verwijderen bevestigen",
    });
    await userEvent.click(submit);
    // The button is disabled now, so a real click cannot reach it a second
    // time; the guard inside the submit handler is what a stray resubmission
    // (an Enter key the disabled button does not intercept) would meet.
    const form = submit.closest("form");
    expect(form).not.toBeNull();
    if (form !== null) fireEvent.submit(form);
    expect(
      fetchMock.mock.calls.filter((call) =>
        String(call[0]).includes("/api/auth/delete/"),
      ),
    ).toHaveLength(1);
    deleteRequest.resolve();
  });

  it("explains what deletion removes only once the disclosure is open", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await screen.findByText(me.email);
    expect(
      screen.queryByText(/Hiermee verdwijnen uw e-mailadres/),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Account verwijderen" }),
    );
    expect(
      screen.getByText(/Hiermee verdwijnen uw e-mailadres/),
    ).toBeInTheDocument();
  });

  it("renders a field-shaped password error beside the field, as defence in depth", async () => {
    // The current backend never sends this shape (a wrong password is a
    // `detail`, never a `password` key, per `DeleteView.post`), so this is a
    // synthetic response proving the binding works if that ever changes.
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 400, body: { password: ["Dit veld mag niet leeg zijn."] } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(screen.getByLabelText("Uw wachtwoord"), "x");
    await userEvent.click(
      screen.getByRole("button", { name: "Verwijderen bevestigen" }),
    );
    const message = await screen.findByText("Dit veld mag niet leeg zijn.");
    const passwordField = screen.getByLabelText("Uw wachtwoord");
    expect(passwordField).toHaveAttribute("aria-describedby", message.id);
    // One alert only: the field-level message, never joined into a second,
    // form-level sentence.
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByText(me.email)).toBeInTheDocument();
  });

  it("offers the export as a file built from the text the API sent", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    // Pretty-printed on purpose, and not `JSON.stringify(exportPayload)`
    // (compact, no whitespace): a `JSON.parse` followed by a fresh
    // `JSON.stringify` is idempotent on a value already produced by
    // `JSON.stringify`, so a test built that way could never tell the
    // correct implementation apart from one that reparses and reserialises.
    // Formatting a real API would never add is what a reparse discards, and
    // it stands in here for the amount a reparse would otherwise round.
    const raw = `${JSON.stringify(exportPayload, null, 2)}\n`;
    const created: Blob[] = [];
    // jsdom implements neither of these, so both are stubbed rather than
    // spied on. Grafted onto the real `URL` rather than replacing the global
    // wholesale: jsdom's own `document.cookie` getter constructs `new URL(...)`
    // internally on every read (`accounts.ts` reads that cookie for the CSRF
    // token on every unsafe call), so swapping in a plain object here would
    // break that unrelated path the moment `exportAccount()` runs. Restored to
    // whatever jsdom itself had (neither exists there) once this test is done,
    // so no later test finds them.
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = (blob: Blob) => {
      created.push(blob);
      return "blob:een-url";
    };
    URL.revokeObjectURL = () => {};
    try {
      stub([
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 200, text: raw },
      ]);
      render(<AccountPage />);
      await userEvent.click(
        await screen.findByRole("button", { name: "Gegevens exporteren" }),
      );
      expect(created).toHaveLength(1);
      await expect(created[0]?.text()).resolves.toBe(raw);
    } finally {
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    }
  });

  it("signs out on a 204 and asks nothing afterwards", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 204 },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Uitloggen" }),
    );
    expect(
      await screen.findByRole("button", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(seen.filter((url) => url.includes("/api/auth/me/"))).toHaveLength(1);
    expect(
      seen.filter((url) => url.includes("/api/auth/refresh/")),
    ).toHaveLength(0);
  });

  it("asks for the password again before deleting, and moves focus to it", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    const opener = await screen.findByRole("button", {
      name: "Account verwijderen",
    });
    expect(opener).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(opener);
    expect(opener).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Uw wachtwoord")).toHaveFocus();
  });

  it("confirms in one line and shows the sign-in view after a 204", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 204 },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(
      screen.getByLabelText("Uw wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Verwijderen bevestigen" }),
    );
    const confirmation = await screen.findByRole("status");
    expect(confirmation).toHaveTextContent("Uw account is verwijderd.");
    // A `role="status"` inserted already holding its text is not reliably
    // announced by assistive tech unless something moves focus to it, so the
    // element itself, not the sign-in group beside it, has to be where focus
    // lands.
    expect(document.activeElement).toBe(confirmation);
    expect(
      screen.getByRole("button", { name: "Inloggen" }),
    ).toBeInTheDocument();
    // The 204 is the proof. A me/ afterwards would spend an auth-read on a
    // question already answered, and a 401 there is indistinguishable from a
    // session that simply expired. There is also nothing left to exchange:
    // the RefreshSession rows went with the account.
    expect(seen.filter((url) => url.includes("/api/auth/me/"))).toHaveLength(1);
    expect(
      seen.filter((url) => url.includes("/api/auth/refresh/")),
    ).toHaveLength(0);
  });

  it("shows the API's own sentence when a wrong password is given", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 403, body: { detail: "e-mailadres of wachtwoord klopt niet" } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Account verwijderen" }),
    );
    await userEvent.type(screen.getByLabelText("Uw wachtwoord"), "verkeerd");
    await userEvent.click(
      screen.getByRole("button", { name: "Verwijderen bevestigen" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "e-mailadres of wachtwoord klopt niet",
    );
    expect(screen.getByText(me.email)).toBeInTheDocument();
  });
});

describe("the meter section on the account page", () => {
  const MAY_LINK = {
    may_link: true,
    linked: false,
    created_at: null,
    last_seen_at: null,
    last_seen_label: null,
  };

  const LINKED = {
    may_link: true,
    linked: true,
    created_at: "2026-09-09T09:00:00Z",
    last_seen_at: "2026-09-09T10:15:00Z",
    last_seen_label: "9 september 2026 12:15",
  };

  const ISSUED_KEY = {
    token: "a".repeat(43),
    push_path: "/api/meter/readings/",
    created_at: "2026-09-09T09:00:00Z",
  };

  const CHECK = {
    advice_token: "b".repeat(22),
    check: {
      typed_kwh: 2800,
      p10_kwh: 3600,
      p50_kwh: 4000,
      p90_kwh: 4400,
      runs: 8,
      quarters_used: 5376,
      message: "Uw meter wijst op 3600 tot 4400 kWh per jaar.",
      measured_over:
        "Gemeten over 5376 kwartieren van uw eigen meter, in 8 herberekeningen met telkens een week weggelaten.",
      accept_label: "Reken met 4000 kWh",
      keep_own: "Doet u niets, dan blijft uw advies op uw eigen getal rekenen.",
      installation_note: null,
    },
  };

  it("turns a pasted link into an advice and asks the meter again", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 201, body: { token: "c".repeat(22) } },
      ],
      {
        meterStatus: { status: 200, body: LINKED },
        consumptionCheck: { advice_token: null, check: null },
      },
    );

    render(<AccountPage />);
    await userEvent.type(
      await screen.findByLabelText("Link van uw advies"),
      `/advies/${"b".repeat(22)}/`,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Koppel aan mijn account" }),
    );

    const claim = seen.filter((url) => url.includes("/api/auth/advice/claim/"));
    expect(claim).toHaveLength(1);
    // Asked again afterwards, because the account now has a household for the
    // meter to be held against.
    expect(
      seen.filter((url) => url.includes("/api/auth/advice/check/")).length,
    ).toBeGreaterThan(1);
  });

  it("asks what the meter says and shows it beside the link", async () => {
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
      ],
      {
        meterStatus: { status: 200, body: LINKED },
        consumptionCheck: CHECK,
      },
    );

    render(<AccountPage />);

    expect(await screen.findByText(CHECK.check.message)).toBeInTheDocument();
  });

  it("does not ask at all when no meter is linked", async () => {
    // Answering runs the engine several times, so a household without a link
    // must not spend that on a question whose answer is already known.
    const { seen } = stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
      ],
      { meterStatus: { status: 200, body: MAY_LINK } },
    );

    render(<AccountPage />);
    await screen.findByRole("button", { name: "Koppel uw meter" });

    expect(seen.some((url) => url.includes("/api/auth/advice/check/"))).toBe(
      false,
    );
  });

  it("stays usable when the answer about the meter cannot be read", async () => {
    // Silent by design. A household who cannot be told what their meter
    // thinks is not a household with a broken account page, so the section
    // renders its ordinary linked state and nothing else.
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
      ],
      {
        meterStatus: { status: 200, body: LINKED },
        consumptionCheck: { advice_token: 12, check: "onleesbaar" },
      },
    );

    render(<AccountPage />);

    expect(
      await screen.findByRole("button", { name: "Ontkoppel" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /kWh/ }),
    ).not.toBeInTheDocument();
  });

  it("accepts the measured figure and points at the recomputed advice", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 201, body: { token: "c".repeat(22) } },
      ],
      {
        meterStatus: { status: 200, body: LINKED },
        consumptionCheck: CHECK,
      },
    );

    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: /4000 kWh/ }),
    );

    const link = await screen.findByRole("link", {
      name: "Bekijk het nieuwe advies",
    });
    expect(link).toHaveAttribute("href", `/advies/${"c".repeat(22)}/`);
    expect(
      seen.some((url) =>
        url.includes(`/api/auth/advice/${"b".repeat(22)}/accept/`),
      ),
    ).toBe(true);
  });

  it("says what went wrong when accepting fails, and keeps the offer", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 400, body: { detail: "er valt nu niets te corrigeren" } },
      ],
      {
        meterStatus: { status: 200, body: LINKED },
        consumptionCheck: CHECK,
      },
    );

    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: /4000 kWh/ }),
    );

    expect(
      await screen.findByText("er valt nu niets te corrigeren"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Bekijk het nieuwe advies" }),
    ).not.toBeInTheDocument();
  });

  it("shows the issued key once linking succeeds", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 201, body: ISSUED_KEY },
      ],
      { meterStatus: { status: 200, body: MAY_LINK } },
    );
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Koppel uw meter" }),
    );
    expect(await screen.findByText(ISSUED_KEY.token)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(ISSUED_KEY.push_path.replace("/", "\\/"))),
    ).toBeInTheDocument();
  });

  it("removes the linked indicators once unlinking succeeds", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 204 },
      ],
      {
        // The status before the unlink, then the refreshed status after it,
        // the same two-call sequence `linkAction`/`unlinkAction` in
        // `AccountPage.tsx` make: call, then reload the status.
        meterStatus: [
          { status: 200, body: LINKED },
          { status: 200, body: MAY_LINK },
        ],
      },
    );
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Ontkoppel" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Ontkoppelen bevestigen" }),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Ontkoppel" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: "Koppel uw meter" }),
    ).toBeInTheDocument();
  });

  it("shows the API's Dutch sentence when linking is refused with a 403 detail", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        {
          status: 403,
          body: { detail: "geen toestemming of geen bevestigd e-mailadres" },
        },
      ],
      { meterStatus: { status: 200, body: MAY_LINK } },
    );
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Koppel uw meter" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "geen toestemming of geen bevestigd e-mailadres",
    );
  });

  it("shows the API's sentence and keeps the link when unlinking fails", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        {
          status: 429,
          body: { detail: "u vraagt dit te vaak, probeer het later opnieuw" },
        },
      ],
      { meterStatus: { status: 200, body: LINKED } },
    );
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Ontkoppel" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Ontkoppelen bevestigen" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "u vraagt dit te vaak, probeer het later opnieuw",
    );
    // The koppeling this page showed before the click is still what it
    // shows after a failed unlink: the opener is back (the confirmation
    // step closes on any click, success or failure, the same as it does for
    // the account deletion form's disclosure one section down) and it
    // still reads "Ontkoppel", not the possible-to-link state a successful
    // unlink would have moved to.
    expect(screen.getByRole("button", { name: "Ontkoppel" })).toBeEnabled();
  });

  /**
   * The genuine red-proof for the check above: a 403 whose body carries no
   * `detail` at all leaves `ApiError.message` empty, per `accounts.ts`'s own
   * contract (`detail ?? ""`). `describeAuthError` turns that into the
   * standing "could not be read" sentence rather than an empty alert.
   * Showing `error.message` on this path instead of routing through
   * `describeAuthError` (as every other handler in this file already does)
   * would show nothing at all here, which is what this test is red-proofed
   * against: change `linkAction`'s catch to
   * `setFailure(error instanceof ApiError ? error.message : "")` and this
   * assertion fails on an empty alert.
   */
  it("falls back to the generic sentence, not an empty alert, when linking fails without one", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub(
      [
        { status: 200, body: me },
        { status: 200, body: consentTexts },
        { status: 403, body: {} },
      ],
      { meterStatus: { status: 200, body: MAY_LINK } },
    );
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Koppel uw meter" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "De server gaf een antwoord dat wij niet konden lezen.",
    );
  });
});

// ---------------------------------------------------------------------------
// The route file, which is the half of this page that ships without JavaScript
// ---------------------------------------------------------------------------

describe("the account route as Next will call it", () => {
  it("ships the heading and the paragraph that say what this page is", () => {
    // The client component underneath asks `me/` on mount. A request that
    // never settles keeps this render on the loading sentence, so what is
    // asserted below is what the server component itself put in
    // out/account/index.html and not something a fetch decided.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => new Promise(() => {})),
    );
    render(<AccountRoute />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Uw account" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Voor de rekenmachine is geen account nodig\./),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Uw gegevens worden opgehaald.",
    );
  });

  it("names itself once and asks not to be indexed", () => {
    expect(metadata.title).toBe("Uw account");
    expect(String(metadata.description).length).toBeGreaterThan(50);
    expect(metadata.alternates?.canonical).toBe("/account/");
    // A string and not a URL, for the reason the file gives: Next reads a URL
    // here as a base and canonicalises the page to the root.
    expect(typeof metadata.alternates?.canonical).toBe("string");
    // Absent from the sitemap says which pages this product wants found. Only
    // this tag says it to a crawler that arrived by an inbound link.
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});

describe("a link with a token in its fragment", () => {
  const TOKEN = "F".repeat(43);

  afterEach(() => {
    window.history.replaceState(null, "", "/account/");
  });

  it("opens the new-password form on a reset fragment when nobody is signed in", async () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    const replaceState = vi.spyOn(window.history, "replaceState");
    try {
      stub([
        { status: 401, body: { detail: "u bent niet ingelogd" } },
        { status: 200 },
        { status: 401, body: { detail: "u bent niet ingelogd" } },
      ]);
      render(<AccountPage />);
      expect(
        await screen.findByRole("heading", { name: "Nieuw wachtwoord" }),
      ).toBeInTheDocument();
      expect(window.location.hash).toBe("");
      // The fragment left the address bar through replaceState and not
      // through a navigation: the page, not the browser, took the token out
      // of history. The first argument is `null`, not `expect.anything()`
      // (which Vitest's matcher explicitly refuses to match against `null`):
      // the setup above put the browser in a state of `null` before this
      // render, and fragment.ts's own contract is to carry that state
      // through unchanged rather than clobber it, which this pins to the
      // concrete value rather than to "some value or other".
      expect(replaceState).toHaveBeenCalledWith(null, "", "/account/");
      expect(document.body.innerHTML).not.toContain(TOKEN);
      expect(document.activeElement).toBe(document.body);
    } finally {
      // In a `finally`, not at the end of the `try`: a failed assertion
      // above must not leave this spy in place for whichever test runs
      // next.
      replaceState.mockRestore();
    }
  });

  it("clears the fragment from the address bar before the first answer arrives", async () => {
    // Spec 6.1: the token is read once and cleared "meteen", immediately,
    // not once `me/` has settled. A deferred `me/` response is what makes
    // this failable: without the deferral, the exchange could resolve
    // before this assertion runs and the test would pass whether or not the
    // clearing actually happened before that answer.
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    const replaceState = vi.spyOn(window.history, "replaceState");
    const meRequest = deferred<Response>();
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => meRequest.promise),
    );
    try {
      render(<AccountPage />);
      // Still loading: the deferred `me/` has not answered, and the page
      // has not asked anything else yet either.
      expect(screen.getByRole("status")).toHaveTextContent(
        "Uw gegevens worden opgehaald.",
      );
      expect(window.location.hash).toBe("");
      expect(replaceState).toHaveBeenCalledWith(null, "", "/account/");
      const call = replaceState.mock.calls[0];
      expect(call).toBeDefined();
      expect(String(call?.[2])).not.toContain("#");
    } finally {
      meRequest.resolve(
        new Response(JSON.stringify({ detail: "u bent niet ingelogd" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      );
      replaceState.mockRestore();
    }
  });

  it("ignores a reset fragment when somebody is signed in", async () => {
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    expect(await screen.findByText(me.email)).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Nieuw wachtwoord" }),
    ).not.toBeInTheDocument();
  });

  it("returns to signing in with a notice after the password was saved", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    const { seen } = stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 204 },
    ]);
    render(<AccountPage />);
    await userEvent.type(
      // `{ selector: "input" }`, the same disambiguation
      // `ResetConfirmForm.test.tsx` already uses: chapter 6.2 gives this
      // form's one field the same label text as its own heading, so an
      // unqualified label-text lookup also matches the (unlabelled here, but
      // still self-referencing) `<section>` around it.
      await screen.findByLabelText("Nieuw wachtwoord", { selector: "input" }),
      "een-ander-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord opslaan" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord.",
    );
    expect(
      screen.getByRole("heading", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(seen.at(-1)).toContain("/api/auth/reset/confirm/");
    expect(seen.filter((url) => url.endsWith("/me/"))).toHaveLength(2);
  });

  it("asks for a new link once a reset link turns out to be stale", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    window.history.replaceState(null, "", `/account/#herstel=${TOKEN}`);
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      {
        status: 400,
        body: {
          token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"],
        },
      },
    ]);
    render(<AccountPage />);
    await userEvent.type(
      await screen.findByLabelText("Nieuw wachtwoord", { selector: "input" }),
      "een-ander-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord opslaan" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Wachtwoord vergeten?" }),
    );
    expect(
      screen.getByRole("heading", { name: "Wachtwoord herstellen" }),
    ).toBeInTheDocument();
  });

  it("confirms an address only after the first me/, and asks me/ again when signed in", async () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    // Answered by path and not by position (ruling 74): the confirmation is
    // posted from the session callback, before React has mounted AccountView
    // and started its consent-texts effect, so the order between those two
    // requests, and between either of them and the second me/ (which fires
    // the instant `confirmEmailVerification` resolves, racing the DOM update
    // `findByText` below waits for), is an implementation detail this test
    // must not depend on. What it asserts is the order between the FIRST
    // me/ and verify/confirm/, which is the rule, and that there are
    // exactly two me/ calls in total.
    const seen: string[] = [];
    let meCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
        const url = String(input);
        seen.push(url);
        const path = new URL(url).pathname;
        if (path === "/api/auth/me/") {
          meCalls += 1;
          const body =
            meCalls === 1
              ? me
              : { ...me, email_verified_at: "2026-09-06T10:00:00+00:00" };
          return new Response(JSON.stringify(body), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        }
        if (path === "/api/auth/consent-texts/")
          return new Response(JSON.stringify(consentTexts), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        if (path === "/api/auth/verify/confirm/")
          return new Response(null, { status: 204 });
        throw new Error(`no answer planned for ${path}`);
      }),
    );
    render(<AccountPage />);
    const confirmed = await screen.findByText("Uw e-mailadres is bevestigd.");
    expect(confirmed).toHaveAttribute("role", "status");
    const paths = seen.map((url) => new URL(url).pathname);
    expect(paths.indexOf("/api/auth/verify/confirm/")).toBeGreaterThan(
      paths.indexOf("/api/auth/me/"),
    );
    expect(paths.filter((path) => path === "/api/auth/me/")).toHaveLength(2);
    expect(
      await screen.findByText("E-mailadres bevestigd"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Verstuur de bevestigingsmail opnieuw",
      }),
    ).not.toBeInTheDocument();
  });

  it("confirms an address for a visitor who is not signed in, and shows the sign-in form", async () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    const seen: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
        const url = String(input);
        seen.push(url);
        const path = new URL(url).pathname;
        if (path === "/api/auth/me/")
          return new Response(
            JSON.stringify({ detail: "u bent niet ingelogd" }),
            { status: 401, headers: { "content-type": "application/json" } },
          );
        if (path === "/api/auth/refresh/")
          return new Response(null, { status: 200 });
        if (path === "/api/auth/verify/confirm/")
          return new Response(null, { status: 204 });
        throw new Error(`no answer planned for ${path}`);
      }),
    );
    render(<AccountPage />);
    const confirmed = await screen.findByText("Uw e-mailadres is bevestigd.");
    expect(confirmed).toHaveAttribute("role", "status");
    expect(
      screen.getByRole("heading", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(seen.filter((url) => url.endsWith("/me/"))).toHaveLength(2);
    // Exactly four requests here, in a fixed order: me/, refresh/, me/ (the
    // one exchange `loadSession` allows), then verify/confirm/ last, because
    // nothing is posted before that exchange settles.
    const paths = seen.map((url) => new URL(url).pathname);
    expect(paths).toEqual([
      "/api/auth/me/",
      "/api/auth/refresh/",
      "/api/auth/me/",
      "/api/auth/verify/confirm/",
    ]);
  });

  it("keeps the confirmed sentence when the second me/ fails after a successful confirmation", async () => {
    // Important 1: the second `me/` used to sit inside the `try` guarding
    // `confirmEmailVerification`, so a dropped connection here ran the
    // confirmation's own `catch` and replaced "Uw e-mailadres is bevestigd."
    // with an error sentence, telling a household its address was not
    // confirmed while the token was already spent.
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    let meCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
        const path = new URL(String(input)).pathname;
        if (path === "/api/auth/me/") {
          meCalls += 1;
          if (meCalls === 1) {
            return new Response(JSON.stringify(me), {
              status: 200,
              headers: { "content-type": "application/json" },
            });
          }
          throw new TypeError("Failed to fetch");
        }
        if (path === "/api/auth/consent-texts/")
          return new Response(JSON.stringify(consentTexts), {
            status: 200,
            headers: { "content-type": "application/json" },
          });
        if (path === "/api/auth/verify/confirm/")
          return new Response(null, { status: 204 });
        throw new Error(`no answer planned for ${path}`);
      }),
    );
    render(<AccountPage />);
    const confirmed = await screen.findByText("Uw e-mailadres is bevestigd.");
    expect(confirmed).toHaveAttribute("role", "status");
    // The failed second me/ falls back to the same answer this page gives a
    // failed me/ anywhere else: the sign-in view, with the network sentence.
    expect(
      await screen.findByRole("heading", { name: "Inloggen" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Wij konden de server niet bereiken.",
    );
    // And the confirmation sentence is still there, untouched by that.
    expect(
      screen.getByText("Uw e-mailadres is bevestigd."),
    ).toBeInTheDocument();
  });

  it("shows the API's sentence when the confirmation link is stale", async () => {
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    const seen: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input: RequestInfo | URL) => {
        const url = String(input);
        seen.push(url);
        const path = new URL(url).pathname;
        if (path === "/api/auth/me/")
          return new Response(
            JSON.stringify({ detail: "u bent niet ingelogd" }),
            { status: 401, headers: { "content-type": "application/json" } },
          );
        if (path === "/api/auth/refresh/")
          return new Response(null, { status: 200 });
        if (path === "/api/auth/verify/confirm/")
          return new Response(
            JSON.stringify({
              token: [
                "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
              ],
            }),
            { status: 400, headers: { "content-type": "application/json" } },
          );
        throw new Error(`no answer planned for ${path}`);
      }),
    );
    render(<AccountPage />);
    // findByText, not findByRole("status"): the loading sentence is also a
    // role="status" paragraph, present on the very first render, so a plain
    // findByRole("status") resolves on that one before this effect's fetch
    // chain has had a turn to run.
    expect(
      await screen.findByText(
        "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
      ),
    ).toBeInTheDocument();
    const paths = seen.map((url) => new URL(url).pathname);
    expect(paths).toEqual([
      "/api/auth/me/",
      "/api/auth/refresh/",
      "/api/auth/me/",
      "/api/auth/verify/confirm/",
    ]);
  });

  it("shows the server's own sentence when confirming fails without a token-specific message", async () => {
    // The other side of the ternary at the confirmation's catch: a 429
    // carries only `detail`, no `token` field, so `describeAuthError` is
    // what has to answer.
    window.history.replaceState(null, "", `/account/#verificatie=${TOKEN}`);
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      {
        status: 429,
        body: { detail: "u vraagt dit te vaak, probeer het later opnieuw" },
      },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByText(
        "u vraagt dit te vaak, probeer het later opnieuw",
      ),
    ).toBeInTheDocument();
  });
});

describe("the address line in the account view", () => {
  it("says the address is not yet confirmed, offers to resend, and says why it matters", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    const { seen } = stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      { status: 202, body: {} },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByText("E-mailadres nog niet bevestigd"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Voor het koppelen van een slimme meter is een bevestigd e-mailadres nodig.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", {
        name: "Verstuur de bevestigingsmail opnieuw",
      }),
    );
    expect(
      await screen.findByText("De bevestigingsmail is onderweg."),
    ).toBeInTheDocument();
    expect(seen.at(-1)).toContain("/api/auth/verify/request/");
  });

  it("shows the API's own sentence when resending the confirmation mail fails", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 200, body: me },
      { status: 200, body: consentTexts },
      {
        status: 429,
        body: { detail: "u vraagt dit te vaak, probeer het later opnieuw" },
      },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Verstuur de bevestigingsmail opnieuw",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "u vraagt dit te vaak, probeer het later opnieuw",
    );
    expect(
      screen.getByText("E-mailadres nog niet bevestigd"),
    ).toBeInTheDocument();
  });

  it("says the address is confirmed and offers nothing when it is", async () => {
    stub([
      {
        status: 200,
        body: { ...me, email_verified_at: "2026-09-06T10:00:00+00:00" },
      },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    expect(
      await screen.findByText("E-mailadres bevestigd"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Verstuur de bevestigingsmail opnieuw",
      }),
    ).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain("2026-09-06");
  });

  it("says a mail is on its way right after registering", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200, body: consentTexts },
      { status: 201 },
      { status: 200, body: me },
      { status: 200, body: consentTexts },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Nog geen account? Account aanmaken",
      }),
    );
    await userEvent.type(
      await screen.findByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(
      screen.getByLabelText("Wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Account aanmaken" }),
    );
    expect(
      await screen.findByText(
        "Er is een e-mail onderweg om uw adres te bevestigen.",
      ),
    ).toBeInTheDocument();
  });

  it("reaches the request form from the sign-in form and back", async () => {
    const userEvent = (await import("@testing-library/user-event")).default;
    stub([
      { status: 401, body: { detail: "u bent niet ingelogd" } },
      { status: 200 },
      { status: 401, body: { detail: "u bent niet ingelogd" } },
    ]);
    render(<AccountPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Wachtwoord vergeten?" }),
    );
    expect(
      screen.getByRole("heading", { name: "Wachtwoord herstellen" }),
    ).toBeInTheDocument();
    expect(document.activeElement).not.toBe(document.body);
    await userEvent.click(
      screen.getByRole("button", { name: "Terug naar inloggen" }),
    );
    expect(
      screen.getByRole("heading", { name: "Inloggen" }),
    ).toBeInTheDocument();
  });
});
