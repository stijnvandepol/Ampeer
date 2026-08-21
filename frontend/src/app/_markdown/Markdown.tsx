import { Fragment, type ReactNode } from "react";
import { parseMarkdown, type Block, type Span } from "./parse";

const HEADING_CLASS: Readonly<Record<number, string>> = {
  1: "text-3xl font-bold",
  2: "mt-10 text-xl font-medium",
  3: "mt-8 text-lg font-medium",
  4: "mt-6 font-medium",
  5: "mt-6 font-medium",
  6: "mt-6 font-medium",
};

function renderSpans(spans: readonly Span[]): ReactNode {
  return spans.map((span, index) => (
    <Fragment key={index}>
      {span.bold ? <strong>{span.text}</strong> : span.text}
    </Fragment>
  ));
}

function renderBlock(block: Block, key: number): ReactNode {
  if (block.kind === "heading") {
    // The document's own levels, kept as they are. Renumbering them to fit the
    // page would break the heading outline a screen reader navigates by, and
    // the document is the thing being published rather than a decoration on a
    // page that has its own structure.
    const Tag = `h${block.level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
    return (
      <Tag
        key={key}
        className={HEADING_CLASS[block.level] ?? "mt-6 font-medium"}
      >
        {renderSpans(block.spans)}
      </Tag>
    );
  }
  if (block.kind === "paragraph") {
    return (
      <p key={key} className="mt-4 text-ink-muted">
        {renderSpans(block.spans)}
      </p>
    );
  }
  if (block.kind === "list") {
    return (
      <ul
        key={key}
        className="mt-4 flex list-disc flex-col gap-2 pl-5 text-ink-muted"
      >
        {block.items.map((item, index) => (
          <li key={index}>{renderSpans(item)}</li>
        ))}
      </ul>
    );
  }
  return (
    // A table is the one block that can be wider than the column, so it gets
    // its own scroller with a tab stop, rather than pushing the page sideways
    // on a phone. tabIndex makes the scroller reachable from the keyboard,
    // which is what WCAG 2.2 asks of any region that scrolls.
    <div
      key={key}
      className="mt-6 overflow-x-auto"
      tabIndex={0}
      role="group"
      aria-label="Tabel"
    >
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {block.header.map((cell, index) => (
              <th
                key={index}
                scope="col"
                className="border-b border-border-strong px-3 py-2 text-left font-medium"
              >
                {renderSpans(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="border-b border-hairline px-3 py-2 text-ink-muted"
                >
                  {renderSpans(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface Props {
  readonly source: string;
}

/**
 * Markdown as React elements, never as markup.
 *
 * Every string below reaches the DOM as a text node, which is what makes the
 * question of whether the source is trusted one this component does not have
 * to answer. See `parse.ts` for what is supported and what happens to the rest.
 */
export function Markdown({ source }: Props) {
  return (
    <>
      {parseMarkdown(source).map((block, index) => renderBlock(block, index))}
    </>
  );
}
