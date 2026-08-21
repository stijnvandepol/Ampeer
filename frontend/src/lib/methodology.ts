import { access, readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

/**
 * The methodology, read from the repository at build time.
 *
 * `docs/methodologie.md` is the document this product is judged on, and the
 * Python tests guard it. Copying it into the frontend would give the published
 * page a second life of its own, and the first correction to the model would
 * leave the two disagreeing with nobody the wiser. So the page is built from
 * the file itself, which makes drift impossible rather than unlikely.
 *
 * This module is build-time only. It reads the filesystem, so it belongs in a
 * server component or a build script and can never run in a browser. That is
 * not a limitation to work around: the file is on the machine that builds the
 * site and nowhere else, because `next.config.ts` sets `output: "export"` and
 * no Node process exists in production.
 *
 * It returns Markdown source and never HTML. There is a semgrep rule in
 * `.semgrep/frontend.yml` that fails the build on `dangerouslySetInnerHTML`,
 * and it is there on purpose: this string is a file's contents, and the moment
 * it is injected as markup the page renders whatever that file happens to
 * contain. Render it as elements, or as text. Do not hand it to a parser whose
 * output goes straight into the DOM.
 */

/** Relative to the repository root, which is the only place it lives. */
const METHODOLOGY_PATH = join("docs", "methodologie.md");

/**
 * The repository root, found by walking up from the working directory.
 *
 * Not `process.cwd()` and not a `../` count: `next build` runs in `frontend/`,
 * vitest runs in `frontend/`, and a script may run from the root. A hard-coded
 * number of levels is a path that works until somebody runs the build from
 * somewhere else, and then reads a file that is not there or, worse, one that
 * is.
 */
async function findRepositoryRoot(from: string): Promise<string> {
  let directory = resolve(from);
  for (;;) {
    try {
      await access(join(directory, METHODOLOGY_PATH));
      return directory;
    } catch {
      const parent = dirname(directory);
      if (parent === directory) {
        throw new Error(`${METHODOLOGY_PATH} is not above ${resolve(from)}`);
      }
      directory = parent;
    }
  }
}

/** The contents of `docs/methodologie.md`, as Markdown. */
export async function loadMethodology(): Promise<string> {
  const root = await findRepositoryRoot(process.cwd());
  return readFile(join(root, METHODOLOGY_PATH), "utf-8");
}
