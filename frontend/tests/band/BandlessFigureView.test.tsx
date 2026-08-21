import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { render, screen } from "@testing-library/react";
import fixture from "../fixtures/advice-response.json";
import { BandlessFigureView } from "@/components/band/BandlessFigureView";
import type { Advice } from "@/lib/types";

const advice = fixture as unknown as Advice;

describe("a figure with no band", () => {
  it("shows the model's own reason instead of an invented margin", () => {
    const figure = advice.battery!.sized_capacity_kwh;
    render(<BandlessFigureView figure={figure} unit="kwh" />);
    expect(screen.getByText(figure.basis_text)).toBeInTheDocument();
  });

  it("writes no explanation of its own", () => {
    // The sentence is Dutch advice text and belongs to the API's language
    // layer. A sentence written here would be Dutch outside nl.py.
    const source = readFileSync("src/components/band/BandlessFigureView.tsx", "utf-8");
    expect(source).not.toMatch(/geen marge|schatting|omdat/i);
  });

  it("draws no band-shaped thing at all", () => {
    const figure = advice.battery!.sized_capacity_kwh;
    const { container } = render(<BandlessFigureView figure={figure} unit="kwh" />);
    expect(container.querySelector('[data-role="band-end"]')).toBeNull();
    expect(container.querySelector('[data-role="band-middle"]')).toBeNull();
  });
});
