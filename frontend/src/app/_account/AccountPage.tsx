"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  BASE,
  confirmEmailVerification,
  deleteAccount,
  exportAccount,
  getConsentTexts,
  getMe,
  checkConsumption,
  getMeterStatus,
  acceptConsumption,
  claimAdvice,
  linkMeter,
  logout,
  postConsent,
  requestEmailVerification,
  unlinkMeter,
  type ConsentAction,
  type ConsentKind,
  type ConsentTexts,
  type Me,
  type MeterKey,
  type ConsumptionCheckAnswer,
  type MeterStatus,
} from "@/lib/accounts";
import { ConsentRow } from "./ConsentRow";
import { MeterSection } from "./MeterSection";
import { tokenFromPath } from "../_advice/link";
import { RegisterForm } from "./RegisterForm";
import { ResetConfirmForm } from "./ResetConfirmForm";
import { ResetRequestForm } from "./ResetRequestForm";
import { SignInForm } from "./SignInForm";
import { downloadJson } from "./download";
import { readRecoveryFragment } from "./fragment";
import { describeAuthError, fieldErrors } from "./messages";
import { LOADING, loadSession, signedOut, type AccountState } from "./session";

/** Which of the four signed-out forms is showing. State, not an address. */
type SignedOutView = "sign_in" | "register" | "reset_request" | "reset_confirm";

/**
 * Render order, not `CONSENT_KINDS`'s order.
 *
 * Mirrors `CONSENT_RENDER_ORDER` in `RegisterForm.tsx` rather than diverging
 * from it: `CONSENT_KINDS` is alphabetical, which puts `LEAD_GENERATION`, the
 * commercial consent, above `METER_LINK`, the one that improves the advice.
 * This is the one screen where this product's neutrality is visible, so the
 * consent that pays nobody renders first.
 */
const CONSENT_RENDER_ORDER: readonly ConsentKind[] = [
  "METER_LINK",
  "LEAD_GENERATION",
];

/**
 * Shown once, in a `role="status"`, on the sign-in view that replaces this one.
 *
 * A named constant and not a literal at the call site: the extractor behind
 * `e2e/language.spec.ts` walks variable initialisers, JSX text and a handful of
 * operators that can carry a string to one of those, but not a plain call
 * argument, so `onSignedOut("Uw account is verwijderd.")` would have been
 * invisible to `ui-strings.txt` and to the language check that reads it.
 */
const DELETION_CONFIRMATION = "Uw account is verwijderd.";

/**
 * Shown above the sign-in view, and above the account view, for the same
 * reason `DELETION_CONFIRMATION` above is a module constant: the extractor
 * behind `e2e/language.spec.ts` reads a variable initialiser and not a call
 * argument.
 */
const PASSWORD_CHANGED =
  "Uw wachtwoord is gewijzigd. Log in met uw nieuwe wachtwoord.";
const ADDRESS_CONFIRMED = "Uw e-mailadres is bevestigd.";
const CONFIRMATION_MAIL_UNDERWAY =
  "Er is een e-mail onderweg om uw adres te bevestigen.";
/**
 * Shown after the resend button's 202, for the same reason the other
 * notices above are module constants: a plain call argument
 * (`setMailNotice("...")`) sits in a position `e2e/language.spec.ts`'s
 * extractor does not walk, so the sentence would be invisible to
 * `ui-strings.txt` and the language check would pass while showing English
 * nowhere, having simply never looked at this text at all.
 */
const RESEND_CONFIRMATION_MAIL_UNDERWAY = "De bevestigingsmail is onderweg.";

/**
 * What deletion removes and what stays, read before the password field.
 *
 * Ruling 52: spec 6.3 as written asks only for a password field and a confirm
 * button, which tells a visitor nothing about what they destroy. This mirrors
 * `delete_account` in `backend/accounts/service.py` (the CASCADE takes the
 * email, both consents and every stored advice) and the DPIA's own line about
 * the audit id that outlives the account and points nowhere afterwards. A
 * module constant for the same reason `DELETION_CONFIRMATION` above is one:
 * the extractor does not walk into a JSX expression's identifier, only into
 * the variable declaration that gave it a value.
 */
