import { beforeAll, describe, expect, it } from "vitest";
import { ESLint } from "eslint";
import { existsSync } from "node:fs";
import { join } from "node:path";

// `eslint.config.mjs` relaxes `@typescript-eslint/no-unused-vars` with
// `ignoreRestSiblings: true`, so that the binding in
// `const { year: _dropped, ...without } = fixture` stops being reported. That
// is a loosening, and a loosening is worth nothing on the word of the person
// who wrote it: the question is whether the rule can still go red at all
// afterwards. Both directions are asserted here, because only the pair
// distinguishes "correctly configured" from "switched off". Proved on
// 2026-09-01 by setting the option back to false and watching the third case
// fail while the first two stayed green.
//
// This runs eslint over source text rather than over a file on disk. A fixture
// file holding a deliberately unused variable would itself be linted by
// `pnpm lint`, so the repository would have to ignore it, and a path the gate
// skips is not evidence about the gate.

// Vitest's root, which is `frontend/`, and not `import.meta.url`: under the
// transform that is not a `file:` URL and `fileURLToPath` throws on it. The
// check is here because an eslint instance pointed at the wrong directory
// finds no configuration and reports nothing at all, and "reports nothing" is
// what the third case asserts. Without this, that failure would read as a
// pass. It has already earned its place once, on a run started from the
// repository root instead of from `frontend/`.
const cwd = process.cwd();
if (!existsSync(join(cwd, "eslint.config.mjs"))) {
  throw new Error(
    `no eslint.config.mjs under ${cwd}; these tests would be vacuous`,
  );
}

// Booting eslint loads `eslint-config-next` and the typescript-eslint parser,
// which is the expensive part: measured at 2.5 s on its own and over 5 s
// alongside the other test files. It used to happen once per case, and on
// 2026-09-13 the three boots together passed 30 s under the parallel load of
// 52 test files and the suite failed on how busy the machine was rather than
// on what the rule does. Raising the budget again would be the same treatment
// applied harder, so the boot moved into setup and happens once.
//
// Sharing one instance across the three cases does not couple them.
// `lintText` returns a result and keeps nothing between calls, so no case can
// see what another did; what is shared is the cost of loading a parser, not
// state.
const BOOTS_ESLINT = 30_000;

let eslint: ESLint;

beforeAll(async () => {
  eslint = new ESLint({ cwd });
  // Linting something is what pays for the boot. Constructing an `ESLint` is
  // cheap and loads nothing; the configuration and the typescript-eslint
  // parser arrive on the first `lintText`, so a setup that only constructed
  // would leave the cost on whichever case ran first. Measured on 2026-09-13:
  // without this line the first case timed out at five seconds on every run.
  await eslint.lintText("export const warm = 1;\n", {
    filePath: join(cwd, "src", "unused-vars-warmup.ts"),
  });
}, BOOTS_ESLINT);

async function lint(code: string): Promise<readonly string[]> {
  const results = await eslint.lintText(code, {
    // Never written to disk. The path only decides which configuration entries
    // apply, and this one is inside `src/` like the code the rule guards.
    filePath: join(cwd, "src", "unused-vars-probe.ts"),
  });
  const result = results[0];
  if (result === undefined) {
    // eslint returns nothing at all for a path its configuration ignores, and
    // an empty result would read here as "the rule reported no problems",
    // which is what the third case asserts. Same reason as the check above:
    // the vacuous case has to be loud.
    throw new Error("eslint linted nothing; the probe path is being ignored");
  }
  return result.messages
    .filter((message) => message.ruleId === "@typescript-eslint/no-unused-vars")
    .map((message) => message.message);
}

describe("the unused variable rule after ignoreRestSiblings", () => {
  it("still reports a variable that is simply never used", async () => {
    const messages = await lint(
      "const forgotten = 1;\nexport const used = 2;\n",
    );
    expect(messages).toHaveLength(1);
    expect(messages[0]).toContain("forgotten");
  });

  it("still reports an import that nothing in the file uses", async () => {
    const messages = await lint(
      'import { readFile } from "node:fs";\nexport const used = 2;\n',
    );
    expect(messages).toHaveLength(1);
    expect(messages[0]).toContain("readFile");
  });

  it("leaves the binding that exists so a rest element can exclude it", async () => {
    const messages = await lint(
      "const fixture = { year: 2026, rest: 1 };\n" +
        "const { year: _dropped, ...without } = fixture;\n" +
        "export const kept = without;\n",
    );
    expect(messages).toEqual([]);
  });
});
