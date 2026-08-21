import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { COMPASS_AZIMUTH_DEG, RoofPicker } from "@/components/form/RoofPicker";

/**
 * The compass names are matched anchored (/^zuid$/i and not /zuid/i) on
 * purpose. Testing Library matches a regex against the whole accessible name,
 * so an unanchored /zuid/i also matches "Zuidoost" and "Zuidwest" and the query
 * throws on three results. Anchoring is the stricter query, not the looser one.
 */

describe("the roof picker", () => {
  it("asks the question in compass directions, not in degrees", () => {
    // Nobody knows their azimuth. Asking for it in degrees is asking a
    // question the visitor cannot answer, and then trusting the answer.
    render(<RoofPicker azimuth={0} tilt={35} onChange={() => {}} />);
    expect(screen.getByRole("radio", { name: /^zuid$/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /^oost$/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /^west$/i })).toBeInTheDocument();
    // And there is no number field anywhere in the control asking for one.
    expect(screen.queryAllByRole("spinbutton")).toHaveLength(0);
  });

  it("offers every direction the mapping knows", () => {
    render(<RoofPicker azimuth={0} tilt={35} onChange={() => {}} />);
    expect(screen.getAllByRole("radio")).toHaveLength(
      Object.keys(COMPASS_AZIMUTH_DEG).length,
    );
  });

  it("reports whole degrees, because that is what the cache is keyed on", async () => {
    const onChange = vi.fn();
    render(<RoofPicker azimuth={0} tilt={35} onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: /^west$/i }));
    const next = onChange.mock.calls.at(-1)?.[0];
    expect(Number.isInteger(next.azimuth)).toBe(true);
    expect(Number.isInteger(next.tilt)).toBe(true);
  });

  it("rounds a fractional tilt it was handed rather than passing it on", async () => {
    const onChange = vi.fn();
    render(<RoofPicker azimuth={0} tilt={35.4} onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: /^west$/i }));
    expect(onChange).toHaveBeenLastCalledWith({ azimuth: 90, tilt: 35 });
  });

  it("puts east on the negative side and west on the positive one", async () => {
    // The sign convention is the whole difference between a morning roof and an
    // evening roof, and getting it backwards raises nothing anywhere: the
    // simulation just answers about a house that does not exist.
    const onChange = vi.fn();
    render(<RoofPicker azimuth={0} tilt={35} onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: /^oost$/i }));
    expect(onChange.mock.calls.at(-1)?.[0].azimuth).toBeLessThan(0);
    await userEvent.click(screen.getByRole("radio", { name: /^west$/i }));
    expect(onChange.mock.calls.at(-1)?.[0].azimuth).toBeGreaterThan(0);
  });

  it("maps south to zero and stays inside the range the API accepts", () => {
    // MIN_AZIMUTH_DEG and MAX_AZIMUTH_DEG in backend/advice/serializers.py.
    expect(COMPASS_AZIMUTH_DEG.SOUTH).toBe(0);
    for (const degrees of Object.values(COMPASS_AZIMUTH_DEG)) {
      expect(Number.isInteger(degrees)).toBe(true);
      expect(degrees).toBeGreaterThanOrEqual(-180);
      expect(degrees).toBeLessThanOrEqual(180);
    }
  });

  it("reads -180 and 180 as the same north", () => {
    render(<RoofPicker azimuth={-180} tilt={35} onChange={() => {}} />);
    expect(screen.getByRole("radio", { name: /^noord$/i })).toBeChecked();
  });

  it("checks nothing for an azimuth that is not one of the eight", () => {
    // A restored session carries whatever was stored, and storage is the
    // browser, where anything may have written it. 37 degrees is not a
    // direction this control offers, so it shows none as chosen rather than
    // rounding it into one the visitor never picked.
    render(<RoofPicker azimuth={37} tilt={35} onChange={() => {}} />);
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).not.toBeChecked();
    }
  });

  it("is operable from the keyboard alone", async () => {
    const onChange = vi.fn();
    render(<RoofPicker azimuth={0} tilt={35} onChange={onChange} />);
    await userEvent.tab();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalled();
    expect(Number.isInteger(onChange.mock.calls.at(-1)?.[0].azimuth)).toBe(
      true,
    );
  });

  it("checks nothing at all before a direction has been chosen", () => {
    // South is the most common roof in the Netherlands and the one this
    // control used to start on, which made it the one direction that could not
    // be given as an answer. A radio that arrives checked is announced as
    // "Zuid, aangevinkt" to a screen reader, so the interface asserts an
    // answer nobody gave, and clicking or pressing Space on an already checked
    // radio fires no change event, so choosing it changes nothing. The only
    // way out was to pick a wrong direction and come back.
    render(<RoofPicker azimuth={null} tilt={35} onChange={() => {}} />);
    for (const radio of screen.getAllByRole("radio")) {
      expect(radio).not.toBeChecked();
    }
  });

  it("reports no direction when only the tilt was moved", () => {
    // The tilt is half of one question and the direction is the other half.
    // A visitor who nudges only the slider has said nothing about which way
    // the roof faces, and an east roof simulated as a south roof raises
    // nothing anywhere: it just answers about a house that does not exist.
    const onChange = vi.fn();
    render(<RoofPicker azimuth={null} tilt={35} onChange={onChange} />);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "40" } });
    expect(onChange).toHaveBeenLastCalledWith({ azimuth: null, tilt: 40 });
  });

  it("keeps the direction already chosen when the tilt moves afterwards", () => {
    const onChange = vi.fn();
    render(<RoofPicker azimuth={-90} tilt={35} onChange={onChange} />);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "40" } });
    expect(onChange).toHaveBeenLastCalledWith({ azimuth: -90, tilt: 40 });
  });

  it("lets south be chosen, which is the roof most of this country has", async () => {
    const onChange = vi.fn();
    render(<RoofPicker azimuth={null} tilt={35} onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: /^zuid$/i }));
    expect(onChange).toHaveBeenLastCalledWith({ azimuth: 0, tilt: 35 });
  });

  it("keeps the tilt slider inside the bounds it was given", () => {
    render(
      <RoofPicker
        azimuth={0}
        tilt={35}
        onChange={() => {}}
        tiltMin={10}
        tiltMax={60}
      />,
    );
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("min", "10");
    expect(slider).toHaveAttribute("max", "60");
    expect(slider).toHaveAttribute("step", "1");
  });
});