const DELETION_CONSEQUENCES =
  "Hiermee verdwijnen uw e-mailadres, uw twee toestemmingen, uw opgeslagen adviezen en uw sessies. In ons logboek blijft alleen de regel staan dat een account is verwijderd, met een nummer dat nergens meer heen wijst.";

/** The six actions that share one disabled state, alongside a `ConsentKind`. */
type AccountActionId =
  | "export"
  | "logout"
  | "delete"
  | "verify"
  | "meter_link"
  | "meter_unlink"
  | "consumption_accept"
  | "advice_claim";

/**
 * One route, three views, and the state comes from `me/`.
 *
 * `/account/inloggen/` and `/account/registreren/` would be two statically
 * exported pages that both ask `me/` the same question in order to find out
 * which of the two they are allowed to show, plus a third that does the same.
 * The choice between the three views is state and not an address.
 *
 * Only a 200 on `me/` produces the account view. Every other outcome, a request
 * that never arrived included, produces the sign-in view, because nothing is
 * then known about who is signed in.
 */
export function AccountPage() {
  const [state, setState] = useState<AccountState>(LOADING);
  const [view, setView] = useState<SignedOutView>("sign_in");
  // The sentence to show above the sign-in view once, after a sign out or a
  // deletion. It is not `AccountState.notice`: that is rendered in
  // `role="alert"` because it always describes a failure, and "your account
  // has been deleted" is not a failure but the requested result.
  const [confirmation, setConfirmation] = useState<string | null>(null);
  // False until the visitor has done something on this route, and the gate on
  // every focus move below.
  //
  // The first settle, `loading` -> `signed_out` or `signed_in`, is not
  // something they did: it is this page finishing the question it asked
  // `me/` before anybody touched it. Moving focus there carries a keyboard
  // or screen reader visitor past the skip link, the navigation, the `<h1>`
  // and the paragraph that says what this page is, and lands them in the
  // middle of the document without their asking. So focus stays where the
  // browser put it, at the top, until the visitor switches view, signs in,
  // registers, signs out or deletes, all of which they asked for.
  //
  // State and not a ref, so the value is fixed at the moment the handler runs
  // and read at render like any other: a ref written in a handler and read in
  // an effect works today and depends on effect ordering to keep working.
  const [visitorActed, setVisitorActed] = useState(false);
  // The token off a reset link, held here and rendered nowhere. Read once,
  // before `me/` is asked, so the fragment is gone from the address bar
  // whatever `me/` answers.
  const [resetToken, setResetToken] = useState<string | null>(null);
  // What a confirmation link led to: nothing yet, the sentence for success,
  // or the API's sentence for a stale link. Rendered in a `role="status"`
  // above whichever view `me/` decided on.
  const [verification, setVerification] = useState<string | null>(null);
  // Whether the account view was reached by registering just now, which is
  // the one moment "a mail is on its way" is true and worth saying.
  const [justRegistered, setJustRegistered] = useState(false);
  // Where focus goes once the signed-out view settles or changes. The signed-in
  // view owns its own heading and manages its own focus, in `AccountView`
  // below, because it mounts fresh every time `me/` answers with a person.
  const signedOutRegion = useRef<HTMLDivElement>(null);
  const confirmationRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    // `alive` rather than an abort: the answer decides what is on the screen,
    // and setting state on a component that has gone is exactly the shape of
    // a stale-answer bug even where React swallows it.
    //
    // THIS GUARD AND THE ONE IN `AccountView` BELOW STAND UNTESTED, on
    // purpose. Three tests used to assert `console.error` was not called
    // after a late answer, and on 2026-09-06 all three stayed green with the
    // guard deleted: React 19 drops an update whose fiber has no root before
    // it reaches the act check, so nothing is logged either way. A probe that
    // recorded every console channel, unhandled rejections and the DOM
    // produced byte-identical output with the guard present and absent. There
    // is no assertion that can tell the two apart, so there is no test here
    // rather than three that read green by construction.
    let alive = true;
    // The fragment first, and `me/` after it. Order is the rule of chapter 2:
    // nothing is posted before the first `me/` has come back, so a
    // confirmation link waits for it, and a reset token only decides a view.
    //
    // `window.location.hash` cannot be read during render: this page is
    // statically exported, so the first render also runs on the server,
    // where `window` does not exist. Deciding `view` and `resetToken` here,
    // in the one place that IS client-only, is therefore synchronising with
    // an external system (the URL, per `react-hooks/set-state-in-effect`'s
    // own description of what an effect is for) and not deriving state that
    // render could have computed itself; the first `setState` call below is
    // disabled for that rule on that basis, having tried and reverted both
    // alternatives it suggests (a `useState` lazy initialiser breaks the
    // static export with "window is not defined"; a ref cannot be read
    // during render either, per this codebase's `react-hooks/refs` rule).
    const fragment = readRecoveryFragment();
    if (fragment?.kind === "reset") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setResetToken(fragment.token);
      setView("reset_confirm");
    }
    void loadSession().then(async (next) => {
      if (!alive) return;
      setState(next);
      if (fragment?.kind !== "verify") return;
      try {
        await confirmEmailVerification({ token: fragment.token });
      } catch (error) {
        if (!alive) return;
        const perField = fieldErrors(error);
        setVerification(
          perField.token === undefined
            ? describeAuthError(error)
            : perField.token.join(" "),
        );
        return;
      }
      if (!alive) return;
      // Set before the second question is asked, and never taken back by
      // that question's own failure: the 204 above already spent the token,
      // so a dropped connection here must not tell a household its address
      // is unconfirmed when it is not.
      setVerification(ADDRESS_CONFIRMED);
      if (next.status !== "signed_in") return;
      try {
        // A second `me/` after a change, so the address line below says
        // what the server now says. Not a retry: the first answer was
        // right at the time and the question has changed since.
        const refreshed = await getMe();
        if (alive) setState({ status: "signed_in", me: refreshed });
      } catch (error) {
        // The same answer this page gives a failed `me/` anywhere else
        // (`askWhoIsSignedIn` in `session.ts`): the sign-in view, with the
        // network's own sentence. The confirmation line above is untouched
        // by this branch and stays on screen regardless of `state.status`.
        if (alive) setState(signedOut(describeAuthError(error)));
      }
    });
    return () => {
      alive = false;
    };
  }, []);

  // Focus follows the view, for the reason `advies/page.tsx` gives for its own
  // heading: nothing on this route is a navigation, so without this a visitor
  // is left on a control the switch just removed (the "Nog geen account?"
  // button is gone the moment the registration view replaces it), or on
  // nothing at all the moment the loading sentence turns into a form.
  //
  // A confirmation, when there is one, takes focus ahead of the group: a
  // `role="status"` inserted into the DOM already holding its text is not
  // reliably announced unless something moves focus to it, and the only
  // destructive action on this route deserves better than a confirmation
  // that might go unheard.
  useEffect(() => {
    if (!visitorActed) return;
    if (state.status !== "signed_out") return;
    if (confirmation !== null) confirmationRef.current?.focus();
    else signedOutRegion.current?.focus();
  }, [state.status, view, confirmation, visitorActed]);

  function signedIn(who: Me): void {
    setVisitorActed(true);
    setState({ status: "signed_in", me: who });
  }

  function registered(who: Me): void {
    setJustRegistered(true);
    signedIn(who);
  }

  // A confirmation belongs to the sign-in view it was raised on; the form the
  // visitor switches to next has nothing to confirm.
  function switchView(next: SignedOutView): void {
    setVisitorActed(true);
    setConfirmation(null);
    setView(next);
  }

  if (state.status === "loading") {
    // A visible sentence and not an empty element. See the test above for the
    // measurement that made this a rule rather than a nicety. There is nothing
    // focusable here: there is nothing yet to hand focus to.
    return <p role="status">Uw gegevens worden opgehaald.</p>;
  }

  if (state.status === "signed_in") {
    return (
      <div className="flex flex-col gap-8">
        {verification !== null && (
          <p role="status" className="max-w-[60ch]">
            {verification}
          </p>
        )}
        <AccountView
          me={state.me}
          focusHeadingOnMount={visitorActed}
          justRegistered={justRegistered}
          onSignedOut={(line) => {
            setVisitorActed(true);
            setConfirmation(line);
            setView("sign_in");
            setJustRegistered(false);
            setState(signedOut(null));
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {verification !== null && (
        <p role="status" className="max-w-[60ch]">
          {verification}
        </p>
      )}
      {confirmation !== null && (
        <p ref={confirmationRef} tabIndex={-1} role="status">
          {confirmation}
        </p>
      )}
      {state.notice !== null && (
        <p role="alert" className="text-danger">
          {state.notice}
        </p>
      )}
      <div
        ref={signedOutRegion}
        tabIndex={-1}
        role="group"
        aria-labelledby={GROUP_HEADING[view]}
      >
        {view === "sign_in" && (
          <SignInForm
            onSignedIn={signedIn}
            onRegister={() => switchView("register")}
            onForgot={() => switchView("reset_request")}
          />
        )}
        {view === "register" && (
          <RegisterForm
            onRegistered={registered}
            onSignIn={() => switchView("sign_in")}
          />
        )}
        {view === "reset_request" && (
          <ResetRequestForm onBack={() => switchView("sign_in")} />
        )}
        {view === "reset_confirm" && resetToken !== null && (
          <ResetConfirmForm
            token={resetToken}
            onReset={() => {
              setResetToken(null);
              setVisitorActed(true);
              setConfirmation(PASSWORD_CHANGED);
              setView("sign_in");
            }}
            onRequestNew={() => {
              setResetToken(null);
              switchView("reset_request");
            }}
          />
        )}
      </div>
    </div>
  );
}

/** The `id` of the heading each signed-out view's `role="group"` is labelled by. */
const GROUP_HEADING: Readonly<Record<SignedOutView, string>> = {
  sign_in: "inloggen",
  register: "registreren",
  reset_request: "wachtwoord-herstellen",
  reset_confirm: "nieuw-wachtwoord",
};

/**
 * The account: an address, two consents, and three things you can do with it.
 *
 * The consent texts are fetched here as well as in the registration form, for
 * the reason chapter 6.2 gives: they are fetched when a view that shows those
 * sentences opens, and not on every page load. Somebody who only signs in
 * never opens either view and never spends the request.
 */
function AccountView({
  me,
  focusHeadingOnMount,
  justRegistered,
  onSignedOut,
}: {
  readonly me: Me;
  /**
   * Whether the visitor asked to be here, which decides whether focus moves.
   *
   * This component mounts on two occasions and they are not the same event:
   * right after somebody signs in or registers, and on a plain page load by
   * somebody whose cookies were still valid. The first is a view they asked
   * for; the second is the page they opened, and taking their focus down to
   * this heading skips the skip link, the navigation and the `<h1>` above it.
   */
  readonly focusHeadingOnMount: boolean;
  /** Whether this view was reached by registering just now. */
  readonly justRegistered: boolean;
  readonly onSignedOut: (confirmation: string | null) => void;
}) {
  const passwordId = useId();
  const passwordErrorId = `${passwordId}-error`;
  const passwordField = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const [texts, setTexts] = useState<ConsentTexts | null>(null);
  const [meterStatus, setMeterStatus] = useState<MeterStatus | null>(null);
  // Set once, right after linking, and never fetched back: design chapter 3,
  // the key exists only in the memory of the request that made it and in this
  // one answer. Cleared on unlinking so a stale key never survives past the
  // link it belonged to.
  const [issuedKey, setIssuedKey] = useState<MeterKey | null>(null);
  const [check, setCheck] = useState<ConsumptionCheckAnswer | null>(null);
  const [acceptedToken, setAcceptedToken] = useState<string | null>(null);
  const [mailNotice, setMailNotice] = useState<string | null>(
    justRegistered ? CONFIRMATION_MAIL_UNDERWAY : null,
  );
  const [consents, setConsents] = useState<Record<ConsentKind, boolean>>({
    ...me.consents,
  });
  // A set, not one shared string: `ConsentRow` reads `busy.has(kind)`, so an
  // export in flight no longer disables a toggle button (that button reads
  // only its own kind), and a toggle's own `finally` no longer gets clobbered
  // by an unrelated action's `finally` clearing the same single value out
  // from under it. The three plain buttons below read `busy.size > 0`, so
  // none of them re-enables while anything, including a toggle, is still in
  // flight.
  const [busy, setBusy] = useState<ReadonlySet<AccountActionId | ConsentKind>>(
    new Set(),
  );
  const [failure, setFailure] = useState<string | null>(null);
  const [fields, setFields] = useState<ReturnType<typeof fieldErrors>>({});
  const [expanded, setExpanded] = useState(false);
  const [password, setPassword] = useState("");

  useEffect(() => {
    // Untested for the reason spelled out at the guard in `AccountPage`
    // above: nothing observable differs between this guard and no guard.
    let alive = true;
    getConsentTexts()
      .then((answer) => {
        if (alive) setTexts(answer);
      })
      .catch(() => {
        // Deliberately silent. The rows below say what this costs, in the one
        // place where it changes what a visitor can do: granting.
        if (alive) setTexts(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    // Untested for the same reason as the guard above: nothing observable
    // differs between this guard and no guard.
    let alive = true;
    getMeterStatus()
      .then((answer) => {
        if (alive) setMeterStatus(answer);
      })
      .catch(() => {
        // Deliberately silent, the same choice `getConsentTexts` above makes:
        // `MeterSection` renders nothing beyond its own heading while
        // `status` is null, rather than a second failure sentence beside
        // `failure` below.
        if (alive) setMeterStatus(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    // Only for an account that actually has a meter. Answering this runs the
    // engine several times, so asking on every page load for a household
    // without a link would spend that for a question whose answer is known.
    if (meterStatus === null || !meterStatus.linked) return;
    let alive = true;
    checkConsumption()
      .then((answer) => {
        if (alive) setCheck(answer);
      })
      .catch(() => {
        // Silent, like the meter status above: `MeterSection` shows nothing
        // when there is nothing, and a household who cannot be told what
        // their meter thinks is not a household with a broken account page.
        if (alive) setCheck(null);
      });
    return () => {
      alive = false;
    };
  }, [meterStatus]);

  // Right after signing in, focus follows the view that replaced the form the
  // visitor was standing in, because otherwise they are left on a control
  // that no longer exists. On a page load it does not move: nothing was
  // removed from under them, and the top of the document is where a visitor
  // who has just arrived belongs.
  useEffect(() => {
    if (focusHeadingOnMount) heading.current?.focus();
  }, [focusHeadingOnMount]);

  // Focus follows the field that appeared, which is what makes the disclosure
  // usable from a keyboard rather than merely operable.
  useEffect(() => {
    if (expanded) passwordField.current?.focus();
  }, [expanded]);

  function markBusy(id: AccountActionId | ConsentKind): void {
    setBusy((current) => new Set(current).add(id));
  }

  function clearBusy(id: AccountActionId | ConsentKind): void {
    setBusy((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  }

  async function toggle(
    kind: ConsentKind,
    action: ConsentAction,
  ): Promise<void> {
    markBusy(kind);
    setFailure(null);
    try {
      const result = await postConsent(
        action === "GRANTED" && texts !== null
          ? { kind, action, text_version: texts.text_version }
          : { kind, action },
      );
      // The answer is the new state of that row. No second `me/`.
      setConsents((current) => ({ ...current, [result.kind]: result.granted }));
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy(kind);
    }
  }

  async function claimAction(link: string): Promise<void> {
    // A pasted link or a bare token, reduced to the token by the same helper
    // the advice page reads its own URL with, so there is one definition of
    // which part of a path is a token.
    const token = tokenFromPath(link) ?? link;
    markBusy("advice_claim");
    setFailure(null);
    try {
      await claimAdvice(token);
      // The account has an advice now, so the question this page asks about
      // the meter has a household to be asked about. Asked rather than
      // assumed, like every other refresh here.
      setCheck(await checkConsumption());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("advice_claim");
    }
  }

  async function acceptAction(): Promise<void> {
    if (check === null || check.advice_token === null) return;
    markBusy("consumption_accept");
    setFailure(null);
    try {
      setAcceptedToken(await acceptConsumption(check.advice_token));
      // The advice it applied to now runs on the accepted figure, so the
      // meter has nothing left to contradict. Asked again rather than
      // assumed, because that is the same question this block always answers.
      setCheck(await checkConsumption());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("consumption_accept");
    }
  }

  async function linkAction(): Promise<void> {
    markBusy("meter_link");
    setFailure(null);
    try {
      const key = await linkMeter();
      setIssuedKey(key);
      // The new state of the koppeling. Not a second `me/`: nothing about
      // the account changed, only the koppeling did.
      setMeterStatus(await getMeterStatus());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("meter_link");
    }
  }

  async function unlinkAction(): Promise<void> {
    markBusy("meter_unlink");
    setFailure(null);
    try {
      await unlinkMeter();
      setIssuedKey(null);
      setMeterStatus(await getMeterStatus());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("meter_unlink");
    }
  }

  async function download(): Promise<void> {
    markBusy("export");
    setFailure(null);
    try {
      downloadJson(await exportAccount());
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("export");
    }
  }

  async function resendConfirmation(): Promise<void> {
    markBusy("verify");
    setFailure(null);
    try {
      await requestEmailVerification();
      setMailNotice(RESEND_CONFIRMATION_MAIL_UNDERWAY);
    } catch (error) {
      setFailure(describeAuthError(error));
    } finally {
      clearBusy("verify");
    }
  }

  async function signOut(): Promise<void> {
    markBusy("logout");
    setFailure(null);
    try {
      await logout();
      // 204, view signed out, and no question asked afterwards.
      onSignedOut(null);
    } catch (error) {
      setFailure(describeAuthError(error));
      clearBusy("logout");
    }
  }

  async function remove(): Promise<void> {
    markBusy("delete");
    setFailure(null);
    setFields({});
    try {
      await deleteAccount(password);
      onSignedOut(DELETION_CONFIRMATION);
    } catch (error) {
      // The password field carries its own message, bound by
      // `aria-describedby`. The form-level alert below is left for what no
      // field can carry: a network failure, a 500, a `detail` with no field.
      // Never a joined sentence and never `ApiError`'s English default, which
      // is exactly what `describeAuthError` guards against.
      //
      // Defence in depth rather than a reachable path: `DeleteView.post` in
      // `backend/accounts/views.py` answers a wrong password with
      // `PermissionDenied(NL["credentials_invalid"])`, which DRF serialises
      // as `{"detail": ...}` and never as `{"password": [...]}`. Nothing
      // today produces a field-shaped error here; the binding stays so a
      // future serializer-level validation on this field renders correctly
      // without a second look at this component.
      const perField = fieldErrors(error);
      setFields(perField);
      setFailure(
        perField.password === undefined ? describeAuthError(error) : null,
      );
      clearBusy("delete");
    }
  }

  return (
    <section aria-labelledby="uw-gegevens" className="flex flex-col gap-6">
      <h2 id="uw-gegevens" ref={heading} tabIndex={-1} className="text-2xl">
        Uw gegevens
      </h2>
      <p>{me.email}</p>

      <div className="flex flex-col gap-2">
        <p className="text-sm">
          {me.email_verified_at === null
            ? "E-mailadres nog niet bevestigd"
            : "E-mailadres bevestigd"}
        </p>
        {me.email_verified_at === null && (
          <>
            <p className="max-w-[60ch] text-sm text-ink-muted">
              Voor het koppelen van een slimme meter is een bevestigd
              e-mailadres nodig.
            </p>
            <p>
              <button
                type="button"
                className="button-quiet"
                disabled={busy.size > 0}
                onClick={() => void resendConfirmation()}
              >
                Verstuur de bevestigingsmail opnieuw
              </button>
              {busy.has("verify") && (
                <span role="status" aria-live="polite" className="sr-only">
                  Bezig.
                </span>
              )}
            </p>
          </>
        )}
        {mailNotice !== null && <p role="status">{mailNotice}</p>}
      </div>

      {CONSENT_RENDER_ORDER.map((kind) => (
        <ConsentRow
          key={kind}
          kind={kind}
          label={texts === null ? null : texts.labels[kind]}
          text={texts === null ? null : texts.texts[kind]}
          granted={consents[kind] === true}
          busy={busy.has(kind)}
          onToggle={(action) => void toggle(kind, action)}
        />
      ))}

      <MeterSection
        status={meterStatus}
        issuedKey={issuedKey}
        apiBase={BASE}
        busy={
          busy.has("meter_link") ||
          busy.has("meter_unlink") ||
          busy.has("advice_claim") ||
          busy.has("consumption_accept")
        }
        onLink={() => void linkAction()}
        onUnlink={() => void unlinkAction()}
        check={check}
        onAccept={() => void acceptAction()}
        onClaim={(link) => void claimAction(link)}
      />

      {acceptedToken !== null && (
        <p className="max-w-[60ch] text-sm">
          Uw advies is opnieuw berekend.{" "}
          <a className="underline" href={`/advies/${acceptedToken}/`}>
            Bekijk het nieuwe advies
          </a>
          .
        </p>
      )}

      {failure !== null && (
        <p role="alert" className="text-danger">
          {failure}
        </p>
      )}

      <div className="flex flex-wrap gap-3 border-t border-hairline pt-4">
        <p>
          <button
            type="button"
            className="button-quiet"
            disabled={busy.size > 0}
            onClick={() => void download()}
          >
            Gegevens exporteren
          </button>
          {/*
            A live region rather than `aria-busy` on this button: a disabled
            control leaves the tab order, and the accessibility tree along
            with it in most assistive tech, exactly when "busy" matters. The
            pattern `ConsentRow`, `SignInForm` and `RegisterForm` already use.
          */}
          {busy.has("export") && (
            <span role="status" aria-live="polite" className="sr-only">
              Bezig.
            </span>
          )}
        </p>
        <p>
          <button
            type="button"
            className="button-quiet"
            disabled={busy.size > 0}
            onClick={() => void signOut()}
          >
            Uitloggen
          </button>
          {busy.has("logout") && (
            <span role="status" aria-live="polite" className="sr-only">
              Bezig.
            </span>
          )}
        </p>
      </div>

      {/*
        Collapsed, this is a button and not a warning. It is the heaviest thing
        on the page and it should read as neither an offer nor a threat.
      */}
      <div className="flex flex-col gap-3 border-t border-hairline pt-4">
        <p>
          <button
            type="button"
            className="button-quiet"
            aria-expanded={expanded}
            onClick={() => setExpanded(!expanded)}
          >
            Account verwijderen
          </button>
        </p>
        {expanded && (
          <form
            noValidate
            className="flex flex-col gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (busy.size === 0) void remove();
            }}
          >
            {/*
              Ruling 52: informed consent to deletion, read before the
              password field and not after it, the same order article 7(3)
              asks of a consent given rather than withdrawn.
            */}
            <p className="max-w-[60ch] text-sm text-ink-muted">
              {DELETION_CONSEQUENCES}
            </p>
            <div className="flex flex-col gap-1">
              <label htmlFor={passwordId}>Uw wachtwoord</label>
              <input
                id={passwordId}
                ref={passwordField}
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
              <button
                type="submit"
                className="button-accent"
                disabled={busy.size > 0}
              >
                Verwijderen bevestigen
              </button>
              {busy.has("delete") && (
                <span role="status" aria-live="polite" className="sr-only">
                  Bezig.
                </span>
              )}
            </p>
          </form>
        )}
      </div>
    </section>
  );
}
