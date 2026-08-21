import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  ALL_QUESTION_COUNT,
  Progress,
  ROUND_ONE_QUESTION_COUNT,
  ROUND_TWO_QUESTION_COUNT,
} from "@/components/form/Progress";

describe("the progress indicator", () => {
  it("says where you are in words as well as in pixels", () => {
    render(<Progress step={2} of={4} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "4");
    expect(bar).toHaveAttribute("aria-valuemin", "1");
    expect(screen.getByText("Vraag 2 van 4")).toBeInTheDocument();
  });

  it("counts four questions in round one, not five values", () => {
    // Orientation and tilt are one question about one roof. Counting five
    // here would be the same mistake that would push every estimate past the
    // GOOD threshold in the API. The count comes from the constant rather than
    // from a literal in the test, so the test cannot pass while the flow uses
    // a different number.
    render(<Progress step={1} of={ROUND_ONE_QUESTION_COUNT} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuemax",
      "4",
    );
  });

  it("agrees with the question counts the serializers carry", () => {
    // EstimateInputSerializer.QUESTION_COUNT is 4 and
    // RefineInputSerializer.QUESTION_COUNT is 9, and that count is what decides
    // the confidence label, so the two sides have to mean the same thing.
    expect(ROUND_ONE_QUESTION_COUNT).toBe(4);
    expect(ROUND_TWO_QUESTION_COUNT).toBe(5);
    expect(ALL_QUESTION_COUNT).toBe(9);
  });
});
