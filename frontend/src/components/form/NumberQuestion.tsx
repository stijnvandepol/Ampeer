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
  if (parsed === null) return "Vul een getal in.";
  if (parsed < limits.min)
    return `Vul minstens ${limits.min} ${limits.unit} in.`;
  if (parsed > limits.max)
    return `Vul hoogstens ${limits.max} ${limits.unit} in.`;
  if (limits.integer && !Number.isInteger(parsed)) {
    return "Vul een heel getal in, zonder cijfers achter de komma.";
  }
  return null;
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
 * range was passed and what that end is.
 */
export function NumberQuestion({
  id,
  label,
  value,
  min,
  max,
  unit,
  integer = false,
  onChange,
  onRefusal,
}: Props) {
  const [draft, setDraft] = useState<string>(() =>
    value === null ? "" : String(value),
  );
  const [seen, setSeen] = useState<number | null>(value);

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
  const error = messageFor(draft, limits);

  function handleChange(raw: string) {
    setDraft(raw);
    const refusal = messageFor(raw, limits);
    onRefusal?.(refusal !== null);
    onChange(refusal === null ? parse(raw) : null);
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id}>{label}</label>
      <div className="flex items-baseline gap-2">
        <input
          id={id}
          type="number"
          inputMode={integer ? "numeric" : "decimal"}
          min={min}
          max={max}
          step={integer ? 1 : "any"}
          value={draft}
          aria-invalid={error !== null}
          aria-describedby={error === null ? hintId : `${hintId} ${errorId}`}
          onChange={(event) => handleChange(event.target.value)}
        />
        <span id={hintId} className="text-sm">
          {unit}
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
