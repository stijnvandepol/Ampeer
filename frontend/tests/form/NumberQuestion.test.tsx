import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NumberQuestion } from "@/components/form/NumberQuestion";

describe("a number question", () => {
  it("refuses a value outside the bounds it was given", async () => {
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={onChange}
      />,
    );
    const field = screen.getByLabelText(/wattpiek/i);
    await userEvent.type(field, "999999");
    // The message waits for blur. It used to appear on the first keystroke,
    // which put "Vul minstens 1000 in." under the visitor's fingers after one
    // digit and, because it is a live region, announced it again on every
    // character. The refusal below does NOT wait: the flow is told at once.
    await userEvent.tab();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    // Refusing means not reporting it upwards either, so a caller cannot send
    // on a number this component has just told the visitor is impossible.
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("says what is wrong rather than only that something is", async () => {
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    await userEvent.type(screen.getByLabelText(/wattpiek/i), "999999");
    await userEvent.tab();
    expect(screen.getByRole("alert").textContent).toMatch(/30000|30\.000/);
  });

  it("names the lower bound when that is the one that broke", async () => {
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={500}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    await userEvent.type(screen.getByLabelText(/wattpiek/i), "3");
    await userEvent.tab();
    const message = screen.getByRole("alert").textContent ?? "";
    expect(message).toMatch(/500/);
    expect(message).not.toMatch(/30000|30\.000/);
  });

  it("ties its error to the field for a screen reader", async () => {
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    const field = screen.getByLabelText(/wattpiek/i);
    await userEvent.type(field, "999999");
    await userEvent.tab();
    expect(field).toHaveAttribute(
      "aria-describedby",
      expect.stringContaining("wp"),
    );
    expect(field).toHaveAttribute("aria-invalid", "true");
    const described = (field.getAttribute("aria-describedby") ?? "").split(" ");
    expect(described).toContain(screen.getByRole("alert").id);
  });

  it("reports a value inside the bounds and shows nothing wrong", async () => {
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={onChange}
      />,
    );
    await userEvent.type(screen.getByLabelText(/wattpiek/i), "3500");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/wattpiek/i)).toHaveAttribute(
      "aria-invalid",
      "false",
    );
    expect(onChange).toHaveBeenLastCalledWith(3500);
  });

  it("keeps what the visitor typed even though the parent rejected it", async () => {
    // The parent is told null for an out-of-range number, so the value prop
    // never comes back. The characters have to stay on the screen anyway, or
    // the field empties itself under the visitor while they read the error.
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    const field = screen.getByLabelText(/wattpiek/i);
    await userEvent.type(field, "999999");
    // A string, because the field is type="text" with inputmode="numeric". A
    // number input silently discards anything it cannot parse, which on the
    // postcode field meant "3811 EP" left an EMPTY box with no message.
    expect(field).toHaveValue("999999");
  });

  it("takes a value the parent changed from somewhere else", () => {
    // A restored session, or stepping back to a question already answered.
    const { rerender } = render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    rerender(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={4200}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    expect(screen.getByLabelText(/wattpiek/i)).toHaveValue("4200");
  });

  it("shows its error in the colour every other error on this site uses", async () => {
    // Measured byte-identical to the label beside it: text-sm and nothing
    // more. An error that looks like a label is an error nobody reads, and
    // "text-danger" is the one class the rest of the site marks failure with.
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    await userEvent.type(screen.getByLabelText(/wattpiek/i), "999999");
    await userEvent.tab();
    expect(screen.getByRole("alert")).toHaveClass("text-danger");
  });

  it("says out loud that it is refusing what the field holds", async () => {
    // onChange(null) means two things: an empty field, and a field holding a
    // number this component has already refused. The flow above has to tell
    // them apart, or it puts "Beantwoord deze vraag om verder te gaan" over a
    // question that was answered.
    const onRefusal = vi.fn();
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
        onRefusal={onRefusal}
      />,
    );
    const field = screen.getByLabelText(/wattpiek/i);
    await userEvent.type(field, "999999");
    expect(onRefusal).toHaveBeenLastCalledWith(true);
    await userEvent.clear(field);
    expect(onRefusal).toHaveBeenLastCalledWith(false);
    await userEvent.type(field, "3500");
    expect(onRefusal).toHaveBeenLastCalledWith(false);
  });

  it("keeps the digits when somebody writes a Dutch postcode", async () => {
    /*
     * The defect this component was rewritten for, measured in a browser on
     * 2026-09-01 on the first field of the flow. With type="number", typing
     * "3811 EP", which is how a Dutch postcode is written, left the field
     * EMPTY with aria-invalid="false" and no message at all: a number input
     * reports what it cannot parse as the empty string, so the 3811 went with
     * the letters and the "Vul een getal in" branch could never fire.
     */
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="pc"
        label="Postcode"
        value={null}
        min={1000}
        max={9999}
        unit=""
        integer
        onChange={onChange}
      />,
    );
    const field = screen.getByLabelText(/postcode/i);
    await userEvent.type(field, "3811 EP");
    expect(field).toHaveValue("3811 EP");
    await userEvent.tab();
    expect(screen.getByRole("alert").textContent).toMatch(/getal/i);
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("does not step its own value on the arrow keys", async () => {
    /*
     * The other half of the same defect. A number input steps on ArrowUp and
     * ArrowDown, so a keyboard visitor scrolling the page silently edited their
     * postcode: measured, 3811 became 3810 on one press, with nothing on screen
     * saying so.
     */
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="pc"
        label="Postcode"
        value={null}
        min={1000}
        max={9999}
        unit=""
        integer
        onChange={onChange}
      />,
    );
    const field = screen.getByLabelText(/postcode/i);
    await userEvent.type(field, "3811");
    await userEvent.keyboard("{ArrowDown}");
    expect(field).toHaveValue("3811");
    expect(onChange).toHaveBeenLastCalledWith(3811);
  });

  it("says the range it accepts before anything is typed", async () => {
    // The bounds were props all along and were secret until a visitor broke
    // one. The NL Design System asks for valid values to be stated up front.
    render(
      <NumberQuestion
        id="pc"
        label="Postcode"
        value={null}
        min={1000}
        max={9999}
        unit=""
        onChange={() => {}}
      />,
    );
    expect(screen.getByText("1000 tot 9999")).toBeInTheDocument();
    // And no double space where the unit is empty, which is what
    // "Vul minstens 1000  in." used to read.
    await userEvent.type(screen.getByLabelText(/postcode/i), "1");
    await userEvent.tab();
    expect(screen.getByRole("alert").textContent).toBe("Vul minstens 1000 in.");
  });

  it("is labelled, so the field can be reached by its name", () => {
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={7000}
        min={1}
        max={30000}
        unit="Wp"
        onChange={() => {}}
      />,
    );
    expect(screen.getByLabelText(/wattpiek/i)).toHaveValue("7000");
  });
});

