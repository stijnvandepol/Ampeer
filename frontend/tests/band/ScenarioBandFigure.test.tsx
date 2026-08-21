import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../fixtures/advice-response.json";
import { ScenarioBandFigure } from "@/components/band/ScenarioBandFigure";
import type { Advice, ScenarioBand } from "@/lib/types";

const advice = fixture as unknown as Advice;
const band = advice.routes.flatMap((r) => r.rules).find((r) => r.saving_eur)!.saving_eur as ScenarioBand;

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
    expect(container.querySelector('[data-band-kind="scenario"]')).not.toBeNull();
    expect(container.querySelector('[data-band-kind="percentile"]')).toBeNull();
  });

  it("keeps the middle no larger than the ends here too", () => {
    // The same rule as the headline. A scenario band is smaller overall and
    // still a band, so the middle is still a marking inside it.
    const { container } = render(<ScenarioBandFigure band={band} unit="eur" />);
    const middle = container.querySelector('[data-role="band-middle"]');
    const end = container.querySelector('[data-role="band-end"]');
    const size = (el: Element) => Number.parseFloat(getComputedStyle(el).fontSize || "0");
    expect(size(middle!)).toBeGreaterThan(0);
    expect(size(end!)).toBeGreaterThan(0);
    expect(size(middle!)).toBeLessThanOrEqual(size(end!));
  });

  it("renders amounts as given, without going through a number", () => {
    // parseFloat("126.09").toString() is "126.09" today and a rounding bug the
    // first time an amount has trailing precision. The string is the value.
    render(<ScenarioBandFigure band={band} unit="eur" />);
    expect(screen.getByText(new RegExp(band.mid.replace(".", "[.,]")))).toBeInTheDocument();
  });

  it("says the unit it was given rather than assuming euros", () => {
    const years = advice.battery!.payback_years;
    render(<ScenarioBandFigure band={years} unit="years" />);
    expect(screen.getAllByText(/jaar/)).toHaveLength(3);
    expect(screen.getByText(new RegExp(`${years.mid} jaar`))).toBeInTheDocument();
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
    expect(screen.queryByText(/supply_price/)).toBeNull();
    expect(screen.queryByText(/feed_in_cost_per_kwh/)).toBeNull();
  });
});
