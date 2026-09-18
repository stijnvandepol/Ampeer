"use client";

import { useEffect, useSyncExternalStore } from "react";

import {
  type Consent,
  GA_MEASUREMENT_ID,
  disableAnalytics,
  loadAnalytics,
  readConsent,
  writeConsent,
} from "./analytics";

/**
 * The question, and the store that remembers the answer.
 *
 * The answer lives in localStorage and not in React, the same arrangement
 * themeStore.ts uses and for the same reason: the first render has to agree
 * with the static HTML, and the static HTML cannot know what this visitor
 * chose. So the build snapshot is null, which renders nothing, and the real
 * answer arrives in the commit React would have used for a second render
 * anyway. A visitor who already said no never sees the question flash.
 *
 * The banner is `position: fixed`, so it takes no room in the document and
 * moves nothing when it appears or leaves. /berekenen/ learned on the same
 * day what a late-arriving block does to the page under it.
 */

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function snapshot(): Consent {
  return readConsent(window.localStorage);
}

function buildSnapshot(): null {
  return null;
}

export function setConsent(
  consent: Consent,
  measurementId: string = GA_MEASUREMENT_ID,
): void {
  writeConsent(window.localStorage, consent);
  if (consent === "denied") disableAnalytics(window, measurementId);
  for (const listener of listeners) listener();
}

/**
 * Two answers of equal weight. The order is no first, because a banner whose
 * first and most reachable button is yes is a banner designed to be agreed
 * with, and the law asks for a choice rather than a nudge. Neither is styled
 * as the primary action.
 */
export function ConsentBanner({
  measurementId = GA_MEASUREMENT_ID,
}: {
  readonly measurementId?: string;
}) {
  const consent = useSyncExternalStore(subscribe, snapshot, buildSnapshot);

  useEffect(() => {
    if (consent === "granted") loadAnalytics(document, window, measurementId);
  }, [consent, measurementId]);

  if (measurementId === "" || consent !== "unknown") return null;

  return (
    <section
      role="dialog"
      aria-labelledby="meting-vraag"
      aria-describedby="meting-uitleg"
      data-consent-banner
      className="fixed inset-x-3 bottom-3 z-50 mx-auto flex max-w-xl flex-col gap-3 rounded-lg border border-hairline bg-surface p-4 text-ink shadow-[var(--shadow-raised)] sm:inset-x-4 sm:bottom-4 sm:p-5"
    >
      {/*
        Measured on 2026-09-16 on a 390 by 664 viewport: the first version
        stood 430 pixels tall, more than half the screen, over the hero of
        every page. The copy lost a clause and the heading a size; the two
        buttons kept their height, because a target under 44 pixels is the
        one economy a consent question may not make.
      */}
      <h2 id="meting-vraag" className="text-base font-bold sm:text-lg">
        Mogen wij meten hoe deze site gebruikt wordt?
      </h2>
      <p id="meting-uitleg" className="text-sm text-ink-muted">
        Alleen na uw ja laden wij Google Analytics. Dat telt welke pagina&apos;s
        bezocht worden, niet wie u bent. Wijzigen kan altijd op de
        privacypagina.
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => setConsent("denied", measurementId)}
          className="min-h-12 flex-1 rounded-md border border-current/30 px-4 text-base font-medium"
        >
          Nee, liever niet
        </button>
        <button
          type="button"
          onClick={() => setConsent("granted", measurementId)}
          className="min-h-12 flex-1 rounded-md border border-current/30 px-4 text-base font-medium"
        >
          Ja, dat mag
        </button>
      </div>
    </section>
  );
}

/**
 * The way back, on /privacy/. Clearing the answer makes the question return
 * on the next render, which is the banner above on this same page.
 */
export function ConsentReset({
  measurementId = GA_MEASUREMENT_ID,
}: {
  readonly measurementId?: string;
}) {
  const consent = useSyncExternalStore(subscribe, snapshot, buildSnapshot);
  if (measurementId === "") return null;
  const current =
    consent === "granted"
      ? "U heeft ja gezegd."
      : consent === "denied"
        ? "U heeft nee gezegd."
        : "U heeft nog niets gekozen.";
  return (
    <p className="flex flex-wrap items-center gap-3">
      <span>{current}</span>
      {consent !== "unknown" && consent !== null && (
        <button
          type="button"
          onClick={() => setConsent("unknown", measurementId)}
          className="min-h-11 rounded-md border border-current/30 px-4 text-base font-medium"
        >
          Uw keuze wijzigen
        </button>
      )}
    </p>
  );
}
