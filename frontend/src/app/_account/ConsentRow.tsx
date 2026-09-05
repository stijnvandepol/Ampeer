"use client";

import type { ConsentAction, ConsentKind } from "@/lib/accounts";

/**
 * What each consent is about, in three or four words.
 *
 * Interface text and not the consent itself: this names the row so a reader can
 * see at a glance which one they are looking at. The sentence they agree to is
 * the one from the API, underneath, and it is the only one that is recorded.
 */
export const CONSENT_LABELS: Readonly<Record<ConsentKind, string>> = {
  LEAD_GENERATION: "Doorgeven aan een installateur",
  METER_LINK: "Kwartiergegevens van uw slimme meter",
};

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
  text,
  checked,
  onChange,
}: {
  readonly kind: ConsentKind;
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
        <span className="block font-medium">{CONSENT_LABELS[kind]}</span>
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
 * The same `aria-describedby` also carries the explanation for why granting
 * is blocked, when it is. A `disabled` button drops out of the tab order and,
 * in most assistive tech, the accessibility tree along with it, so a sentence
 * that only sits beside a disabled button is a sentence a keyboard or screen
 * reader user never reaches. The description is read (most assistive tech
 * still exposes `aria-describedby` on a disabled control) even though the
 * button itself cannot be activated, which keeps the visual "unavailable"
 * state exactly as before.
 */
export function ConsentRow({
  kind,
  text,
  granted,
  busy,
  onToggle,
}: {
  readonly kind: ConsentKind;
  readonly text: string | null;
  readonly granted: boolean;
  readonly busy: boolean;
  readonly onToggle: (action: ConsentAction) => void;
}) {
  const action: ConsentAction = granted ? "WITHDRAWN" : "GRANTED";
  const unavailable = !granted && text === null;
  const labelId = `consent-label-${kind.toLowerCase()}`;
  const explanationId = `consent-unavailable-${kind.toLowerCase()}`;
  const describedBy = [labelId, unavailable ? explanationId : null]
    .filter((value): value is string => value !== null)
    .join(" ");
  return (
    <div className="flex flex-col gap-2 border-t border-hairline pt-4">
      <p id={labelId} className="font-medium">
        {CONSENT_LABELS[kind]}
      </p>
      {text !== null && (
        <p className="max-w-[60ch] text-sm text-ink-muted">{text}</p>
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
