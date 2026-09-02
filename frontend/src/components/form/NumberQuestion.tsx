"use client";

import { useState } from "react";

/** "" and "abc" are both "no number yet"; neither is a zero. */
function parse(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * The message this field would show for what is in it, or null for nothing to
 * say. An empty field says nothing: it has not been answered yet, which is the
 * flow's business rather than this component's.
 *
 * One function and not two copies, because the message on the screen and the
 * refusal reported upwards have to be the same decision. While they were two
 * pieces of arithmetic side by side, a field could show an error and report
 * upwards that it had none.
 */
function messageFor(raw: string, limits: Limits): string | null {
  if (raw.trim() === "") return null;
  const parsed = parse(raw);
  if (parsed === null) return "Vul een getal in, zonder letters of spaties.";
  if (parsed < limits.min)
    return `Vul minstens ${bound(limits.min, limits)} in.`;
  if (parsed > limits.max)
    return `Vul hoogstens ${bound(limits.max, limits)} in.`;
  if (limits.integer && !Number.isInteger(parsed)) {
    return "Vul een heel getal in, zonder cijfers achter de komma.";
  }
  return null;
}

/**
 * A bound with its unit, and without a double space when it has none.
 *
 * The postcode field passes an empty unit, so the message read
 * "Vul minstens 1000  in." with two spaces in the middle, on the first screen
 * of the flow.
 */
function bound(value: number, limits: Limits): string {
  return limits.unit === "" ? String(value) : `${value} ${limits.unit}`;
}

interface Limits {
  readonly min: number;
  readonly max: number;
  readonly unit: string;
  readonly integer: boolean;
}

interface Props {
  readonly id: string;
  readonly label: string;
  readonly value: number | null;
  /**
   * The bounds the API enforces. They are passed in rather than held here:
   * `lib/validation` fetches them, so there is one place they live and no
   * second copy to drift. They exist to tell the visitor before the round trip,
   * not to decide anything; the API refuses out-of-range input regardless.
   */
  readonly min: number;
  readonly max: number;
  readonly unit: string;
  /**
   * True when the API's field is an IntegerField rather than a FloatField.
   *
   * peak_power_wp, azimuth_deg and tilt_deg are integers in
   * backend/advice/serializers.py; annual_consumption_kwh, heat_demand_kwh and
   * battery_capacity_kwh are not. Without this the component would happily
   * report 3500.5 watt-peak and the API would answer 400 with a message the
   * visitor never asked for. The bound they broke is named here instead.
   */
  readonly integer?: boolean;
  /**
   * The autofill token for this field, where one honestly exists.
   *
   * Only the postcode has one. There is no autofill name for "watt-peak on my
   * roof", and inventing one would put a browser's saved address data into a
   * field that is not an address.
   */
  readonly autoComplete?: string | undefined;
  /**
   * Anything else already describing this field, by id.
   *
   * The consumption question's note is the case this exists for. It is the
   * sentence that stops a visitor entering their annual bill total instead of
   * their base consumption, which is worth 176 to 184 euro of accuracy, and it
   * sat in a paragraph that nothing pointed at: a screen reader user tabbing
   * into the field heard the label and the unit and never the warning.
   */
  readonly describedBy?: string | undefined;
  readonly onChange: (value: number | null) => void;
  /**
   * Told whether this field is refusing what it holds.
   *
   * `onChange(null)` means two different things: an empty field, and a field
   * holding a number this component has already told the visitor it cannot
   * use. The flow above has to tell them apart, because "Beantwoord deze vraag
   * om verder te gaan" over a question that was answered, badly, is a false
   * message printed underneath a true one.
   */
  readonly onRefusal?: (refusing: boolean) => void;
}

/**
 * One number, with the bound it broke named out loud.
 *
 * "Ongeldige waarde" tells somebody that they are wrong and not what would be
 * right, which turns a form into guessing. The message says which end of the
 * range was passed and what that end is, and the accepted range is on the
 * screen before anything is typed rather than only after it is broken.
 *
 * IT IS NOT type="number", AND THAT WAS A DEFECT RATHER THAN A PREFERENCE.
 * Measured in a browser on 2026-09-01, on the postcode field, which is the
 * first thing anybody touches:
 *
 *   typing "3811 EP", which is how a Dutch postcode is written, left the field
 *   EMPTY with aria-invalid="false" and no message. A number input reports a
 *   value it cannot parse as the empty string, so the 3811 went too, the
 *   controlled draft became "", and the "Vul een getal in" branch below could
 *   never fire for any of the five fields in this flow.
 *
 *   typing "3811" and pressing ArrowDown once gave 3810. A number input steps
 *   on the arrow keys, so a keyboard visitor scrolling the page silently
 *   edited their own postcode, and on the consumption field the same key moves
 *   a four figure number by one, which looks like nothing happened at all.
 *
 * GOV.UK says not to use type="number" unless research shows a need, for these
 * two reasons by name. `inputmode` is what actually decides the phone keyboard,
 * and it is unchanged.
 *
 * VALIDATION WAITS FOR blur. It used to run on every keystroke, so typing the
 * first digit of a postcode put "Vul minstens 1000 in." under the visitor's
 * fingers, and because the message is a live region a screen reader announced
 * it again on every character: 1, 12, 123. The NL Design System asks for blur
 * or submit; Nielsen Norman calls validating before an entry is finished a
 * hostile pattern. The value is still reported upward on every keystroke, so
 * nothing downstream waits.
 */
export function NumberQuestion({
  id,
  label,
  value,
  min,
  max,
  unit,
  integer = false,
  autoComplete,
  describedBy,
  onChange,
  onRefusal,
}: Props) {
  const [draft, setDraft] = useState<string>(() =>
    value === null ? "" : String(value),
  );
  const [seen, setSeen] = useState<number | null>(value);
  /**
   * Whether this field has been left at least once.
   *
   * The message is withheld until it has. Not the refusal: the flow is told on
   * every keystroke, so the forward button behaves the same as before and the
   * only thing that waits is the sentence a visitor reads.
   */
  const [left, setLeft] = useState(false);

  // The parent owns the value, but it may reject what was typed (by reporting
  // null for an out-of-range number), and when it does the visitor still has to
  // see the characters they entered. So the prop only overwrites the draft when
  // the prop itself changed to something the draft does not already say. This
  // is the adjust-state-during-render pattern rather than an effect: an effect
  // would render the stale field once first, which is a visible flicker in the
  // one case this exists for.
  if (value !== seen) {
    setSeen(value);
    if (value !== null && value !== parse(draft)) setDraft(String(value));
  }

  const limits: Limits = { min, max, unit, integer };
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const refusal = messageFor(draft, limits);
  const error = left ? refusal : null;

  function handleChange(raw: string) {
    setDraft(raw);
    const next = messageFor(raw, limits);
    onRefusal?.(next !== null);
    onChange(next === null ? parse(raw) : null);
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id}>{label}</label>
      <div className="flex items-baseline gap-2">
        <input
          id={id}
          /*
           * text, with inputMode deciding the phone keyboard. See the note on
           * the component: a number input eats what it cannot parse and steps
           * on the arrow keys, and both of those were measured here rather
           * than assumed.
           */
          type="text"
          inputMode={integer ? "numeric" : "decimal"}
          spellCheck={false}
          autoComplete={autoComplete ?? "off"}
          value={draft}
          aria-invalid={error !== null}
          aria-describedby={
            [hintId, describedBy, error === null ? null : errorId]
              .filter((part) => part !== null && part !== undefined)
              .join(" ") || undefined
          }
          onChange={(event) => handleChange(event.target.value)}
          onBlur={() => setLeft(true)}
        />
        {/*
          The unit and the accepted range, before anything is typed rather than
          only after it is broken. The NL Design System asks for valid values to
          be stated up front and not left in a placeholder; the bounds were
          already props here and were secret until a visitor tripped over one.
        */}
        <span id={hintId} className="text-sm text-ink-muted">
          {unit === "" ? `${min} tot ${max}` : `${unit}, ${min} tot ${max}`}
        </span>
      </div>
      {/*
        text-danger is the colour every other failure on this site is marked
        with. Without it this paragraph carried the same class as the unit
        beside the field and nothing else: an error dressed as a caption.
      */}
      {error !== null && (
        <p id={errorId} role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
