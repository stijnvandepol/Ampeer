/**
 * Where the visitor is in the flow, in words as well as in pixels.
 *
 * A bar alone says "somewhere", which is what a bar says to anybody who cannot
 * see it and roughly what it says to anybody who can. The sentence next to it
 * is the part that answers the question.
 */

/**
 * Round one asks four questions and collects five values, because orientation
 * and tilt are one question about one roof.
 *
 * This number is not a styling choice. `EstimateInputSerializer.QUESTION_COUNT`
 * in backend/advice/serializers.py is 4 for the same reason, and that count is
 * what decides the confidence label the advice carries. Counting the values
 * instead of the questions would push every round-one estimate past the GOOD
 * threshold in the API while nothing anywhere reported a problem, so the two
 * sides of the wire have to agree on the same four.
 */
export const ROUND_ONE_QUESTION_COUNT = 4;

/** Round two adds five, which is why the serializer's total is nine. */
export const ROUND_TWO_QUESTION_COUNT = 5;

/** What `RefineInputSerializer.QUESTION_COUNT` is on the other side. */
export const ALL_QUESTION_COUNT =
  ROUND_ONE_QUESTION_COUNT + ROUND_TWO_QUESTION_COUNT;

interface Props {
  readonly step: number;
  readonly of: number;
}

export function Progress({ step, of }: Props) {
  const total = Math.max(1, Math.round(of));
  const current = Math.min(total, Math.max(1, Math.round(step)));
  const text = `Vraag ${current} van ${total}`;
  const filled = Math.round((current / total) * 100);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm">{text}</p>
      <div
        role="progressbar"
        aria-label="Voortgang"
        aria-valuenow={current}
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuetext={text}
        className="h-1.5 w-full overflow-hidden rounded-full bg-current/15"
      >
        <div
          className="h-full rounded-full bg-current/60"
          style={{ width: `${filled}%` }}
        />
      </div>
    </div>
  );
}
