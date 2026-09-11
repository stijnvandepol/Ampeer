"use client";

import { useId, useState } from "react";
import { requestPasswordReset } from "@/lib/accounts";
import { describeAuthError, fieldErrors } from "./messages";

/**
 * Shown once, after the 202, in place of the field. The same sentence for
 * every address, known or not, because the API says nothing either: a page
 * that revealed which addresses have an account would be an address book.
 * A module constant for the reason `DELETION_CONFIRMATION` in
 * `AccountPage.tsx` is one: the extractor behind `e2e/language.spec.ts`
 * walks variable initialisers and JSX text, not a call argument.
 */
const SENT =
  "Als dit adres bij ons bekend is, staat er binnen enkele minuten een e-mail voor u klaar. De link daarin werkt een uur.";

/**
 * Asking for a reset link: one field, one button, one sentence afterwards.
 *
 * Reached from the sign-in form's "Wachtwoord vergeten?" button, which stands
 * where the sentence saying there was no reset used to stand.
 */
export function ResetRequestForm({ onBack }: { readonly onBack: () => void }) {
  const emailId = useId();
  const emailErrorId = `${emailId}-error`;
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    setFields({});
    try {
      await requestPasswordReset({ email });
      setSent(true);
    } catch (error) {
      const perField = fieldErrors(error);
      setFields(perField);
      setFailure(
        Object.keys(perField).length > 0 ? null : describeAuthError(error),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="wachtwoord-herstellen"
      className="flex flex-col gap-6"
    >
      <h2 id="wachtwoord-herstellen" className="text-2xl">
        Wachtwoord herstellen
      </h2>
      {sent ? (
        <p role="status" className="max-w-[60ch]">
          {SENT}
        </p>
      ) : (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!busy) void submit();
          }}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor={emailId}>E-mailadres</label>
            <input
              id={emailId}
              type="email"
              autoComplete="email"
              value={email}
              aria-invalid={fields.email !== undefined}
              aria-describedby={
                fields.email !== undefined ? emailErrorId : undefined
              }
              onChange={(event) => setEmail(event.target.value)}
            />
            {fields.email !== undefined && (
              <p id={emailErrorId} role="alert" className="text-sm text-danger">
                {fields.email.join(" ")}
              </p>
            )}
          </div>
          <p>
            <button type="submit" className="button-accent" disabled={busy}>
              Stuur een herstellink
            </button>
          </p>
          {busy && (
            <p role="status" aria-live="polite" className="sr-only">
              Bezig.
            </p>
          )}
        </form>
      )}
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p>
        <button type="button" className="button-quiet" onClick={onBack}>
          Terug naar inloggen
        </button>
      </p>
    </section>
  );
}
