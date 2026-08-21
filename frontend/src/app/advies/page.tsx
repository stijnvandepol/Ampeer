"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BandlessFigureView } from "@/components/band/BandlessFigureView";
import { HeadlineBand } from "@/components/band/HeadlineBand";
import { RouteSection } from "@/components/band/RouteSection";
import { ScenarioBandFigure } from "@/components/band/ScenarioBandFigure";
import { getAdvice } from "@/lib/api";
import type { Advice, BatteryAdvice } from "@/lib/types";
import { tokenFromPath } from "../_advice/link";
import { describeApiError } from "../_flow/messages";
import { useLocationHref, useLocationPath } from "../_shell/browser";

/** Where the second round of questions lives, which is the first of the two calls to action. */
const REFINE_HREF = "/berekenen/?ronde=2";

/**
 * The battery block, when the model produced one.
 *
 * Every figure here either carries its band or carries the sentence that says
 * why it has none. `sized_capacity_kwh` is the second kind: the model chose it
 * from five simulated capacities rather than estimating it, and it sends the
 * sentence that says so. Drawing a margin around it would be this page
 * answering a question the model declined to answer.
 *
 * `battery.verdict` is deliberately not rendered. It is a rule id, which is an
 * English identifier for a machine; the Dutch that goes with it travels in the
 * matching entry of `routes` and is already on the page above.
 */
