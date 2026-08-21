import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChoiceQuestion } from "@/components/form/ChoiceQuestion";

// The real member names of ampeer_sim.types.EVChargingBehaviour, which is what
// RefineInputSerializer.ev_behaviour derives its choices from. The labels are
// this lane's; the values are the API's and are not invented here.
const options = [
  { value: "NIGHT", label: "Snachts" },
  { value: "ARRIVAL", label: "Zodra de auto thuis is" },
  { value: "SOLAR", label: "Als de zon schijnt" },
] as const;

describe("a choice question", () => {
  it("renders one radio per option, labelled the way it was given", () => {
    render(
      <ChoiceQuestion id="ev" label="Wanneer laadt de auto?" options={options} value={null} onChange={() => {}} />,
    );
    expect(screen.getAllByRole("radio")).toHaveLength(options.length);
    for (const option of options) {
      expect(screen.getByRole("radio", { name: option.label })).toBeInTheDocument();
    }
  });

  it("reports the value and not the label", async () => {
    // The label is Dutch and the value is the enum member the API accepts.
    const onChange = vi.fn();
    render(
      <ChoiceQuestion id="ev" label="Wanneer laadt de auto?" options={options} value={null} onChange={onChange} />,
    );
    await userEvent.click(screen.getByRole("radio", { name: "Snachts" }));
    expect(onChange).toHaveBeenLastCalledWith("NIGHT");
  });

  it("shows which answer is the current one", () => {
    render(
      <ChoiceQuestion
        id="ev"
        label="Wanneer laadt de auto?"
        options={options}
        value="SOLAR"
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("radio", { name: "Als de zon schijnt" })).toBeChecked();
  });

  it("is operable from the keyboard alone", async () => {
    const onChange = vi.fn();
    render(
      <ChoiceQuestion id="ev" label="Wanneer laadt de auto?" options={options} value={null} onChange={onChange} />,
    );
    await userEvent.tab();
    await userEvent.keyboard("{ArrowDown}");
    expect(onChange).toHaveBeenCalled();
  });

  it("names the group, so the question is not lost between the answers", () => {
    render(
      <ChoiceQuestion id="ev" label="Wanneer laadt de auto?" options={options} value={null} onChange={() => {}} />,
    );
    expect(screen.getByRole("group", { name: "Wanneer laadt de auto?" })).toBeInTheDocument();
  });
});
