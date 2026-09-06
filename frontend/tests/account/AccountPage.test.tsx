import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import me from "../fixtures/me-response.json";
import consentTexts from "../fixtures/consent-texts.json";
import exportPayload from "../fixtures/export-response.json";
import { AccountPage } from "@/app/_account/AccountPage";

afterEach(() => vi.unstubAllGlobals());

/** One answer per request, in order, plus the addresses that were asked for. */
function stub(
  answers: readonly {
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
  }[],
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
    const body = JSON.parse(
      String((fetchMock.mock.calls[2]?.[1] as RequestInit).body),
    );
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
    const body = JSON.parse(
      String((fetchMock.mock.calls[2]?.[1] as RequestInit).body),
    );
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
