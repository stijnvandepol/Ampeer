import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PriceGap } from "@/components/gap/PriceGap";
import {
  EXPORTED_2027_CENTS,
  SELF_USED_CENTS,
  boxOf,
} from "@/components/gap/prices";

function plotOf(): HTMLElement {
  return screen.getByRole("img", { name: /Wat een kilowattuur waard is/ });
}

/** The two band elements, in the order the figure draws them. */
function bands(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll("span")].filter(
    (element) => element.style.height !== "",
  ) as HTMLElement[];
}

describe("the price gap", () => {
  it("starts with the two bands on top of each other", () => {
    // Not a styling detail. While saldering lasts an exported kilowatt hour is
    // worth exactly the imported one it cancels, so two bands at different
    // heights here would be the figure claiming saldering does something it
    // does not.
    const { container } = render(<PriceGap />);
    const [self, away] = bands(container);
    expect(self?.style.top).toBe(away?.style.top);
    expect(self?.style.height).toBe(away?.style.height);
  });

  it("drops the exported band and widens it when the year changes", () => {
    const { container } = render(<PriceGap />);
    const before = bands(container)[1]?.style.top;
    fireEvent.click(screen.getByRole("button", { name: "Vanaf 2027" }));
    const [self, away] = bands(container);

    // Down the plot, which is a larger percentage from the top.
    expect(Number.parseFloat(away?.style.top ?? "0")).toBeGreaterThan(
      Number.parseFloat(before ?? "0"),
    );
    // And wider than the band it left, because the price stopped being known.
    // This is the half that makes the movement allowed at all: what moves is
    // the uncertainty.
    expect(Number.parseFloat(away?.style.height ?? "0")).toBeGreaterThan(
      Number.parseFloat(self?.style.height ?? "0"),
    );
    // The self-used band did not move. The change is not that using your own
    // power became worth more.
    expect(self?.style.top).toBe(`${boxOf(SELF_USED_CENTS).top}%`);
  });

  it("says the figure in words, with both ends and the sign", () => {
    render(<PriceGap />);
    expect(screen.getByText(/dat is de regeling/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Vanaf 2027" }));
    // Both ends of the band, and the fact that the lower one is negative. A
    // caption naming only the top would be the "3 tot 8 cent" mistake in this
    // product's own voice.
    expect(screen.getByText(/-6,5 tot 3,2 cent/)).toBeInTheDocument();
    expect(screen.getByText(/kost terugleveren u geld/)).toBeInTheDocument();
    expect(EXPORTED_2027_CENTS.low).toBeLessThan(0);
  });

  it("tells a screen reader which year it is showing", () => {
    render(<PriceGap />);
    const now = screen.getByRole("button", { name: "Zoals het nu is" });
    const later = screen.getByRole("button", { name: "Vanaf 2027" });
    expect(now).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(later);
    expect(later).toHaveAttribute("aria-pressed", "true");
    expect(now).toHaveAttribute("aria-pressed", "false");
    expect(plotOf()).toHaveAttribute("data-regime", "2027");
  });

  it("describes what it draws for somebody who cannot see it", () => {
    render(<PriceGap />);
    const described = plotOf().getAttribute("aria-label") ?? "";
    expect(described).toContain("minder dan nul");
    expect(described.length).toBeGreaterThan(120);
  });
});
