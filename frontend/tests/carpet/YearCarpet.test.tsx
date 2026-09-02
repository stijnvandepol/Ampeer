import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { installMatchMedia } from "../matchMedia";
import fixture from "../fixtures/advice-response.json";
import { YearCarpet } from "@/components/carpet/YearCarpet";
import type { Advice, YearSeries } from "@/lib/types";

const advice = fixture as unknown as Advice;

/** The real year the API sends, out of the fixture the generator writes. */
function realYear(): YearSeries {
  const year = advice.year;
  if (year === undefined) {
    throw new Error(
      "the committed fixture carries no year; tests/helpers/advice_fixture.py " +
        "builds it and this test is what notices when it stops",
    );
  }
  return year;
}

/**
 * A 2d context, because jsdom has none.
 *
 * jsdom answers getContext with null, and the component treats that as a
 * browser that cannot draw and renders everything except the picture. That is
 * a real path and it has its own test below, but it is not the path that draws
 * 35040 cells, so the drawing tests need a context to draw into.
 */
function installContext(): Record<string, unknown> {
  const context = {
    createImageData: (width: number, height: number) => ({
      data: new Uint8ClampedArray(width * height * 4),
      width,
      height,
    }),
    putImageData: vi.fn(),
    fillRect: vi.fn(),
    fillStyle: "",
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );
  return context;
}

/**
 * A palette, because jsdom resolves no custom properties.
 *
 * The component refuses to draw without all four, which is deliberate: three
 * of four is a plate that says something untrue. So a test that wants the
 * drawing path has to supply them.
 */
function installPalette(): void {
  vi.spyOn(window, "getComputedStyle").mockReturnValue({
    getPropertyValue: (name: string) =>
      ({
        "--colour-carpet-ground": "#071019",
        "--colour-carpet-own": "#f5c64a",
        "--colour-carpet-offtake": "#5c7385",
        "--colour-carpet-export": "#16232e",
      })[name] ?? "",
  } as unknown as CSSStyleDeclaration);
}

