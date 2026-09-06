import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResetConfirmForm } from "@/app/_account/ResetConfirmForm";

afterEach(() => vi.unstubAllGlobals());

const TOKEN = "T".repeat(43);

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

describe("choosing a new password with a link", () => {
  it("posts the token and the password, and reports back on a 204", async () => {
    const fetchMock = stub(204, null);
    const onReset = vi.fn();
    render(
      <ResetConfirmForm
        token={TOKEN}
        onReset={onReset}
        onRequestNew={vi.fn()}
      />,
    );
    await userEvent.type(
      screen.getByLabelText("Nieuw wachtwoord"),
      "een-ander-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord opslaan" }),
    );
    await vi.waitFor(() => expect(onReset).toHaveBeenCalledTimes(1));
    expect(
      JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body)),
    ).toEqual({
      token: TOKEN,
      password: "een-ander-wachtwoord",
    });
    expect(document.body.textContent).not.toContain(TOKEN);
  });

  it("hangs a token error on the password field and offers a new link", async () => {
    stub(400, {
      token: ["deze link is verlopen of al gebruikt; vraag een nieuwe aan"],
    });
    const onRequestNew = vi.fn();
    render(
      <ResetConfirmForm
        token={TOKEN}
        onReset={vi.fn()}
        onRequestNew={onRequestNew}
      />,
    );
    await userEvent.type(
      screen.getByLabelText("Nieuw wachtwoord"),
      "een-ander-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord opslaan" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    );
    expect(
      screen.getByLabelText("Nieuw wachtwoord"),
    ).toHaveAccessibleDescription(
      "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord vergeten?" }),
    );
    expect(onRequestNew).toHaveBeenCalledTimes(1);
  });

  it("hangs a password error on the password field, like registration does", async () => {
    stub(400, { password: ["wachtwoord moet minimaal 12 tekens bevatten"] });
    render(
      <ResetConfirmForm
        token={TOKEN}
        onReset={vi.fn()}
        onRequestNew={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText("Nieuw wachtwoord"), "kort");
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord opslaan" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "wachtwoord moet minimaal 12 tekens bevatten",
    );
    expect(
      screen.queryByRole("button", { name: "Wachtwoord vergeten?" }),
    ).not.toBeInTheDocument();
  });

  it("shows a 429 as the API wrote it, and never English", async () => {
    stub(429, {
      detail:
        "te veel verzoeken achter elkaar; probeer het over 900 seconden opnieuw",
    });
    render(
      <ResetConfirmForm
        token={TOKEN}
        onReset={vi.fn()}
        onRequestNew={vi.fn()}
      />,
    );
    await userEvent.type(
      screen.getByLabelText("Nieuw wachtwoord"),
      "een-ander-wachtwoord",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Wachtwoord opslaan" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "te veel verzoeken achter elkaar; probeer het over 900 seconden opnieuw",
    );
    expect(screen.getByLabelText("Nieuw wachtwoord")).not.toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(document.body.textContent).not.toContain("API returned");
  });

  it("never renders the token anywhere in the document", () => {
    render(
      <ResetConfirmForm
        token={TOKEN}
        onReset={vi.fn()}
        onRequestNew={vi.fn()}
      />,
    );
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });
});
