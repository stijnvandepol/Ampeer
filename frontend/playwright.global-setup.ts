import { readdirSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

/**
 * Refuse to run the end-to-end tests against a build that is older than the
 * code they are meant to be testing.
 *
 * `playwright.config.ts` serves `out/` and does not build it. CI gets this
 * right by ordering, `pnpm build` then `pnpm e2e`, and a developer running
 * `pnpm e2e` on its own gets whatever `out/` happens to hold. That is not a
 * theoretical hazard. On 2026-09-02 the language check failed on a footer
 * sentence that had been rewritten an hour earlier: the allowlist came from
 * the source, the page came from a build that predated it, and the message
 * said nothing about either. Two changes were verified against yesterday's
 * site before anybody noticed.
 *
 * The dangerous direction is the other one, and it is why this exists at all.
 * A stale build usually produces a confusing failure. It can equally produce a
 * PASS, and a green end-to-end suite that never loaded the code under test is
 * the most expensive kind of green there is.
 *
 * Compared by modification time and not by content hash, deliberately. A hash
 * would be exact and would also have to decide which inputs count; a timestamp
 * is coarse, cannot be wrong in the direction that matters, and its one false
 * positive, a rebuild that touched nothing, costs a rebuild.
 */

/*
 * `__dirname` and not `import.meta.url`. Playwright loads this file as
 * CommonJS, because the nearest package.json declares no `"type": "module"`,
 * and `import.meta` is a syntax error there rather than a value that is merely
 * wrong. The check below is the same discipline the vitest lint probe needed:
 * a path resolving to the wrong directory would make everything in this file
 * vacuous, and vacuous reads here as "the build is fine".
 */
const HERE = __dirname;
const OUT = join(HERE, "out");

if (!existsSync(join(HERE, "playwright.config.ts"))) {
  throw new Error(
    `global setup resolved ${HERE}, which is not the frontend package; every check below would be vacuous`,
  );
}

/** Everything the export is built from, in the order a build reads it. */
const SOURCES = [
  join(HERE, "src"),
  join(HERE, "next.config.ts"),
  join(HERE, "serve.json"),
  // The methodology page is rendered from this file at build time, so a change
  // to the document is a change to the site.
  join(HERE, "..", "docs", "methodologie.md"),
];

function newest(path: string): { at: number; file: string } {
  if (!existsSync(path)) return { at: 0, file: path };
  const stat = statSync(path);
  if (!stat.isDirectory()) return { at: stat.mtimeMs, file: path };
  let best = { at: 0, file: path };
  for (const entry of readdirSync(path)) {
    const found = newest(join(path, entry));
    if (found.at > best.at) best = found;
  }
  return best;
}

export default function assertBuildIsCurrent(): void {
  if (!existsSync(join(OUT, "index.html"))) {
    throw new Error(
      "frontend/out/ holds no index.html, so there is nothing to test against. Run `pnpm build`.",
    );
  }
  const built = newest(join(OUT, "index.html")).at;
  for (const source of SOURCES) {
    const latest = newest(source);
    if (latest.at > built) {
      const behind = Math.round((latest.at - built) / 1000);
      throw new Error(
        `the export in frontend/out/ is ${behind} seconds older than ` +
          `${latest.file.replace(HERE, "frontend")}, so these tests would run ` +
          "against code that is not the code in this working tree. Run `pnpm build` first.",
      );
    }
  }
}
