import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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
    expect(screen.getAllByRole("radio")).toHaveLength(Object.keys(COMPASS_AZIMUTH_DEG).length);
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

  it("is operable from the keyboard alone", async () => {
    const onChange = vi.fn();
    render(<RoofPicker azimuth={0} tilt={35} onChange={onChange} />);
    await userEvent.tab();
    await userEvent.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenCalled();
    expect(Number.isInteger(onChange.mock.calls.at(-1)?.[0].azimuth)).toBe(true);
  });

  it("keeps the tilt slider inside the bounds it was given", () => {
    render(<RoofPicker azimuth={0} tilt={35} onChange={() => {}} tiltMin={10} tiltMax={60} />);
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("min", "10");
    expect(slider).toHaveAttribute("max", "60");
    expect(slider).toHaveAttribute("step", "1");
  });
});
