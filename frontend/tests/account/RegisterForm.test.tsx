import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import consentTexts from "../fixtures/consent-texts.json";
import me from "../fixtures/me-response.json";
import { RegisterForm } from "@/app/_account/RegisterForm";
import { ConsentRow } from "@/app/_account/ConsentRow";

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

async function fillIn(): Promise<void> {
  await userEvent.type(
    screen.getByLabelText("E-mailadres"),
    "iemand@voorbeeld.nl",
  );
  await userEvent.type(
    screen.getByLabelText("Wachtwoord"),
    "een-heel-lang-wachtwoord",
  );
}

describe("the registration view", () => {
  it("shows the sentence the API sent, byte for byte", async () => {
    stub([{ status: 200, body: consentTexts }]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    expect(
      await screen.findByText(consentTexts.texts.METER_LINK),
    ).toBeInTheDocument();
    expect(
      screen.getByText(consentTexts.texts.LEAD_GENERATION),
    ).toBeInTheDocument();
  });

  it("starts with both boxes unticked and neither one required", async () => {
    // Not pre-ticked is a property of this line and of the serializer, which
    // gives the fields no default. Not required is article 7(4): the API
    // creates the account with both refused, so the form may not refuse it.
    stub([{ status: 200, body: consentTexts }]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    const boxes = await screen.findAllByRole("checkbox");
    expect(boxes).toHaveLength(2);
    for (const box of boxes) {
      expect(box).not.toBeChecked();
      expect(box).not.toBeRequired();
    }
  });

  it("cannot be submitted while the consent texts have not come back", () => {
    // A `true` sent for a sentence nobody read is not consent, so there is
    // nothing to press until the sentences are on the screen.
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(() => new Promise(() => {})),
    );
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    expect(
      screen.queryByRole("button", { name: "Account aanmaken" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "De toestemmingsteksten worden opgehaald.",
    );
  });

  it("says so, and offers no button, when the texts could not be fetched", async () => {
    stub([{ status: 500, body: {} }]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "De toestemmingsteksten konden niet worden opgehaald.",
    );
    expect(
      screen.queryByRole("button", { name: "Account aanmaken" }),
    ).not.toBeInTheDocument();
  });

  it("registers with both consents refused, which the API accepts", async () => {
    const fetchMock = stub([
      { status: 200, body: consentTexts },
      { status: 201 },
      { status: 200, body: me },
    ]);
    const onRegistered = vi.fn();
    render(<RegisterForm onRegistered={onRegistered} onSignIn={vi.fn()} />);
    await screen.findAllByRole("checkbox");
    await fillIn();
    await userEvent.click(
      screen.getByRole("button", { name: "Account aanmaken" }),
    );
    const body = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(body).toEqual({
      email: "iemand@voorbeeld.nl",
      password: "een-heel-lang-wachtwoord",
      consent_meter_link: false,
      consent_lead_generation: false,
      text_version: consentTexts.text_version,
    });
    expect(onRegistered).toHaveBeenCalledWith(me);
  });

  it("sends the version the sentences on the screen came with", async () => {
    // Not a constant in the frontend: that would be a second place the version
    // lives, and the 400 in chapter 5.2 exists precisely to close the window
    // in which those two can disagree.
    const fetchMock = stub([
      { status: 200, body: { ...consentTexts, text_version: "2027-01-01" } },
      { status: 201 },
      { status: 200, body: me },
    ]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    await screen.findAllByRole("checkbox");
    await fillIn();
    await userEvent.click(
      screen.getByRole("button", { name: "Account aanmaken" }),
    );
    const body = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(body.text_version).toBe("2027-01-01");
  });

  it("shows the API's Dutch message on a stale version", async () => {
    stub([
      { status: 200, body: consentTexts },
      {
        status: 400,
        body: {
          text_version: [
            "de toestemmingstekst is gewijzigd, herlaad de pagina en probeer het opnieuw",
          ],
        },
      },
    ]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    await screen.findAllByRole("checkbox");
    await fillIn();
    await userEvent.click(
      screen.getByRole("button", { name: "Account aanmaken" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "de toestemmingstekst is gewijzigd",
    );
  });

  it("offers the way back to the sign-in view", async () => {
    stub([{ status: 200, body: consentTexts }]);
    const onSignIn = vi.fn();
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={onSignIn} />);
    await userEvent.click(
      await screen.findByRole("button", {
        name: "Ik heb al een account. Inloggen",
      }),
    );
    expect(onSignIn).toHaveBeenCalledTimes(1);
  });

  it("sends a ticked box as true", async () => {
    // The two boxes start unticked (a separate test above), but ticking one
    // has to reach the request: an onChange nobody wired up would tick the
    // box on the screen while the API still received false underneath it.
    const fetchMock = stub([
      { status: 200, body: consentTexts },
      { status: 201 },
      { status: 200, body: me },
    ]);
    render(<RegisterForm onRegistered={vi.fn()} onSignIn={vi.fn()} />);
    const boxes = await screen.findAllByRole("checkbox");
    await fillIn();
    for (const box of boxes) await userEvent.click(box);
    await userEvent.click(
      screen.getByRole("button", { name: "Account aanmaken" }),
    );
    const body = JSON.parse(
      String((fetchMock.mock.calls[1]?.[1] as RequestInit).body),
    );
    expect(body).toEqual({
      email: "iemand@voorbeeld.nl",
      password: "een-heel-lang-wachtwoord",
      consent_meter_link: true,
      consent_lead_generation: true,
      text_version: consentTexts.text_version,
    });
  });
});

describe("the account view's consent row", () => {
  it("offers to give consent when none is granted, and says so", () => {
    const onToggle = vi.fn();
    render(
      <ConsentRow
        kind="METER_LINK"
        text={consentTexts.texts.METER_LINK}
        granted={false}
        busy={false}
        onToggle={onToggle}
      />,
    );
    expect(screen.getByText("Geen toestemming gegeven")).toBeInTheDocument();
    expect(screen.getByText(consentTexts.texts.METER_LINK)).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Toestemming geven" });
    expect(button).not.toBeDisabled();
  });

  it("offers to withdraw consent when it is granted, sentence or none", () => {
    const onToggle = vi.fn();
    render(
      <ConsentRow
        kind="LEAD_GENERATION"
        text={null}
        granted={true}
        busy={false}
        onToggle={onToggle}
      />,
    );
    expect(screen.getByText("Toestemming gegeven")).toBeInTheDocument();
    const button = screen.getByRole("button", {
      name: "Toestemming intrekken",
    });
    expect(button).not.toBeDisabled();
  });

  it("calls onToggle with the opposite of the current state", async () => {
    const onToggle = vi.fn();
    render(
      <ConsentRow
        kind="METER_LINK"
        text={consentTexts.texts.METER_LINK}
        granted={false}
        busy={false}
        onToggle={onToggle}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Toestemming geven" }),
    );
    expect(onToggle).toHaveBeenCalledWith("GRANTED");
  });

  it("refuses to grant a consent whose sentence could not be fetched", () => {
    // Withdrawing may never be harder than granting, so this refusal only
    // applies while the consent is not yet granted.
    render(
      <ConsentRow
        kind="METER_LINK"
        text={null}
        granted={false}
        busy={false}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/Intrekken kan wel, aanzetten niet/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Toestemming geven" }),
    ).toBeDisabled();
  });

  it("goes dead while a toggle is in flight", () => {
    render(
      <ConsentRow
        kind="METER_LINK"
        text={consentTexts.texts.METER_LINK}
        granted={true}
        busy={true}
        onToggle={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", {
      name: "Toestemming intrekken",
    });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });
});
