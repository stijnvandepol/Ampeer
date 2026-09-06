import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import me from "../fixtures/me-response.json";
import { SignInForm } from "@/app/_account/SignInForm";

afterEach(() => vi.unstubAllGlobals());

function stub(answers: readonly { status: number; body?: unknown }[]) {
  let index = 0;
  const fetchMock = vi.fn<typeof fetch>(async () => {
    const answer = answers[index];
    index += 1;
    if (answer === undefined)
      throw new Error(`request ${index} was not planned for`);
    return new Response(JSON.stringify(answer.body ?? null), {
      status: answer.status,
      headers: { "content-type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("the sign-in view", () => {
  it("asks for an address and a password, and says so to a screen reader", () => {
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    const email = screen.getByLabelText("E-mailadres");
    const password = screen.getByLabelText("Wachtwoord");
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
  });

  it("says out loud that a lost password cannot be recovered", () => {
    // Chapter 10 of the auth design calls this the weakest place in that
    // design and names the consequence: somebody who loses their password
    // also loses the delete endpoint. That belongs on the screen where
    // somebody needs it and not in a document.
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    expect(screen.getByText(/wij het niet herstellen/i)).toBeInTheDocument();
  });

  it("asks me/ after a 200, because login/ answers with no body", async () => {
    const fetchMock = stub([{ status: 200 }, { status: 200, body: me }]);
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} onRegister={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(
      screen.getByLabelText("Wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(onSignedIn).toHaveBeenCalledWith(me);
  });

  it("shows the API's own sentence on a wrong password", async () => {
    stub([
      { status: 401, body: { detail: "e-mailadres of wachtwoord klopt niet" } },
    ]);
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(screen.getByLabelText("Wachtwoord"), "verkeerd");
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("e-mailadres of wachtwoord klopt niet");
  });

  it("does not call onSignedIn when the second request fails", async () => {
    // The half a test that only checks the first call would miss: login
    // succeeded, so the cookies are set, and the view still may not claim to
    // know who is signed in.
    stub([{ status: 200 }, { status: 500, body: {} }]);
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} onRegister={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(
      screen.getByLabelText("Wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
  });

  it("puts each field's own message beside its own field, not joined into one sentence", async () => {
    // Property 3's red-proof: remove the per-field rendering and this fails,
    // because the two messages below would then arrive concatenated into the
    // one form-level alert instead of sitting beside their own input.
    stub([
      {
        status: 400,
        body: {
          email: ["dit e-mailadres is niet geldig"],
          password: ["dit wachtwoord is te kort"],
        },
      },
    ]);
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(screen.getByLabelText("Wachtwoord"), "kort");
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    const email = screen.getByLabelText("E-mailadres");
    const password = screen.getByLabelText("Wachtwoord");
    const emailError = await screen.findByText(
      "dit e-mailadres is niet geldig",
    );
    const passwordError = screen.getByText("dit wachtwoord is te kort");
    expect(email.getAttribute("aria-describedby")).toBe(emailError.id);
    expect(password.getAttribute("aria-describedby")).toBe(passwordError.id);
  });

  it("shows the network sentence when the request never arrives", async () => {
    // A rejected fetch (the network is gone, the origin unreachable) is not
    // an ApiError, so fieldErrors(error) must fall through empty and this
    // stays a form-level sentence rather than a field one.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => Promise.reject(new TypeError("network gone"))),
    );
    render(<SignInForm onSignedIn={vi.fn()} onRegister={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.type(
      screen.getByLabelText("Wachtwoord"),
      "een-heel-lang-wachtwoord",
    );
    await userEvent.click(screen.getByRole("button", { name: "Inloggen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Wij konden de server niet bereiken",
    );
  });

  it("offers the way to the registration view", async () => {
    const onRegister = vi.fn();
    render(<SignInForm onSignedIn={vi.fn()} onRegister={onRegister} />);
    await userEvent.click(
      screen.getByRole("button", {
        name: "Nog geen account? Account aanmaken",
      }),
    );
    expect(onRegister).toHaveBeenCalledTimes(1);
  });
});
