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
      <ChoiceQuestion
        id="ev"
        label="Wanneer laadt de auto?"
        options={options}
        value={null}
        onChange={() => {}}
      />,
    );
    expect(screen.getAllByRole("radio")).toHaveLength(options.length);
    for (const option of options) {
      expect(
        screen.getByRole("radio", { name: option.label }),
      ).toBeInTheDocument();
    }
  });

  it("reports the value and not the label", async () => {
    // The label is Dutch and the value is the enum member the API accepts.
    const onChange = vi.fn();
    render(
      <ChoiceQuestion
        id="ev"
        label="Wanneer laadt de auto?"
        options={options}
        value={null}
        onChange={onChange}
      />,
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
    expect(
      screen.getByRole("radio", { name: "Als de zon schijnt" }),
    ).toBeChecked();
  });

  it("is operable from the keyboard alone", async () => {
    const onChange = vi.fn();
    render(
      <ChoiceQuestion
        id="ev"
        label="Wanneer laadt de auto?"
        options={options}
        value={null}
        onChange={onChange}
      />,
    );
    await userEvent.tab();
    await userEvent.keyboard("{ArrowDown}");
    expect(onChange).toHaveBeenCalled();
  });

  it("names the group, so the question is not lost between the answers", () => {
    render(
      <ChoiceQuestion
        id="ev"
        label="Wanneer laadt de auto?"
        options={options}
        value={null}
        onChange={() => {}}
      />,
    );
    expect(
      screen.getByRole("group", { name: "Wanneer laadt de auto?" }),
    ).toBeInTheDocument();
  });
  it("borrows a name that is already on the screen instead of repeating it", () => {
    // The one-question-per-screen case. QuestionShell's heading asks the
    // question; a legend underneath it would ask the same thing again, and
    // until 2026-09-02 it asked it in different words, with the qualifier that
    // decides the answer only in the second copy. So the group is named by the
    // heading and writes no legend of its own.
    render(
      <>
        <h2 id="vraag-titel">
          Is er op een doordeweekse dag overdag meestal iemand thuis?
        </h2>
        <ChoiceQuestion
          id="thuis"
          labelledBy="vraag-titel"
          options={options}
          value={null}
          onChange={() => {}}
        />
      </>,
    );
    const group = screen.getByRole("group", {
      name: "Is er op een doordeweekse dag overdag meestal iemand thuis?",
    });
    expect(group).toBeInTheDocument();
    expect(group.querySelector("legend")).toBeNull();
  });
});
