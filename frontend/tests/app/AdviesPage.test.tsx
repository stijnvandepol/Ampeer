import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { installMatchMedia } from "../matchMedia";
import fixture from "../fixtures/advice-response.json";
import AdviesPage from "@/app/advies/page";
import { dutchAmount } from "@/components/band/format";
import { ROUTE_ORDER } from "@/lib/types";

const TOKEN = fixture.token;

function respondWith(body: unknown, status = 200) {
  return vi.fn(() =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    } as Response),
  );
}

function goTo(path: string) {
  window.history.pushState({}, "", path);
}

/** jsdom implements no clipboard, so the one the button reaches for is put here. */
function stubClipboard(writeText: () => Promise<void>) {
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
}

beforeEach(() => {
  installMatchMedia(false);
  goTo(`/advies/${TOKEN}/`);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the advice page", () => {
  it("says what is happening before the answer arrives", async () => {
    // A blank page and a spinner without an end are two different failures and
    // both are failures. This is the third thing: a sentence.
    let settle: (value: unknown) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise((resolve) => (settle = resolve))),
    );
    render(<AdviesPage />);
    expect(screen.getByRole("status")).toHaveTextContent("Een moment");
    settle({ ok: true, status: 200, json: () => Promise.resolve(fixture) });
    await screen.findByText(fixture.confidence_label);
    expect(screen.queryByText(/Een moment/)).toBeNull();
  });

  it("draws the headline band with its ends, its middle and its confidence label", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);

    const headline = container.querySelector('[data-band-kind="percentile"]');
    expect(headline).not.toBeNull();
    // The amounts reach the screen in Dutch, and with every digit the API sent.
    // They used to reach it as "1395.51", which is the en-US form and not the
    // language of this application. What may not happen on the way is a trip
    // through a number, so the second assertion is the one that matters: the
    // digits on the screen are the digits that arrived, in the same order.
    const digits = (text: string) => text.replace(/[.,]/g, "");
    for (const amount of [
      fixture.headline.p10,
      fixture.headline.p50,
      fixture.headline.p90,
    ]) {
      expect(headline?.textContent).toContain(dutchAmount(amount));
      expect(headline?.textContent).not.toContain(amount);
      expect(digits(dutchAmount(amount))).toBe(digits(amount));
    }
  });

  it("renders all three routes in the order the API sent them", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    const rendered = [...container.querySelectorAll("[data-route]")].map(
      (element) => element.getAttribute("data-route"),
    );
    expect(rendered).toEqual([...ROUTE_ORDER]);
  });

  it("shows an empty route rather than hiding it", async () => {
    const withEmpty = {
      ...fixture,
      routes: fixture.routes.map((route, index) =>
        index === 1 ? { ...route, rules: [] } : route,
      ),
    };
    vi.stubGlobal("fetch", respondWith(withEmpty));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    expect(container.querySelectorAll("[data-route]")).toHaveLength(3);
    expect(screen.getByText(/levert deze route niets op/i)).toBeInTheDocument();
  });

  it("has an answer for a household with nothing left to gain", async () => {
    // The shape two of the six golden households produce: no rule fires in any
    // route, so `battery` is null as well, because a battery is only priced for
    // a household some storage rule reached. Each half is covered above and
    // neither half is this: a page with nothing at all to say had never been
    // rendered, and it is the answer somebody who already uses 94 percent of
    // their own production receives.
    const nothingToGain = {
      ...fixture,
      routes: fixture.routes.map((route) => ({ ...route, rules: [] })),
      battery: null,
    };
    vi.stubGlobal("fetch", respondWith(nothingToGain));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);

    // What it still owes them: the figure, its band and how sure it is.
    expect(screen.getByText(fixture.confidence_label)).toBeInTheDocument();
    expect(
      container.querySelector('[data-band-kind="percentile"]'),
    ).not.toBeNull();

    // All three routes, in order, each saying so for itself rather than the
    // page hiding what it found nothing in.
    expect(container.querySelectorAll("[data-route]")).toHaveLength(3);
    expect(screen.getAllByText(/levert deze route niets op/i)).toHaveLength(3);

    // And no battery. A household just told there is nothing to gain from
    // storage must not then be shown a battery sized and priced for them; that
    // is the one place where this product could read as selling something.
    // data-role and not a data-battery attribute: the first version of this
    // line asserted on one that does not exist anywhere in the source, which
    // would have passed whether the block rendered or not.
    expect(container.querySelector('[data-role="battery-detail"]')).toBeNull();
    expect(screen.queryByText(/doorgerekend/i)).toBeNull();
  });

  it("gives the bandless capacity its own sentence and no invented margin", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    const bandless = container.querySelector('[data-band-kind="none"]');
    expect(bandless).not.toBeNull();
    expect(bandless?.querySelector('[data-role="band-middle"]')).toBeNull();
    expect(
      bandless?.querySelector('[data-role="basis-text"]')?.textContent,
    ).toBe(fixture.battery.sized_capacity_kwh.basis_text);
  });

  it("draws every figure in the battery block with a band, including the curve", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    const scenario = container.querySelectorAll('[data-band-kind="scenario"]');
    // Two fired rules carry one, and the battery block carries three plus one
    // per point of the curve. The first step block at the top draws the first
    // rule's band and the route below it then leaves that one out, so the
    // total is unchanged: the figure moved rather than multiplied. It was
    // briefly on the page twice on 2026-09-15 and this number said so.
    const expected = 2 + 3 + fixture.battery.curve.length;
    expect(scenario).toHaveLength(expected);
  });

  it("keeps the battery block shut when the model is not recommending one", async () => {
    // Measured on the built page at 1280x900 before this: the headline band was
    // 345px, the two free routes 313px each, and "De batterij, doorgerekend"
    // 1365px, which is 38.5% of the page and 2.2 times the two free routes
    // together, on a household the model was not recommending a battery to. It
    // passed all five rules, because "free routes first" was implemented as DOM
    // order, and order is the weakest form of precedence there is. Reading the
    // page, it said no and then handed over a sizing menu with prices in it.
    //
    // The guard is on the property and not on one id. It read
    // BATTERY_DOES_NOT_PAY_BACK until 2026-08-26, when the fixture household
    // crossed the twelve year line and became BATTERY_DEPENDS_ON_PRICE. That is
    // still not a recommendation, so the behaviour under test is unchanged and
    // only the guard had to be, which is the sign it was written one id too
    // narrow. An empty or unknown verdict still fails it.
    expect(["BATTERY_DOES_NOT_PAY_BACK", "BATTERY_DEPENDS_ON_PRICE"]).toContain(
      fixture.battery.verdict,
    );
    vi.stubGlobal("fetch", respondWith(fixture));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    const toggle = container.querySelector("[data-role='battery-detail']");
    expect(toggle).not.toBeNull();
    expect(toggle?.getAttribute("aria-expanded")).toBe("false");
    const panel = document.getElementById(
      toggle?.getAttribute("aria-controls") ?? "",
    );
    expect(
      panel,
      "aria-controls names an element that is not in the document",
    ).not.toBeNull();
    expect(panel?.hasAttribute("hidden")).toBe(true);
    // The figures are in the document, so nothing has been hidden from anybody
    // who goes looking; they are behind a control that starts closed.
    expect(panel?.querySelectorAll('[data-band-kind="scenario"]').length).toBe(
      3 + fixture.battery.curve.length,
    );
  });

  it("opens it when the model says a battery is worth considering", async () => {
    // The verdict is a rule id, which is a machine's word for which storage
    // rule fired, and it is the only thing on the response that says whether
    // this is a route the model is recommending. A household it does recommend
    // one to should not have to click to see the sizing.
    const recommended = {
      ...fixture,
      battery: { ...fixture.battery, verdict: "CONSIDER_BATTERY" },
    };
    vi.stubGlobal("fetch", respondWith(recommended));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    const toggle = container.querySelector("[data-role='battery-detail']");
    expect(toggle?.getAttribute("aria-expanded")).toBe("true");
    const panel = document.getElementById(
      toggle?.getAttribute("aria-controls") ?? "",
    );
    expect(panel?.hasAttribute("hidden")).toBe(false);
  });

  it("announces that the advice arrived and puts focus on it", async () => {
    // The loading sentence used to be replaced rather than updated, so its
    // removal announced nothing, the arriving content was in no live region,
    // and focus never moved. A screen reader opening a shared link heard "Een
    // moment" and then silence.
    let settle: (value: unknown) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise((resolve) => (settle = resolve))),
    );
    render(<AdviesPage />);
    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("Een moment");
    settle({ ok: true, status: 200, json: () => Promise.resolve(fixture) });
    await screen.findByText(fixture.confidence_label);
    // The same element, updated. A live region that is removed and replaced by
    // a different element announces nothing at all.
    expect(region).toBeInTheDocument();
    expect(region).toHaveTextContent(/advies/i);
    expect(region).not.toHaveTextContent("Een moment");
    await waitFor(() =>
      expect(document.activeElement).toBe(
        screen.getByRole("heading", { level: 1 }),
      ),
    );
  });

  it("does not put the verdict rule id in front of a reader", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    // The id is an English identifier for a machine. The Dutch that goes with
    // it travels in the matching route and is already on the page.
    expect(screen.queryByText(fixture.battery.verdict)).toBeNull();
  });

  it("still shows the rest when the model produced no battery block", async () => {
    vi.stubGlobal("fetch", respondWith({ ...fixture, battery: null }));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    expect(container.querySelectorAll("[data-route]")).toHaveLength(3);
    expect(container.querySelector('[data-band-kind="none"]')).toBeNull();
  });

  it("offers exactly two calls to action and neither leaves for a seller", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const { container } = render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    expect(
      screen.getByRole("link", { name: "Verfijn uw antwoord" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Kopieer deze link" }),
    ).toBeInTheDocument();
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });

  it("says so when the clipboard refuses, rather than pretending it copied", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const writeText = vi.fn(() => Promise.reject(new Error("denied")));
    stubClipboard(writeText);
    render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    await userEvent.click(
      screen.getByRole("button", { name: "Kopieer deze link" }),
    );
    await waitFor(() =>
      expect(
        screen.getByText(/Neem de link hierboven over/),
      ).toBeInTheDocument(),
    );
  });

  it("confirms a copy that worked", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    const writeText = vi.fn(() => Promise.resolve());
    stubClipboard(writeText);
    render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    await userEvent.click(
      screen.getByRole("button", { name: "Kopieer deze link" }),
    );
    await waitFor(() =>
      expect(screen.getByText("Gekopieerd.")).toBeInTheDocument(),
    );
    expect(writeText).toHaveBeenCalledWith(window.location.href);
  });

  it("names what went wrong when the API refused", async () => {
    vi.stubGlobal(
      "fetch",
      respondWith({ detail: "Request was throttled." }, 429),
    );
    render(<AdviesPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("over een uur");
  });

  it("says the link carries no advice, without spending a request on it", async () => {
    const fetchSpy = respondWith(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    goTo("/advies/");
    render(<AdviesPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "er staat er geen in de link",
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("refuses a token the API never issues before making a request", async () => {
    const fetchSpy = respondWith(fixture);
    vi.stubGlobal("fetch", fetchSpy);
    goTo("/advies/nietEenToken/");
    render(<AdviesPage />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows what it was computed with, and not the enum it has no Dutch for", async () => {
    vi.stubGlobal("fetch", respondWith(fixture));
    render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    expect(screen.getByText("Motorversie")).toBeInTheDocument();
    // One assertion per version, each on its own value. This counted both at
    // once until 2026-08-26, when the engine moved to 0.2.0 and the advice
    // version stayed at 0.1.0. The comment here used to say the two "happen to
    // be the same string today", which was true and was the whole reason a
    // count could stand in for two lookups; the day that stopped being true,
    // the page was showing both correctly and the test was the thing that
    // failed. Looked up separately, a page that dropped one of them fails too.
    expect(screen.getByText(fixture.engine_version)).toBeInTheDocument();
    expect(screen.getByText(fixture.advice_version)).toBeInTheDocument();
    expect(fixture.engine_version).not.toBe(fixture.advice_version);
    expect(screen.getByText(String(fixture.weather_year))).toBeInTheDocument();
    // The Dutch sentence, never the enum. "FALLBACK" in front of a reader is
    // the language boundary being crossed by the frontend, and which of the two
    // sources it was changes how much weight the whole answer deserves.
    expect(
      screen.getByText(fixture.production_source_text),
    ).toBeInTheDocument();
    expect(screen.queryByText(fixture.production_source)).toBeNull();
  });

  it("shows the consumption it modelled, so a doubled figure can be caught", async () => {
    // The visibility half of decision 26. The question asks for consumption
    // WITHOUT a car and a heat pump, and its one failure mode is a visitor who
    // enters the total off their annual bill anyway: they are otherwise
    // indistinguishable from a correct one and lose between a quarter and half
    // of their answer with nothing reporting it. This figure is the only place
    // they can recognise the number the model actually used, or fail to.
    vi.stubGlobal("fetch", respondWith(fixture));
    render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    const modelled = fixture.modelled_consumption_kwh;
    expect(modelled).toBeDefined();
    expect(screen.getByText(`${modelled!.value} kWh`)).toBeInTheDocument();
    // The sentence with it, from the API. Without it the figure is a number in
    // a list of versions and a reader has no reason to check it against
    // anything. The basis enum stays out of sight, same boundary as the
    // production source above.
    expect(screen.getByText(modelled!.basis_text)).toBeInTheDocument();
    expect(screen.queryByText(modelled!.basis)).toBeNull();
  });

  it("renders the page it rendered before the field existed when it is absent", async () => {
    // Optional on the wire, like `year`. A build talking to an older API shows
    // no gap where the figure would be.
    const { modelled_consumption_kwh: _absent, ...without } = fixture;
    vi.stubGlobal("fetch", respondWith(without));
    render(<AdviesPage />);
    await screen.findByText(fixture.confidence_label);
    expect(screen.queryByText("Verbruik")).toBeNull();
    expect(screen.getByText("Motorversie")).toBeInTheDocument();
  });
});
