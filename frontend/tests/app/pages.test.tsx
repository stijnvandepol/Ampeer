import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "@/app/page";
import MethodologiePage from "@/app/methodologie/page";
import { Markdown } from "@/app/_markdown/Markdown";
import { SiteFooter } from "@/app/_shell/SiteFooter";
import { SiteHeader } from "@/app/_shell/SiteHeader";
import { THEME_ATTRIBUTE, THEME_STORAGE_KEY } from "@/app/_shell/theme";
import {
  useLocationHref,
  useLocationPath,
  useSearchParam,
} from "@/app/_shell/browser";

describe("the landing page", () => {
  it("leads into the four questions and nowhere else", () => {
    const { container } = render(<Home />);
    // Two ways in and no third. Two is the ceiling: one closing the first
    // screen and one closing the page. A third, a sticky bar or a repeat
    // halfway down is how a way in becomes a funnel, and neither of the two
    // calls to action the spec allows belongs here at all, because both refer
    // to an answer that does not exist yet.
    //
    // The trailing slash is next.config.ts's doing and is added by the build,
    // not by Link, so this accepts the path with or without it.
    const ways = screen.getAllByRole("link", {
      name: "Beantwoord vier vragen",
    });
    expect(ways).toHaveLength(2);
    for (const way of ways) {
      expect(way.getAttribute("href")).toMatch(/^\/berekenen\/?$/);
    }
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    expect(hrefs.filter((href) => /^https?:/.test(href ?? ""))).toEqual([]);
  });

  it("links to each page written to be found by a search", () => {
    // Measured on the built site on 2026-09-13: out/index.html linked to
    // /berekenen/, /einde-saldering/ and the four footer pages, and to neither
    // /thuisbatterij/ nor /zelf-verbruiken/. Those two exist to answer a
    // question somebody types into a search engine, and they were reachable
    // only from /einde-saldering/ and from each other, so the page with the
    // most weight pointed at neither of them. A visitor here who wants to know
    // whether a battery suits them had no way to the page that answers it.
    //
    // Asserted on the route rather than on the link text, because the text is
    // allowed to change and the route is the thing that would go missing. The
    // trailing slash is optional for the reason the calculator link states:
    // Link renders the href it was given and the build adds the slash.
    const { container } = render(<Home />);
    const hrefs = [...container.querySelectorAll("a[href]")].map((element) =>
      element.getAttribute("href"),
    );
    for (const route of ["thuisbatterij", "zelf-verbruiken"]) {
      expect(
        hrefs.filter((href) => new RegExp(`^/${route}/?$`).test(href ?? "")),
      ).toHaveLength(1);
    }
  });

  it("puts no euro amount on the page, because it has computed none", () => {
    // Every amount this product knows comes out of a simulation of one
    // specific household, with a band around it. A number here would be a
    // number nobody computed for the person reading it.
    const { container } = render(<Home />);
    expect(container.textContent).not.toMatch(/€|\d+\s*euro/);
  });

  it("carries no countdown and no scarcity", () => {
    const { container } = render(<Home />);
    const text = (container.textContent ?? "").toLowerCase();
    for (const pattern of [
      "nog maar",
      "laatste kans",
      "huishoudens gingen",
      "mis niet",
    ]) {
      expect(text).not.toContain(pattern);
    }
  });
});

describe("the site shell", () => {
  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute(THEME_ATTRIBUTE);
  });

  it("names the pages that exist and adds no third call to action", () => {
    render(<SiteHeader />);
    expect(screen.getByRole("link", { name: "Ampeer" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      screen.getByRole("link", { name: "Berekenen" }).getAttribute("href"),
    ).toMatch(/^\/berekenen\/?$/);
    expect(
      screen.getByRole("link", { name: "Methodologie" }).getAttribute("href"),
    ).toMatch(/^\/methodologie\/?$/);
  });

  it("says what Ampeer does not sell", () => {
    render(<SiteFooter />);
    expect(screen.getByText(/verkoopt geen panelen/)).toBeInTheDocument();
  });

  it("starts on the system palette and writes the choice where the next page finds it", async () => {
    render(<SiteHeader />);
    const select = screen.getByLabelText("Thema");
    expect(select).toHaveValue("system");

    await userEvent.selectOptions(select, "dark");
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

    await userEvent.selectOptions(select, "system");
    expect(document.documentElement.hasAttribute(THEME_ATTRIBUTE)).toBe(false);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });
});

