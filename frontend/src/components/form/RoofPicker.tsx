"use client";

import { useId } from "react";

/**
 * The one place a compass direction becomes an azimuth.
 *
 * Zero is south, negative is east, positive is west. That is the convention
 * PVGIS uses, the one `PVSystem.__post_init__` in `ampeer_sim` enforces, and
 * the one `backend/advice/serializers.py` repeats above MIN_AZIMUTH_DEG. A sign
 * error here does not raise anything: an east roof simulated as a west roof
 * still produces a plausible year, with its production peak on the wrong side
 * of noon and a self-consumption figure that is wrong by more than the whole
 * advice is worth. That is why the mapping is one constant with this comment on
 * it and not eight numbers spread through the markup.
 *
 * North is written as 180 and not as -180. Both name the same direction and
 * both sit inside the API's range, but one spelling keeps the value this
 * control emits equal to the value it later reads back.
 */
export const COMPASS_AZIMUTH_DEG = {
  NORTH: 180,
  NORTHEAST: -135,
  EAST: -90,
  SOUTHEAST: -45,
  SOUTH: 0,
  SOUTHWEST: 45,
  WEST: 90,
  NORTHWEST: 135,
} as const;

export type CompassDirection = keyof typeof COMPASS_AZIMUTH_DEG;

/**
 * What the visitor reads. Nobody knows their azimuth, so the question is asked
 * in the words somebody would use about their own house and converted here.
 */
const DIRECTION_LABELS: Record<CompassDirection, string> = {
  NORTH: "Noord",
  NORTHEAST: "Noordoost",
  EAST: "Oost",
  SOUTHEAST: "Zuidoost",
  SOUTH: "Zuid",
  SOUTHWEST: "Zuidwest",
  WEST: "West",
  NORTHWEST: "Noordwest",
};

/** Clockwise from north, so arrow keys walk the compass the way it is drawn. */
const DIRECTION_ORDER: readonly CompassDirection[] = [
  "NORTH",
  "NORTHEAST",
  "EAST",
  "SOUTHEAST",
  "SOUTH",
  "SOUTHWEST",
  "WEST",
  "NORTHWEST",
];

/**
 * Whole degrees, always.
 *
 * The API rounds azimuth and tilt to integers on the way in and says why: a
 * float reaches the PVGIS cache key, misses its own entry, and a later rounded
 * lookup returns a series computed for a slightly different roof than the
 * simulation then assumes. Rounding here as well means the value the visitor
 * saw, the value that was sent and the value that was cached are one number.
 */
function toWholeDegrees(value: number): number {
  return Math.round(value);
}

/** -180 and 180 are the same direction; the picker only ever emits the latter. */
function normaliseAzimuth(value: number): number {
  const whole = toWholeDegrees(value);
  return whole === -180 ? 180 : whole;
}

function selectedDirection(azimuth: number): CompassDirection | null {
  const normalised = normaliseAzimuth(azimuth);
  for (const direction of DIRECTION_ORDER) {
    if (COMPASS_AZIMUTH_DEG[direction] === normalised) return direction;
  }
  return null;
}

interface Props {
  readonly azimuth: number;
  readonly tilt: number;
  readonly onChange: (next: { azimuth: number; tilt: number }) => void;
  /**
   * The tilt bounds the API enforces, fetched once by `lib/validation` and
   * handed down. They are optional only so this control still works before that
   * fetch has returned; the fallbacks are the geometric limits of a plane, not
   * a second copy of the API's rules. If the two ever disagree, the API wins.
   */
  readonly tiltMin?: number;
  readonly tiltMax?: number;
}

/**
 * One question about one roof: which way it faces and how steep it is.
 *
 * Counting this as two questions is the mistake that would put every round-one
 * estimate one confidence level too high, so the flow counts it once. See
 * ROUND_ONE_QUESTION_COUNT in Progress.tsx.
 */
export function RoofPicker({ azimuth, tilt, onChange, tiltMin = 0, tiltMax = 90 }: Props) {
  const groupName = useId();
  const tiltId = `${useId()}-tilt`;
  const tiltValueId = `${tiltId}-value`;

  const lowest = toWholeDegrees(Math.min(tiltMin, tiltMax));
  const highest = toWholeDegrees(Math.max(tiltMin, tiltMax));
  const currentTilt = Math.min(highest, Math.max(lowest, toWholeDegrees(tilt)));
  const selected = selectedDirection(azimuth);

  function emit(next: { azimuth: number; tilt: number }) {
    onChange({
      azimuth: normaliseAzimuth(next.azimuth),
      tilt: Math.min(highest, Math.max(lowest, toWholeDegrees(next.tilt))),
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2">Welke kant ligt het dak op?</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {DIRECTION_ORDER.map((direction) => {
            const inputId = `${groupName}-${direction}`;
            return (
              <div key={direction} className="flex items-center gap-2">
                <input
                  type="radio"
                  id={inputId}
                  name={groupName}
                  value={direction}
                  checked={selected === direction}
                  onChange={() => emit({ azimuth: COMPASS_AZIMUTH_DEG[direction], tilt })}
                />
                <label htmlFor={inputId}>{DIRECTION_LABELS[direction]}</label>
              </div>
            );
          })}
        </div>
      </fieldset>

      <div className="flex flex-col gap-2">
        <label htmlFor={tiltId}>Hoe schuin staat het dak?</label>
        <input
          type="range"
          id={tiltId}
          min={lowest}
          max={highest}
          step={1}
          value={currentTilt}
          aria-describedby={tiltValueId}
          onChange={(event) => emit({ azimuth, tilt: Number(event.target.value) })}
        />
        <output id={tiltValueId} htmlFor={tiltId} className="text-sm">
          {currentTilt} graden
        </output>
      </div>
    </div>
  );
}
