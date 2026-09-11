"use client";

import { useEffect, useId, useState } from "react";
import {
  getConsentTexts,
  getMe,
  register,
  type ConsentKind,
  type ConsentTexts,
  type Me,
} from "@/lib/accounts";
import { ConsentCheckbox } from "./ConsentRow";
import { describeAuthError, fieldErrors } from "./messages";

/**
 * Render order, not `CONSENT_KINDS`'s order.
 *
 * `CONSENT_KINDS` is alphabetical, which puts `LEAD_GENERATION`, the
 * commercial consent, above `METER_LINK`, the one that improves the advice.
 * This is the one screen where this product's neutrality is visible, so the
 * consent that pays nobody renders first. `CONSENT_KINDS` itself is left
 * alone: task 4's list, pinned sorted against the Python side.
 */
const CONSENT_RENDER_ORDER: readonly ConsentKind[] = [
  "METER_LINK",
  "LEAD_GENERATION",
];

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
  const emailErrorId = `${emailId}-error`;
  const passwordErrorId = `${passwordId}-error`;
  const [texts, setTexts] = useState<ConsentTexts | null>(null);
  const [textsFailed, setTextsFailed] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Keyed by `ConsentKind` and not by `string`: a typo in a key is then a
  // build error rather than a checkbox that silently reads `undefined` and
  // submits a `false` nobody chose. `Partial`, because a box nobody has
  // touched has no entry at all, which is what `=== true` below reads.
  const [given, setGiven] = useState<Partial<Record<ConsentKind, boolean>>>({});
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});

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
    setFields({});
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
      // Chapter 8: email and password errors sit beside their own field,
      // bound by aria-describedby. text_version has no field of its own on
      // this form, so its message renders beside the consent block instead
      // of under email, and none of the three is joined into the
      // form-level sentence, which is left for what none of them can carry.
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
              autoComplete="new-password"
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
          {fields.text_version !== undefined && (
            <p role="alert" className="text-sm text-danger">
              {fields.text_version.join(" ")}
            </p>
          )}
          {CONSENT_RENDER_ORDER.map((kind) => (
            <ConsentCheckbox
              key={kind}
              kind={kind}
              label={texts.labels[kind]}
              text={texts.texts[kind]}
              checked={given[kind] === true}
              onChange={(checked) =>
                setGiven((current) => ({ ...current, [kind]: checked }))
              }
            />
          ))}
          <p>
            <button type="submit" className="button-accent" disabled={busy}>
              Account aanmaken
            </button>
          </p>
          {/*
            A live region rather than aria-busy on the button: a disabled
            control leaves the tab order, and the accessibility tree along
            with it in most assistive tech, exactly when "busy" matters.
          */}
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
        <button type="button" className="button-quiet" onClick={onSignIn}>
          Ik heb al een account. Inloggen
        </button>
      </p>
    </section>
  );
}
