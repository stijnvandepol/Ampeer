/** What the file is called on the visitor's own disk. */
export const EXPORT_FILENAME = "ampeer-gegevens.json";

/**
 * Hand the export to the browser as a file, built from the text the API sent.
 *
 * The text goes into the Blob unchanged. Not `JSON.parse` and `JSON.stringify`
 * around it: every amount inside an advice is a string because JSON has floats
 * and no decimals, and a round trip through a parser is the rounding this
 * project avoids everywhere else. There is a semgrep rule on `parseFloat` over
 * an amount and it would see nothing here, because it would be a
 * `JSON.stringify` of a parsed tree doing it quietly.
 *
 * The object URL is revoked immediately after the click. The browser has
 * already read it by then, and an unrevoked one keeps the whole export alive
 * in memory for as long as the document lives.
 */
export function downloadJson(text: string): void {
  const url = URL.createObjectURL(
    new Blob([text], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = EXPORT_FILENAME;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
