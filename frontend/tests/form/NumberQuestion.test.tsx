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
    expect(field).toHaveValue(999999);
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
    expect(screen.getByLabelText(/wattpiek/i)).toHaveValue(4200);
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
    expect(screen.getByLabelText(/wattpiek/i)).toHaveValue(7000);
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
});
