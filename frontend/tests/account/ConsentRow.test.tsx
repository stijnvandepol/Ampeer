import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import consentTexts from "../fixtures/consent-texts.json";
import { CONSENT_LABELS, ConsentRow } from "@/app/_account/ConsentRow";

describe("the account view's consent row", () => {
  it("offers to give consent when none is granted, and says so", () => {
    const onToggle = vi.fn();
    render(
      <ConsentRow
        kind="METER_LINK"
        text={consentTexts.texts.METER_LINK}
        granted={false}
        busy={false}
        onToggle={onToggle}
      />,
    );
    expect(screen.getByText("Geen toestemming gegeven")).toBeInTheDocument();
    expect(screen.getByText(consentTexts.texts.METER_LINK)).toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Toestemming geven" });
    expect(button).not.toBeDisabled();
  });

  it("offers to withdraw consent when it is granted, sentence or none", () => {
    const onToggle = vi.fn();
    render(
      <ConsentRow
        kind="LEAD_GENERATION"
        text={null}
        granted={true}
        busy={false}
        onToggle={onToggle}
      />,
    );
    expect(screen.getByText("Toestemming gegeven")).toBeInTheDocument();
    const button = screen.getByRole("button", {
      name: "Toestemming intrekken",
    });
    expect(button).not.toBeDisabled();
  });

  it("calls onToggle with the opposite of the current state", async () => {
    const onToggle = vi.fn();
    render(
      <ConsentRow
        kind="METER_LINK"
        text={consentTexts.texts.METER_LINK}
        granted={false}
        busy={false}
        onToggle={onToggle}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Toestemming geven" }),
    );
    expect(onToggle).toHaveBeenCalledWith("GRANTED");
  });

  it("refuses to grant a consent whose sentence could not be fetched", () => {
    // Withdrawing may never be harder than granting, so this refusal only
    // applies while the consent is not yet granted.
    render(
      <ConsentRow
        kind="METER_LINK"
        text={null}
        granted={false}
        busy={false}
        onToggle={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/Intrekken kan wel, aanzetten niet/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Toestemming geven" }),
    ).toBeDisabled();
  });

  it("goes dead while a toggle is in flight, and says so in a live region", () => {
    render(
      <ConsentRow
        kind="METER_LINK"
        text={consentTexts.texts.METER_LINK}
        granted={true}
        busy={true}
        onToggle={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", {
      name: "Toestemming intrekken",
    });
    expect(button).toBeDisabled();
    // Not aria-busy on the button itself: a disabled control drops out of
    // the tab order, and in most assistive tech the accessibility tree along
    // with it, exactly when "busy" matters. A live region reaches everybody.
    expect(button).not.toHaveAttribute("aria-busy");
    expect(screen.getByRole("status")).toHaveTextContent("Bezig.");
  });

  it("names two rows with the same action differently, by description", () => {
    // Both rows' buttons share the accessible NAME ("Toestemming geven"): the
    // action is one of two words regardless of which consent it acts on.
    // What has to differ is the DESCRIPTION, so a screen reader user can
    // tell the two rows apart.
    //
    // And the description is the label PLUS the consent sentence, not the
    // label alone. The sentence is the only text saying what is agreed to and
    // it is the text the API recorded; a description that stopped at three
    // words would leave somebody on the toggle hearing a heading for a
    // paragraph nobody read to them.
    render(
      <>
        <ConsentRow
          kind="METER_LINK"
          text={consentTexts.texts.METER_LINK}
          granted={false}
          busy={false}
          onToggle={vi.fn()}
        />
        <ConsentRow
          kind="LEAD_GENERATION"
          text={consentTexts.texts.LEAD_GENERATION}
          granted={false}
          busy={false}
          onToggle={vi.fn()}
        />
      </>,
    );
    const meterDescription = `${CONSENT_LABELS.METER_LINK} ${consentTexts.texts.METER_LINK}`;
    const leadDescription = `${CONSENT_LABELS.LEAD_GENERATION} ${consentTexts.texts.LEAD_GENERATION}`;
    const meterButton = screen.getByRole("button", {
      name: "Toestemming geven",
      description: meterDescription,
    });
    const leadButton = screen.getByRole("button", {
      name: "Toestemming geven",
      description: leadDescription,
    });
    expect(meterButton).not.toBe(leadButton);
    expect(meterButton).toHaveAccessibleDescription(meterDescription);
    expect(leadButton).toHaveAccessibleDescription(leadDescription);
  });

  it("describes the disabled grant button with the explanation for why", () => {
    render(
      <ConsentRow
        kind="METER_LINK"
        text={null}
        granted={false}
        busy={false}
        onToggle={vi.fn()}
      />,
    );
    const button = screen.getByRole("button", { name: "Toestemming geven" });
    expect(button).toHaveAccessibleDescription(
      /Intrekken kan wel, aanzetten niet/,
    );
  });
});
