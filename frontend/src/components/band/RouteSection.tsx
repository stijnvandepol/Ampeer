import type { RouteBlock } from "@/lib/types";
import { RuleCard } from "./RuleCard";
import styles from "./band.module.css";

interface Props {
  readonly route: RouteBlock;
  /**
   * The rule whose band is already drawn at the top of the page, so this
   * section renders its reasoning without repeating the figure.
   *
   * Two identical bands, one under the other, was what the page did until
   * 2026-09-15: the same three amounts twice within one screen. The figure
   * belongs with the instruction a reader acts on; the paragraph here is the
   * why, and it does not need the number again to make its point.
   */
  readonly bandShownAbove?: string | undefined;
}

/**
 * One of the three routes, always rendered.
 *
 * A route the model found nothing in shows that it found nothing, rather than
 * disappearing. An empty section is itself an answer, and hiding it would also
 * make the frontend responsible for an order the API already guarantees.
 * `route.title` is the API's heading; this component never writes one.
 */
export function RouteSection({ route, bandShownAbove }: Props) {
  const headingId = `route-${route.route.toLowerCase()}`;

  return (
    <section
      className={styles.route}
      data-route={route.route}
      aria-labelledby={headingId}
    >
      <h2 id={headingId} className={styles.routeTitle}>
        {route.title}
      </h2>
      {route.rules.length === 0 ? (
        <p className={styles.empty}>
          Voor uw huishouden levert deze route niets op.
        </p>
      ) : (
        <ul className={styles.rules}>
          {route.rules.map((rule) => (
            <li key={rule.rule_id}>
              <RuleCard
                rule={rule}
                hideBand={rule.rule_id === bandShownAbove}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
