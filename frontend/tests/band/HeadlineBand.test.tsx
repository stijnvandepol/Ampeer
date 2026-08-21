import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { installMatchMedia } from "../matchMedia";
import fixture from "../fixtures/advice-response.json";
import { HeadlineBand } from "@/components/band/HeadlineBand";
import type { Advice } from "@/lib/types";

const advice = fixture as unknown as Advice;

// jsdom has no matchMedia, so a component that reads a media preference throws
// on render without this. See matchMedia.ts.
beforeEach(() => installMatchMedia(false));

describe("the headline band", () => {
  it("shows all three figures, not just the middle", () => {
    render(<HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />);
    expect(screen.getByText(new RegExp(advice.headline.p10))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(advice.headline.p50))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(advice.headline.p90))).toBeInTheDocument();
  });

  it("never renders the middle larger than the ends", () => {
    // The rule the whole design rests on. A p50 set in display type with the
    // ends in small print is a single number with decoration, not a band.
    const { container } = render(
      <HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />,
    );
    const middle = container.querySelector('[data-role="band-middle"]');
    const end = container.querySelector('[data-role="band-end"]');
    expect(middle).not.toBeNull();
    expect(end).not.toBeNull();
    const size = (el: Element) => Number.parseFloat(getComputedStyle(el).fontSize || "0");
    expect(size(middle!)).toBeLessThanOrEqual(size(end!) * 1.5);
  });

  it("sets both sizes somewhere a test can read them", () => {
    // Guards the test above against passing vacuously. jsdom loads no
    // stylesheet, so a font size that lives only in a stylesheet reads back as
    // zero, and zero is less than or equal to zero.
    const { container } = render(
      <HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />,
    );
    const middle = container.querySelector('[data-role="band-middle"]');
    const end = container.querySelector('[data-role="band-end"]');
    const size = (el: Element) => Number.parseFloat(getComputedStyle(el).fontSize || "0");
    expect(size(middle!)).toBeGreaterThan(0);
    expect(size(end!)).toBeGreaterThan(0);
  });

  it("says how many runs produced it, because that is what makes it a band", () => {
    render(<HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />);
    expect(screen.getByText(new RegExp(String(advice.headline.runs)))).toBeInTheDocument();
  });

  it("carries the whole band in its accessible description, not only the middle", () => {
    render(<HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />);
    const figure = screen.getByRole("figure");
    const description = figure.getAttribute("aria-label") ?? "";
    expect(description).toContain(advice.headline.p10);
    expect(description).toContain(advice.headline.p90);
  });

  it("shows the confidence label as text", () => {
    render(<HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />);
    expect(screen.getByText(advice.confidence_label)).toBeInTheDocument();
  });

  it("shows the band without motion when the visitor asked for less of it", () => {
    // Under a reduced motion preference the band is simply there. Shortening
    // the same animation would leave the meaning in the movement, which is the
    // thing the preference exists to remove.
    installMatchMedia(true);
    const { container } = render(
      <HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />,
    );
    const fill = container.querySelector('[data-role="band-fill"]');
    expect(fill).not.toBeNull();
    expect((fill as HTMLElement).style.width).toBe("100%");
    expect((fill as HTMLElement).style.transitionDuration).toBe("0ms");
  });

  it("renders every amount as the string the API sent", () => {
    // Not "1395,51", not "1.395,51", not 1395.51 rounded by a formatter. The
    // string is the value; reformatting it here is the same class of mistake as
    // parsing it.
    render(<HeadlineBand band={advice.headline} confidence={advice.confidence} label={advice.confidence_label} />);
    for (const amount of [advice.headline.p10, advice.headline.p50, advice.headline.p90]) {
      expect(screen.getByText(new RegExp(amount)).textContent).toContain(amount);
    }
  });
});
