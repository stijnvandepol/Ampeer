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

export function installMatchMedia(reduceMotion: boolean): void {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const query = (media: string): MediaQueryList =>
    ({
      media,
      matches: media.includes("prefers-reduced-motion") ? reduceMotion : false,
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
}
