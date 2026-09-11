"use client";

import { useId, useState } from "react";
import { getMe, login, type Me } from "@/lib/accounts";
import { describeAuthError, fieldErrors } from "./messages";

/**
 * Signing in, and the way out for somebody who cannot: the reset request
 * stands where a sentence saying there was no reset stood until 2026-09-06.
 *
 * `me/` is asked after the 200 because `login/` answers with no body at all,
 * and that second call is not a retry: it is the question that fills the
 * account view. The order is also forced from the other side, by chapter 2 of
 * the design: nothing is posted anywhere before the first `me/` has come back,
 * because that is the response that carries the CSRF cookie.
 */
export function SignInForm({
  onSignedIn,
  onRegister,
  onForgot,
}: {
  readonly onSignedIn: (me: Me) => void;
  readonly onRegister: () => void;
  readonly onForgot: () => void;
}) {
  const emailId = useId();
  const passwordId = useId();
  const emailErrorId = `${emailId}-error`;
  const passwordErrorId = `${passwordId}-error`;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    setFields({});
    try {
      await login({ email, password });
      onSignedIn(await getMe());
    } catch (error) {
      // Chapter 8: a field error sits beside its field, bound by
      // aria-describedby, and never joined into the form-level sentence.
      // The form-level alert is left for what a field cannot carry: a 401's
      // detail, a 429, a network failure, or an unreadable body.
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
    <section aria-labelledby="inloggen" className="flex flex-col gap-6">
      <h2 id="inloggen" className="text-2xl">
        Inloggen
      </h2>
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
        <div className="flex flex-col gap-1">
          <label htmlFor={passwordId}>Wachtwoord</label>
          <input
            id={passwordId}
            type="password"
            autoComplete="current-password"
            value={password}
            aria-invalid={fields.password !== undefined}
            aria-describedby={
              fields.password !== undefined ? passwordErrorId : undefined
            }
            onChange={(event) => setPassword(event.target.value)}
          />
          {fields.password !== undefined && (
            <p
              id={passwordErrorId}
              role="alert"
              className="text-sm text-danger"
            >
              {fields.password.join(" ")}
            </p>
          )}
        </div>
        <p>
          <button type="submit" className="button-accent" disabled={busy}>
            Inloggen
          </button>
        </p>
        {/*
          A live region rather than aria-busy on the button: a disabled
          control leaves the tab order and, in most assistive tech, the
          accessibility tree along with it, which is exactly when "busy"
          matters most. Modelled on the same pattern in app/advies/page.tsx.
        */}
        {busy && (
          <p role="status" aria-live="polite" className="sr-only">
            Bezig.
          </p>
        )}
      </form>
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p>
        <button type="button" className="button-quiet" onClick={onForgot}>
          Wachtwoord vergeten?
        </button>
      </p>
      <p>
        <button type="button" className="button-quiet" onClick={onRegister}>
          Nog geen account? Account aanmaken
        </button>
      </p>
    </section>
  );
}
