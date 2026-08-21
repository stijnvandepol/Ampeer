import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionShell } from "@/components/form/QuestionShell";

function shell(
  step: number,
  title: string,
  handlers: { onBack: () => void; onNext: () => void },
) {
  return (
    <QuestionShell
      step={step}
      of={4}
      title={title}
      onBack={handlers.onBack}
      onNext={handlers.onNext}
    >
      <label htmlFor="iets">Iets</label>
      <input id="iets" type="text" />
    </QuestionShell>
  );
}

describe("the question shell", () => {
  it("shows the question as a heading with the progress above it", () => {
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(2, "Hoeveel stroom gebruikt u?", handlers));
    expect(
      screen.getByRole("heading", { name: "Hoeveel stroom gebruikt u?" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "2",
    );
  });

  it("moves focus to the question heading when the step changes", async () => {
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    const { rerender } = render(shell(1, "Een", handlers));
    rerender(shell(2, "Twee", handlers));
    expect(screen.getByRole("heading", { name: "Twee" })).toHaveFocus();
  });

  it("does not take focus away from anybody on arrival", () => {
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(1, "Een", handlers));
    expect(screen.getByRole("heading", { name: "Een" })).not.toHaveFocus();
  });

  it("does not advance when Enter is pressed in a field", async () => {
    // A form with one input submits implicitly. Somebody pressing Enter to
    // confirm what they typed would skip to the next question with a value
    // they had not finished checking.
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(1, "Een", handlers));
    await userEvent.type(screen.getByLabelText("Iets"), "3500{Enter}");
    expect(handlers.onNext).not.toHaveBeenCalled();
  });

  it("goes dead in both directions while an answer is being computed", async () => {
    // The window this exists for is the two and a half seconds a computation
    // takes. A live forward button in it is one full server-side simulation
    // per impatient click, out of twenty an hour, with no retry anywhere in
    // this codebase to undo them; a live Terug walks back to the previous
    // question while the navigation already under way pulls the page away.
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(
      <QuestionShell
        step={4}
        of={4}
        title="Vier"
        nextLabel="Bereken"
        busy
        onBack={handlers.onBack}
        onNext={handlers.onNext}
      >
        <p>Iets</p>
      </QuestionShell>,
    );
    const compute = screen.getByRole("button", { name: "Bereken" });
    expect(compute).toBeDisabled();
    expect(compute).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Terug" })).toBeDisabled();
    await userEvent.click(compute);
    await userEvent.click(screen.getByRole("button", { name: "Terug" }));
    expect(handlers.onNext).not.toHaveBeenCalled();
    expect(handlers.onBack).not.toHaveBeenCalled();
  });

  it("is operable from the keyboard, both ways", async () => {
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(2, "Twee", handlers));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(handlers.onNext).toHaveBeenCalledTimes(1);
    screen.getByRole("button", { name: "Terug" }).focus();
    await userEvent.keyboard("{Enter}");
    expect(handlers.onBack).toHaveBeenCalledTimes(1);
  });
});
