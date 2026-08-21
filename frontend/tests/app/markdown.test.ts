import { describe, expect, it } from "vitest";
import { loadMethodology } from "@/lib/methodology";
import {
  UnsupportedMarkdown,
  parseMarkdown,
  parseSpans,
} from "@/app/_markdown/parse";

describe("the markdown the methodology page is built from", () => {
  it("reads a heading with its level", () => {
    expect(parseMarkdown("## Kort samengevat")).toEqual([
      {
        kind: "heading",
        level: 2,
        spans: [{ text: "Kort samengevat", bold: false }],
      },
    ]);
  });

  it("joins the lines of a wrapped paragraph", () => {
    const blocks = parseMarkdown(
      "Wij bouwen uit jouw antwoorden\neen patroon van een jaar.",
    );
    expect(blocks).toEqual([
      {
        kind: "paragraph",
        spans: [
          {
            text: "Wij bouwen uit jouw antwoorden een patroon van een jaar.",
            bold: false,
          },
        ],
      },
    ]);
  });

  it("keeps bold as a span rather than as characters", () => {
    expect(parseSpans("Een **vet** woord", 1)).toEqual([
      { text: "Een ", bold: false },
      { text: "vet", bold: true },
      { text: " woord", bold: false },
    ]);
  });

  it("attaches a wrapped line to the list item above it", () => {
    const blocks = parseMarkdown("- eerste regel\n  loopt door\n- tweede");
    expect(blocks).toEqual([
      {
        kind: "list",
        items: [
          [{ text: "eerste regel loopt door", bold: false }],
          [{ text: "tweede", bold: false }],
        ],
      },
    ]);
  });

  it("reads a pipe table as a header and rows", () => {
    const blocks = parseMarkdown(
      "| Wat | Laag |\n|---|---|\n| Stroomprijs | 0,22 |",
    );
    expect(blocks).toEqual([
      {
        kind: "table",
        header: [
          [{ text: "Wat", bold: false }],
          [{ text: "Laag", bold: false }],
        ],
        rows: [
          [
            [{ text: "Stroomprijs", bold: false }],
            [{ text: "0,22", bold: false }],
          ],
        ],
      },
    ]);
  });

  it("does not swallow the paragraph that follows a block", () => {
    const blocks = parseMarkdown(
      "# Titel\n\n- een\n\nDaarna.\n\n| a |\n|---|\n| b |",
    );
    expect(blocks.map((block) => block.kind)).toEqual([
      "heading",
      "list",
      "paragraph",
      "table",
    ]);
  });

  // The refusals. A renderer that quietly printed the raw characters would put
  // a visible defect on the published page and tell nobody, which is the exact
  // failure building the page from the file is meant to make impossible.
  it.each([
    ["a link", "Zie [de wet](https://example.invalid)."],
    ["an image", "![grafiek](grafiek.png)"],
    ["a fenced code block", "```python\nprint(1)\n```"],
    ["a blockquote", "> geciteerd"],
    ["raw html", "<div>hallo</div>"],
    ["an ordered list", "1. eerste"],
    ["a thematic break", "---"],
    ["an unclosed bold run", "Een **vet woord"],
  ])("refuses %s rather than rendering it as characters", (_name, source) => {
    expect(() => parseMarkdown(source)).toThrow(UnsupportedMarkdown);
  });

  it("names the line, so the error points at the document and not at this file", () => {
    expect(() => parseMarkdown("Eerste.\n\nZie [hier](x).")).toThrow(/line 3/);
  });

  it("parses the real docs/methodologie.md without falling back to anything", async () => {
    // The one test here that guards the published page rather than the parser.
    // The document is edited by people who are not thinking about this file,
    // so the day it gains a construct this renderer does not know has to be a
    // red build and not a page with brackets on it.
    const blocks = parseMarkdown(await loadMethodology());
    const kinds = new Set(blocks.map((block) => block.kind));
    expect(kinds).toEqual(new Set(["heading", "paragraph", "list", "table"]));
    expect(
      blocks.filter((block) => block.kind === "table").length,
    ).toBeGreaterThan(0);
  });
});
