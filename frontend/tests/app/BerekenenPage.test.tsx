import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../fixtures/advice-response.json";
import BerekenenPage from "@/app/berekenen/page";
import BerekenenLayout, { metadata } from "@/app/berekenen/layout";
import { ANSWERS_STORAGE_KEY } from "@/app/_flow/answers";
import { forgetCachedAnswers } from "@/app/_flow/store";

/**
 * The call to one endpoint, out of every call the page made.
 *
 * Not `mock.calls[0]`, which these tests used until 2026-09-02 and which said
 * "the first request the page makes carries this body". That stopped being the
 * property anybody wanted the moment the flow also counted its own funnel: the
 * counters go to `/api/advice/count/` and fire earlier, so the assertion began
 * failing on a page that was doing exactly the right thing. Locating the call
 * by its path says what the test always meant.
 */
function callTo(
  spy: { mock: { calls: unknown[][] } },
  path: string,
): [string, RequestInit] {
  const found = spy.mock.calls.find((call) => String(call[0]).includes(path));
  if (found === undefined) {
    const seen = spy.mock.calls.map((call) => String(call[0]));
    throw new Error(
      `no request to ${path}; the page called ${seen.join(", ")}`,
    );
  }
  return found as unknown as [string, RequestInit];
}

/**
 * The three questions of round one that have a field, each written once.
 *
 * These are the headings, and since 2026-09-02 they are also the accessible
 * names of the fields underneath them: the controls carry `aria-labelledby`
 * pointing at QuestionShell's heading rather than a second, differently worded
 * label of their own. So every query below asks for the textbox BY the
 * question, which is now also an assertion that the question and the field say
 * the same thing.
 *
 * `getByRole("textbox", ...)` and not `getByLabelText`, because the heading
 * names two things: the field, and the `<section>` QuestionShell wraps the
 * question in. A label query matches both and fails on the ambiguity; the role
 * says which of the two this test means.
 *
 * The consumption one is spelled out rather than matched loosely, because the
 * three words this test would happily drop are the whole of decision 26. The
 * model adds the car and the heat pump on top of this figure, so a visitor who
 * reads the total off their annual bill is counted twice and loses between a
 * quarter and half of their answer with nothing reporting it. A
 * `getByLabelText(/Verbruik/)` here would keep passing through exactly the
 * edit that undoes that.
 */
