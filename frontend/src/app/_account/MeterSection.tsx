"use client";

import { useState } from "react";
import type { MeterKey, MeterStatus } from "@/lib/accounts";

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

const UNLINK_CONSEQUENCE = "Na het ontkoppelen zijn de metingen van deze meter weg.";

/** `Europe/Amsterdam`, per the timestamp convention in `CLAUDE.md`. */
function formatLastSeen(iso: string): string {
  return new Date(iso).toLocaleString("nl-NL", {
    timeZone: "Europe/Amsterdam",
  });
}

export interface MeterSectionProps {
  readonly status: MeterStatus | null;
  readonly issuedKey: MeterKey | null;
  readonly apiBase: string;
  readonly busy: boolean;
  readonly onLink: () => void;
  readonly onUnlink: () => void;
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
}: MeterSectionProps) {
  const [confirmingUnlink, setConfirmingUnlink] = useState(false);

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
          <p className="max-w-[60ch] text-sm">{apiBase + issuedKey.push_path}</p>
          <p className="max-w-[60ch] text-sm text-ink-muted">
            {KEY_SHOWN_ONCE}
          </p>
        </div>
      )}

      {issuedKey === null && status !== null && status.linked && (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            {status.last_seen_at === null
              ? NOTHING_RECEIVED_YET
              : `Laatst binnengekomen: ${formatLastSeen(status.last_seen_at)}`}
          </p>
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

      {issuedKey === null && status !== null && !status.linked && status.may_link && (
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

      {issuedKey === null && status !== null && !status.linked && !status.may_link && (
        <p className="max-w-[60ch] text-sm text-ink-muted">
          {REQUIREMENT_SENTENCE}
        </p>
      )}
    </section>
  );
}
