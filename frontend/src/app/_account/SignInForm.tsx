"use client";

import { useId, useState } from "react";
import { getMe, login, type Me } from "@/lib/accounts";
import { describeAuthError } from "./messages";

/**
 * Signing in, and the one honest sentence underneath it.
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
}: {
  readonly onSignedIn: (me: Me) => void;
  readonly onRegister: () => void;
}) {
  const emailId = useId();
  const passwordId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function submit(): Promise<void> {
    setBusy(true);
    setFailure(null);
    try {
      await login({ email, password });
      onSignedIn(await getMe());
    } catch (error) {
      setFailure(describeAuthError(error));
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
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={passwordId}>Wachtwoord</label>
          <input
            id={passwordId}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <p>
          <button
            type="submit"
            className="button-accent"
            disabled={busy}
            aria-busy={busy}
          >
            Inloggen
          </button>
        </p>
      </form>
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p className="max-w-[60ch] text-sm text-ink-muted">
        Bent u uw wachtwoord kwijt, dan kunnen wij het niet herstellen. Er is
        nog geen wachtwoordherstel, en zonder uw wachtwoord komt u ook niet meer
        bij de knop waarmee u uw account verwijdert.
      </p>
      <p>
        <button type="button" className="button-quiet" onClick={onRegister}>
          Nog geen account? Account aanmaken
        </button>
      </p>
    </section>
  );
}
