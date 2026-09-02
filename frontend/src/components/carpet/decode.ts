/**
 * The wire format of a year, read back out.
 *
 * `backend/advice/series.py` holds the other half of this and says why the
 * packing looks the way it does. The short version: two base64 strings of one
 * byte per quarter, `own` for what the household used of its own production and
 * `meter` for the one flow that crossed the meter, because a quarter is a
 * surplus or a shortfall and never both. The Python side asserts that rather
 * than assuming it, over a full year, and got zero quarters holding both.
 *
 * THE ONE MISTAKE THIS FILE EXISTS TO NOT MAKE. The meter byte is not a
 * magnitude. Its high bit is the direction and only the low SEVEN bits are the
 * number, so the divisor is 127. Read as a whole byte over 255 the code still
 * runs, still produces a plausible plate, and is wrong in both directions at
 * once: every offtake quarter halves and every export quarter gains the flag as
 * magnitude. Measured from Python on 2026-08-27 on the reference household,
 * that reading gives 1132,3 kWh of offtake against 2273,8 and 4007,8 of export
 * against 2447,8. Nothing about the picture would look broken.
 * `tests/carpet/decode.test.ts` is written against that specific misreading.
 *
 * Nothing here touches the DOM and nothing here formats anything for a reader.
 * The component is a separate file for that reason: a decode that needs a
 * browser is a decode that gets checked in a browser, which is where the
 * checking stops happening.
 */

import type { YearCeilings, YearSeries } from "@/lib/types";

/** 24 hours of quarters. The grid this whole product runs on. */
export const QUARTERS_PER_DAY = 96;

/** The high bit of the meter byte. Set means the quarter exported. */
export const EXPORT_FLAG = 0x80;

/** The seven bits under it, which is the magnitude either direction gets. */
export const MAGNITUDE_MASK = 0x7f;

/** The own-use byte spends all eight bits: it has no direction to carry. */
export const OWN_FULL_SCALE = 0xff;

export interface DecodedYear {
  readonly days: number;
  readonly quartersPerDay: number;
  readonly own: Uint8Array;
  readonly meter: Uint8Array;
  readonly ceilings: YearCeilings;
}

/** One quarter of an hour, in kWh, with which side of the meter it was on. */
export interface Cell {
  readonly day: number;
  readonly quarter: number;
  readonly exported: boolean;
  readonly ownKwh: number;
  readonly meterKwh: number;
}

/**
 * One byte, or zero when the index is off the end.
 *
 * A single place where an out of range read is answered, so there is one
 * branch to test rather than one per call site. `noUncheckedIndexedAccess` is
 * on in this project, which makes every `bytes[i]` a `number | undefined`, and
 * an unreachable `?? 0` in a loop body is a branch no test can ever cover.
 */
export function byteAt(bytes: Uint8Array, index: number): number {
  return bytes[index] ?? 0;
}

/** base64 to bytes, or null when the string is not base64. */
function bytesFrom(base64: string): Uint8Array | null {
  try {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let at = 0; at < binary.length; at += 1) {
      bytes[at] = binary.charCodeAt(at);
    }
    return bytes;
  } catch {
    // Not a decode this browser could make sense of. The caller draws nothing,
    // which is the honest answer: a plate built from half a payload is a
    // picture of a year that did not happen.
    return null;
  }
}

/**
 * The payload, unpacked, or null when it does not describe a year.
 *
 * Every refusal here is a payload that cannot be drawn truthfully rather than a
 * payload that is merely unusual. A length that disagrees with `quarters` is
 * the one that matters: base64 decodes happily to the wrong number of bytes,
 * and the plate would then be a year silently shifted by however many quarters
 * went missing, which reads as a household that gets up earlier as the year
 * goes on.
 */
export function decodeYear(year: YearSeries): DecodedYear | null {
  if (year.quarters <= 0 || year.quarters % QUARTERS_PER_DAY !== 0) return null;
  const own = bytesFrom(year.own);
  const meter = bytesFrom(year.meter);
  if (own === null || meter === null) return null;
  if (own.length !== year.quarters || meter.length !== year.quarters) {
    return null;
  }
  return {
    days: year.quarters / QUARTERS_PER_DAY,
    quartersPerDay: QUARTERS_PER_DAY,
    own,
    meter,
    ceilings: year.ceilings,
  };
}

/**
 * One quarter read back in kWh, or null when that quarter is not in the year.
 *
 * The two ceilings are not interchangeable and the direction decides which one
 * applies: export peaks around three times higher than offtake on the same
 * household, which is the whole reason they travel separately.
 */
export function cellAt(
  year: DecodedYear,
  day: number,
  quarter: number,
): Cell | null {
  if (day < 0 || day >= year.days) return null;
  if (quarter < 0 || quarter >= year.quartersPerDay) return null;
  const index = day * year.quartersPerDay + quarter;
  const meter = byteAt(year.meter, index);
  const exported = (meter & EXPORT_FLAG) !== 0;
  const magnitude = (meter & MAGNITUDE_MASK) / MAGNITUDE_MASK;
  return {
    day,
    quarter,
    exported,
    ownKwh: (byteAt(year.own, index) / OWN_FULL_SCALE) * year.ceilings.own,
    meterKwh:
      magnitude * (exported ? year.ceilings.export : year.ceilings.grid),
  };
}
