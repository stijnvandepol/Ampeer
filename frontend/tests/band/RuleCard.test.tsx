import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import fixture from "../fixtures/advice-response.json";
import { RuleCard } from "@/components/band/RuleCard";
import type { Advice, FiredRule } from "@/lib/types";

const advice = fixture as unknown as Advice;
const withBand = advice.routes
  .flatMap((r) => r.rules)
  .find((r) => r.saving_eur !== null)!;
const withoutBand = advice.routes
  .flatMap((r) => r.rules)
  .find((r) => r.saving_eur === null)!;

describe("a rule card", () => {
  it("shows the API's sentence and nothing it wrote itself", () => {
    render(<RuleCard rule={withBand} />);
    expect(screen.getByText(withBand.text)).toBeInTheDocument();
  });

  it("draws a band beside a rule that carries one", () => {
    const { container } = render(<RuleCard rule={withBand} />);
    expect(
      container.querySelector('[data-band-kind="scenario"]'),
    ).not.toBeNull();
  });

  it("invents no band for a rule that carries none", () => {
    // A rule with saving_eur null is a rule the model put no number on. A
    // placeholder here would be a number nobody computed.
    const rule: FiredRule = withoutBand;
    const { container } = render(<RuleCard rule={rule} />);
    expect(container.querySelector("[data-band-kind]")).toBeNull();
    expect(screen.getByText(rule.text)).toBeInTheDocument();
  });
});