function BatteryBlock({ battery }: { readonly battery: BatteryAdvice }) {
  return (
    <section aria-labelledby="batterij" className="flex flex-col gap-8">
      <h2 id="batterij" className="text-xl font-medium">
        De batterij, doorgerekend
      </h2>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Maat waarop dit is gebaseerd
        </h3>
        <BandlessFigureView figure={battery.sized_capacity_kwh} unit="kwh" />
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Wat die maat per jaar oplevert
        </h3>
        <ScenarioBandFigure band={battery.annual_saving_eur} unit="eur" />
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Terugverdientijd
        </h3>
        <ScenarioBandFigure band={battery.payback_years} unit="years" />
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Prijs per kWh waarbij hij precies uit kan
        </h3>
        <ScenarioBandFigure band={battery.break_even_cost_per_kwh} unit="eur_per_kwh" />
      </div>

      <div className="flex flex-col gap-4">
        <h3 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Wat andere maten zouden opleveren
        </h3>
        <ul className="flex flex-col gap-5">
          {battery.curve.map(([capacity, band]) => (
            <li key={capacity} className="flex flex-col gap-2">
              {/*
               * The capacity is a coordinate and not a figure with a margin:
               * it names which simulation the band beside it came from. The
               * band is the answer, and it is the thing that carries a range.
               */}
              <p className="text-sm text-ink-muted">{capacity} kWh opslag</p>
              <ScenarioBandFigure band={band} unit="eur" />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** The two calls to action. There is no third and neither leaves for a seller. */
function CallsToAction({ shareUrl }: { readonly shareUrl: string }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyState("copied");
    } catch {
      // A browser may refuse the clipboard without asking anybody. The link is
      // on the screen either way, so the fallback is telling the visitor to
      // take it from there rather than pretending the copy worked.
      setCopyState("failed");
    }
  }

  return (
    <section aria-labelledby="verder" className="flex flex-col gap-5 border-t border-hairline pt-8">
      <h2 id="verder" className="text-xl font-medium">
        Verder
      </h2>

      <div className="flex flex-col gap-2">
        <p className="text-ink-muted">
          Vijf vragen erbij maken deze uitkomst scherper: of er overdag iemand thuis is, hoe de
          auto laadt, of er een warmtepomp is, wat voor contract u heeft en of er al opslag is.
        </p>
        <p>
          <Link
            href={REFINE_HREF}
            className="inline-flex rounded-md bg-accent px-5 py-3 font-medium text-on-accent"
          >
            Verfijn uw antwoord
          </Link>
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-ink-muted">
          Deze link opent dit advies opnieuw, zonder account. Bewaar hem als u er later bij wilt.
        </p>
        <p className="break-all font-mono text-sm text-ink">{shareUrl}</p>
        <p className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => void copy()}
            className="rounded-md border border-border-strong px-4 py-2 font-medium text-ink"
          >
            Kopieer deze link
          </button>
          <span role="status" className="text-sm text-ink-muted">
            {copyState === "copied" && "Gekopieerd."}
            {copyState === "failed" && "Kopieren lukte niet. Neem de link hierboven over."}
          </span>
        </p>
      </div>
    </section>
  );
}

/** What the answer was computed with, so the reader can check it against the methodology. */
function Provenance({ advice }: { readonly advice: Advice }) {
  return (
    <section aria-labelledby="herkomst" className="flex flex-col gap-3 border-t border-hairline pt-8">
      <h2 id="herkomst" className="text-sm font-medium uppercase tracking-wide text-ink-muted">
        Waarmee gerekend is
      </h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm text-ink-muted">
        <dt>Motorversie</dt>
        <dd>{advice.engine_version}</dd>
        <dt>Adviesversie</dt>
        <dd>{advice.advice_version}</dd>
        <dt>Verbruiksjaar</dt>
        <dd>{advice.profile_year}</dd>
        <dt>Weerjaar</dt>
        <dd>{advice.weather_year}</dd>
      </dl>
    </section>
  );
}

/**
 * The advice, read back from the link.
 *
 * The token comes out of the path rather than out of a query string, so the
 * URL a visitor sends to somebody else looks like a page and not like a form
 * submission. See `_advice/link.ts` for the one line of proxy configuration
 * that arrangement costs.
 *
 * The routes render in the order the API sent them and in no other. Sorting
 * them here would make this file responsible for a promise the API already
 * keeps, in a second place, where the two can disagree. `ROUTE_ORDER` in
 * `lib/types.ts` is what that order is expected to be, and `e2e/rules.spec.ts`
 * checks the page against it; neither is used to rearrange anything.
 *
 * This page writes no advice text. Every sentence about the household comes
 * from the API.
 */
export default function AdviesPage() {
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [fetchFailure, setFetchFailure] = useState<string | null>(null);
  const shareUrl = useLocationHref();
  const path = useLocationPath();
  // Three states, not two. Undefined is the built HTML, where there is no URL
  // to read; null is a URL with no token in it. Collapsing them would put the
  // "this link has no advice in it" screen into every static build.
  const token = path === undefined ? undefined : tokenFromPath(path);

  useEffect(() => {
    if (token === undefined || token === null) return;
    let current = true;
    getAdvice(token)
      .then((result) => {
        if (current) setAdvice(result);
      })
      .catch((error: unknown) => {
        if (current) setFetchFailure(describeApiError(error, "link"));
      });
    return () => {
      current = false;
    };
  }, [token]);

  const failure =
    token === null
      ? "Deze pagina hoort bij een berekening en er staat er geen in de link."
      : fetchFailure;

  if (failure !== null) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-16">
        <h1 className="text-2xl font-bold">Dit advies konden wij niet laten zien</h1>
        <p role="alert" className="text-danger">
          {failure}
        </p>
        <p>
          <Link href="/berekenen/" className="underline underline-offset-4">
            Begin een nieuwe berekening
          </Link>
        </p>
      </div>
    );
  }

  if (advice === null) {
    // Not a blank page and not a spinner without an end. It says what is
    // happening, and the failure branch above is what replaces it when the
    // request does not arrive, so there is no state in which this sentence
    // stays on the screen forever.
    return (
      <div className="mx-auto w-full max-w-3xl px-6 py-16">
        <h1 className="text-2xl font-bold">Uw advies wordt opgehaald</h1>
        <p role="status" className="mt-4 text-ink-muted">
          Een moment, wij halen de doorrekening op die bij deze link hoort.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-12 px-6 py-12">
      <section className="flex flex-col gap-6">
        <h1 className="text-2xl font-bold">Wat het einde van de saldering u per jaar kost</h1>
        <HeadlineBand
          band={advice.headline}
          confidence={advice.confidence}
          label={advice.confidence_label}
        />
      </section>

      {advice.routes.map((route) => (
        <RouteSection key={route.route} route={route} />
      ))}

      {advice.battery !== null && <BatteryBlock battery={advice.battery} />}

      <CallsToAction shareUrl={shareUrl} />
      <Provenance advice={advice} />
    </div>
  );
}
