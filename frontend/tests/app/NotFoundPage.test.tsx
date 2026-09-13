import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import NotFound, { metadata } from "@/app/not-found";
import { SITEMAP_ROUTES } from "@/app/_shell/site";

describe("the page every address that does not exist is served", () => {
  it("is in Dutch, which Next's own page is not", () => {
    // Without a not-found.tsx Next serves "404: This page could not be found."
    // inside this site's Dutch shell, and appends its own <title> after the
    // layout's so the document carries two. Measured on the built site on
    // 2026-09-13. CLAUDE.md makes the split hard: everything a user reads is
    // Dutch, and this is the page a mistyped address lands on.
    const { container } = render(<NotFound />);
    expect(container.textContent).not.toMatch(/could not be found|Not Found/i);
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(container.querySelector("h1")?.textContent).toMatch(/bestaat niet/);
  });

  it("offers a way on rather than only an apology", () => {
    // Somebody here wanted something. The useful thing is the shortest route
    // to it, so every route this site has a page for is offered, including the
    // two written to answer a question.
    const { container } = render(<NotFound />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    // The trailing slash is optional for the reason the other page tests give:
    // Link renders the href it was given and the build adds the slash, so an
    // exact string match asserts the wrong half of that pair.
    expect(hrefs).toContain("/");
    for (const route of [
      "berekenen",
      "thuisbatterij",
      "zelf-verbruiken",
      "einde-saldering",
    ]) {
      expect(
        hrefs.filter((href) => new RegExp(`^/${route}/?$`).test(href ?? "")),
      ).toHaveLength(1);
    }
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });

  it("sets no robots key of its own, because Next already sets one", () => {
    // Next emits noindex for this route by itself. Setting it again produced
    // two <meta name="robots"> tags in the built page; they agreed, so nothing
    // was broken, but the second was a claim this file did not need to make.
    // Asserted so that adding it back is a deliberate edit rather than a
    // plausible looking improvement.
    expect(metadata.robots).toBeUndefined();
    expect(metadata.title).toBe("Deze pagina bestaat niet");
  });

  it("is not in the sitemap, because it is not a page anybody should find", () => {
    const paths = SITEMAP_ROUTES.map((entry) => entry.path);
    expect(paths).not.toContain("/404/");
    expect(paths).not.toContain("/not-found/");
  });

  it("puts no euro amount on the page", () => {
    const { container } = render(<NotFound />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro/);
  });
});
