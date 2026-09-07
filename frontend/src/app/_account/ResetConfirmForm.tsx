"use client";

import { useId, useState } from "react";
import { confirmPasswordReset } from "@/lib/accounts";
import { describeAuthError, fieldErrors } from "./messages";

/**
 * A new password, with the token that arrived in the fragment.
 *
 * The token is a prop and lives in the page's state; it is never rendered,
 * not in a hidden input and not in an attribute. A 400 under `token` is the
 * API's one sentence for expired, spent, superseded and unknown, hung on the
 * password field because it is the only field here, with the one button that
 * still helps: asking for a new link. A 400 under `password` is the same
 * list of sentences registration gives.
 *
 * After the 204 the page switches to signing in with a notice; nothing here
 * signs anybody in, because `login/` is the only place a session starts.
 */
export function ResetConfirmForm({
  token,
  onReset,
  onRequestNew,
}: {
  readonly token: string;
  readonly onReset: () => void;
  readonly onRequestNew: () => void;
}) {
  const passwordId = useId();
  const passwordErrorId = `${passwordId}-error`;
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});

  const fieldMessage = fields.token ?? fields.password;

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    setFields({});
    try {
      await confirmPasswordReset({ token, password });
      onReset();
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
    <section aria-labelledby="nieuw-wachtwoord" className="flex flex-col gap-6">
      <h2 id="nieuw-wachtwoord" className="text-2xl">
        Nieuw wachtwoord
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
          <label htmlFor={passwordId}>Nieuw wachtwoord</label>
          <input
            id={passwordId}
            type="password"
            autoComplete="new-password"
            value={password}
            aria-invalid={fieldMessage !== undefined}
            aria-describedby={
              fieldMessage !== undefined ? passwordErrorId : undefined
            }
            onChange={(event) => setPassword(event.target.value)}
          />
          {fieldMessage !== undefined && (
            <p
              id={passwordErrorId}
              role="alert"
              className="text-sm text-danger"
            >
              {fieldMessage.join(" ")}
            </p>
          )}
        </div>
        <p>
          <button type="submit" className="button-accent" disabled={busy}>
            Wachtwoord opslaan
          </button>
        </p>
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
      {fields.token !== undefined && (
        <p>
          <button type="button" className="button-quiet" onClick={onRequestNew}>
            Wachtwoord vergeten?
          </button>
        </p>
      )}
    </section>
  );
}
