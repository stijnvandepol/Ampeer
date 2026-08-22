import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../fixtures/advice-response.json";
import { ScenarioBandFigure } from "@/components/band/ScenarioBandFigure";
import { dutchAmount } from "@/components/band/format";
import { bandSpanFraction } from "@/components/band/position";
import type { Advice, ScenarioBand } from "@/lib/types";

const advice = fixture as unknown as Advice;
const band = advice.routes.flatMap((r) => r.rules).find((r) => r.saving_eur)!
  .saving_eur as ScenarioBand;

describe("a scenario band", () => {
  it("shows its low and high, not only its middle", () => {
    render(<ScenarioBandFigure band={band} unit="eur" />);
    expect(screen.getByText(new RegExp(band.low))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(band.high))).toBeInTheDocument();
  });

  it("can say what it varied and what it held", () => {
    // The API sends these because this band is narrower than the headline and
    // has to be able to admit it.
    render(<ScenarioBandFigure band={band} unit="eur" />);
    const disclosure = screen.getByRole("button", { name: /waarover/i });
    expect(disclosure).toBeInTheDocument();
  });

  it("names every varied and pinned input once the disclosure is open", async () => {
    render(<ScenarioBandFigure band={band} unit="eur" />);
    const disclosure = screen.getByRole("button", { name: /waarover/i });
    expect(disclosure).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(disclosure);
    expect(disclosure).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("group", { name: /waarover/i });
    // The Dutch names, one for each identifier. Asserting on band.varied here
    // would pass on a component that printed "supply_price" at a Dutch reader,
    // which is what this used to do.
    for (const name of [...band.varied_text, ...band.pinned_text]) {
      expect(panel.textContent ?? "").toContain(name);
    }
    expect(band.varied_text).toHaveLength(band.varied.length);
    expect(band.pinned_text).toHaveLength(band.pinned.length);
  });

  it("is visually distinct from a percentile band", () => {
    const { container } = render(<ScenarioBandFigure band={band} unit="eur" />);
    expect(
      container.querySelector('[data-band-kind="scenario"]'),
    ).not.toBeNull();
    expect(container.querySelector('[data-band-kind="percentile"]')).toBeNull();
  });

  it("keeps the middle no larger than the ends here too", () => {
    // The same rule as the headline. A scenario band is smaller overall and
    // still a band, so the middle is still a marking inside it.
    const { container } = render(<ScenarioBandFigure band={band} unit="eur" />);
    const middle = container.querySelector('[data-role="band-middle"]');
    const end = container.querySelector('[data-role="band-end"]');
    const size = (el: Element) =>
      Number.parseFloat(getComputedStyle(el).fontSize || "0");
    expect(size(middle!)).toBeGreaterThan(0);
    expect(size(end!)).toBeGreaterThan(0);
    expect(size(middle!)).toBeLessThanOrEqual(size(end!));
  });

  it("renders amounts in Dutch, without going through a number", () => {
    // parseFloat("126.09").toString() is "126.09" today and a rounding bug the
    // first time an amount has trailing precision. The digits are the value;
    // only the separators move.
    const { container } = render(<ScenarioBandFigure band={band} unit="eur" />);
    const shown = container.textContent ?? "";
    const digits = (text: string) => text.replace(/[.,]/g, "");
    for (const amount of [band.low, band.mid, band.high]) {
      expect(shown).toContain(dutchAmount(amount));
      expect(digits(dutchAmount(amount))).toBe(digits(amount));
    }
  });

  it("says the unit it was given rather than assuming euros", () => {
    const years = advice.battery!.payback_years;
    const { container } = render(
      <ScenarioBandFigure band={years} unit="years" />,
    );
    const shown = [
      ...container.querySelectorAll(
        '[data-role="band-end"],[data-role="band-middle"]',
      ),
    ].map((element) => element.textContent);
    expect(shown).toEqual([
      `${dutchAmount(years.low)} jaar`,
      `${dutchAmount(years.mid)} jaar`,
      `${dutchAmount(years.high)} jaar`,
    ]);
  });

  it("puts the unit in its accessible name too, not only on the visible numbers", () => {
    // Ten of these are on an advice page and the description used to interpolate
    // the raw values, so a listener heard "Tussen 6.99 en 18.89" for a payback
    // time and "Tussen 571.80 en 772.69" for a price per kWh: the same unitless
    // sentence for euros, years and euros per kWh. The unit prop was in scope
    // and unused.
    const spoken = [
      [advice.battery!.payback_years, "years", "jaar"],
      [advice.battery!.break_even_cost_per_kwh, "eur_per_kwh", "euro per kWh"],
      [band, "eur", "euro"],
    ] as const;
    for (const [figure, unit, word] of spoken) {
      const { unmount } = render(
        <ScenarioBandFigure band={figure} unit={unit} />,
      );
      const description =
        screen.getByRole("figure").getAttribute("aria-label") ?? "";
      expect(description, `${unit} is read out without a unit`).toContain(word);
      expect(description).toContain(dutchAmount(figure.low));
      expect(description).toContain(dutchAmount(figure.high));
      unmount();
    }
  });

  it("gives each disclosure a name of its own, pointing at a panel that exists", () => {
    // All ten carried the identical accessible name, and aria-controls named an
    // id that was not in the document for as long as the panel stayed closed,
    // which is every one of them until somebody clicks.
    const first = render(<ScenarioBandFigure band={band} unit="eur" />);
    const other = render(
      <ScenarioBandFigure band={advice.battery!.payback_years} unit="years" />,
    );
    const [one, two] = screen.getAllByRole("button", { name: /waarover/i });
    expect(one?.getAttribute("aria-label")).not.toBe(
      two?.getAttribute("aria-label"),
    );
    // SC 2.5.3: the visible label has to be in the accessible name.
    expect(one?.getAttribute("aria-label")).toContain(one?.textContent ?? "");
    for (const button of [one, two]) {
      const controls = button?.getAttribute("aria-controls") ?? "";
      expect(controls).not.toBe("");
      expect(
        document.getElementById(controls),
        `${controls} is not in the document`,
      ).not.toBeNull();
    }
    first.unmount();
    other.unmount();
  });

  it("draws its own spread and not the width of the track", () => {
    const { container } = render(<ScenarioBandFigure band={band} unit="eur" />);
    const figure = container.querySelector("[data-band-span]");
    const expected = bandSpanFraction(band.low, band.high);
    expect(expected).toBeGreaterThan(0);
    expect(expected).toBeLessThan(1);
    expect(Number(figure?.getAttribute("data-band-span"))).toBeCloseTo(
      expected,
      4,
    );
    const segment = container.querySelector(
      '[class*="segment"]',
    ) as HTMLElement;
    expect(segment.style.width).toBe(`${expected * 100}%`);
  });
});

describe("what a scenario band says it varied", () => {
  it("shows the Dutch names, not the model's identifiers", async () => {
    // "supply_price" in front of a Dutch reader is the language boundary
    // leaking. The API translates; this renders what it sent.
    render(<ScenarioBandFigure band={band} unit="eur" />);
    await userEvent.click(screen.getByRole("button", { name: /waarover/i }));
    for (const dutch of band.varied_text) {
      expect(screen.getByText(new RegExp(dutch))).toBeInTheDocument();
    }
    // Taken from the band rather than written out. The two names that used to
    // stand here were a guess about what could leak: one of them,
    // feed_in_cost_per_kwh, is not in this band at all, so that assertion was
    // never going to find anything and read as a check on the language
    // boundary while being one on nothing. These are the identifiers this
    // band actually carries, so a rename in the model cannot outrun them and
    // a new one is covered on arrival.
    expect(band.varied.length + band.pinned.length).toBeGreaterThan(0);
    for (const identifier of [...band.varied, ...band.pinned]) {
      expect(
        screen.queryByText(new RegExp(identifier)),
        `${identifier} reached the screen instead of its Dutch name`,
      ).toBeNull();
    }
  });
});
