/**
 * The advice API's response, in one place.
 *
 * Four lanes read this file and none of them may edit it. It is the seam
 * between two codebases that share a JSON shape, which is the classic way a
 * frontend ends up quietly showing something the backend did not mean.
 * tests/test_frontend_contract.py compares it against what the API actually
 * returns, from the Python side, where the response is produced.
 *
 * Every euro amount is a string. JSON has floats and no decimals, so an amount
 * that passes through a JSON number is rounded by whichever parser touches it
 * last. Do not parseFloat one of these to display it.
 */

/** A real percentile band over the full factorial sensitivity grid. */
export interface PercentileBand {
  readonly p10: string;
  readonly p50: string;
  readonly p90: string;
  readonly runs: number;
}

/**
 * The same simulated year re-priced at three tariff levels. Narrower than a
 * PercentileBand and it says so itself: `varied` names what moved and `pinned`
 * names what was held. It must never be drawn as if it were the headline band.
 */
export interface ScenarioBand {
  readonly low: string;
  readonly mid: string;
  readonly high: string;
  readonly varied: readonly string[];
  readonly pinned: readonly string[];
  /**
   * The same two lists in Dutch, already translated.
   *
   * `varied` and `pinned` are English identifiers from the simulation core and
   * a reader was being shown "supply_price" verbatim. Translating them here
   * would put a second copy of the model's vocabulary in this codebase, and it
   * would drift the first time an assumption is added. So the names live in
   * ampeer_advice/nl.py beside the advice text and arrive translated. Render
   * these; the identifiers above are for a machine.
   */
  readonly varied_text: readonly string[];
  readonly pinned_text: readonly string[];
  readonly combinations: number;
}

/**
 * Why a figure carries no band. The two values are the whole set: the renderer
 * picks between exactly these, so a comparison against a third is a typo the
 * compiler can catch rather than a branch that never runs.
 */
export type SizingBasis =
  "CHOSEN_FROM_SIMULATED_CAPACITIES" | "LIMITED_BY_LARGEST_SIMULATED_CAPACITY";

/**
 * A figure the model deliberately does not put a margin around, carrying the
 * sentence that says why. Render `basis_text`; never invent a margin.
 */
export interface BandlessFigure {
  readonly value: number;
  readonly band: null;
  readonly basis: SizingBasis;
  readonly basis_text: string;
}

export interface FiredRule {
  readonly rule_id: string;
  readonly text: string;
  readonly saving_eur: ScenarioBand | null;
}

export interface RouteBlock {
  readonly route: "SHIFT_BEHAVIOUR" | "SMART_CONTROL" | "STORAGE";
  readonly title: string;
  readonly rules: readonly FiredRule[];
}

export interface BatteryAdvice {
  /**
   * The storage rule id the advice landed on, read back from the fired rules
   * rather than decided again here. A rule id and not a sentence: the Dutch
   * beside it travels in the matching entry of `routes`.
   */
  readonly verdict: string;
  readonly sized_capacity_kwh: BandlessFigure;
  readonly annual_saving_eur: ScenarioBand;
  readonly payback_years: ScenarioBand;
  readonly break_even_cost_per_kwh: ScenarioBand;
  /** (capacity_kwh, saving) pairs. The capacity is a coordinate, not a figure. */
  readonly curve: readonly (readonly [number, ScenarioBand])[];
}

/**
 * The largest quarter of each series, in kWh. Every byte on the wire is a
 * fraction of one of these, so nothing can be read back out without them.
 *
 * Three ceilings and not one. Export peaks around three times higher than
 * offtake on the same household, so a shared ceiling would spend the meter
 * byte's seven bits on export and leave offtake a third of the resolution it
 * can have for free. They are maxima rather than percentiles, deliberately:
 * see `backend/advice/series.py`, which says why the clipping belongs to
 * whoever draws the picture and not to whoever packs it.
 */
export interface YearCeilings {
  readonly own: number;
  readonly export: number;
  readonly grid: number;
}

