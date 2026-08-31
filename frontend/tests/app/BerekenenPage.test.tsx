import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../fixtures/advice-response.json";
import BerekenenPage from "@/app/berekenen/page";
import { ANSWERS_STORAGE_KEY } from "@/app/_flow/answers";
import { forgetCachedAnswers } from "@/app/_flow/store";

/**
 * The consumption field's label, in full.
 *
 * Spelled out rather than matched loosely, because the two words this test
 * would happily drop are the whole of decision 26. The model adds the car and
 * the heat pump on top of this figure, so a visitor who reads the total off
 * their annual bill is counted twice and loses between a quarter and half of
 * their answer with nothing reporting it. A `getByLabelText(/Verbruik/)` here
 * would keep passing through exactly the edit that undoes that.
 */
const CONSUMPTION_LABEL = "Verbruik per jaar, zonder auto en warmtepomp";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

/** Where window.location.assign would have taken the browser, without jsdom navigating. */
const assign = vi.fn();

/**
 * jsdom's Location.assign is a non-writable own property, so it cannot be
 * spied on. window.location itself is configurable, so the whole object is
 * replaced by one that reads through to the real one and answers assign()
 * with a recording. Reading through matters: history.pushState still drives
 * the real location, and the page reads the search string from it.
 */
const realLocation = window.location;

function stubAssign() {
  Object.defineProperty(window, "location", {
    configurable: true,
    get: () => ({
      get href() {
        return realLocation.href;
      },
      get pathname() {
        return realLocation.pathname;
      },
      get search() {
        return realLocation.search;
      },
      assign,
    }),
  });
}

function restoreLocation() {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: realLocation,
  });
}

function respondWith(body: unknown, status = 201) {
  return vi.fn(() =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    } as Response),
  );
}

/**
 * A fetch that has been sent and has not come back yet.
 *
 * The whole point of the busy state is the two and a half seconds in which the
 * answer is being computed, so the test has to be able to stand inside that
 * window and click.
 */
function respondLater(body: unknown, status = 201) {
  let release = () => {};
  const arrived = new Promise<void>((resolve) => {
    release = resolve;
  });
  const fetchSpy = vi.fn(() =>
    arrived.then(
      () =>
        ({
          ok: status >= 200 && status < 300,
          status,
          json: () => Promise.resolve(body),
        }) as Response,
    ),
  );
  return { fetchSpy, release: () => release() };
}

function goTo(path: string) {
  window.history.pushState({}, "", path);
}

beforeEach(() => {
  push.mockClear();
  assign.mockClear();
  window.sessionStorage.clear();
  forgetCachedAnswers();
  goTo("/berekenen/");
  stubAssign();
});

