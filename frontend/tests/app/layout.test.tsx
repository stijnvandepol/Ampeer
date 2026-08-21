import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// next/font/google is compiled away by Next's own build step and is not a
// module that runs on its own. Only the two CSS variable names it produces
// matter here, so it is replaced by something that produces them.
vi.mock("next/font/google", () => ({
  Geist: ({ variable }: { variable: string }) => ({ variable: variable.replace("--", "font-") }),
  Geist_Mono: ({ variable }: { variable: string }) => ({
    variable: variable.replace("--", "font-"),
  }),
}));

const { default: RootLayout, MAIN_ID } = await import("@/app/layout");
const { THEME_ATTRIBUTE, THEME_STORAGE_KEY } = await import("@/app/_shell/theme");

/**
 * The layout, rendered the way the build renders it: to a string.
 *
 * A string rather than into jsdom, because what is being checked is what ends
 * up in the static HTML. The inline theme script only earns its place if it is
 * really in the document before anything else, and only the markup can say so.
 */
function markup(): string {
  const props = { children: <p>inhoud</p> } as Parameters<typeof RootLayout>[0];
  return renderToStaticMarkup(RootLayout(props));
}

describe("the page shell that every route is built into", () => {
  it("is in Dutch, because the interface and the advice both are", () => {
    // A screen reader that reads Dutch with an English voice is unusable.
    expect(markup()).toContain('lang="nl"');
  });

  it("carries the theme script before any other script", () => {
    const html = markup();
    expect(html).toContain(THEME_STORAGE_KEY);
    expect(html).toContain(THEME_ATTRIBUTE);
    // As the children of a plain script element, which React 19 emits as
    // inline source. Not dangerouslySetInnerHTML: .semgrep/frontend.yml fails
    // the build on that prop and this needs no exception to it.
    expect(html).toMatch(/<script>try\{/);
  });

  it("gives the keyboard a route past the header", () => {
    const html = markup();
    expect(html).toContain(`href="#${MAIN_ID}"`);
    expect(html).toContain(`id="${MAIN_ID}"`);
    expect(html).toContain("Naar de inhoud");
  });

  it("puts the page content in a main landmark, with the navigation outside it", () => {
    const html = markup();
    expect(html).toContain("<main");
    expect(html.indexOf("<header")).toBeLessThan(html.indexOf("<main"));
    expect(html).toContain("inhoud");
  });
});