/**
 * One household's year of quarter-hour flows, packed.
 *
 * Two base64 strings of one byte per quarter. `own` is what the household used
 * of its own production, scaled against `ceilings.own` over the full 255.
 *
 * `meter` is one byte for both directions, because a quarter is a surplus or a
 * shortfall and never both: bit 0x80 set means the quarter EXPORTED, clear
 * means it took from the grid, and the low SEVEN bits are the magnitude
 * against that direction's ceiling, so the divisor is 127 and not 255.
 *
 * That divisor is the trap in this format and it fails silently. Reading the
 * meter byte whole over 255, which is what a reader ported from a three-array
 * prototype writes, halves every offtake quarter and turns the direction flag
 * into magnitude, so export inflates and offtake collapses and the picture
 * still looks like a picture. Measured from Python on 2026-08-27 on the
 * reference household: offtake 1132,3 kWh against 2273,8 and export 4007,8
 * against 2447,8. `tests/carpet/decode.test.ts` is written against exactly
 * that mistake.
 *
 * `provenance` is SYNTHETIC for a series modelled from a national profile and
 * what the visitor typed, and MEASURED for one off their own meter. Nothing
 * produces a measured series today and the API refuses to serve one over a
 * shareable link, which is why the frontend renders neither word: there is no
 * `provenance_text` beside it, and translating a model's enum in the browser
 * is the second copy of the model's vocabulary this file exists to prevent.
 */
export interface YearSeries {
  readonly own: string;
  readonly meter: string;
  readonly ceilings: YearCeilings;
  readonly provenance: "SYNTHETIC" | "MEASURED";
  readonly quarters: number;
}

export interface Advice {
  readonly token: string;
  readonly confidence: "INDICATIVE" | "GOOD" | "PRECISE";
  readonly confidence_label: string;
  /** Where the annual consumption came from. A household that accepted a
   *  figure read off its own meter and one that answered nine questions
   *  both read GOOD, and the confidence word alone cannot tell them apart. */
  readonly consumption_source: "TYPED" | "MEASURED";
  readonly headline: PercentileBand;
  readonly routes: readonly RouteBlock[];
  readonly battery: BatteryAdvice | null;
  readonly engine_version: string;
  readonly advice_version: string;
  readonly production_source: string;
  /**
   * The same fact in Dutch. `production_source` is an enum name for a
   * machine; a reader told "FALLBACK" learns nothing, while one told the
   * sun figures came from an offline table rather than a live query knows
   * how much weight to give the answer. Render this one.
   */
  readonly production_source_text: string;
  /**
   * The consumption the model used, in kWh, and why it carries no band.
   *
   * A `BandlessFigure` because it is an echo of an input rather than an
   * estimate of anything: it is what the visitor entered, plus whatever the
   * car and the heat pump added on top. `basis` distinguishes those two cases
   * and `basis_text` is the sentence that goes with it.
   *
   * On the page so that a visitor who answered the consumption question with
   * the total off their annual bill can see it. That question asks for
   * consumption WITHOUT those assets, and somebody who reads past it is
   * otherwise indistinguishable from somebody who answered correctly. See
   * decision 26.
   *
   * Optional on the wire, like `year`: an older API does not send it, and a
   * build talking to one renders the page it rendered before the field
   * existed.
   */
  readonly modelled_consumption_kwh?: BandlessFigure;
  readonly profile_year: number;
  readonly weather_year: number;
  /**
   * The year, when the API sent one. Optional on purpose and optional forever:
   * an advice is a complete answer without it, and a browser that cannot draw
   * it must show the same page rather than a hole where a picture was. The
   * advice page renders the plate only when this is present, and
   * `e2e/carpet.spec.ts` pins that an advice without it lays out exactly as it
   * did before this field existed.
   */
  readonly year?: YearSeries;
}

/** The order the reader sees. Free routes first, whatever they are worth. */
export const ROUTE_ORDER = [
  "SHIFT_BEHAVIOUR",
  "SMART_CONTROL",
  "STORAGE",
] as const;
