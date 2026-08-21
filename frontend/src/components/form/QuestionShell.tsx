"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { Progress } from "./Progress";

const HEADING_ID = "vraag-titel";

interface Props {
  readonly step: number;
  readonly of: number;
  readonly title: string;
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
 * Two things here are for the keyboard and not for the mouse. Focus moves to
 * the heading when the step changes, because otherwise focus stays on the Next
 * button that is now labelled the same and pointing at a different question,
 * and nothing announces that the screen changed. And Enter inside a field does
 * not advance: a form with a single input submits implicitly, so the visitor
 * who presses Enter to confirm what they typed would skip ahead with a value
 * they had not finished checking.
 */
export function QuestionShell({
  step,
  of,
  title,
  nextLabel = "Volgende",
  busy = false,
  onBack,
  onNext,
  children,
}: Props) {
  const heading = useRef<HTMLHeadingElement>(null);
  const mounted = useRef(false);

  useEffect(() => {
    // Not on the first render: moving focus on arrival would take it away from
    // wherever the visitor actually was, which is a different bug than the one
    // this fixes.
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    heading.current?.focus();
  }, [step]);

  return (
    <section aria-labelledby={HEADING_ID} className="flex flex-col gap-6">
      <Progress step={step} of={of} />
      <h2 id={HEADING_ID} ref={heading} tabIndex={-1} className="text-2xl">
        {title}
      </h2>
      <form
        noValidate
        onSubmit={(event) => event.preventDefault()}
        className="flex flex-col gap-6"
      >
        {children}
        <div className="flex gap-3">
          <button type="button" disabled={busy} onClick={onBack}>
            Terug
          </button>
          <button
            type="button"
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
