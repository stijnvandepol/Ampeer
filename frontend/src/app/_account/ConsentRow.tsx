"use client";

import type { ConsentAction, ConsentKind } from "@/lib/accounts";

/**
 * One consent as a checkbox, for the registration form.
 *
 * No `required`, and that is a rule rather than an omission: article 7(4) says
 * a service made conditional on consent it does not need is a service whose
 * consent is not freely given. The API accepts a registration with both
 * refused, so the form may not refuse it either, and a test asserts this
 * attribute is absent.
 *
 * The two look identical and are the same size. Rule 4 of the frontend design
 * forbids scarcity and social proof on the advice page; here it means there is
 * no visual preference for yes over no.
 */
export function ConsentCheckbox({
  kind,
  label,
  text,
  checked,
  onChange,
}: {
  readonly kind: ConsentKind;
  readonly label: string;
  readonly text: string;
  readonly checked: boolean;
  readonly onChange: (checked: boolean) => void;
}) {
  const id = `toestemming-${kind.toLowerCase()}`;
  return (
    <div className="flex gap-3">
      <input
        id={id}
        type="checkbox"
        className="mt-1"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <label htmlFor={id} className="max-w-[60ch] text-sm">
        <span className="block font-medium">{label}</span>
        <span className="block text-ink-muted">{text}</span>
      </label>
    </div>
  );
}

/**
 * One consent as a row with a switch, for the account view.
 *
 * The asymmetry is chapter 6.3 and it is article 7(3) in a component: taking a
 * consent back may never be harder than giving it, so withdrawing works even
 * when the sentence could not be fetched, and granting does not. Granting with
 * no sentence on the screen would be agreeing to something nobody read.
 *
 * The toggle button's accessible NAME is the same on every row ("Toestemming
 * geven" or "Toestemming intrekken"), because it is the action and the action
 * is one of two words regardless of which consent it acts on. What has to
 * differ between rows is the DESCRIPTION, so `aria-describedby` names this
 * button's own label paragraph: two rows on the same screen must not read as
 * two buttons with nothing distinguishing them.
 *
 * The consent sentence itself is named too, and that is the point rather than
 * a nicety. It is the only text that says what is being agreed to, it is the
 * text the API recorded, and a description of three or four words leaves a
 * screen reader user on the toggle hearing the heading of a paragraph they
 * were never read. The label comes first so the row is identified before it
 * is explained.
 *
 * The same `aria-describedby` also carries the explanation for why granting
 * is blocked, when it is. A `disabled` button drops out of the tab order and,
 * in most assistive tech, the accessibility tree along with it, so a sentence
 * that only sits beside a disabled button is a sentence a keyboard or screen
 * reader user never reaches. The description is read (most assistive tech
 * still exposes `aria-describedby` on a disabled control) even though the
 * button itself cannot be activated, which keeps the visual "unavailable"
 * state exactly as before.
 *
 * The label is a prop since 2026-09-06 and comes from the same
 * `consent-texts/` answer as the sentence, under the same version (decision
 * 38). When that answer could not be fetched there is no label either, and
 * the description carries only the explanation; two rows then read alike,
 * which is the same degradation this row already accepts for the sentence,
 * reachable only while the API is down with the page open.
 */
export function ConsentRow({
  kind,
  label,
  text,
  granted,
  busy,
  onToggle,
}: {
  readonly kind: ConsentKind;
  readonly label: string | null;
  readonly text: string | null;
  readonly granted: boolean;
  readonly busy: boolean;
  readonly onToggle: (action: ConsentAction) => void;
}) {
  const action: ConsentAction = granted ? "WITHDRAWN" : "GRANTED";
  const unavailable = !granted && text === null;
  const labelId = `consent-label-${kind.toLowerCase()}`;
  const textId = `consent-text-${kind.toLowerCase()}`;
  const explanationId = `consent-unavailable-${kind.toLowerCase()}`;
  const describedBy = [
    label === null ? null : labelId,
    text === null ? null : textId,
    unavailable ? explanationId : null,
  ]
    .filter((value): value is string => value !== null)
    .join(" ");
  return (
    <div className="flex flex-col gap-2 border-t border-hairline pt-4">
      {label !== null && (
        <p id={labelId} className="font-medium">
          {label}
        </p>
      )}
      {text !== null && (
        <p id={textId} className="max-w-[60ch] text-sm text-ink-muted">
          {text}
        </p>
      )}
      <p className="text-sm">
        {granted ? "Toestemming gegeven" : "Geen toestemming gegeven"}
      </p>
      {unavailable && (
        <p id={explanationId} className="text-sm text-ink-muted">
          De toestemmingstekst kon niet worden opgehaald. Intrekken kan wel,
          aanzetten niet.
        </p>
      )}
      <p>
        <button
          type="button"
          className="button-quiet"
          disabled={busy || unavailable}
          aria-describedby={describedBy}
          onClick={() => onToggle(action)}
        >
          {granted ? "Toestemming intrekken" : "Toestemming geven"}
        </button>
        {/*
          A live region rather than aria-busy on this button: a disabled
          control leaves the tab order, and the accessibility tree along with
          it in most assistive tech, exactly when "busy" matters.
        */}
        {busy && (
          <span role="status" aria-live="polite" className="sr-only">
            Bezig.
          </span>
        )}
      </p>
    </div>
  );
}
