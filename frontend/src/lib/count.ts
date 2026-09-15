/**
 * Aggregate counters, and the reason this is nine lines rather than a library.
 *
 * Phase 0 of this product exists, in CLAUDE.md's own words, to validate whether
 * the question exists at all, and until 2026-09-02 nothing measured that. What
 * is worth knowing is small and specific: how many people finish the four
 * questions, and where the ones who do not stop. Per-question abandonment is
 * the number that says whether the form is the problem, and no other instrument
 * can see it, because the four questions are one URL.
 *
 * WHY NOT A PRODUCT. The site's CSP is `connect-src 'self'`, so anything that
 * beacons elsewhere is blocked, which is the constraint doing its job. A hosted
 * analytics product would mean a proxy, a second store and a consent question;
 * this needs none of the three, because the thing it sends is not about the
 * visitor. Since 2026-09-15 Google Analytics sits beside it, behind exactly
 * that consent question (_shell/analytics.ts); this counter stays, because it
 * counts the visitors who said no as well, which is most of what it is for. `POST {"name": "funnel_question_2"}` carries no identifier, no
 * session and nothing derived from either, and the server adds one to a row
 * that is a date, a name and an integer. Two visitors doing the same thing on
 * the same day are the same increment, so there is nothing here to correlate.
 *
 * WHAT IT DELIBERATELY DOES NOT DO. It never blocks, never retries, never
 * reports, and never lets a failure reach the visitor. A counter that can break
 * the form it measures is worse than no counter, so every failure path here
 * ends in silence. It also sends no outcome: the distribution of verdicts is
 * written by the server from what it decided, because a number a caller can
 * move is not evidence of anything.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * The names the API accepts. Kept in step with `DailyCounter.CLIENT_NAMES` in
 * `backend/advice/models.py`, which refuses anything else with a 400 rather
 * than counting it into a name nobody reads, so a drift here shows up as a
 * refused request and not as a silently missing number.
 */
export type CountName =
  | "funnel_started"
  | "funnel_question_1"
  | "funnel_question_2"
  | "funnel_question_3"
  | "funnel_question_4"
  | "funnel_submitted"
  | "funnel_refine_started"
  | "funnel_refine_submitted";

export function count(name: CountName): void {
  // `keepalive` so the last event of a visit still leaves a page that is being
  // closed, which is exactly the event that says somebody abandoned.
  void fetch(`${BASE}/api/advice/count/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
    keepalive: true,
  }).catch(() => {
    // Silence on purpose. See the note at the top of this file: a counter that
    // can break the form it measures is worse than no counter.
  });
}