const POSTCODE_LABEL = "Wat zijn de eerste vier cijfers van uw postcode?";
const PEAK_POWER_LABEL = "Hoeveel wattpiek aan zonnepanelen ligt er op uw dak?";
const CONSUMPTION_LABEL =
  "Hoeveel stroom verbruikt u per jaar, zonder auto en warmtepomp?";

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
    screen.getByRole("textbox", { name: POSTCODE_LABEL }),
    "5401",
  );
  await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: PEAK_POWER_LABEL }),
    "4200",
  );
  await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
  await userEvent.click(screen.getByLabelText("Zuidwest"));
  await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
  await userEvent.type(
    screen.getByRole("textbox", { name: CONSUMPTION_LABEL }),
    "3400",
  );
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
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: PEAK_POWER_LABEL }),
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
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
      "999",
    );
    await userEvent.tab();
    expect(screen.getByRole("alert")).toHaveTextContent("1000");
  });

  it("sends exactly the body the estimate serializer accepts", async () => {
    const fetchSpy = respondWith(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    render(<BerekenenPage />);
    await answerRoundOne();
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const call = callTo(fetchSpy, "/api/advice/estimate/");
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
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
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
    expect(screen.getByRole("textbox", { name: POSTCODE_LABEL })).toHaveValue(
      "5401",
    );
  });

  it("checks no direction on the roof question before the visitor answers one", async () => {
    // South is the most common roof in this country and it used to arrive
    // checked, which is the one direction that could then not be given as an
    // answer: a radio that is already checked fires no change event.
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: PEAK_POWER_LABEL }),
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
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: PEAK_POWER_LABEL }),
      "4200",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.click(screen.getByLabelText("Zuid"));
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByText("Vraag 4 van 4")).toBeInTheDocument();
    await userEvent.type(
      screen.getByRole("textbox", { name: CONSUMPTION_LABEL }),
      "3400",
    );
    await userEvent.click(screen.getByRole("button", { name: "Bereken" }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const call = callTo(fetchSpy, "/api/advice/estimate/");
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
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
      "5401",
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    await userEvent.type(
      screen.getByRole("textbox", { name: PEAK_POWER_LABEL }),
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
    // The computation, not every request: the page also counts its own funnel,
    // and those go to a different path. Four presses must still buy one
    // computation, which is what this test is about.
    // `as unknown as` because this spy is declared with no argument types, so
    // TypeScript types its recorded calls as the empty tuple and refuses an
    // index. The same reason `callTo` above takes a loosened shape.
    const computes = (fetchSpy.mock.calls as unknown as unknown[][]).filter(
      (call) => String(call[0]).includes("/api/advice/estimate/"),
    );
    expect(computes).toHaveLength(1);
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
    await userEvent.clear(
      screen.getByRole("textbox", { name: CONSUMPTION_LABEL }),
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: CONSUMPTION_LABEL }),
      "99999999",
    );
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
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
      "999",
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Volgende" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Beantwoord deze vraag",
    );
  });

  it("walks back to the previous question, and off the flow from the first", async () => {
    render(<BerekenenPage />);
    await userEvent.type(
      screen.getByRole("textbox", { name: POSTCODE_LABEL }),
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
    const call = callTo(fetchSpy, "/api/advice/refine/");
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

/**
 * The server shell around the flow, as a component.
 *
 * `params` is required by `LayoutProps<"/berekenen">` and is a promise of an
 * empty object for a route with no segments. It is never read; it is here
 * because the generated type says a layout takes one.
 */
function Shell({ children }: { children: React.ReactNode }) {
  return (
    <BerekenenLayout params={Promise.resolve({})}>{children}</BerekenenLayout>
  );
}

describe("the page a crawler and a first paint both get", () => {
  /**
   * The half of this route that does not wait for hydration.
   *
   * Measured on the built `out/berekenen/index.html` on 2026-09-02: no `<h1>`
   * at all and 32 words of body text, all of them header, footer and "De vragen
   * worden klaargezet." The whole page was behind hydration. `e2e/form.spec.ts`
   * asserts this against the file that ships with JavaScript switched off,
   * which is the honest instrument; these are the fast versions that fail in a
   * second rather than after a build.
   */
  it("names itself with the same words the tab does", () => {
    render(<Shell>{null}</Shell>);
    const heading = screen.getByRole("heading", { level: 1 });
    // The route's title, not a paraphrase of it. They disagreed until
    // 2026-09-02: the tab said "Uw situatie doorrekenen" and the heading said
    // "Uw gegevens", so a screen reader announced two names for one page.
    expect(heading).toHaveTextContent(String(metadata.title));
  });

  it("says what the calculator asks for before the flow has rendered", () => {
    // `{null}` is the flow that has not arrived: no questions, no client
    // component, nothing that needs a browser. What is left has to stand on
    // its own, because for a retrieval crawler that is the whole page.
    const { container } = render(<Shell>{null}</Shell>);
    const text = container.textContent ?? "";
    for (const phrase of [
      "De salderingsregeling stopt op 1 januari 2027",
      "De vier vragen",
      "wattpiek aan zonnepanelen",
      "geen e-mailadres",
      "Ampeer verkoopt geen zonnepanelen",
    ]) {
      expect(text, `the shell never says "${phrase}"`).toContain(phrase);
    }
    // Non-vacuous: 32 words was the defect, and a page that lost its shell
    // would still pass every phrase check above if one paragraph survived.
    expect(text.split(/\s+/).filter(Boolean).length).toBeGreaterThan(180);
  });

  it("puts the route's one first-level heading in the shell, not in the flow", () => {
    // The flow used to carry an `<h1>Uw gegevens</h1>`: a heading that named a
    // section of the form rather than the page, that disagreed with the tab,
    // and that no reader without JavaScript ever saw. Both halves matter. The
    // flow must contribute none, and the route must still end up with exactly
    // one, because two is the failure a careless move of this heading makes.
    const flow = render(<BerekenenPage />);
    expect(flow.container.querySelectorAll("h1")).toHaveLength(0);
    flow.unmount();

    render(
      <Shell>
        <BerekenenPage />
      </Shell>,
    );
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});
