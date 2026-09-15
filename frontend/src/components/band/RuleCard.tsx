import type { FiredRule } from "@/lib/types";
import { ScenarioBandFigure } from "./ScenarioBandFigure";
import styles from "./band.module.css";

interface Props {
  readonly rule: FiredRule;
  /** True when the first step block above already drew this rule's band. */
  readonly hideBand?: boolean | undefined;
}

/**
 * One fired rule, with its band beside it when it has one.
 *
 * `rule.text` is the API's sentence and is rendered as it arrived. A rule whose
 * `saving_eur` is null gets no figure at all, not a dash and not a zero: the
 * model put no number on it, and a placeholder would be a number nobody
 * computed. `rule_id` rides along on the element so the advice stays traceable
 * back to the rule that produced it.
 */
export function RuleCard({ rule, hideBand = false }: Props) {
  return (
    <article className={styles.rule} data-rule-id={rule.rule_id}>
      <p className={styles.ruleText}>{rule.text}</p>
      {rule.saving_eur === null || hideBand ? null : (
        <ScenarioBandFigure band={rule.saving_eur} unit="eur" />
      )}
    </article>
  );
}
