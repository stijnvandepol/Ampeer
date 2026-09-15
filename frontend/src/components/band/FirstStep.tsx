import type { RouteBlock } from "@/lib/types";
import { ScenarioBandFigure } from "./ScenarioBandFigure";
import styles from "./band.module.css";

interface Props {
  readonly routes: readonly RouteBlock[];
}

/** What this block calls itself. Interface text; the advice is the API's. */
const EYEBROW = "Begin hier";

/**
 * The one thing to do first, lifted to the top of the page.
 *
 * WHY IT EXISTS. The advice page opened on a euro band, which is an honest
 * picture of what the end of netting costs and not an answer to the question
 * somebody arrived with. The answer was always on the page, three screens
 * down, inside the first route. A visitor who does not scroll reads a number
 * and leaves knowing what it costs and not what to do about it.
 *
 * IT WRITES NOTHING. `rule.action` is the API's own one line version of the
 * same advice, from ampeer_advice/nl.py beside the paragraph it shortens. That
 * is the language boundary, and it is also why the two cannot drift: both live
 * in one file, next to each other, under a test that holds them together.
 *
 * THE PARAGRAPH IS NOT REPEATED HERE. `rule.text` says what to do, why it is
 * worth doing and what it costs, and it earns its length; on a phone it is
 * seven lines. A household that opened the page to find out what to do should
 * not read seven lines to find out. It is directly below, in the route it
 * belongs to, where it always was.
 *
 * WHICH RULE. The first rule of the first route that has one, which is the
 * API's own order: `CLAUDE.md` requires the free routes before storage, and
 * the serializer emits them that way. So this is always the cheapest thing the
 * model found, never the most profitable, and if the model found nothing free
 * it says whatever the model did find.
 *
 * NOTHING WHEN THERE IS NOTHING. A household the model has no action for gets
 * no block rather than an encouraging placeholder, and the three route
 * sections below still render and still say where nothing is to be had.
 */
export function firstActionableRule(routes: readonly RouteBlock[]) {
  return routes.find((candidate) => candidate.rules.length > 0)?.rules[0];
}

export function FirstStep({ routes }: Props) {
  const rule = firstActionableRule(routes);
  if (rule === undefined) return null;

  return (
    <section
      className={styles.firstStep}
      // A name of its own, not `data-rule-id`. That attribute is how
      // e2e/happy-path.spec.ts finds each fired rule exactly once, and a second
      // element carrying the same id turned that assertion into a strict mode
      // violation rather than the check it was written to be.
      data-first-step-rule-id={rule.rule_id}
      aria-labelledby="eerste-stap"
    >
      <p id="eerste-stap" className={styles.firstStepEyebrow}>
        {EYEBROW}
      </p>
      <p className={styles.firstStepText}>{rule.action}</p>
      {rule.saving_eur === null ? null : (
        <ScenarioBandFigure band={rule.saving_eur} unit="eur" />
      )}
    </section>
  );
}
