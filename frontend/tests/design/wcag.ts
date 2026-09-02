/**
 * WCAG 2.2 relative luminance and contrast, straight from the definition.
 *
 * Shared rather than copied. `contrast.test.ts` measures the stylesheet's
 * named pairs and `carpet/palette.test.ts` measures every colour the plate
 * can draw, and those are two questions about one formula. Two copies of it
 * would be two instruments that can drift apart, and the one that drifts is
 * always the one nobody re-derived.
 *
 * Not under `src/`: this is a measuring instrument for the tests and ships in
 * nothing. Vitest's coverage runs with `all` on over `src/**`, so a helper
 * placed there would be counted as unreached product code.
 *
 * The two anchors that prove the formula is the real one, white on black at
 * 21:1 and the WCAG worked example at 4,54:1, are asserted in
 * `contrast.test.ts` rather than here, because a helper file is not collected
 * as a suite.
 */

/** Eight-bit red, green and blue, as the stylesheet and the canvas both hold. */
export type Channels = readonly [number, number, number];

function channel(eight: number): number {
  const c = eight / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** Relative luminance, 0 for black and 1 for white. */
export function luminance([r, g, b]: Channels): number {
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** The ratio between two opaque colours, from 1:1 to 21:1, order free. */
export function contrast(a: Channels, b: Channels): number {
  const [x, y] = [luminance(a), luminance(b)];
  const [lighter, darker] = x > y ? [x, y] : [y, x];
  return (lighter + 0.05) / (darker + 0.05);
}

/** "#f5c64a" to its three channels. Six digits, with or without the hash. */
export function fromHex(hex: string): Channels {
  const digits = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((at) =>
    Number.parseInt(digits.slice(at, at + 2), 16),
  );
  return [r ?? 0, g ?? 0, b ?? 0];
}
