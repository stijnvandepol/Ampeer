"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useReducedMotion } from "@/design/motion";
import { Progress } from "./Progress";

/**
 * The id the question heading carries, so a control can borrow it as its name.
 *
 * Exported since 2026-09-02, when every question on this route was being asked
 * twice in two different wordings: the h2 said "Is er overdag meestal iemand
 * thuis?" and the legend under it said "Is er op een doordeweekse dag meestal
 * iemand thuis?", and the qualifier that decides the answer was only in the
 * second. A screen reader read both. The fix is that there is now one string:
 * the heading is the question, and the control on the screen is named by this
 * id rather than by a paraphrase of it. That is the one-question-per-page
 * pattern the GOV.UK Design System spells out, where the legend is the heading.
 */
export const HEADING_ID = "vraag-titel";

/**
 * The id the note carries, so a field can point at it.
 *
 * The consumption question's note is the case this exists for: it is the
 * sentence that stops a visitor entering their annual bill total instead of
 * their base consumption, worth 176 to 184 euro of accuracy, and until
 * 2026-09-01 nothing referenced it. Somebody tabbing straight into the field
 * heard the label and the unit and never the warning.
 */
export const NOTE_ID = "vraag-toelichting";

interface Props {
  readonly step: number;
  readonly of: number;
  readonly title: string;
  /**
   * What the question means, when the title alone can be read two ways.
   *
   * Under the heading and above the field, because the one question this
   * exists for is the one a visitor answers wrongly by skimming. It is
   * described by the section, so a screen reader reaching the heading gets it
   * before the field rather than after.
   */
  // `| undefined` spelled out because exactOptionalPropertyTypes is on: the
  // caller passes undefined for the questions that have no note, and without
  // this that is a type error rather than an absent prop.
  readonly note?: string | undefined;
  /**
   * What the forward button says. "Volgende" on every question but the last
   * one, where the button no longer leads to a question and saying so is the
   * difference between a form and a trap.
   */
  readonly nextLabel?: string;
  /**
   * True while the answer is being computed, which is a request that has left
   * and not come back.
   *
   * Both buttons go dead for the length of it, and the forward one says so
   * with aria-busy. A live compute button during those seconds is four full
   * server-side simulations for four impatient clicks, a fifth of a
   * household's twenty an hour, and there is no retry anywhere in this
   * codebase to undo them. A live Terug is worse in a quieter way: it walks
   * back to the previous question and the navigation that is already under way
   * then pulls the page out from under the visitor.
   */
  readonly busy?: boolean;
  readonly onBack: () => void;
  readonly onNext: () => void;
  readonly children: ReactNode;
}

/**
 * One question on the screen, with the progress above it.
 *
 * Three things here are for the keyboard and not for the mouse. Focus moves to
 * the heading when the step changes, because otherwise focus stays on the Next
 * button that is now labelled the same and pointing at a different question,
 * and nothing announces that the screen changed. The section is also put at
 * the top of the viewport on every step, deliberately, and not left to
 * whatever `.focus()` alone would do. And Enter inside a field advances, which
 * is what a one-question-per-screen form has to do: see the note on the form
 * element for why it used to do nothing instead.
 *
 * WHY FOCUS ALONE IS NOT ENOUGH. `.focus()` with no options asks the browser
 * to scroll only if the target is not already "sufficiently visible", by its
 * own nearest-edge heuristic, using whatever scroll position the PREVIOUS
 * question left behind. Measured at 390x844 on 2026-09-02: reaching question 2
 * from question 1 left the field's own bottom edge 14px past the bottom of the
 * viewport, not because question 2 is long, but because question 1 was short
 * enough that the browser decided no scroll was needed at all. The outcome for
 * any one question therefore depended on the question answered before it,
 * which made this an intermittent fault across the whole flow rather than a
 * defect confined to one screen.
 *
 * The fix replaces a heuristic with a destination: focus moves with
 * `preventScroll` so the browser's own guess never fires, and the section is
 * then scrolled to `block: "start"` in the same effect, every time, regardless
 * of where the visitor arrived from. The section and not the heading, so the
 * progress indicator above the heading lands on screen together with the
 * question rather than being scrolled past it.
 */
export function QuestionShell({
  step,
  of,
  title,
  note,
  nextLabel = "Volgende",
  busy = false,
  onBack,
  onNext,
  children,
}: Props) {
  const section = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const mounted = useRef(false);
  const reducedMotion = useReducedMotion();
  // Read inside the effect instead of listed as a dependency: the OS-level
  // setting this tracks can change mid-form (Focus mode, a Control Centre
  // toggle) without the step changing, and a visitor mid-keystroke in a field
  // should never have focus and scroll pulled away from them by a setting
  // that has nothing to do with which question is on screen. Kept current by
  // its own effect rather than written during render, which React refuses:
  // a ref is a value for event handlers and effects, not for the render
  // that computes what to show.
  const reducedMotionRef = useRef(reducedMotion);
  useEffect(() => {
    reducedMotionRef.current = reducedMotion;
  }, [reducedMotion]);

  useEffect(() => {
    // Not on the first render: moving focus and scroll on arrival would take
    // both away from wherever the visitor actually was, which is a different
    // bug than the one this fixes.
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    heading.current?.focus({ preventScroll: true });
    section.current?.scrollIntoView({
      block: "start",
      behavior: reducedMotionRef.current ? "instant" : "smooth",
    });
  }, [step]);

  return (
    <section
      ref={section}
      aria-labelledby={HEADING_ID}
      className="flex flex-col gap-6"
    >
      <Progress step={step} of={of} />
      <h2 id={HEADING_ID} ref={heading} tabIndex={-1} className="text-2xl">
        {title}
      </h2>
      {note !== undefined && (
        <p id={NOTE_ID} className="max-w-[60ch] text-sm text-ink-muted">
          {note}
        </p>
      )}
      {/*
        Enter in a field goes forward.

        It used to do nothing at all: onSubmit called preventDefault and both
        buttons were type="button", so the one gesture that means "I am done
        with this field" on a one-question-per-screen form was a silent no-op,
        which teaches a visitor the page is broken. The comment that stood here
        argued Enter would let somebody skip ahead with a value they had not
        finished checking; that costs one press of Terug, and the value is kept,
        while a key that does nothing costs the visitor their confidence in the
        form.

        `onNext` is the same handler the button uses, and the flow above already
        refuses an incomplete question and says so, so nothing new can slip
        through here.
      */}
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) onNext();
        }}
        className="flex flex-col gap-6"
      >
        {children}
        {/*
          Two real buttons, and the forward one is the loud one.

          They were unstyled until 2026-08-31: the default control of whatever
          browser the visitor happened to have, side by side, on the only screen
          in this product where somebody has to press something to continue.
          Both looked identical, so nothing on the screen said which one went
          forwards, and neither looked disabled while a computation was running.

          Back on the left and forward on the right, which is the order they are
          read in, the order they are tabbed in and the order they sit in the
          source. One order for all three is worth more here than any
          arrangement that has to be explained.
        */}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="button-quiet"
            disabled={busy}
            onClick={onBack}
          >
            Terug
          </button>
          <button
            type="button"
            className="button-accent"
            disabled={busy}
            aria-busy={busy}
            onClick={onNext}
          >
            {nextLabel}
          </button>
        </div>
      </form>
    </section>
  );
}