afterEach(() => {
  restoreLocation();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function answerRoundOne() {
  await userEvent.type(
    screen.getByLabelText("Postcode, alleen de vier cijfers"),
    "5401",
  );
  await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
  await userEvent.type(
    screen.getByLabelText("Vermogen van de installatie"),
    "4200",
  );
  await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
  await userEvent.click(screen.getByLabelText("Zuidwest"));
  await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
  await userEvent.type(screen.getByLabelText(CONSUMPTION_LABEL), "3400");
}

describe("the question flow", () => {
  it("asks four questions in round one and counts them as four", () => {
    // Orientation and tilt are one question about one roof. Counting them as
    // two would put every round-one estimate one confidence level too high,
    // because EstimateInputSerializer.QUESTION_COUNT is what decides the label.
    render(<BerekenenPage />);
    expect(screen.getByText("Vraag 1 van 4")).toBeInTheDocument();
  });

  it("will not advance past a question that has no answer, and says why", async () => {
    render(<BerekenenPage />);
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Beantwoord deze vraag",
    );
    expect(screen.getByText("Vraag 1 van 4")).toBeInTheDocument();
  });

  it("will not accept the roof nobody touched", async () => {
    // The compass starts pointing south and the slider starts at 35 degrees,
    // because they have to point somewhere. That is a starting position and
    // not an answer.
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByLabelText("Vermogen van de installatie"),
      "4200",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Beantwoord deze vraag",
    );
  });

  it("names the bound that was broken instead of calling the value invalid", async () => {
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "999",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("1000");
  });

  it("sends exactly the body the estimate serializer accepts", async () => {
    const fetchSpy = respondWith(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const call = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(call[0]).toContain("/api/advice/estimate/");
    expect(JSON.parse(String(call[1].body))).toEqual({
      // A string, because the API's field is a RegexField over four digits.
      postcode4: "5401",
      peak_power_wp: 4200,
      // Southwest, on the convention where zero is south and west is positive.
      azimuth_deg: 45,
      tilt_deg: 35,
      annual_consumption_kwh: 3400,
    });
  });

  it("goes to the shareable path rather than pushing a route that does not exist", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith(`/advies/${fixture.token}/`),
    );
  });

  it("says what the API said when it refused, and stays on the question", async () => {
    vi.stubGlobal(
      "fetch",
      respondWith({ postcode4: ["geen Nederlandse postcode"] }, 400),
    );
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));
    await waitFor(() =>
      expect(screen.getByText(/geen Nederlandse postcode/)).toBeInTheDocument(),
    );
    expect(assign).not.toHaveBeenCalled();
  });

  it("keeps a half filled form in sessionStorage, not in localStorage", async () => {
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "5401",
    );
    // Consumption data about a household, from which it can be read when
    // somebody is home. It should not outlive the tab.
    expect(window.sessionStorage.getItem(ANSWERS_STORAGE_KEY)).toContain(
      "5401",
    );
    expect(window.localStorage.getItem(ANSWERS_STORAGE_KEY)).toBeNull();
  });

  it("comes back to a form that was already half filled", () => {
    window.sessionStorage.setItem(
      ANSWERS_STORAGE_KEY,
      JSON.stringify({ postcode4: 5401, peakPowerWp: 4200 }),
    );
    forgetCachedAnswers();
    render(<BerekenenPage />);
    expect(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
    ).toHaveValue(5401);
  });

  it("checks no direction on the roof question before the visitor answers one", async () => {
    // South is the most common roof in this country and it used to arrive
    // checked, which is the one direction that could then not be given as an
    // answer: a radio that is already checked fires no change event.
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByLabelText("Vermogen van de installatie"),
      "4200",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).not.toBeChecked();
    }
  });

  it("takes south as an answer and sends it, without a detour past a wrong roof", async () => {
    const fetchSpy = respondWith(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByLabelText("Vermogen van de installatie"),
      "4200",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(screen.getByLabelText("Zuid"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByText("Vraag 4 van 4")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(CONSUMPTION_LABEL), "3400");
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const call = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toMatchObject({
      azimuth_deg: 0,
      tilt_deg: 35,
    });
  });

  it("does not take the tilt slider as an answer about the direction", async () => {
    // Half a question is not an answer. Without this the visitor who moves
    // only the slider posts azimuth_deg 0, and a south roof that is really an
    // east roof raises nothing anywhere: it answers about a house that does
    // not exist, with a self-consumption figure that is wrong by more than the
    // whole advice is worth.
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByLabelText("Vermogen van de installatie"),
      "4200",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    fireEvent.change(screen.getByRole("slider"), { target: { value: "40" } });
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Beantwoord deze vraag",
    );
    expect(screen.getByText("Vraag 3 van 4")).toBeInTheDocument();
  });

  it("computes once however often the button is pressed", async () => {
    // Four clicks used to be four POSTs and four full simulations, a fifth of
    // a household budget of twenty an hour, spent on one answer.
    const { fetchSpy, release } = respondLater(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    render(<BerekenenPage />);
    await answerRoundOne();
    const compute = screen.getByRole("button", { name: "Bereken" });
    await userEvent.click(compute);
    await userEvent.click(compute);
    await userEvent.click(compute);
    await userEvent.click(compute);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    release();
    await waitFor(() => expect(assign).toHaveBeenCalled());
  });

  it("says the request is under way instead of leaving the button live", async () => {
    const { fetchSpy, release } = respondLater(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));
    const compute = screen.getByRole("button", { name: "Bereken" });
    expect(compute).toBeDisabled();
    expect(compute).toHaveAttribute("aria-busy", "true");
    // Terug too: pressing it mid flight went back to question four and the
    // navigation then pulled the page away underneath.
    expect(screen.getByRole("button", { name: "Terug" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("doorgerekend");
    release();
    await waitFor(() => expect(assign).toHaveBeenCalled());
  });

  it("hands the buttons back when the API refused", async () => {
    vi.stubGlobal(
      "fetch",
      respondWith({ postcode4: ["geen Nederlandse postcode"] }, 400),
    );
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));
    await waitFor(() =>
      expect(screen.getByText(/geen Nederlandse postcode/)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Bereken" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Terug" })).toBeEnabled();
  });

  it("says one true thing about a number it refused, not two things", async () => {
    // The field already says which bound was passed. Adding "beantwoord deze
    // vraag om verder te gaan" underneath says the question was not answered,
    // which is false: it was answered with something unusable.
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.clear(screen.getByLabelText(CONSUMPTION_LABEL));
    await userEvent.type(screen.getByLabelText(CONSUMPTION_LABEL), "99999999");
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));
    const alerts = screen.getAllByRole("alert");
    expect(alerts).toHaveLength(1);
    expect(alerts[0]).toHaveTextContent(/hoogstens/i);
    expect(
      screen.queryByText("Beantwoord deze vraag om verder te gaan."),
    ).toBeNull();
  });

  it("still says the question is unanswered when the field is empty", async () => {
    // The other half of the same branch: an empty field has no message of its
    // own, so the flow has to be the one that speaks.
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "999",
    );
    await userEvent.clear(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Beantwoord deze vraag",
    );
  });

  it("walks back to the previous question, and off the flow from the first", async () => {
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByLabelText("Postcode, alleen de vier cijfers"),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByText("Vraag 2 van 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Terug" }));
    expect(screen.getByText("Vraag 1 van 4")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Terug" }));
    expect(push).toHaveBeenCalledWith("/");
  });
});

