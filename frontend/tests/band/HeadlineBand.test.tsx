import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { installMatchMedia } from "../matchMedia";
import fixture from "../fixtures/advice-response.json";
import { HeadlineBand } from "@/components/band/HeadlineBand";
import { dutchAmount } from "@/components/band/format";
import {
  axisPercentage,
  bandIsRightPinned,
  bandOffsetFraction,
  bandSpanFraction,
  LABEL_ANCHOR_PROPERTY,
  labelAnchor,
} from "@/components/band/position";

/** The one number a label is placed by. The stylesheet derives the rest. */
function anchorOf(element: Element | null): string {
  return (
    (element as HTMLElement | null)?.style.getPropertyValue(
      LABEL_ANCHOR_PROPERTY,
    ) ?? ""
  );
}
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
    // This fixture's low end is positive, so its right edge, not its left, is
    // pinned to the axis's own end (see bandIsRightPinned): the fill is
    // anchored by `right`, and `left` is left for the browser to compute.
    expect(bandIsRightPinned(advice.headline.p10)).toBe(true);
    expect(fill.style.left).toBe("");
    expect(fill.style.right).toBe(
      `${Math.max(0, (1 - offset - expected) * 100)}%`,
    );
    const figure = container.querySelector("[data-band-span]");
    expect(Number(figure?.getAttribute("data-band-span"))).toBeCloseTo(
      expected,
      4,
    );
  });

  it("anchors each end label to the end of the band it names, not to the end of the track", () => {
    // The two ends used to be a flex row spanning the whole track with
    // justify-content: space-between, so on this fixture the fill covered the
    // right third and "€ 1.382,13" was typeset under the axis's zero. Neither
    // end label carried a position at all, which is what this asserts now: the
    // low label's left is the fill's own left, and the high label's is the far
    // end of the band. The actual pixels are measured in e2e/rules.spec.ts,
    // because jsdom lays nothing out and cannot see a layout defect; this is
    // the cheap half that fails the moment an end label loses its anchor.
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
    const ends = [
      ...container.querySelectorAll('[data-role="band-end"]'),
    ] as HTMLElement[];
    expect(ends).toHaveLength(2);

    const offset = bandOffsetFraction(advice.headline.p10, advice.headline.p90);
    const span = bandSpanFraction(advice.headline.p10, advice.headline.p90);
    // Non-vacuous: if the band started at the left of the track then "at the
    // end of the band" and "at the end of the track" would be the same place
    // and this test would pass on the layout it exists to forbid.
    expect(offset).toBeGreaterThan(0.2);

    const low = labelAnchor(offset * 100)[LABEL_ANCHOR_PROPERTY];
    const high = labelAnchor((offset + span) * 100)[LABEL_ANCHOR_PROPERTY];
    expect(anchorOf(ends[0] ?? null)).toBe(low);
    expect(anchorOf(ends[1] ?? null)).toBe(high);
    // This fixture's low end is positive, so the fill is anchored by `right`,
    // not `left` (see bandIsRightPinned): the edge that cannot be a second,
    // independently drifting computation of a label's position is now the
    // high end and the fill's own right, rather than the low end and left.
    expect(bandIsRightPinned(advice.headline.p10)).toBe(true);
    const highFromFill = 100 - Number.parseFloat(fill.style.right);
    expect(labelAnchor(highFromFill)[LABEL_ANCHOR_PROPERTY]).toBe(high);
  });

  it("anchors the middle label and the axis's zero by the same mechanism", () => {
    // One placement rule for every label on the figure. Two would drift, and
    // the middle being anchored while the ends were not is exactly how this
    // figure came to contradict itself.
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    const middle = container.querySelector(
      '[data-role="band-middle"]',
    ) as HTMLElement;
    const expected = labelAnchor(
      axisPercentage(
        advice.headline.p10,
        advice.headline.p50,
        advice.headline.p90,
      ),
    );
    expect(anchorOf(middle)).toBe(expected[LABEL_ANCHOR_PROPERTY]);

    // The scale's zero, at the axis's own zero. Hidden from assistive
    // technology: the aria-label already spells the band out, and "0 euro" in
    // it would suggest the model said something about zero.
    const zero = screen.getByText(/^€\s*0$/);
    expect(zero).toHaveAttribute("aria-hidden", "true");
    expect(anchorOf(zero)).toBe(
      labelAnchor(
        axisPercentage(advice.headline.p10, "0", advice.headline.p90),
      )[LABEL_ANCHOR_PROPERTY],
    );
  });

  it("places the labels from the amounts, so reduced motion changes nothing about them", () => {
    // The fill's width is animated and the labels are not. A label that was
    // positioned off the drawn width would be in the wrong place for the first
    // 320ms without a reduced motion preference, and in the right place with
    // one, which is a defect only half the visitors could see.
    const anchors = (mode: boolean) => {
      installMatchMedia(mode);
      const { container, unmount } = render(
        <HeadlineBand
          band={advice.headline}
          confidence={advice.confidence}
          label={advice.confidence_label}
        />,
      );
      const found = [
        ...container.querySelectorAll(
          '[data-role="band-end"],[data-role="band-middle"]',
        ),
      ].map(anchorOf);
      unmount();
      return found;
    };
    const still = anchors(true);
    const moving = anchors(false);
    expect(still).toHaveLength(3);
    expect(still.every((at) => at.endsWith("%"))).toBe(true);
    expect(moving).toEqual(still);
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

  it("speaks the confidence but no longer prints it", () => {
    // It moved to ConfidenceBadge on 2026-09-15, above the first step, because
    // rule two puts it in the first screen and this band is no longer the first
    // thing on the page. Both halves are asserted here: the figure must not
    // draw it twice, and its spoken description must still end with it, because
    // a screen reader hears one sentence about a figure and should not need a
    // separate badge for that sentence to make sense.
    const { container } = render(
      <HeadlineBand
        band={advice.headline}
        confidence={advice.confidence}
        label={advice.confidence_label}
      />,
    );
    expect(screen.queryByText(advice.confidence_label)).toBeNull();
    const figure = container.querySelector("[data-band-kind='percentile']");
    expect(figure?.getAttribute("aria-label")).toContain(
      advice.confidence_label,
    );
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
