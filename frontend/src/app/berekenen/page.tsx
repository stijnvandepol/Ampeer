"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChoiceQuestion } from "@/components/form/ChoiceQuestion";
import { NumberQuestion } from "@/components/form/NumberQuestion";
import {
  ALL_QUESTION_COUNT,
  ROUND_ONE_QUESTION_COUNT,
} from "@/components/form/Progress";
import { NOTE_ID, QuestionShell } from "@/components/form/QuestionShell";
import { RoofPicker } from "@/components/form/RoofPicker";
import { postEstimate, postRefine } from "@/lib/api";
import { BOUNDS, type Bound } from "@/lib/validation";
import { advicePath } from "../_advice/link";
import {
  stepComplete,
  toEstimateInput,
  toRefineInput,
  type Answers,
  type EvAnswer,
} from "../_flow/answers";
import { describeApiError } from "../_flow/messages";
import {
  answersDuringBuild,
  answersSnapshot,
  subscribeAnswers,
  updateAnswers,
} from "../_flow/store";
import { useSearchParam } from "../_shell/browser";

/** `/berekenen/?ronde=2` continues with the five questions round one leaves out. */
const ROUND_PARAM = "ronde";

const YES_NO = [
  { value: "ja", label: "Ja" },
  { value: "nee", label: "Nee" },
] as const;

const EV_OPTIONS: readonly { value: EvAnswer; label: string }[] = [
  { value: "NONE", label: "Wij hebben geen elektrische auto" },
  { value: "NIGHT", label: "Meestal 's nachts" },
  {
    value: "ARRIVAL",
    label: "Meestal bij thuiskomst, aan het begin van de avond",
  },
  { value: "SOLAR", label: "Overdag, op ons eigen overschot" },
];

const ROUND_ONE_TITLES = [
  "Wat zijn de eerste vier cijfers van uw postcode?",
  "Hoeveel wattpiek aan zonnepanelen ligt er?",
  "Hoe ligt het dak?",
  "Hoeveel stroom verbruikt u per jaar, zonder auto en warmtepomp?",
] as const;

/**
 * What a question means, where the title alone can be read two ways.
 *
 * Only one question has one, and it is the question this whole mechanism was
 * added for. The model scales the base profile to the figure entered here and
 * then ADDS the car and the heat pump on top, so the figure being asked for is
 * consumption without them. A visitor who charges at home and reads the total
 * off their annual bill has the car in that number already, and the model then
 * counts it twice: measured on the reference household, 447 euro where the
 * truth is 624, and four of six golden households also lose a fired rule.
 *
 * Saying it here is the whole repair. It was chosen over carving the assets
 * back out inside the model, which produces the same figure to the cent but
 * puts the largest single correction in the product where the visitor cannot
 * see it. See decision 26 in docs/decisions.md.
 *
 * "Een schatting is genoeg" is measured rather than reassuring. Chapter 4 of
 * docs/methodologie.md carries the sensitivity, remeasured on the shipping
 * model on 2026-08-31: being 500 kWh out costs about 31 euro with a heat pump
 * and 46 with a car, against the 176 to 184 that entering the bill total
 * costs. A visitor who abandons the question because they cannot produce an
 * exact figure is worse off than one who estimates, by a factor of about four.
 */
const ROUND_ONE_NOTES: readonly (string | undefined)[] = [
  undefined,
  undefined,
  undefined,
  "Zonder het laden van een elektrische auto en zonder een warmtepomp, ook als u die wel heeft. Daar vragen wij zo apart naar en wij tellen ze er dan zelf bij op. Staan ze op uw jaarnota, haal ze er dan af. Een schatting is genoeg.",
] as const;

const ROUND_TWO_TITLES = [
  "Is er overdag meestal iemand thuis?",
  "Wanneer laadt uw elektrische auto?",
  "Heeft u een warmtepomp?",
  "Heeft u een dynamisch energiecontract?",
  "Heeft u een thuisbatterij?",
] as const;

/**
 * The bound, or a failure, never a second copy of the number.
 *
 * `lib/validation` mirrors `backend/advice/serializers.py` and says out loud
 * that the API wins if the two disagree. Writing `?? 1000` beside a lookup
 * here would create a third copy, in the file furthest from both, and it is
 * the copy nobody would think to check. This cannot fire while every name
 * below is in BOUNDS; if a rename makes it fire, that is a form silently
 * accepting what the API refuses, and it should be loud.
 */
function bound(name: string): Bound {
  const found = BOUNDS[name];
  if (found === undefined)
    throw new Error(`lib/validation has no bound named ${name}`);
  return found;
}

function boolFromChoice(value: string): boolean {
  return value === "ja";
}

function choiceFromBool(value: boolean | null): string | null {
  if (value === null) return null;
  return value ? "ja" : "nee";
}

