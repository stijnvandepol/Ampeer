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
    expect(screen.getByText(/niets meer te halen/i)).toBeInTheDocument();
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
    // per point of the curve.
    const expected = 2 + 3 + fixture.battery.curve.length;
    expect(scenario).toHaveLength(expected);
  });

  it("keeps the battery block shut when the model said it does not pay back", async () => {
    // Measured on the built page at 1280x900 before this: the headline band was
    // 345px, the two free routes 313px each, and "De batterij, doorgerekend"
    // 1365px, which is 38.5% of the page and 2.2 times the two free routes
    // together, on a household whose verdict is BATTERY_DOES_NOT_PAY_BACK and
    // whose rule text says "niet de moeite waard". It passed all five rules,
    // because "free routes first" was implemented as DOM order, and order is
    // the weakest form of precedence there is. Reading the page, it said no and
    // then handed over a sizing menu with prices in it.
    expect(fixture.battery.verdict).toBe("BATTERY_DOES_NOT_PAY_BACK");
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
    // Two versions that happen to be the same string today, which is why this
    // counts them rather than looking one up.
    expect(screen.getAllByText(fixture.engine_version)).toHaveLength(2);
    expect(screen.getByText(String(fixture.weather_year))).toBeInTheDocument();
    // The Dutch sentence, never the enum. "FALLBACK" in front of a reader is
    // the language boundary being crossed by the frontend, and which of the two
    // sources it was changes how much weight the whole answer deserves.
    expect(
      screen.getByText(fixture.production_source_text),
    ).toBeInTheDocument();
    expect(screen.queryByText(fixture.production_source)).toBeNull();
  });
});
