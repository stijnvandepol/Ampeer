import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DayCounting } from "@/components/day/DayCounting";
import { QUARTERS, blockSizes, illustrativeDay } from "@/components/day/shape";

const COUNTS = blockSizes(illustrativeDay());

/**
 * A palette, because jsdom resolves no custom properties.
 *
 * The component lifts each cell towards white with the plate's own function,
 * and that function needs the plate's own four tokens. Without them it refuses,
 * which is a real path with its own test below.
 */
function installPalette(): void {
  vi.spyOn(window, "getComputedStyle").mockReturnValue({
    getPropertyValue: (name: string) =>
      ({
        "--colour-carpet-ground": "#071019",
        "--colour-carpet-own": "#f5c64a",
        "--colour-carpet-offtake": "#8b9ba8",
        "--colour-carpet-export": "#3f6489",
      })[name] ?? "",
  } as unknown as CSSStyleDeclaration);
}

function stripOf(): HTMLElement {
  return screen.getByRole("img", { name: /voorbeelddag van 96 kwartieren/ });
}

afterEach(() => vi.restoreAllMocks());

describe("the day figure", () => {
  it("draws one cell per quarter of the day", () => {
    installPalette();
    render(<DayCounting />);
    expect(stripOf().children).toHaveLength(QUARTERS);
  });

  it("says in words what the picture says in colour", () => {
    installPalette();
    render(<DayCounting />);
    // The counts are the figure's only numbers, and they are read out of the
    // same day the cells are drawn from rather than written twice.
    expect(
      screen.getByText(new RegExp(`${COUNTS.own} van de 96 kwartieren`)),
    ).toBeInTheDocument();
  });

  it("moves the cells into blocks and changes what it claims", () => {
    installPalette();
    render(<DayCounting />);
    const strip = stripOf();
    expect(strip).toHaveAttribute("data-order", "time");
    // The clock is on the axis while the cells are in time.
    expect(screen.getByText("12:00")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Zoals salderen telt" }),
    );

    expect(strip).toHaveAttribute("data-order", "meter");
    expect(screen.getByText(/nooit langs de meter/)).toBeInTheDocument();
    // And gone once they are not: a clock under sorted cells is a lie, and it
    // is the smallest form of the thing this figure argues.
    expect(screen.queryByText("12:00")).not.toBeInTheDocument();
    expect(
      screen.getByText(`teruggeleverd ${COUNTS.export}`),
    ).toBeInTheDocument();
  });

  it("tells a screen reader which order it is looking at", () => {
    installPalette();
    render(<DayCounting />);
    const time = screen.getByRole("button", { name: "Op tijd" });
    const meter = screen.getByRole("button", { name: "Zoals salderen telt" });
    expect(time).toHaveAttribute("aria-pressed", "true");
    expect(meter).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(meter);
    expect(meter).toHaveAttribute("aria-pressed", "true");
    expect(time).toHaveAttribute("aria-pressed", "false");
  });

  it("lifts each cell with the plate's own rule", () => {
    installPalette();
    render(<DayCounting />);
    const cells = [...stripOf().children] as HTMLElement[];
    const painted = cells.filter((cell) => cell.style.background !== "");
    expect(painted).toHaveLength(QUARTERS);
    // Every colour the lift can produce is inside a band
    // tests/carpet/palette.test.ts measures, because it is that module's
    // function doing the lifting. What is checked here is only that it ran.
    expect(
      new Set(painted.map((cell) => cell.style.background)).size,
    ).toBeGreaterThan(20);
  });

  it("still draws the day when the palette cannot be read", () => {
    // jsdom's own answer without the stub above, and a real browser's before
    // the stylesheet has resolved. The cells keep the class the server gave
    // them, which paints each state's token, which is the floor of its band.
    render(<DayCounting />);
    const cells = [...stripOf().children] as HTMLElement[];
    expect(cells).toHaveLength(QUARTERS);
    expect(cells.every((cell) => cell.style.background === "")).toBe(true);
    expect(cells[0]?.className).toMatch(/offtake/);
  });
});
