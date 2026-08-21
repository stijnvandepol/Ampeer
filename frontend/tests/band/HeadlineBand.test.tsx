import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { installMatchMedia } from "../matchMedia";
import fixture from "../fixtures/advice-response.json";
import { HeadlineBand } from "@/components/band/HeadlineBand";
import { dutchAmount } from "@/components/band/format";
import {
  bandOffsetFraction,
  bandSpanFraction,
} from "@/components/band/position";
import type { Advice } from "@/lib/types";

const advice = fixture as unknown as Advice;

// jsdom has no matchMedia, so a component that reads a media preference throws
// on render without this. See matchMedia.ts.
beforeEach(() => installMatchMedia(false));

describe("the headline band", () => {
  it("shows all three figures, not just the middle", () => {
    render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    for (const amount of [
      advice.headline.p10,
      advice.headline.p50,
      advice.headline.p90,
    ]) {
      expect(
        screen.getByText(dutchAmount(amount), { exact: false }),
      ).toBeInTheDocument();
    }
  });

  it("draws the band at the width of its own spread, not at the width of the track", () => {
    // The fill was width: 100% on every band, so a spread of 60 euro and one of
    // 383 were the same object at the same size and the only visual variable on
    // the page was the marker, which encodes skew. See position.ts.
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const fill = container.querySelector(
      '[data-role="band-fill"]',
    ) as HTMLElement;
    const expected = bandSpanFraction(advice.headline.p10, advice.headline.p90);
    expect(expected).toBeGreaterThan(0);
    expect(expected).toBeLessThan(1);
    // Not yet grown: the animated property is the width, so it starts at zero
    // and the reduced-motion case below is where the final width is asserted.
    expect(fill.style.width).toBe("0%");
    const offset = bandOffsetFraction(advice.headline.p10, advice.headline.p90);
    expect(offset).toBeGreaterThan(0);
    expect(fill.style.left).toBe(`${offset * 100}%`);
    const figure = container.querySelector("[data-band-span]");
    expect(Number(figure?.getAttribute("data-band-span"))).toBeCloseTo(
      expected,
      4,
    );
  });

  it("never renders the middle larger than the ends", () => {
    // The rule the whole design rests on. A p50 set in display type with the
    // ends in small print is a single number with decoration, not a band.
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const middle = container.querySelector('[data-role="band-middle"]');
    const end = container.querySelector('[data-role="band-end"]');
    expect(middle).not.toBeNull();
    expect(end).not.toBeNull();
    const size = (el: Element) =>
      Number.parseFloat(getComputedStyle(el).fontSize || "0");
    // Not "within half as large again": no larger. The allowance that used to
    // sit here let a middle at 1.5x an end pass a test named for the opposite.
    expect(size(middle!)).toBeLessThanOrEqual(size(end!));
  });

  it("sets both sizes somewhere a test can read them", () => {
    // Guards the test above against passing vacuously. jsdom loads no
    // stylesheet, so a font size that lives only in a stylesheet reads back as
    // zero, and zero is less than or equal to zero.
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const middle = container.querySelector('[data-role="band-middle"]');
    const end = container.querySelector('[data-role="band-end"]');
    const size = (el: Element) =>
      Number.parseFloat(getComputedStyle(el).fontSize || "0");
    expect(size(middle!)).toBeGreaterThan(0);
    expect(size(end!)).toBeGreaterThan(0);
  });

  it("says how many runs produced it, because that is what makes it a band", () => {
    render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    expect(
      screen.getByText(new RegExp(String(advice.headline.runs))),
    ).toBeInTheDocument();
  });

  it("carries the whole band in its accessible description, not only the middle", () => {
    render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const figure = screen.getByRole("figure");
    const description = figure.getAttribute("aria-label") ?? "";
    expect(description).toContain(dutchAmount(advice.headline.p10));
    expect(description).toContain(dutchAmount(advice.headline.p90));
    // The unit, spoken. A band read out without one is a number a listener
    // cannot place.
    expect(description).toContain("euro");
  });

  it("shows the confidence label as text", () => {
    render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    expect(screen.getByText(advice.confidence_label)).toBeInTheDocument();
  });

  it("shows the band without motion when the visitor asked for less of it", () => {
    // Under a reduced motion preference the band is simply there. Shortening
    // the same animation would leave the meaning in the movement, which is the
    // thing the preference exists to remove.
    installMatchMedia(true);
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const fill = container.querySelector(
      '[data-role="band-fill"]',
    ) as HTMLElement;
    expect(fill).not.toBeNull();
    // Its own width, arrived at without moving. Not 100%: that was the bug.
    const span = bandSpanFraction(advice.headline.p10, advice.headline.p90);
    expect(fill.style.width).toBe(`${span * 100}%`);
    expect(span).toBeLessThan(1);
    expect(fill.style.transitionDuration).toBe("0ms");
  });

  it("renders every amount in Dutch, with every digit the API sent", () => {
    // This used to require the en-US string the API sends, on the grounds that
    // the string is the value and reformatting it is the same class of mistake
    // as parsing it. Half of that is right: parsing it is the mistake, and the
    // formatter never does. The other half made the application English, which
    // CLAUDE.md does not allow. So the assertion is the one that catches the
    // real failure instead: the digits on the screen are the digits that
    // arrived, in the same order, and only the separators moved.
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const shown = container.textContent ?? "";
    const digits = (text: string) => text.replace(/[.,]/g, "");
    for (const amount of [
      advice.headline.p10,
      advice.headline.p50,
      advice.headline.p90,
    ]) {
      expect(shown).toContain(dutchAmount(amount));
      expect(shown).not.toContain(amount);
      expect(digits(dutchAmount(amount))).toBe(digits(amount));
    }
  });
});
