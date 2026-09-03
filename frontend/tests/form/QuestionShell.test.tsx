import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionShell } from "@/components/form/QuestionShell";
import { installMatchMedia } from "../matchMedia";

// Every scroll/focus test below spies on a prototype method shared by the
// whole test run. Restoring it here, rather than trusting each test to clean
// up after itself, is what keeps one test's spy from silently carrying its
// call count into the next.
afterEach(() => {
  vi.restoreAllMocks();
});

function shell(
  step: number,
  title: string,
  handlers: { onBack: () => void; onNext: () => void },
  busy = false,
) {
  return (
    <QuestionShell
      step={step}
      of={4}
      title={title}
      busy={busy}
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

  it("scrolls its own section to the top of the viewport on every step, not wherever .focus() alone would leave it", () => {
    // `.focus()` with no options scrolls only when the browser's own
    // nearest-edge heuristic decides the target is not "sufficiently
    // visible", judged against whatever scroll position the previous
    // question left behind. Measured at 390x844 on 2026-09-02: question 2
    // arrived with its own field 14px past the bottom of the viewport,
    // because question 1 was short enough that the heuristic saw no need to
    // scroll at all. This is the deterministic replacement: a real
    // scrollIntoView call, on the section rather than the heading so the
    // progress indicator above the heading arrives with the question, made on
    // every step change regardless of where the previous one left the page.
    const scrolled = vi.spyOn(Element.prototype, "scrollIntoView");
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    const { rerender, container } = render(shell(1, "Een", handlers));
    expect(scrolled).not.toHaveBeenCalled();
    rerender(shell(2, "Twee", handlers));
    const section = container.querySelector("section");
    expect(scrolled).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ block: "start" }),
    );
    // On the section, and not on the heading: scrolling the heading itself to
    // the very top of the viewport would push the progress bar above it out
    // of view, which is the one thing this fix is not supposed to do.
    expect(scrolled.mock.instances[0]).toBe(section);
  });

  it("does not fight its own focus call with the browser's default scroll", () => {
    // Two competing scroll instructions on one step change, one implicit
    // (the browser's own reaction to an unqualified .focus()) and one
    // explicit (the scrollIntoView above), is not "belt and suspenders": it
    // is a race, and whichever one runs second wins with no guarantee it is
    // the deterministic one. `preventScroll` is what removes the implicit
    // instruction rather than merely outrunning it.
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    const { rerender } = render(shell(1, "Een", handlers));
    const focused = vi.spyOn(HTMLElement.prototype, "focus");
    rerender(shell(2, "Twee", handlers));
    expect(focused).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ preventScroll: true }),
    );
  });

  it("scrolls without animation for a visitor who asked for less motion", () => {
    installMatchMedia(true);
    const scrolled = vi.spyOn(Element.prototype, "scrollIntoView");
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    const { rerender } = render(shell(1, "Een", handlers));
    rerender(shell(2, "Twee", handlers));
    expect(scrolled).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ behavior: "instant" }),
    );
    installMatchMedia(false);
  });

  it("advances when Enter is pressed in a field", async () => {
    /*
     * Reversed on 2026-09-01. It used to refuse, on the argument that somebody
     * pressing Enter to confirm what they typed would skip ahead with a value
     * they had not finished checking. What it actually produced was a key that
     * did NOTHING: no advance, no message, no focus change. On a form with one
     * question per screen, Enter is the gesture that means "I am done here",
     * and a silent no-op teaches a visitor the page is broken. The stated risk
     * costs one press of Terug and the value is kept.
     *
     * It goes through the same handler as the button, and the flow above
     * refuses an incomplete question and says so, so nothing new slips past.
     */
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(1, "Een", handlers));
    await userEvent.type(screen.getByLabelText("Iets"), "3500{Enter}");
    expect(handlers.onNext).toHaveBeenCalledTimes(1);
  });

  it("does not advance on Enter while the answer is being computed", async () => {
    // The button goes dead for the length of the request and Enter has to go
    // dead with it, or the one path that was guarded is reopened by a key.
    const handlers = { onBack: vi.fn(), onNext: vi.fn() };
    render(shell(1, "Een", handlers, true));
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
