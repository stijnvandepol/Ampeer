"use client";

import { useEffect, useId, useState } from "react";
import {
  CONSENT_KINDS,
  getConsentTexts,
  getMe,
  register,
  type ConsentTexts,
  type Me,
} from "@/lib/accounts";
import { ConsentCheckbox } from "./ConsentRow";
import { describeAuthError } from "./messages";

/**
 * Making an account, which is two fields and two questions that may both be no.
 *
 * The consent texts are fetched when this view opens and not on every page
 * load: `auth-read` is one bucket of 120 an hour shared with `me/`, and
 * somebody who only signs in never sees these sentences and should not pay for
 * them.
 *
 * While they have not come back there is no submit button at all, which is
 * stronger than a disabled one and says the same thing: a `true` sent for a
 * sentence nobody has read is not consent.
 */
export function RegisterForm({
  onRegistered,
  onSignIn,
}: {
  readonly onRegistered: (me: Me) => void;
  readonly onSignIn: () => void;
}) {
  const emailId = useId();
  const passwordId = useId();
  const [texts, setTexts] = useState<ConsentTexts | null>(null);
  const [textsFailed, setTextsFailed] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [given, setGiven] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getConsentTexts()
      .then((answer) => {
        if (alive) setTexts(answer);
      })
      .catch(() => {
        if (alive) setTextsFailed(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  async function submit(current: ConsentTexts): Promise<void> {
    setBusy(true);
    setFailure(null);
    try {
      await register({
        email,
        password,
        consent_meter_link: given["METER_LINK"] === true,
        consent_lead_generation: given["LEAD_GENERATION"] === true,
        // The version the sentences above came with, never a constant here.
        text_version: current.text_version,
      });
      onRegistered(await getMe());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="registreren" className="flex flex-col gap-6">
      <h2 id="registreren" className="text-2xl">
        Account aanmaken
      </h2>
      {texts === null && !textsFailed && (
        <p role="status">De toestemmingsteksten worden opgehaald.</p>
      )}
      {textsFailed && (
        <p role="alert" className="text-danger">
          De toestemmingsteksten konden niet worden opgehaald. Herlaad de pagina
          om een account aan te maken.
        </p>
      )}
      {texts !== null && (
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!busy) void submit(texts);
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
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          {CONSENT_KINDS.map((kind) => (
            <ConsentCheckbox
              key={kind}
              kind={kind}
              text={texts.texts[kind]}
              checked={given[kind] === true}
              onChange={(checked) =>
                setGiven((current) => ({ ...current, [kind]: checked }))
              }
            />
          ))}
          <p>
            <button
              type="submit"
              className="button-accent"
              disabled={busy}
              aria-busy={busy}
            >
              Account aanmaken
            </button>
          </p>
        </form>
      )}
      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}
      <p>
        <button type="button" className="button-quiet" onClick={onSignIn}>
          Ik heb al een account. Inloggen
        </button>
      </p>
    </section>
  );
}
