"use client";

import { useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { ChoiceQuestion } from "@/components/form/ChoiceQuestion";
import { NumberQuestion } from "@/components/form/NumberQuestion";
import { ALL_QUESTION_COUNT, ROUND_ONE_QUESTION_COUNT } from "@/components/form/Progress";
import { QuestionShell } from "@/components/form/QuestionShell";
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
  { value: "ARRIVAL", label: "Meestal bij thuiskomst, aan het begin van de avond" },
  { value: "SOLAR", label: "Overdag, op ons eigen overschot" },
];

const ROUND_ONE_TITLES = [
  "Wat zijn de eerste vier cijfers van uw postcode?",
  "Hoeveel wattpiek aan zonnepanelen ligt er?",
  "Hoe ligt het dak?",
  "Hoeveel stroom verbruikt u per jaar?",
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
  if (found === undefined) throw new Error(`lib/validation has no bound named ${name}`);
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
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  // The stored answers and the round both live in the browser, which the
  // machine that builds this page is not. Both come through
  // useSyncExternalStore rather than through an effect that sets state, so the
  // built HTML says "not known yet" and the browser's answer arrives in the
  // first commit instead of in a second render.
  const stored = useSyncExternalStore(subscribeAnswers, answersSnapshot, answersDuringBuild);
  const wantedRound = useSearchParam(ROUND_PARAM);

  function update(change: Partial<Answers>) {
    updateAnswers(change);
    setMissing(false);
  }

  if (stored === null || wantedRound === undefined) {
    // Not a blank page and not a spinner. The one thing this state can say
    // truthfully is that it is about to show questions, so it says that.
    return (
      <div className="mx-auto w-full max-w-2xl px-6 py-16">
        <p role="status">De vragen worden klaargezet.</p>
      </div>
    );
  }

  const answers = stored;
  const round: 1 | 2 = wantedRound === "2" ? 2 : 1;
  const titles = round === 1 ? ROUND_ONE_TITLES : ROUND_TWO_TITLES;
  const last = index === titles.length - 1;

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
      setMissing(true);
      return;
    }
    setMissing(false);
    if (last) {
      void submit();
      return;
    }
    setIndex(index + 1);
  }

  function back() {
    setMissing(false);
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
          value={answers.postcode4}
          min={range.min}
          max={range.max}
          unit=""
          integer
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
          onChange={(value) => update({ peakPowerWp: value })}
        />
      );
    }
    if (index === 2) {
      const range = bound("tilt_deg");
      return (
        <RoofPicker
          key="roof"
          azimuth={answers.azimuthDeg}
          tilt={answers.tiltDeg}
          tiltMin={range.min}
          tiltMax={range.max}
          onChange={(roof) =>
            update({ azimuthDeg: roof.azimuth, tiltDeg: roof.tilt, roofAnswered: true })
          }
        />
      );
    }
    const range = bound("annual_consumption_kwh");
    return (
      <NumberQuestion
        key="annual-consumption-kwh"
        id="annual-consumption-kwh"
        label="Verbruik per jaar"
        value={answers.annualConsumptionKwh}
        min={range.min}
        max={range.max}
        unit="kWh"
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
          onChange={(value) => update({ daytimeOccupancy: boolFromChoice(value) })}
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
                heatDemandKwh: boolFromChoice(value) ? answers.heatDemandKwh : null,
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
          onChange={(value) => update({ dynamicContract: boolFromChoice(value) })}
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
              batteryCapacityKwh: boolFromChoice(value) ? answers.batteryCapacityKwh : null,
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
            onChange={(value) => update({ batteryCapacityKwh: value })}
          />
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-6 py-16">
      <QuestionShell
        step={round === 1 ? index + 1 : ROUND_ONE_QUESTION_COUNT + index + 1}
        of={round === 1 ? ROUND_ONE_QUESTION_COUNT : ALL_QUESTION_COUNT}
        title={titles[index] ?? ""}
        nextLabel={last ? "Bereken" : "Volgende"}
        onBack={back}
        onNext={next}
      >
        {round === 1 ? roundOne() : roundTwo()}
        {missing && (
          <p role="alert" className="text-danger">
            Beantwoord deze vraag om verder te gaan.
          </p>
        )}
        {busy && <p role="status">Uw jaar wordt doorgerekend. Dit duurt even.</p>}
        {failure !== null && (
          <p role="alert" className="text-danger">
            {failure}
          </p>
        )}
      </QuestionShell>
    </div>
  );
}