/** jsdom measures every box as zero, and a zero wide plate reads nothing. */
function sizePlate(plate: HTMLElement, width = 365, height = 96): void {
  vi.spyOn(plate, "getBoundingClientRect").mockReturnValue({
    left: 0,
    top: 0,
    width,
    height,
    right: width,
    bottom: height,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
}

function plateOf(): HTMLElement {
  return screen.getByRole("img", { name: /Een jaar in kwartieren/ });
}

beforeEach(() => installMatchMedia(false));
afterEach(() => vi.restoreAllMocks());

describe("the year carpet", () => {
  it("draws a plate as wide as the year and as tall as a day", () => {
    installContext();
    installPalette();
    render(<YearCarpet year={realYear()} />);
    const plate = plateOf();
    expect(plate).toHaveAttribute("width", "365");
    expect(plate).toHaveAttribute("height", "96");
  });

  it("names the three colours it draws, for a reader who cannot see them", () => {
    installContext();
    installPalette();
    render(<YearCarpet year={realYear()} />);
    expect(plateOf().getAttribute("aria-label")).toContain("Geel staat voor");
  });

  it("renders nothing at all when the payload does not describe a year", () => {
    // Not a gap where a plate should be: the page is the page it was before
    // this field existed. Every refusal in decodeYear is a payload that could
    // only be drawn as a year that did not happen.
    const { container } = render(
      <YearCarpet year={{ ...realYear(), quarters: 7 }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders everything but the picture when the browser cannot draw", () => {
    // jsdom's own answer, and a real browser's under some privacy settings.
    // The plate is the one thing on this page a reader can do without.
    render(<YearCarpet year={realYear()} />);
    expect(plateOf()).toBeInTheDocument();
    expect(screen.getByText(/Beweeg over de plaat/)).toBeInTheDocument();
  });

  it("reads a quarter out of the picture where the pointer is", () => {
    installContext();
    installPalette();
    render(<YearCarpet year={realYear()} />);
    const plate = plateOf();
    sizePlate(plate);
    fireEvent.pointerMove(plate, { clientX: 0.5, clientY: 48.5 });
    // Column zero, halfway down: 1 January at midday.
    expect(screen.getByText("1 jan 12:00")).toBeInTheDocument();
    expect(screen.getByText(/kWh zelf gebruikt/)).toBeInTheDocument();
  });

  it("forgets the quarter when the pointer leaves", () => {
    installContext();
    installPalette();
    render(<YearCarpet year={realYear()} />);
    const plate = plateOf();
    sizePlate(plate);
    fireEvent.pointerMove(plate, { clientX: 0.5, clientY: 48.5 });
    fireEvent.pointerLeave(plate);
    expect(screen.getByText(/Beweeg over de plaat/)).toBeInTheDocument();
  });

  it("moves with the arrow keys and says where it went", () => {
    installContext();
    installPalette();
    render(<YearCarpet year={realYear()} />);
    const plate = plateOf();
    fireEvent.keyDown(plate, { key: "ArrowRight" });
    expect(screen.getByText("2 jan 00:00")).toBeInTheDocument();
    fireEvent.keyDown(plate, { key: "ArrowDown" });
    expect(screen.getByText("2 jan 00:15")).toBeInTheDocument();
  });

  it("leaves every other key to the browser", () => {
    // A plate that swallowed every keystroke would take Tab and Escape away
    // from a visitor trying to leave it.
    installContext();
    installPalette();
    render(<YearCarpet year={realYear()} />);
    const taken = fireEvent.keyDown(plateOf(), { key: "Tab" });
    expect(taken).toBe(true);
  });

  it("shows on the plate where the reader is, not only in the sentence", () => {
    installContext();
    installPalette();
    const { container } = render(<YearCarpet year={realYear()} />);
    const crosshair = container.querySelector('[data-role="year-crosshair"]');
    expect(crosshair).toHaveAttribute("data-reading", "false");
    fireEvent.keyDown(plateOf(), { key: "ArrowDown" });
    expect(crosshair).toHaveAttribute("data-reading", "true");
    // Quarter one of ninety six, at the middle of its own row.
    const row = crosshair?.querySelectorAll("span")[1] as HTMLElement;
    expect(row.style.top).toBe("1.5625%");
  });

  it("stands complete at once when motion is not wanted", () => {
    // Not drawn faster: the reveal says something the still plate does not,
    // and under the preference the answer is the still plate.
    installMatchMedia(true);
    const context = installContext();
    installPalette();
    const frames = vi.spyOn(window, "requestAnimationFrame");
    render(<YearCarpet year={realYear()} />);
    expect(context.putImageData).toHaveBeenCalledTimes(1);
    expect(frames).not.toHaveBeenCalled();
  });

  it("draws the year in from January, and marks the edge it is writing at", () => {
    // The frames are driven by hand. jsdom schedules a callback and never runs
    // it before the test ends, so the whole reveal, which is the one movement
    // on this page, would sit uncovered while the test asserted only that it
    // had been asked for.
    const context = installContext();
    installPalette();
    const frames: FrameRequestCallback[] = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((frame) => {
      frames.push(frame);
      return frames.length;
    });
    vi.spyOn(window, "cancelAnimationFrame").mockImplementation(
      () => undefined,
    );

    const started = performance.now();
    render(<YearCarpet year={realYear()} />);
    // One frame asked for, and the ground painted so the year arrives onto the
    // instrument rather than onto whatever the canvas held before.
    expect(frames).toHaveLength(1);
    expect(context.fillRect).toHaveBeenCalledTimes(1);

    frames[0]?.(started + 600);
    // Half way: the columns drawn so far, and one more fillRect for the bright
    // edge the year is being written at.
    expect(context.putImageData).toHaveBeenCalled();
    expect(context.fillRect).toHaveBeenCalledTimes(2);
    expect(frames).toHaveLength(2);

    frames[1]?.(started + 5_000);
    // Past the end: the last column is data like every other, so no edge is
    // drawn over it and nothing more is asked for.
    expect(context.fillRect).toHaveBeenCalledTimes(2);
    expect(frames).toHaveLength(2);
  });
});
