import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FirstStep } from "@/components/band/FirstStep";
import type { RouteBlock } from "@/lib/types";

const RULE = {
  rule_id: "SHIFT_FLEXIBLE_LOAD",
  action: "Zet de wasmachine midden op de dag aan.",
  text: "Verschuif de wasmachine naar het midden van de dag, want dat scheelt.",
  saving_eur: null,
} as const;

function routes(
  ...blocks: readonly Partial<RouteBlock>[]
): readonly RouteBlock[] {
  return blocks.map((block, index) => ({
    route:
      (["SHIFT_BEHAVIOUR", "SMART_CONTROL", "STORAGE"] as const)[index] ??
      "STORAGE",
    title: `Route ${index}`,
    rules: [],
    ...block,
  }));
}

describe("the first step", () => {
  it("shows the first rule of the first route that has one", () => {
    render(<FirstStep routes={routes({ rules: [RULE] }, {})} />);
    expect(screen.getByText(RULE.action)).toBeInTheDocument();
  });

  it("skips an empty route rather than showing nothing", () => {
    // The free routes come first and one of them can be empty. Reading
    // `routes[0]` would then leave the block blank on a household the model
    // did have an action for.
    render(<FirstStep routes={routes({}, { rules: [RULE] })} />);
    expect(screen.getByText(RULE.action)).toBeInTheDocument();
  });

  it("renders nothing at all when the model found no action", () => {
    // Not an encouraging placeholder. The three route sections below still
    // render and still say where there is nothing to be had, which is the
    // answer; inventing a cheerful line here would be the frontend writing
    // advice.
    const { container } = render(<FirstStep routes={routes({}, {}, {})} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("writes no sentence of its own beyond naming itself", () => {
    // The language boundary. `rule.action` arrives from the API and is
    // rendered as it came; the only words this component owns are its label.
    const { container } = render(
      <FirstStep routes={routes({ rules: [RULE] }, {})} />,
    );
    const text = container.textContent ?? "";
    expect(text.replace("Begin hier", "").trim()).toBe(RULE.action);
  });

  it("leaves the paragraph to the route below rather than repeating it", () => {
    // The whole point of the block is that it is short. Showing the long text
    // here as well would put the thing it replaces directly under it.
    render(<FirstStep routes={routes({ rules: [RULE] }, {})} />);
    expect(screen.queryByText(RULE.text)).toBeNull();
  });

  it("carries the rule id, so the advice stays traceable", () => {
    const { container } = render(
      <FirstStep routes={routes({ rules: [RULE] }, {})} />,
    );
    expect(
      container.querySelector(`[data-first-step-rule-id="${RULE.rule_id}"]`),
    ).not.toBeNull();
  });
});
