import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResetRequestForm } from "@/app/_account/ResetRequestForm";

afterEach(() => vi.unstubAllGlobals());

function stub(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const SENT =
  "Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar. De link daarin werkt een uur.";

describe("asking for a reset link", () => {
  it("posts the address and then says the same sentence whatever the address was", async () => {
    const fetchMock = stub(202, {});
    render(<ResetRequestForm onBack={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Stuur een herstellink" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(SENT);
    expect(screen.queryByLabelText("E-mailadres")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body)),
    ).toEqual({
      email: "iemand@voorbeeld.nl",
    });
  });

  it("shows a 400 beside the address field and keeps the form", async () => {
    stub(400, { email: ["geen geldig e-mailadres"] });
    render(<ResetRequestForm onBack={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("E-mailadres"), "geen adres");
    await userEvent.click(
      screen.getByRole("button", { name: "Stuur een herstellink" }),
    );
    const field = screen.getByLabelText("E-mailadres");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "geen geldig e-mailadres",
    );
    expect(field).toHaveAccessibleDescription("geen geldig e-mailadres");
    expect(field).toHaveAttribute("aria-invalid", "true");
  });

  it("shows a 429 as the API wrote it, and never English", async () => {
    stub(429, {
      detail:
        "te veel verzoeken achter elkaar; probeer het over 900 seconden opnieuw",
    });
    render(<ResetRequestForm onBack={vi.fn()} />);
    await userEvent.type(
      screen.getByLabelText("E-mailadres"),
      "iemand@voorbeeld.nl",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Stuur een herstellink" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "te veel verzoeken achter elkaar; probeer het over 900 seconden opnieuw",
    );
    expect(document.body.textContent).not.toContain("API returned");
  });

  it("goes back to signing in on the one button that says so", async () => {
    const onBack = vi.fn();
    render(<ResetRequestForm onBack={onBack} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Terug naar inloggen" }),
    );
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("names its own heading, so the group around it can point at it", () => {
    render(<ResetRequestForm onBack={vi.fn()} />);
    expect(
      screen.getByRole("heading", { name: "Wachtwoord herstellen" }),
    ).toHaveAttribute("id", "wachtwoord-herstellen");
  });
});
