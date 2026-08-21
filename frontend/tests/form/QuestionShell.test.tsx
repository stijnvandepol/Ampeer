import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionShell } from "@/components/form/QuestionShell";

function shell(step: number, title: string, handlers: { onBack: () => void; onNext: () => void }) {
  return (
    <QuestionShell step={step} of={4} title={title} onBack={handlers.onBack} onNext={handlers.onNext}>
      <label htmlFor="iets">Iets</label>
      <input id="iets" type="text" />
    </QuestionShell>
  );
}

describe("the question shell", () => {
  it("shows the question as a heading with the progress above it", () => {
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(2, "Hoeveel stroom gebruikt u?", handlers));
    expect(screen.getByRole("heading", { name: "Hoeveel stroom gebruikt u?" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
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
