"use client";

import { useEffect, useRef, useState } from "react";
import type { Me } from "@/lib/accounts";
import { RegisterForm } from "./RegisterForm";
import { SignInForm } from "./SignInForm";
import { LOADING, loadSession, type AccountState } from "./session";

/** Which of the two signed-out forms is showing. State, not an address. */
type SignedOutView = "sign_in" | "register";

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
  // Where focus goes once the view settles or changes. The account view owns
  // its own heading, so that one gets `tabIndex={-1}` directly, the same
  // pattern `advies/page.tsx` uses on its own `<h1>`. `SignInForm` and
  // `RegisterForm` are task 6's files and keep their own headings; this route
  // has no way to reach into them, so the two signed-out views instead get a
  // wrapper of their own here, labelled by the form's own heading id so a
  // screen reader announces the same words either way.
  const signedOutRegion = useRef<HTMLDivElement>(null);
  const signedInHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    // `alive` rather than an abort: the answer decides what is on the screen,
    // and setting state on a component that has gone is a warning in
    // development and a leak in a test that renders this twice.
    let alive = true;
    void loadSession().then((next) => {
      if (alive) setState(next);
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
  useEffect(() => {
    if (state.status === "signed_in") signedInHeading.current?.focus();
    else if (state.status === "signed_out") signedOutRegion.current?.focus();
  }, [state.status, view]);

  function signedIn(who: Me): void {
    setState({ status: "signed_in", me: who });
  }

  if (state.status === "loading") {
    // A visible sentence and not an empty element. See the test above for the
    // measurement that made this a rule rather than a nicety. There is nothing
    // focusable here: there is nothing yet to hand focus to.
    return <p role="status">Uw gegevens worden opgehaald.</p>;
  }

  if (state.status === "signed_in") {
    return (
      <section aria-labelledby="uw-gegevens" className="flex flex-col gap-4">
        <h2
          id="uw-gegevens"
          ref={signedInHeading}
          tabIndex={-1}
          className="text-2xl"
        >
          Uw gegevens
        </h2>
        <p>{state.me.email}</p>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {state.notice !== null && (
        <p role="alert" className="text-danger">
          {state.notice}
        </p>
      )}
      <div
        ref={signedOutRegion}
        tabIndex={-1}
        role="group"
        aria-labelledby={view === "sign_in" ? "inloggen" : "registreren"}
      >
        {view === "sign_in" ? (
          <SignInForm
            onSignedIn={signedIn}
            onRegister={() => setView("register")}
          />
        ) : (
          <RegisterForm
            onRegistered={signedIn}
            onSignIn={() => setView("sign_in")}
          />
        )}
      </div>
    </div>
  );
}
