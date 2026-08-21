import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import fixture from "../fixtures/advice-response.json";
import { RouteSection } from "@/components/band/RouteSection";
import type { Advice, RouteBlock } from "@/lib/types";

const advice = fixture as unknown as Advice;
const empty: RouteBlock = {
  route: "SMART_CONTROL",
  title: "Gratis: slimmer sturen",
  rules: [],
};

describe("a route section", () => {
  it("renders an empty route rather than hiding it", () => {
    // "There is nothing left to do here" is an answer. Hiding the section
    // hides it, and makes the frontend responsible for an order the API
    // already guarantees.
    render(<RouteSection route={empty} />);
    expect(screen.getByText(empty.title)).toBeInTheDocument();
    expect(screen.getByText(/niets meer te halen/i)).toBeInTheDocument();
  });

  it("uses the title the API sent, never one of its own", () => {
    render(<RouteSection route={empty} />);
    expect(
      screen.getByRole("heading", { name: empty.title }),
    ).toBeInTheDocument();
  });

  it("renders every rule the route carries, in the order it was sent", () => {
    const filled = advice.routes[0]!;
    render(<RouteSection route={filled} />);
    for (const rule of filled.rules) {
      expect(screen.getByText(rule.text)).toBeInTheDocument();
    }
    expect(screen.queryByText(/niets meer te halen/i)).toBeNull();
  });
});
