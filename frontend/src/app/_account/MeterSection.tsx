"use client";

import { useState } from "react";
import type {
  ConsumptionCheckAnswer,
  MeterKey,
  MeterStatus,
} from "@/lib/accounts";

/**
 * The sentence for the one state that has nothing to click.
 *
 * `MeterStatus` carries `may_link` and nothing that says which of the two
 * conditions behind it (a confirmed address, the `METER_LINK` consent) is
 * still missing, so this names the requirement rather than diagnosing which
 * half of it a household still has to do. Design chapter 8.
 */
const REQUIREMENT_SENTENCE =
  "Om een slimme meter te koppelen zijn een bevestigd e-mailadres en toestemming voor het verwerken van kwartiergegevens nodig.";

const KEY_SHOWN_ONCE =
  "Deze sleutel wordt hierna niet meer getoond. Bewaar hem in het apparaat dat de metingen gaat versturen.";

const NOTHING_RECEIVED_YET = "Er is nog niets binnengekomen.";

const NO_ADVICE_YET =
  "Een advies dat u zonder in te loggen hebt gemaakt, hoort nog niet bij uw account. Plak de link erbij, dan rekenen wij het opnieuw voor u.";

const ADVICE_LINK_LABEL = "Link van uw advies";

const CLAIM_BUTTON = "Koppel aan mijn account";

const UNLINK_CONSEQUENCE =
  "Na het ontkoppelen zijn de metingen van deze meter weg.";

export interface MeterSectionProps {
  readonly status: MeterStatus | null;
  readonly issuedKey: MeterKey | null;
  readonly apiBase: string;
  readonly busy: boolean;
  readonly onLink: () => void;
  readonly onUnlink: () => void;
  /**
   * What the meter says about the annual consumption on the most recent
   * advice, or null when it says nothing. Null covers a household with no
   * advice, one whose meter has too little to go on, and one whose meter
   * agrees with them, because all three deserve the same thing here: silence.
   */
  readonly check: ConsumptionCheckAnswer | null;
  readonly onAccept: () => void;
  /** Turn an advice link into one that belongs to this account. */
  readonly onClaim: (link: string) => void;
}

/**
 * The meter link block: three states off `status`, plus the one-time key
 * screen that `issuedKey` overrides them with.
 *
 * Pure presentation, per design chapter 8 and the plan for this task: this
 * component makes no network call of its own. `AccountPage.tsx` fetches the
 * status, calls `linkMeter`/`unlinkMeter`, and hands the results down as
 * props, the same division `ConsentRow` already has with `AccountView`.
 *
 * The unlink confirmation is the disclosure pattern the account deletion
 * block already uses one section up: a button that expands into a second
 * button rather than a native `confirm()`, so the warning sentence is read by
 * assistive tech before the destructive action is reachable.
 */
