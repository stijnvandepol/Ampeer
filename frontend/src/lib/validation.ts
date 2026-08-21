/**
 * The bounds the form checks, so a visitor hears sooner.
 *
 * This file is a courtesy and not an authority. `backend/advice/serializers.py`
 * refuses out-of-range input regardless of what happens here, and it is the
 * only place where refusing means anything: it runs on values a stranger sent,
 * where this runs on values a visitor typed into our own form. The point of
 * having the numbers twice is that somebody who mistypes their wattpeak is
 * told before the round trip rather than after it.
 *
 * IF THE TWO EVER DISAGREE, THE API WINS AND THIS FILE IS THE ONE THAT IS
 * WRONG. Every entry below names the constant in `backend/advice/serializers.py`
 * it mirrors, so the next person can go and check rather than trust this
 * comment. Do not change a number here to make a form accept something the API
 * will refuse; that only moves the refusal to where it is harder to explain.
 *
 * There is deliberately no fetch of the bounds from the API. The API publishes
 * no schema endpoint today, and inventing one so a static site could ask at
 * runtime would add a request to every visit to save a comment.
 */

/** An inclusive range, matching DRF's `min_value` and `max_value`. */
export interface Bound {
  readonly min: number;
  readonly max: number;
}

export const BOUNDS: Readonly<Record<string, Bound>> = {
  // MIN_POSTCODE4 / MAX_POSTCODE4. Four digits is a shape, not a place:
  // "0123" has the shape and is not a Dutch postcode. Checked as a number
  // because that is how the serializer checks it, after POSTCODE4_PATTERN.
  postcode4: { min: 1000, max: 9999 },

  // MIN_PEAK_POWER_WP / MAX_PEAK_POWER_WP. The maximum is a safety bound and
  // not a claim about what households own; it sits under PVSystem's own
  // 50_000 Wp limit rather than restating it.
  peak_power_wp: { min: 1, max: 30_000 },

  // MIN_AZIMUTH_DEG / MAX_AZIMUTH_DEG, copied there from
  // PVSystem.__post_init__. Zero is south, negative is east, positive is
  // west, matching PVGIS and ampeer_sim.
  azimuth_deg: { min: -180, max: 180 },

  // MIN_TILT_DEG / MAX_TILT_DEG, from the same place.
  tilt_deg: { min: 0, max: 90 },

  // MIN_ANNUAL_CONSUMPTION_KWH / MAX_ANNUAL_CONSUMPTION_KWH. The floor sits
  // just above zero because Household raises on zero rather than returning a
  // wrong number, and DRF's min_value is inclusive.
  annual_consumption_kwh: { min: 1, max: 50_000 },

  // MIN_HEAT_DEMAND_KWH / MAX_HEAT_DEMAND_KWH. Round two only, and only when
  // the household says it has a heat pump.
  heat_demand_kwh: { min: 1, max: 40_000 },

  // MIN_BATTERY_CAPACITY_KWH / MAX_BATTERY_CAPACITY_KWH. Round two only, and
  // only when the household says it has a battery.
  battery_capacity_kwh: { min: 0.5, max: 100 },
};

/**
 * Four ASCII digits, mirroring POSTCODE4_PATTERN.
 *
 * `\d` in JavaScript is ASCII-only by default, unlike Python's, so this is the
 * same set. The serializer anchors with `\Z` rather than `$` because Python's
 * `$` also matches before a trailing newline; JavaScript's `$` without the `m`
 * flag does not, so `^[0-9]{4}$` is the faithful translation and not a
 * loosening. `BOUNDS.postcode4` still has to run after it: this pattern
 * accepts "0123".
 */
export const POSTCODE4_PATTERN = /^[0-9]{4}$/;
