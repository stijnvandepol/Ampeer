"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { BandlessFigureView } from "@/components/band/BandlessFigureView";
import { ConfidenceBadge } from "@/components/band/ConfidenceBadge";
import { FirstStep, firstActionableRule } from "@/components/band/FirstStep";
import { HeadlineBand } from "@/components/band/HeadlineBand";
import { RouteSection } from "@/components/band/RouteSection";
import { ScenarioBandFigure } from "@/components/band/ScenarioBandFigure";
import { YearCarpet } from "@/components/carpet/YearCarpet";
import { getAdvice } from "@/lib/api";
import type { Advice, BatteryAdvice } from "@/lib/types";
import { tokenFromPath } from "../_advice/link";
import { describeApiError } from "../_flow/messages";
import { useLocationHref, useLocationPath } from "../_shell/browser";

/** Where the second round of questions lives, which is the first of the two calls to action. */
const REFINE_HREF = "/berekenen/?ronde=2";

/** Navigation, which is what this line is: it goes to the account page. */

/**
 * Whether the sizing detail is shown without the visitor asking for it.
 *
 * `battery.verdict` is the id of the storage rule the model landed on, and
 * ampeer_advice/rules.py has exactly three: CONSIDER_BATTERY,
 * BATTERY_DEPENDS_ON_PRICE and BATTERY_DOES_NOT_PAY_BACK. Only the first is the
 * model saying a battery is worth looking at, so only the first opens the block.
 *
 * WHY THIS EXISTS AT ALL. Measured on the built page at 1280x900, on the
 * fixture household whose verdict is BATTERY_DOES_NOT_PAY_BACK and whose rule
 * text says "niet de moeite waard": the headline band was 345px, the two free
 * routes 313px each, the storage route 219px, and this block 1365px. That is
 * 38.5% of the page and 2.2 times the two free routes together, and inside it
 * was a five-capacity table of what each size earns. It passed all five rules
 * from chapter 2, because "free routes first" was implemented as DOM order, and
 * order is the weakest form of precedence there is: a page can say no and then
 * spend most of itself on a sizing menu without breaking a single one of them.
 *
 * `CLAUDE.md` says the free routes come first "ook als ze niets opleveren voor
 * Ampeer". Nothing said the paid route may then take twice their space, so this
 * says it, and e2e/rules.spec.ts measures it: when the verdict is not a
 * recommendation, this block may not be taller than the free routes together.
 *
 * Nothing is hidden from anybody. Every figure is still in the document and one
 * click away, and the sentence that says why is the API's own, already on the
 * page above in the storage route.
 */
function verdictRecommendsABattery(verdict: string): boolean {
  // A comparison rather than a list of one, and that is not only brevity:
  // e2e/language.spec.ts harvests the initialiser of every variable to build the
  // user-visible string allowlist, and deliberately does not harvest the
  // operands of `===`. A rule id is a machine's word and does not belong in a
  // file whose header says a line in it is something a visitor reads.
  return verdict === "CONSIDER_BATTERY";
}

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
  const [open, setOpen] = useState(verdictRecommendsABattery(battery.verdict));
  const panelId = useId();
  return (
    <section aria-labelledby="batterij" className="flex flex-col gap-4">
      <h2 id="batterij" className="text-2xl font-bold">
        De batterij, doorgerekend
      </h2>

      {/*
        A button with aria-expanded rather than a native details, which is the
        one thing here that looks like the worse choice and is not. The scenario
        bands on this page already disclose themselves this way, so a details
        would be a second disclosure mechanism on one page; and the panel below
        contains ten of those buttons, which an assistive technology and a test
        both have to be able to reach in one pass from the outside in. It is
        rendered whether it is open or not, and hidden with the `hidden`
        attribute, so aria-controls names an element that exists.
      */}
      <button
        type="button"
        data-role="battery-detail"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((was) => !was)}
        className="self-start text-sm text-ink-muted underline underline-offset-4"
      >
        De hele doorrekening van de batterij
      </button>

      <div
        id={panelId}
        hidden={!open}
        className="flex flex-col gap-8 border-l-2 border-hairline pl-4"
      >
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
          <ScenarioBandFigure
            band={battery.break_even_cost_per_kwh}
            unit="eur_per_kwh"
          />
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
      </div>
    </section>
  );
}

/** The two calls to action. There is no third and neither leaves for a seller. */
function CallsToAction({ shareUrl }: { readonly shareUrl: string }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">(
    "idle",
  );

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
    <section
      aria-labelledby="verder"
      className="flex flex-col gap-5 border-t border-hairline pt-8"
    >
      <h2 id="verder" className="text-2xl font-bold">
        Verder
      </h2>

      <div className="flex flex-col gap-2">
        <p className="text-ink-muted">
          Vijf vragen erbij maken deze uitkomst scherper: of er overdag iemand
          thuis is, hoe de auto laadt, of er een warmtepomp is, wat voor
          contract u heeft en of er al opslag is.
        </p>
        <p>
          <Link href={REFINE_HREF} className="button-accent">
            Verfijn uw antwoord
          </Link>
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <p className="text-ink-muted">
          Deze link opent dit advies opnieuw, zonder account. Bewaar hem als u
          er later bij wilt.
        </p>
        {/*
          The link itself is no longer printed. A 60 character URL set in
          monospace wrapped across three lines on a phone and was the least
          readable way to offer the one thing this paragraph is about; the
          button below copies it, and the address bar already holds it for
          anybody who would rather select it by hand.
        */}
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
            {copyState === "failed" &&
              "Kopieren lukte niet. Neem de link hierboven over."}
          </span>
        </p>
      </div>
    </section>
  );
}

