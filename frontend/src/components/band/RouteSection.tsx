import type { RouteBlock } from "@/lib/types";
import { RuleCard } from "./RuleCard";
import styles from "./band.module.css";

interface Props {
  readonly route: RouteBlock;
}

/**
 * One of the three routes, always rendered.
 *
 * A route the model found nothing in shows that it found nothing, rather than
 * disappearing. An empty section is itself an answer, and hiding it would also
 * make the frontend responsible for an order the API already guarantees.
 * `route.title` is the API's heading; this component never writes one.
 */
export function RouteSection({ route }: Props) {
  const headingId = `route-${route.route.toLowerCase()}`;

  return (
    <section className={styles.route} data-route={route.route} aria-labelledby={headingId}>
      <h2 id={headingId} className={styles.routeTitle}>
        {route.title}
      </h2>
      {route.rules.length === 0 ? (
        <p className={styles.empty}>Hier is niets meer te halen.</p>
      ) : (
        <ul className={styles.rules}>
          {route.rules.map((rule) => (
            <li key={rule.rule_id}>
              <RuleCard rule={rule} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
