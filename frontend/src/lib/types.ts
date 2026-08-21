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
  | "CHOSEN_FROM_SIMULATED_CAPACITIES"
  | "LIMITED_BY_LARGEST_SIMULATED_CAPACITY";

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

export interface Advice {
  readonly token: string;
  readonly confidence: "INDICATIVE" | "GOOD" | "PRECISE";
  readonly confidence_label: string;
  readonly headline: PercentileBand;
  readonly routes: readonly RouteBlock[];
  readonly battery: BatteryAdvice | null;
  readonly engine_version: string;
  readonly advice_version: string;
  readonly production_source: string;
  readonly profile_year: number;
  readonly weather_year: number;
}

/** The order the reader sees. Free routes first, whatever they are worth. */
export const ROUTE_ORDER = ["SHIFT_BEHAVIOUR", "SMART_CONTROL", "STORAGE"] as const;