/** What the answer was computed with, so the reader can check it against the methodology. */
function Provenance({ advice }: { readonly advice: Advice }) {
  return (
    <section
      aria-labelledby="herkomst"
      className="flex flex-col gap-3 border-t border-hairline pt-8"
    >
      <h2
        id="herkomst"
        className="text-sm font-medium uppercase tracking-wide text-ink-muted"
      >
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
        {advice.modelled_consumption_kwh !== undefined && (
          <>
            <dt>Verbruik</dt>
            <dd>{advice.modelled_consumption_kwh.value} kWh</dd>
          </>
        )}
      </dl>
      {/*
        Why that consumption figure is what it is, in the API's own words.
        It is on the page rather than in a log because of what it lets a
        visitor catch: the question asks for consumption without a car and a
        heat pump, and somebody who answered it with the total off their annual
        bill is otherwise indistinguishable from somebody who answered it
        correctly. They lose between a quarter and half of their answer with
        nothing anywhere saying so. This is the one place they can see the
        number the model actually used and recognise it, or fail to.
      */}
      {advice.modelled_consumption_kwh !== undefined && (
        <p
          data-role="modelled-consumption"
          className="max-w-prose text-sm text-ink-muted"
        >
          {advice.modelled_consumption_kwh.basis_text}
        </p>
      )}
      {/*
        The sentence, not the enum. production_source arrives as "PVGIS" or
        "FALLBACK", which is for a machine; the API sends the Dutch beside it so
        the frontend never has to translate a model identifier. Which of the two
        it was changes how much weight the whole answer deserves, so it belongs
        on the page rather than in a log.
      */}
      <p
        data-role="production-source"
        className="max-w-prose text-sm text-ink-muted"
      >
        {advice.production_source_text}
      </p>
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
  const heading = useRef<HTMLHeadingElement>(null);
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

  // Focus follows the answer. Nothing on this page is a navigation, so without
  // this the visitor is left wherever they were when the request went out,
  // which for somebody arriving on a shared link is the top of a document that
  // has just changed underneath them.
  useEffect(() => {
    if (advice !== null) heading.current?.focus();
  }, [advice]);

  const failure =
    token === null
      ? "Deze pagina hoort bij een berekening en er staat er geen in de link."
      : fetchFailure;

  if (failure !== null) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-16">
        <h1 className="text-2xl font-bold">
          Dit advies konden wij niet laten zien
        </h1>
        <p role="alert" className="notice-danger">
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

  /*
   * One live region, present in both states, whose text changes.
   *
   * The loading sentence used to live in a paragraph that was replaced wholesale
   * by the answer. Removing a live region announces nothing, the arriving
   * content was inside no live region of its own, and focus did not move, so a
   * screen reader opening a shared link heard "Een moment" and then silence for
   * as long as the visitor was prepared to wait. Keeping one element in the same
   * place in the tree and changing its words is what makes the second sentence
   * an announcement rather than a repaint.
   *
   * It is visually hidden because the visible half is already said twice over:
   * by the heading while the answer is coming, and by the answer itself once it
   * is here.
   */
  const announcement =
    advice === null
      ? "Een moment, wij halen de doorrekening op die bij deze link hoort."
      : "Uw advies is opgehaald.";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-12 px-6 py-12">
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {advice === null ? (
        // Not a blank page and not a spinner without an end. It says what is
        // happening, and the failure branch above is what replaces it when the
        // request does not arrive, so there is no state in which this sentence
        // stays on the screen forever.
        <section className="flex flex-col gap-4 py-4">
          <h1 className="text-2xl font-bold">Uw advies wordt opgehaald</h1>
          <p className="text-ink-muted">{announcement}</p>
        </section>
      ) : (
        <>
          <section className="flex flex-col gap-6">
            {/*
              Deliberately the smallest thing in this block since 2026-09-15.
              It is a label for the band below it, not the message: it says
              what the page is about, and the page is about what to do. The
              largest element is now the instruction inside FirstStep, which is
              what somebody opened this for. It stays the h1 because it is
              still the page's name, and it stays the focus target because
              that is what a screen reader should land on.
            */}
            <h1
              ref={heading}
              tabIndex={-1}
              className="text-base font-medium text-ink-muted"
            >
              Wat het einde van de saldering u per jaar kost
            </h1>
            <ConfidenceBadge
              confidence={advice.confidence}
              label={advice.confidence_label}
            />

            <FirstStep routes={advice.routes} />

            <HeadlineBand
              band={advice.headline}
              confidence={advice.confidence}
              label={advice.confidence_label}
            />
          </section>

          {/*
            The evidence under the figure, and only when the API sent it. The
            field is optional on the wire, so a build talking to an older API
            renders the page it rendered before the field existed rather than a
            gap where a plate should be.
          */}
          {advice.year !== undefined && <YearCarpet year={advice.year} />}

          {advice.routes.map((route) => (
            <RouteSection
              key={route.route}
              route={route}
              bandShownAbove={firstActionableRule(advice.routes)?.rule_id}
            />
          ))}

          {advice.battery !== null && <BatteryBlock battery={advice.battery} />}

          <CallsToAction shareUrl={shareUrl} />

          {/*
            Until 2026-09-15 a link stood here to /account/#advies=<token>,
            the token in the fragment so that nginx, the access log and a
            Referer never saw it (decision 45's arrangement). It is gone with
            the footer's link, on the owner's decision, for the reason the
            footer gives: the account has nothing to offer a household yet.
            The fragment route in _account/fragment.ts still works, so the
            link can return as one line when it does.
          */}
          <Provenance advice={advice} />
        </>
      )}
    </div>
  );
}