export function MeterSection({
  status,
  issuedKey,
  apiBase,
  busy,
  onLink,
  onUnlink,
  check,
  onAccept,
  onClaim,
}: MeterSectionProps) {
  const [confirmingUnlink, setConfirmingUnlink] = useState(false);
  const [adviceLink, setAdviceLink] = useState("");

  function confirmUnlink(): void {
    setConfirmingUnlink(false);
    onUnlink();
  }

  return (
    <section
      aria-labelledby="uw-slimme-meter"
      className="flex flex-col gap-3 border-t border-hairline pt-4"
    >
      <h3 id="uw-slimme-meter" className="text-lg font-medium">
        Uw slimme meter
      </h3>

      {issuedKey !== null && (
        <div className="flex flex-col gap-2">
          <p className="max-w-[60ch] text-sm">
            <code>{issuedKey.token}</code>
          </p>
          <p className="max-w-[60ch] text-sm">
            {apiBase + issuedKey.push_path}
          </p>
          <p className="max-w-[60ch] text-sm text-ink-muted">
            {KEY_SHOWN_ONCE}
          </p>
        </div>
      )}

      {issuedKey === null && status !== null && status.linked && (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            {/*
              `last_seen_label` and not `last_seen_at`: the API converted the
              stored UTC moment to Europe/Amsterdam and wrote it in Dutch,
              because `.semgrep/frontend.yml` forbids this page from
              constructing a `Date` at all. It also means two households
              read the same moment the same way, whatever their browser's
              locale is set to.
            */}
            {status.last_seen_label === null
              ? NOTHING_RECEIVED_YET
              : `Laatst binnengekomen: ${status.last_seen_label}`}
          </p>

          {check !== null && check.advice_token === null && (
            <div className="flex flex-col gap-2 border-l-2 border-hairline pl-3">
              {/*
                Shown only when this account has no advice of its own. The
                calculator posts anonymously and keeps doing so, so an advice
                made there has no owner and the meter has nothing to be held
                against.
              */}
              <p className="max-w-[60ch] text-sm">{NO_ADVICE_YET}</p>
              <label className="flex flex-col gap-1 text-sm">
                {ADVICE_LINK_LABEL}
                <input
                  type="text"
                  className="input"
                  value={adviceLink}
                  disabled={busy}
                  onChange={(event) => setAdviceLink(event.target.value)}
                />
              </label>
              <p>
                <button
                  type="button"
                  className="button-quiet"
                  disabled={busy || adviceLink.trim() === ""}
                  onClick={() => onClaim(adviceLink.trim())}
                >
                  {CLAIM_BUTTON}
                </button>
              </p>
            </div>
          )}

          {check !== null && check.check !== null && (
            <div className="flex flex-col gap-2 border-l-2 border-hairline pl-3">
              {/*
                Every sentence with a number in it comes from the API, which
                computed it. The band is shown rather than a single corrected
                figure: a figure inside it would not have produced this block
                at all, so the band is the finding and not a decoration on it.
              */}
              <p className="max-w-[60ch] text-sm">{check.check.message}</p>
              <p className="max-w-[60ch] text-sm text-ink-muted">
                {check.check.measured_over}
              </p>
              {check.check.installation_note !== null && (
                <p className="max-w-[60ch] text-sm">
                  {check.check.installation_note}
                </p>
              )}
              <p>
                <button
                  type="button"
                  className="button-accent"
                  disabled={busy}
                  onClick={onAccept}
                >
                  {check.check.accept_label}
                </button>
              </p>
              <p className="max-w-[60ch] text-sm text-ink-muted">
                {check.check.keep_own}
              </p>
            </div>
          )}
          <p>
            <button
              type="button"
              className="button-quiet"
              aria-expanded={confirmingUnlink}
              disabled={busy}
              onClick={() => setConfirmingUnlink(!confirmingUnlink)}
            >
              Ontkoppel
            </button>
          </p>
          {confirmingUnlink && (
            <div className="flex flex-col gap-2">
              <p className="max-w-[60ch] text-sm text-ink-muted">
                {UNLINK_CONSEQUENCE}
              </p>
              <p>
                <button
                  type="button"
                  className="button-accent"
                  disabled={busy}
                  onClick={confirmUnlink}
                >
                  Ontkoppelen bevestigen
                </button>
                {busy && (
                  <span role="status" aria-live="polite" className="sr-only">
                    Bezig.
                  </span>
                )}
              </p>
            </div>
          )}
        </div>
      )}

      {issuedKey === null &&
        status !== null &&
        !status.linked &&
        status.may_link && (
          <p>
            <button
              type="button"
              className="button-quiet"
              disabled={busy}
              onClick={onLink}
            >
              Koppel uw meter
            </button>
            {busy && (
              <span role="status" aria-live="polite" className="sr-only">
                Bezig.
              </span>
            )}
          </p>
        )}

      {issuedKey === null &&
        status !== null &&
        !status.linked &&
        !status.may_link && (
          <p className="max-w-[60ch] text-sm text-ink-muted">
            {REQUIREMENT_SENTENCE}
          </p>
        )}
    </section>
  );
}
