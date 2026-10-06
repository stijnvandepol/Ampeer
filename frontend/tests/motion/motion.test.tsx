import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { installMatchMedia } from "../matchMedia";
import { Beam } from "@/components/motion/Beam";
import { CountUp } from "@/components/motion/CountUp";
import { Cursor } from "@/components/motion/Cursor";
import { HeroHeading } from "@/components/motion/HeroHeading";
import { Magnetic } from "@/components/motion/Magnetic";
import { Mesh } from "@/components/motion/Mesh";
import { SpotlightCard } from "@/components/motion/SpotlightCard";

/** A box with a size, because jsdom measures every element as zero. */
function size(element: Element, width = 200, height = 100, left = 0, top = 0) {
  vi.spyOn(element, "getBoundingClientRect").mockReturnValue({
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    x: left,
    y: top,
    toJSON: () => ({}),
  });
}

beforeEach(() => installMatchMedia(false));
afterEach(() => vi.restoreAllMocks());

describe("HeroHeading", () => {
  it("gives a screen reader the sentence and not the letters", () => {
    // A wall of one-character elements is announced one character at a time.
    // The label is the whole heading, once, and every span is hidden.
    render(<HeroHeading text="Reken het door" />);
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveAttribute("aria-label", "Reken het door");
    expect(
      heading.querySelectorAll("[aria-hidden='true']").length,
    ).toBeGreaterThan(0);
    expect(heading.textContent).toBe("Reken het door");
  });

  it("splits on words first, so a line can only break between them", () => {
    const { container } = render(<HeroHeading text="een twee" />);
    // Two words, and every character inside one of them.
    const words = container.querySelectorAll("h1 > span");
    expect(words).toHaveLength(2);
    // Three characters in "een", each its own span inside the word. Counted
    // through `children` and not `querySelectorAll("span span")`: a selector
    // can match using ancestors OUTSIDE the element it is scoped to, so the
    // word span itself matches that one and the count comes back one too high.
    expect(words[0]?.firstElementChild?.children).toHaveLength(3);
  });

  it("numbers the characters straight through, across the space", () => {
    // The delay is the character's index in the whole heading. Restarting the
    // count at each word makes every word begin at once, which reads as words
    // appearing rather than as a line being written.
    const { container } = render(<HeroHeading text="ab cd" />);
    const delays = [...container.querySelectorAll("h1 [style*='--at']")].map(
      (span) => (span as HTMLElement).style.getPropertyValue("--at"),
    );
    expect(delays).toEqual(["0", "1", "2", "3"]);
  });

  it("renders a plain heading when motion is not wanted", () => {
    installMatchMedia(true);
    const { container } = render(<HeroHeading text="Reken het door" />);
    expect(container.querySelectorAll("span")).toHaveLength(0);
    expect(container.querySelector("h1")?.textContent).toBe("Reken het door");
  });
});