/**
 * The question flow: four questions, and then the five that sharpen them.
 *
 * Round one runs on its own and produces an advice. Round two is reached from
 * that advice, which is why the two live in one page behind a query parameter
 * rather than in two: they share the answers, the storage and the components,
 * and the only thing that differs is which five questions are on the screen.
 *
 * Nothing here writes advice text. Every Dutch sentence on this page is a
 * question, a label, or a message about the form itself.
 */
export default function BerekenenPage() {
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const [missing, setMissing] = useState(false);
  /**
   * Whether the field on this screen is refusing what the visitor put in it.
   *
   * A rejected number reaches this page as null, which is the same thing an
   * empty field reports, and the two need different messages: the field
   * already says which bound was passed, so repeating "beantwoord deze vraag"
   * underneath says the question was not answered, which is false. One flag
   * and not one per question, because there is one field on the screen.
   */
  const [refusing, setRefusing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  // The stored answers and the round both live in the browser, which the
  // machine that builds this page is not. Both come through
  // useSyncExternalStore rather than through an effect that sets state, so the
  // built HTML says "not known yet" and the browser's answer arrives in the
  // first commit instead of in a second render.
  const stored = useSyncExternalStore(
    subscribeAnswers,
    answersSnapshot,
    answersDuringBuild,
  );
  const wantedRound = useSearchParam(ROUND_PARAM);

  function update(change: Partial<Answers>) {
    updateAnswers(change);
    setMissing(false);
  }

  if (stored === null || wantedRound === undefined) {
    // Not a blank page and not a spinner. The one thing this state can say
    // truthfully is that it is about to show questions, so it says that.
    return (
      <div className="mx-auto w-full max-w-[var(--shell-max)] px-6 py-16">
        <p role="status">De vragen worden klaargezet.</p>
      </div>
    );
  }

  const answers = stored;
  const round: 1 | 2 = wantedRound === "2" ? 2 : 1;
  const titles = round === 1 ? ROUND_ONE_TITLES : ROUND_TWO_TITLES;
  const last = index === titles.length - 1;

  /*
   * Round two with no round one behind it, caught before it starts.
   *
   * The answers live in sessionStorage, which is per tab, and the advice page's
   * only route onward is a link to `?ronde=2`. So somebody who saves their
   * link, closes the tab and comes back the next day, which is the journey the
   * product asks them to make, arrives here with nothing stored.
   *
   * What happened before 2026-09-01: the five questions were asked and
   * answered, the progress bar claimed "Vraag 5 van 9" for four questions that
   * were never answered, and pressing Bereken on the last one produced
   * "Beantwoord deze vraag om verder te gaan" over a question that visibly was.
   * `toRefineInput` returned null because the base was missing, and the flow
   * reported that against whichever question happened to be on screen. Terug
   * walked back through five answered questions and then off the form. Nothing
   * anywhere named the actual problem.
   *
   * Checked here rather than at submit, because the honest moment to say "this
   * needs the first four questions" is before asking five more.
   */
  if (round === 2 && toEstimateInput(answers) === null) {
    return (
      <div className="mx-auto w-full max-w-[var(--shell-max)] px-6 py-16">
        <div className="flex w-full max-w-2xl flex-col gap-4">
          <h1 className="text-2xl">De eerste vier vragen ontbreken nog</h1>
          <p className="max-w-[60ch] text-ink-muted">
            De vijf vragen hierna maken een antwoord scherper dat er al is, en
            in dit browservenster staat dat antwoord er nog niet. Dat gebeurt
            als u uw bewaarde link in een nieuw venster opent of op een ander
            apparaat.
          </p>
          <p className="max-w-[60ch] text-ink-muted">
            Beantwoord eerst de vier vragen over uw huis. Daarna kunt u
            verfijnen.
          </p>
          <p>
            <Link href="/berekenen/" className="button-accent">
              Beantwoord vier vragen
            </Link>
          </p>
        </div>
      </div>
    );
  }

  async function submit() {
    setBusy(true);
    setFailure(null);
    try {
      // Split rather than a ternary over one variable: the two inputs are two
      // types, and narrowing a union back apart afterwards would need a cast
      // over exactly the values the API validates.
      let token: string;
      if (round === 1) {
        const input = toEstimateInput(answers);
        if (input === null) {
          setBusy(false);
          setMissing(true);
          return;
        }
        token = (await postEstimate(input)).token;
      } else {
        const input = toRefineInput(answers);
        if (input === null) {
          setBusy(false);
          setMissing(true);
          return;
        }
        token = (await postRefine(input)).token;
      }
      // A full navigation and not router.push. With output: "export" there is
      // one built advice page and the token lives in the path after it, so
      // /advies/<token>/ is not a route the app router knows; the reverse
      // proxy is what resolves it. Asking the client router for it would get a
      // not-found for a page that exists.
      window.location.assign(advicePath(token));
    } catch (error) {
      setBusy(false);
      setFailure(describeApiError(error));
    }
  }

  function next() {
    if (!stepComplete(answers, round, index)) {
      // Only when the question is genuinely unanswered. A field that is
      // already showing which bound was passed has said the true thing, and a
      // second message under it saying the question was not answered is a
      // false one printed over a correct one.
      setMissing(!refusing);
      return;
    }
    setMissing(false);
    if (last) {
      void submit();
      return;
    }
    setRefusing(false);
    setIndex(index + 1);
  }

  function back() {
    setMissing(false);
    setRefusing(false);
    setFailure(null);
    if (index === 0) {
      // The first question has nowhere to go back to inside the flow. The
      // landing page is somewhere rather than nowhere, and the browser's own
      // back button still returns to whatever came before.
      router.push("/");
      return;
    }
    setIndex(index - 1);
  }

  /*
   * Every question carries a key, and it is load bearing rather than tidy.
   * Two consecutive questions that are both a NumberQuestion sit at the same
   * position in the tree, so without a key React keeps the component mounted
   * and the previous question's draft text stays in the field: typing 4200 on
   * question two after 5401 on question one produced 54014200 watt-peak, with
   * the visitor watching. A key makes the second question a different element
   * and remounts it empty.
   */
  function roundOne() {
    if (index === 0) {
      const range = bound("postcode4");
      return (
        <NumberQuestion
          key="postcode4"
          id="postcode4"
          label="Postcode, alleen de vier cijfers"
          // The one field in this flow with an honest autofill token. There is
          // no autocomplete name for "watt-peak on my roof", and inventing one
          // would hand a browser's saved address data to a field that is not an
          // address.
          autoComplete="postal-code"
          value={answers.postcode4}
          min={range.min}
          max={range.max}
          unit=""
          integer
          onRefusal={setRefusing}
          onChange={(value) => update({ postcode4: value })}
        />
      );
    }
    if (index === 1) {
      const range = bound("peak_power_wp");
      return (
        <NumberQuestion
          key="peak-power-wp"
          id="peak-power-wp"
          label="Vermogen van de installatie"
          value={answers.peakPowerWp}
          min={range.min}
          max={range.max}
          unit="wattpiek"
          integer
          onRefusal={setRefusing}
          onChange={(value) => update({ peakPowerWp: value })}
        />
      );
    }
    if (index === 2) {
      const range = bound("tilt_deg");
      return (
        <RoofPicker
          key="roof"
          // The stored azimuth only counts as a direction once the visitor has
          // chosen one. Handing the default down as if it were an answer is
          // what put a checked South radio in front of somebody who had said
          // nothing, and a checked radio cannot then be chosen: clicking it
          // fires no change event.
          azimuth={answers.roofAnswered ? answers.azimuthDeg : null}
          tilt={answers.tiltDeg}
          tiltMin={range.min}
          tiltMax={range.max}
          onChange={(roof) =>
            update(
              roof.azimuth === null
                ? // The slider moved and no direction has been chosen. The
                  // tilt is worth keeping; the question stays unanswered,
                  // because an east roof simulated as a south roof raises
                  // nothing and answers about a different house.
                  { tiltDeg: roof.tilt }
                : {
                    azimuthDeg: roof.azimuth,
                    tiltDeg: roof.tilt,
                    roofAnswered: true,
                  },
            )
          }
        />
      );
    }
    const range = bound("annual_consumption_kwh");
    return (
      <NumberQuestion
        key="annual-consumption-kwh"
        id="annual-consumption-kwh"
        label="Verbruik per jaar, zonder auto en warmtepomp"
        // The note above this question is the sentence that stops a visitor
        // entering their annual bill total, which is worth 176 to 184 euro of
        // accuracy. It sat in a paragraph nothing pointed at, so a screen
        // reader user tabbing into the field never heard it.
        describedBy={NOTE_ID}
        value={answers.annualConsumptionKwh}
        min={range.min}
        max={range.max}
        unit="kWh"
        onRefusal={setRefusing}
        onChange={(value) => update({ annualConsumptionKwh: value })}
      />
    );
  }

  function roundTwo() {
    if (index === 0) {
      return (
        <ChoiceQuestion
          key="daytime-occupancy"
          id="daytime-occupancy"
          label="Is er op een doordeweekse dag meestal iemand thuis?"
          options={YES_NO}
          value={choiceFromBool(answers.daytimeOccupancy)}
          onChange={(value) =>
            update({ daytimeOccupancy: boolFromChoice(value) })
          }
        />
      );
    }
    if (index === 1) {
      return (
        <ChoiceQuestion
          key="ev"
          id="ev"
          label="Wanneer laadt de auto?"
          options={EV_OPTIONS}
          value={answers.ev}
          onChange={(value) => {
            // Matched against the list rather than cast to it. The cast would
            // be safe today and would stay compiling on the day somebody adds
            // an option whose value is not an EVChargingBehaviour name.
            const chosen = EV_OPTIONS.find((option) => option.value === value);
            if (chosen !== undefined) update({ ev: chosen.value });
          }}
        />
      );
    }
    if (index === 2) {
      const range = bound("heat_demand_kwh");
      return (
        <div key="heat-pump" className="flex flex-col gap-6">
          <ChoiceQuestion
            id="heat-pump"
            label="Is er een warmtepomp?"
            options={YES_NO}
            value={choiceFromBool(answers.heatPump)}
            onChange={(value) =>
              update({
                heatPump: boolFromChoice(value),
                // A demand without a heat pump is two fields that disagree,
                // and the serializer refuses the pair. Clearing it here means
                // the visitor never has to be told about it.
                heatDemandKwh: boolFromChoice(value)
                  ? answers.heatDemandKwh
                  : null,
              })
            }
          />
          {answers.heatPump === true && (
            <NumberQuestion
              id="heat-demand-kwh"
              label="Hoeveel stroom gebruikt de warmtepomp per jaar?"
              value={answers.heatDemandKwh}
              min={range.min}
              max={range.max}
              unit="kWh"
              onRefusal={setRefusing}
              onChange={(value) => update({ heatDemandKwh: value })}
            />
          )}
        </div>
      );
    }
    if (index === 3) {
      return (
        <ChoiceQuestion
          key="dynamic-contract"
          id="dynamic-contract"
          label="Is uw contract dynamisch, met een prijs per uur?"
          options={YES_NO}
          value={choiceFromBool(answers.dynamicContract)}
          onChange={(value) =>
            update({ dynamicContract: boolFromChoice(value) })
          }
        />
      );
    }
    const range = bound("battery_capacity_kwh");
    return (
      <div key="battery" className="flex flex-col gap-6">
        <ChoiceQuestion
          id="battery"
          label="Is er al een thuisbatterij?"
          options={YES_NO}
          value={choiceFromBool(answers.battery)}
          onChange={(value) =>
            update({
              battery: boolFromChoice(value),
              batteryCapacityKwh: boolFromChoice(value)
                ? answers.batteryCapacityKwh
                : null,
            })
          }
        />
        {answers.battery === true && (
          <NumberQuestion
            id="battery-capacity-kwh"
            label="Hoe groot is de batterij?"
            value={answers.batteryCapacityKwh}
            min={range.min}
            max={range.max}
            unit="kWh"
            onRefusal={setRefusing}
            onChange={(value) => update({ batteryCapacityKwh: value })}
          />
        )}
      </div>
    );
  }

  return (
    /*
      The frame is the site's width and the column inside it is a form's width.
      Both were max-w-2xl and centred, so the questions sat 176 pixels to the
      right of the wordmark above them on a 1440 wide screen: two centred
      columns of different widths never share an edge. A form should not be
      1024 pixels wide, and it should start where everything else on the site
      starts.
    */
    <div className="mx-auto w-full max-w-[var(--shell-max)] px-6 py-16">
      <div className="flex w-full max-w-2xl flex-col gap-6">
        {/*
        The flow is the page; each question is a section of it. So the h1 names
        the task and stays put, and QuestionShell's h2 is the question that
        changes underneath it. Without this the route had no first-level
        heading at all, and the axe run did not say so because the tag filter
        the project uses excludes page-has-heading-one. A gate that is green
        because a rule is switched off is not a gate.
      */}
        <h1 className="text-sm font-medium uppercase tracking-wide text-ink-muted">
          Uw gegevens
        </h1>
        <QuestionShell
          step={round === 1 ? index + 1 : ROUND_ONE_QUESTION_COUNT + index + 1}
          of={round === 1 ? ROUND_ONE_QUESTION_COUNT : ALL_QUESTION_COUNT}
          title={titles[index] ?? ""}
          note={round === 1 ? ROUND_ONE_NOTES[index] : undefined}
          nextLabel={last ? "Bereken" : "Volgende"}
          busy={busy}
          onBack={back}
          onNext={next}
        >
          {round === 1 ? roundOne() : roundTwo()}
          {missing && (
            <p role="alert" className="text-danger">
              Beantwoord deze vraag om verder te gaan.
            </p>
          )}
          {busy && (
            <p role="status">Uw jaar wordt doorgerekend. Dit duurt even.</p>
          )}
          {failure !== null && (
            <p role="alert" className="text-danger">
              {failure}
            </p>
          )}
        </QuestionShell>
      </div>
    </div>
  );
}
