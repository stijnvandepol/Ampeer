/**
 * The small part of Markdown that `docs/methodologie.md` actually uses.
 *
 * WHY THERE IS A PARSER HERE AT ALL. `loadMethodology()` returns Markdown
 * source and never HTML, on purpose, and `.semgrep/frontend.yml` fails the
 * build on `dangerouslySetInnerHTML`, also on purpose. So the two obvious
 * routes are both closed: no markdown-to-HTML library whose output is injected
 * as markup, and no suppression of the rule that says so. The third route is
 * this one: parse the source into a description of blocks, and let React build
 * elements from it. Nothing on this path can produce markup, so the question
 * of whether the input is trusted never has to be answered correctly.
 *
 * The alternative considered and rejected was adding a dependency. A Markdown
 * pipeline is a large amount of third-party code, running at build time, for
 * one page whose source file uses six constructs. This file is under two
 * hundred lines, has no dependencies, and cannot emit HTML even if it is
 * wrong.
 *
 * WHAT IT SUPPORTS. ATX headings, paragraphs, unordered lists with wrapped
 * continuation lines, pipe tables with a header row, and `**bold**` inline.
 * That is every construct in `docs/methodologie.md` today, checked rather than
 * assumed.
 *
 * WHAT IT DOES ABOUT THE REST. It throws. A parser that quietly rendered
 * `[tekst](url)` as those literal characters would put a visible defect on the
 * published page and tell nobody, and the whole reason the page is built from
 * the file is that the published version cannot be allowed to differ from the
 * one the Python tests guard. Failing the build puts the problem in front of
 * the person editing the document, at the moment they edit it, which is the
 * only moment it is cheap.
 */

/** A run of text, bold or not. Bold is the only inline mark the document uses. */
export interface Span {
  readonly text: string;
  readonly bold: boolean;
}

export type Block =
  | {
      readonly kind: "heading";
      readonly level: number;
      readonly spans: readonly Span[];
    }
  | { readonly kind: "paragraph"; readonly spans: readonly Span[] }
  | { readonly kind: "list"; readonly items: readonly (readonly Span[])[] }
  | {
      readonly kind: "table";
      readonly header: readonly (readonly Span[])[];
      readonly rows: readonly (readonly (readonly Span[])[])[];
    };

/** Raised for a construct this parser will not guess at. */
export class UnsupportedMarkdown extends Error {
  constructor(line: number, source: string) {
    super(
      `docs/methodologie.md line ${line}: this renderer supports headings, paragraphs, ` +
        `unordered lists, pipe tables and **bold**, and got: ${source.trim()}`,
    );
    this.name = "UnsupportedMarkdown";
  }
}

const HEADING = /^(#{1,6})\s+(.*)$/;
const LIST_ITEM = /^[-*]\s+(.*)$/;
const TABLE_DELIMITER = /^\|[\s:|-]+\|$/;
const ORDERED_ITEM = /^\d+[.)]\s+/;
const LINK_OR_IMAGE = /!?\[[^\]]*\]\([^)]*\)/;

function refuse(line: number, source: string): never {
  throw new UnsupportedMarkdown(line, source);
}

/** Splits on `**`, so odd runs are bold and even runs are not. */
export function parseSpans(text: string, line: number): readonly Span[] {
  if (LINK_OR_IMAGE.test(text)) refuse(line, text);
  const parts = text.split("**");
  if (parts.length % 2 === 0) refuse(line, text);
  const spans: Span[] = [];
  parts.forEach((part, index) => {
    if (part.length > 0) spans.push({ text: part, bold: index % 2 === 1 });
  });
  return spans;
}

/** `| a | b |` into its cells, without the empty edges the pipes create. */
function tableCells(row: string, line: number): readonly (readonly Span[])[] {
  const trimmed = row.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => parseSpans(cell.trim(), line));
}

function isTableRow(line: string): boolean {
  return line.trimStart().startsWith("|");
}

function refuseUnsupportedBlock(line: string, number_: number): void {
  const trimmed = line.trimStart();
  if (
    trimmed.startsWith("```") ||
    trimmed.startsWith("~~~") ||
    trimmed.startsWith(">") ||
    trimmed.startsWith("<") ||
    ORDERED_ITEM.test(trimmed) ||
    /^={3,}$/.test(trimmed) ||
    /^-{3,}$/.test(trimmed)
  ) {
    refuse(number_, line);
  }
}

/**
 * Markdown source into blocks.
 *
 * Line numbers are one-based so that an error message names the line an editor
 * shows.
 */
export function parseMarkdown(source: string): readonly Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const raw = lines[index] ?? "";
    const number_ = index + 1;

    if (raw.trim() === "") {
      index += 1;
      continue;
    }

    refuseUnsupportedBlock(raw, number_);

    const heading = HEADING.exec(raw.trimStart());
    if (heading !== null) {
      const hashes = heading[1] ?? "";
      const text = heading[2] ?? "";
      blocks.push({
        kind: "heading",
        level: hashes.length,
        spans: parseSpans(text, number_),
      });
      index += 1;
      continue;
    }

    if (isTableRow(raw)) {
      const delimiter = lines[index + 1] ?? "";
      if (!TABLE_DELIMITER.test(delimiter.trim())) refuse(number_, raw);
      const header = tableCells(raw, number_);
      const rows: (readonly (readonly Span[])[])[] = [];
      index += 2;
      while (index < lines.length && isTableRow(lines[index] ?? "")) {
        rows.push(tableCells(lines[index] ?? "", index + 1));
        index += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    if (LIST_ITEM.test(raw.trimStart())) {
      const items: string[] = [];
      while (index < lines.length) {
        const current = lines[index] ?? "";
        if (current.trim() === "") break;
        const item = LIST_ITEM.exec(current.trimStart());
        if (item !== null) {
          items.push(item[1] ?? "");
        } else if (items.length > 0) {
          // A wrapped line belongs to the item above it. Markdown joins them
          // with a space; the source's own line breaks are not meaningful.
          items[items.length - 1] =
            `${items[items.length - 1] ?? ""} ${current.trim()}`;
        } else {
          break;
        }
        index += 1;
      }
      blocks.push({
        kind: "list",
        items: items.map((item) => parseSpans(item, number_)),
      });
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length) {
      const current = lines[index] ?? "";
      if (
        current.trim() === "" ||
        isTableRow(current) ||
        LIST_ITEM.test(current.trimStart())
      ) {
        break;
      }
      if (HEADING.test(current.trimStart())) break;
      refuseUnsupportedBlock(current, index + 1);
      paragraph.push(current.trim());
      index += 1;
    }
    blocks.push({
      kind: "paragraph",
      spans: parseSpans(paragraph.join(" "), number_),
    });
  }

  return blocks;
}