describe("Mesh", () => {
  it("drifts only when motion is wanted", () => {
    const { container, unmount } = render(<Mesh />);
    expect(container.querySelector("[data-role='hero-mesh']")).toHaveAttribute(
      "data-drifting",
      "true",
    );
    unmount();
    installMatchMedia(true);
    const still = render(<Mesh />);
    expect(
      still.container.querySelector("[data-role='hero-mesh']"),
    ).toHaveAttribute("data-drifting", "false");
  });

  it("stays out of the accessibility tree", () => {
    const { container } = render(<Mesh />);
    expect(container.querySelector("[data-role='hero-mesh']")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
  });
});

describe("SpotlightCard", () => {
  it("writes the pointer position onto the card rather than into state", () => {
    // A render per pointer move is the difference between this holding 60fps
    // and this being the reason a page drops frames.
    const { container } = render(<SpotlightCard>kaart</SpotlightCard>);
    const card = container.querySelector("[data-role='spotlight-card']")!;
    size(card, 200, 100);
    fireEvent.pointerEnter(card, { clientX: 150, clientY: 75 });
    const style = (card as HTMLElement).style;
    expect(style.getPropertyValue("--spot-x")).toBe("150px");
    expect(style.getPropertyValue("--spot-y")).toBe("75px");
    expect(style.getPropertyValue("--spot-lit")).toBe("1");
    // The angle points from the middle towards the pointer, so the bright arc
    // is the edge nearest the cursor.
    expect(
      Number.parseFloat(style.getPropertyValue("--spot-angle")),
    ).toBeCloseTo(26.6, 0);
    fireEvent.pointerLeave(card);
    expect(style.getPropertyValue("--spot-lit")).toBe("0");
  });

  it("attaches nothing when motion is not wanted", () => {
    installMatchMedia(true);
    const { container } = render(<SpotlightCard>kaart</SpotlightCard>);
    const card = container.querySelector("[data-role='spotlight-card']")!;
    size(card);
    fireEvent.pointerEnter(card, { clientX: 10, clientY: 10 });
    // A spotlight has no end state to jump to, so the answer is no listener at
    // all rather than a shorter transition.
    expect((card as HTMLElement).style.getPropertyValue("--spot-lit")).toBe("");
  });
});

describe("CountUp", () => {
  it("puts the final number where a screen reader reads it", () => {
    // Never the intermediate values. A number announced forty times is worse
    // than a number not animated at all.
    const { container } = render(<CountUp to={243} />);
    expect(container.querySelector(".sr-only")?.textContent).toBe("243");
  });

  it("groups a large number the Dutch way", () => {
    const { container } = render(<CountUp to={35040} grouped />);
    expect(container.querySelector(".sr-only")?.textContent).toBe("35.040");
  });

  it("shows the final number when there is no observer to watch with", () => {
    // A browser that cannot tell when the element arrives keeps the answer
    // rather than a number that never counts.
    const original = window.IntersectionObserver;
    // @ts-expect-error deleting a global for the length of one test
    delete window.IntersectionObserver;
    const { container } = render(<CountUp to={96} />);
    expect(container.textContent).toContain("96");
    window.IntersectionObserver = original;
  });

  it("counts from zero once it is scrolled to, and lands on the number", () => {
    let observed: (entries: { isIntersecting: boolean }[]) => void = () => {};
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(
          callback: (entries: { isIntersecting: boolean }[]) => void,
        ) {
          observed = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((frame) => {
      frames.push(frame);
      return frames.length;
    });

    const { container } = render(<CountUp to={100} />);
    act(() => observed([{ isIntersecting: true }]));
    expect(container.querySelector("[aria-hidden]")?.textContent).toBe("0");

    act(() => frames[0]?.(0));
    act(() => frames[frames.length - 1]?.(5_000));
    // Past the end it holds the number rather than overshooting it.
    expect(container.querySelector("[aria-hidden]")?.textContent).toBe("100");
  });
});

describe("Beam", () => {
  it("declares its own length, so nothing has to measure the path", () => {
    // pathLength="1" makes every dash value a fraction of the whole line. The
    // alternative is reading the path's length in JavaScript on mount and on
    // every resize.
    const { container } = render(<Beam d="M 0 0 L 100 100" />);
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(2);
    for (const path of paths) expect(path).toHaveAttribute("pathLength", "1");
  });

  it("is decoration and says so", () => {
    const { container } = render(<Beam d="M 0 0 L 0 100" />);
    expect(container.querySelector("svg")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    expect(container.querySelector("svg")).toHaveAttribute(
      "focusable",
      "false",
    );
  });
});

describe("Magnetic", () => {
  it("leans towards the pointer and returns when it leaves", () => {
    const { container } = render(
      <Magnetic>
        <button type="button">ga</button>
      </Magnetic>,
    );
    const magnet = container.querySelector(
      "[data-role='magnetic']",
    )! as HTMLElement;
    size(magnet, 200, 100);
    fireEvent.pointerMove(magnet, { clientX: 150, clientY: 75 });
    // 22 percent of the distance from the middle: 50px and 25px.
    expect(magnet.style.transform).toBe("translate(11.00px, 5.50px)");
    expect(magnet.dataset["leaning"]).toBe("true");
    fireEvent.pointerLeave(magnet);
    expect(magnet.style.transform).toBe("");
    expect(magnet.dataset["leaning"]).toBe("false");
  });

  it("sits still when the pointer is nowhere near it", () => {
    // Without this the child creeps whenever the pointer is anywhere on the
    // page, which is uncanny rather than pleasant.
    const { container } = render(<Magnetic>ga</Magnetic>);
    const magnet = container.querySelector(
      "[data-role='magnetic']",
    )! as HTMLElement;
    size(magnet, 200, 100);
    fireEvent.pointerMove(magnet, { clientX: 900, clientY: 75 });
    expect(magnet.style.transform).toBe("");
  });

  it("wraps the child in nothing at all when motion is not wanted", () => {
    installMatchMedia(true);
    const { container } = render(<Magnetic>ga</Magnetic>);
    expect(container.querySelector("[data-role='magnetic']")).toBeNull();
    expect(container.textContent).toBe("ga");
  });
});

describe("Cursor", () => {
  it("renders nothing at all when motion is not wanted", () => {
    installMatchMedia(true);
    const { container } = render(<Cursor />);
    expect(container).toBeEmptyDOMElement();
  });

  it("follows the pointer and opens over something you can use", () => {
    const { container } = render(<Cursor />);
    const ring = container.querySelector(
      "[data-role='cursor']",
    )! as HTMLElement;
    const link = document.createElement("a");
    link.href = "/berekenen/";
    document.body.append(link);

    // Dispatched from a real element so the DOM sets `target` itself. Assigning
    // it on a hand-made Event throws: it is a getter.
    const move = (from: Element) =>
      from.dispatchEvent(
        Object.assign(
          new MouseEvent("pointermove", {
            bubbles: true,
            clientX: 40,
            clientY: 60,
          }),
        ),
      );

    move(document.body);
    expect(ring.style.getPropertyValue("--ring-x")).toBe("40px");
    expect(ring.style.getPropertyValue("--ring-over")).toBe("0");

    move(link);
    expect(ring.style.getPropertyValue("--ring-over")).toBe("1");
    link.remove();
  });

  it("attaches nothing on a device with no fine pointer", () => {
    // A phone has no cursor to decorate, and would otherwise get a ring
    // wherever the last tap landed.
    installMatchMedia(false, { "(pointer: fine)": false });
    const { container } = render(<Cursor />);
    const ring = container.querySelector(
      "[data-role='cursor']",
    )! as HTMLElement;
    document.body.dispatchEvent(
      new MouseEvent("pointermove", {
        bubbles: true,
        clientX: 40,
        clientY: 60,
      }),
    );
    expect(ring.style.getPropertyValue("--ring-x")).toBe("");
  });
});