describe("round two", () => {
  beforeEach(() => {
    window.sessionStorage.setItem(
      ANSWERS_STORAGE_KEY,
      JSON.stringify({
        postcode4: 5401,
        peakPowerWp: 4200,
        azimuthDeg: 45,
        tiltDeg: 35,
        roofAnswered: true,
        annualConsumptionKwh: 3400,
      }),
    );
    forgetCachedAnswers();
    goTo("/berekenen/?ronde=2");
  });

  it("continues the count from where round one stopped", () => {
    render(<BerekenenPage />);
    expect(screen.getByText("Vraag 5 van 9")).toBeInTheDocument();
  });

  it("asks for the detail behind every yes, and refuses to go on without it", async () => {
    render(<BerekenenPage />);
    await userEvent.click(screen.getByLabelText("Ja"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));

    await userEvent.click(
      screen.getByLabelText("Overdag, op ons eigen overschot"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));

    // The heat pump pair. The serializer refuses one without the other, so the
    // form does too, on the screen where it can be fixed.
    await userEvent.click(screen.getByLabelText("Ja"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Beantwoord deze vraag",
    );
    await userEvent.type(
      screen.getByLabelText("Hoeveel stroom gebruikt de warmtepomp per jaar?"),
      "2400",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByText("Vraag 8 van 9")).toBeInTheDocument();
  });

  it("sends the nine values as the refine serializer wants them", async () => {
    const fetchSpy = respondWith(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    render(<BerekenenPage />);

    await userEvent.click(screen.getByLabelText("Nee"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(
      screen.getByLabelText("Wij hebben geen elektrische auto"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(screen.getByLabelText("Nee"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(screen.getByLabelText("Ja"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(screen.getByLabelText("Nee"));
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const call = fetchSpy.mock.calls[0] as unknown as [string, RequestInit];
    expect(call[0]).toContain("/api/advice/refine/");
    expect(JSON.parse(String(call[1].body))).toEqual({
      postcode4: "5401",
      peak_power_wp: 4200,
      azimuth_deg: 45,
      tilt_deg: 35,
      annual_consumption_kwh: 3400,
      daytime_occupancy: false,
      has_ev: false,
      ev_behaviour: null,
      has_heat_pump: false,
      heat_demand_kwh: null,
      dynamic_contract: true,
      has_battery: false,
      battery_capacity_kwh: null,
    });
  });

  it("drops a capacity when the battery answer goes back to no", async () => {
    render(<BerekenenPage />);
    for (const label of [
      "Nee",
      "Wij hebben geen elektrische auto",
      "Nee",
      "Nee",
    ]) {
      await userEvent.click(screen.getByLabelText(label));
      await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    }
    await userEvent.click(screen.getByLabelText("Ja"));
    await userEvent.type(
      screen.getByLabelText("Hoe groot is de batterij?"),
      "5",
    );
    await userEvent.click(screen.getByLabelText("Nee"));
    // Two fields that disagree let whichever one is read first decide the
    // result, which is why the serializer refuses the pair and why this
    // clears it rather than hiding it.
    expect(screen.queryByLabelText("Hoe groot is de batterij?")).toBeNull();
    expect(window.sessionStorage.getItem(ANSWERS_STORAGE_KEY)).toContain(
      '"batteryCapacityKwh":null',
    );
  });
});