describe("the methodology page", () => {
  it("is the repository's own document, as elements", async () => {
    // An async server component: called, then rendered. It reads the file at
    // build time and there is no browser half of it at all.
    render(await MethodologiePage());
    expect(
      screen.getByRole("heading", { level: 1, name: "Hoe Ampeer rekent" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("table").length).toBeGreaterThan(0);
  });

  it("renders markdown as elements and never as markup", () => {
    const { container } = render(
      <Markdown
        source={
          "# Titel\n\nEen **vet** woord.\n\n- een\n- twee\n\n| a | b |\n|---|---|\n| 1 | 2 |"
        }
      />,
    );
    expect(container.querySelector("h1")?.textContent).toBe("Titel");
    expect(container.querySelector("strong")?.textContent).toBe("vet");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector('th[scope="col"]')?.textContent).toBe("a");
    expect(container.querySelectorAll("tbody td")).toHaveLength(2);
    // The source string reaches the DOM as text nodes, so a tag in the source
    // would be visible characters rather than an element. There is no path
    // through this component that produces markup.
    expect(container.textContent).not.toContain("**");
  });

  it("gives a wide table its own scroller instead of pushing the page sideways", () => {
    const { container } = render(
      <Markdown source={"| a | b |\n|---|---|\n| 1 | 2 |"} />,
    );
    const scroller = container.querySelector(".overflow-x-auto");
    expect(scroller).not.toBeNull();
    expect(scroller?.getAttribute("tabindex")).toBe("0");
  });

  it("renders a heading at every level the document may use", () => {
    const source = [
      "# een",
      "## twee",
      "### drie",
      "#### vier",
      "##### vijf",
      "###### zes",
    ].join("\n\n");
    const { container } = render(<Markdown source={source} />);
    expect(container.querySelectorAll("h1,h2,h3,h4,h5,h6")).toHaveLength(6);
  });
});

/** A component whose only job is to show what the three hooks answered. */
function Probe({ name }: { readonly name: string }) {
  return (
    <ul>
      <li data-testid="href">{useLocationHref()}</li>
      <li data-testid="path">{useLocationPath() ?? "onbekend"}</li>
      <li data-testid="param">{useSearchParam(name) ?? "geen"}</li>
    </ul>
  );
}

describe("the browser, read the way React 19 wants it read", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/berekenen/?ronde=2");
  });

  it("answers with the URL the browser is on", () => {
    render(<Probe name="ronde" />);
    expect(screen.getByTestId("href")).toHaveTextContent(window.location.href);
    expect(screen.getByTestId("path")).toHaveTextContent("/berekenen/");
    expect(screen.getByTestId("param")).toHaveTextContent("2");
  });

  it("says there is no such parameter rather than inventing one", () => {
    render(<Probe name="kleur" />);
    expect(screen.getByTestId("param")).toHaveTextContent("geen");
  });

  it("returns the same snapshot twice, so React's comparison settles", () => {
    // getSnapshot runs on every render and React compares with Object.is. A
    // snapshot that built a fresh object each time would loop forever, which
    // is why every one of these returns a primitive.
    const spy = vi.spyOn(console, "error");
    const { rerender } = render(<Probe name="ronde" />);
    rerender(<Probe name="ronde" />);
    rerender(<Probe name="ronde" />);
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});

describe("the questions a search engine is given", () => {
  it("marks up exactly the questions the home page shows, in the same words", () => {
    // The home page renders its answers as JSX, because one of them ends in a
    // link and JSON-LD carries text, so the same three sentences live twice.
    // This is what keeps them from drifting: a FAQPage whose answers differ
    // from the answers on the page is the kind of thing that gets a site
    // ignored rather than cited, and nothing else would notice.
    const { container } = render(<Home />);
    const scripts = [
      ...container.querySelectorAll('script[type="application/ld+json"]'),
    ].map((element) => JSON.parse(element.textContent ?? "{}"));
    const faq = scripts.find((data) => data["@type"] === "FAQPage");

    expect(faq, "the home page carries no FAQPage markup").toBeDefined();
    expect(faq.mainEntity.map((entry: { name: string }) => entry.name)).toEqual(
      [...container.querySelectorAll("dt")].map(
        (element) => element.textContent ?? "",
      ),
    );
    expect(
      faq.mainEntity.map(
        (entry: { acceptedAnswer: { text: string } }) =>
          entry.acceptedAnswer.text,
      ),
    ).toEqual(
      [...container.querySelectorAll("dd")].map(
        (element) => element.textContent ?? "",
      ),
    );
  });
});
