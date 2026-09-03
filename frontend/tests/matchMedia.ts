/**
 * A jsdom stand-in for `window.matchMedia`.
 *
 * jsdom does not implement it, so any component that reads a media preference
 * throws the moment it is rendered in a component test. That is a gap in the
 * test environment rather than in the component. `tests/setup.ts` installs it
 * with movement allowed, so every test file gets a working `matchMedia` without
 * asking for one; a test that needs the reduced-motion branch calls this again
 * with `true`.
 *
 * It lived in tests/band/ until the barrier moved it here, because the lane
 * that found the gap did not own the shared setup file and reported it instead
 * of reaching across.
 *
 * Verified on 2026-08-21: `typeof window.matchMedia` is "undefined" under
 * jsdom in this repository's vitest environment.
 */

/**
 * What every query other than reduced motion answers.
 *
 * `(pointer: fine)` is true because jsdom is standing in for a desktop
 * browser, which is where the components that ask it are meant to run. It was
 * added on 2026-08-31 with the pointer ring, whose whole behaviour is gated on
 * that query: with the previous blanket false, every test of it would have
 * passed over a component that had attached no listeners, which is a test that
 * proves the opposite of what it says.
 *
 * Anything not named here stays false, which is the conservative answer for a
 * feature query.
 */
const DEFAULT_ANSWERS: Readonly<Record<string, boolean>> = {
  "(pointer: fine)": true,
};

/**
 * Returned by `installMatchMedia` so a test can simulate the query itself
 * changing after render, the way an OS-level setting can: `matches` is read
 * fresh on every call the hook makes, so mutating it here and then notifying
 * whoever subscribed is the live equivalent of the visitor's own toggle,
 * distinct from installing a different starting value before render.
 */
export interface MatchMediaControl {
  fireReducedMotionChange(next: boolean): void;
}

export function installMatchMedia(
  reduceMotion: boolean,
  answers: Readonly<Record<string, boolean>> = {},
): MatchMediaControl {
  const resolved = { ...DEFAULT_ANSWERS, ...answers };
  let currentReduceMotion = reduceMotion;
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const query = (media: string): MediaQueryList =>
    ({
      media,
      matches: media.includes("prefers-reduced-motion")
        ? currentReduceMotion
        : (resolved[media] ?? false),
      onchange: null,
      addEventListener: (
        _type: string,
        listener: (event: MediaQueryListEvent) => void,
      ) => {
        listeners.add(listener);
      },
      removeEventListener: (
        _type: string,
        listener: (event: MediaQueryListEvent) => void,
      ) => {
        listeners.delete(listener);
      },
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => true,
    }) as unknown as MediaQueryList;

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: query,
  });

  return {
    fireReducedMotionChange(next: boolean): void {
      currentReduceMotion = next;
      for (const listener of listeners) {
        listener({ matches: next } as MediaQueryListEvent);
      }
    },
  };
}