describe("a number question for an integer field", () => {
  it("refuses a fractional value and says why", async () => {
    // peak_power_wp, azimuth_deg and tilt_deg are IntegerField in
    // backend/advice/serializers.py. Without this the component reports 3500.5
    // and the API answers 400 with a message the visitor never asked for.
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        integer
        onChange={onChange}
      />,
    );
    await userEvent.type(screen.getByLabelText(/wattpiek/i), "3500.5");
    await userEvent.tab();
    expect(screen.getByRole("alert").textContent).toMatch(/heel getal/i);
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("accepts a whole number on the same field", async () => {
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1}
        max={30000}
        unit="Wp"
        integer
        onChange={onChange}
      />,
    );
    await userEvent.type(screen.getByLabelText(/wattpiek/i), "3500");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(onChange).toHaveBeenLastCalledWith(3500);
  });

  it("still accepts a fraction where the API's field is a float", async () => {
    const onChange = vi.fn();
    render(
      <NumberQuestion
        id="kwh"
        label="Jaarverbruik"
        value={null}
        min={1}
        max={50000}
        unit="kWh"
        onChange={onChange}
      />,
    );
    await userEvent.type(screen.getByLabelText(/jaarverbruik/i), "3500.5");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(onChange).toHaveBeenLastCalledWith(3500.5);
  });
  it("borrows a name that is already on the screen instead of repeating it", () => {
    // See ChoiceQuestion's twin of this test. Question two was headed "Hoeveel
    // wattpiek aan zonnepanelen ligt er?" over a field labelled "Vermogen van
    // de installatie": one question, two wordings sharing not one word, both
    // read out.
    render(
      <>
        <h2 id="vraag-titel">
          Hoeveel wattpiek aan zonnepanelen ligt er op uw dak?
        </h2>
        <NumberQuestion
          id="wp"
          labelledBy="vraag-titel"
          value={null}
          min={1000}
          max={9999}
          unit="wattpiek"
          onChange={() => {}}
        />
      </>,
    );
    expect(
      screen.getByRole("textbox", {
        name: "Hoeveel wattpiek aan zonnepanelen ligt er op uw dak?",
      }),
    ).toBeInTheDocument();
    expect(document.querySelector("label")).toBeNull();
  });

  it("does not let its field hold the row open on a 320 pixel screen", () => {
    // The row is `flex flex-wrap` and the field may shrink. Measured at 320 CSS
    // pixels before the fix: 286 pixels of content in a 272 pixel column,
    // because a text input will not go below its own `size` unless min-width
    // says it may. jsdom has no layout, so this asserts the two class names the
    // browser measurement in e2e/form.spec.ts turned out to depend on.
    render(
      <NumberQuestion
        id="wp"
        label="Wattpiek"
        value={null}
        min={1000}
        max={9999}
        unit="wattpiek"
        onChange={() => {}}
      />,
    );
    const field = screen.getByLabelText("Wattpiek");
    expect(field.className).toContain("min-w-0");
    expect(field.parentElement?.className).toContain("flex-wrap");
  });
});
