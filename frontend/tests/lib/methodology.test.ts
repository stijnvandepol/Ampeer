import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { loadMethodology } from "@/lib/methodology";

// Resolved from the working directory, which vitest sets to frontend/.
// `import.meta.url` is not a file URL under the jsdom environment.
const REPOSITORY_COPY = resolve(process.cwd(), "../docs/methodologie.md");

describe("the methodology", () => {
  it("is the file in the repository, not a copy of it", async () => {
    // The whole point. A copy would let the published page and the document
    // the Python tests guard drift apart, and the first correction to the
    // model is when that would happen.
    expect(await loadMethodology()).toBe(
      readFileSync(REPOSITORY_COPY, "utf-8"),
    );
  });

  it("finds the file from the working directory the build actually runs in", async () => {
    // `next build` and vitest both run in frontend/, a script may run from the
    // repository root. A hard-coded number of `../` works until it does not.
    expect(process.cwd().endsWith("frontend")).toBe(true);
    await expect(loadMethodology()).resolves.toContain("# Hoe Ampeer rekent");
  });

  it("returns Markdown, never markup", async () => {
    // There is a semgrep rule against dangerouslySetInnerHTML and it is there
    // on purpose. This string is a file's contents; the moment it is injected
    // as markup the page renders whatever the file happens to contain.
    const text = await loadMethodology();
    expect(text).not.toMatch(/<script/i);
    expect(text.trimStart().startsWith("#")).toBe(true);
  });

  it("does not render the document itself, and says so where it would be read", () => {
    const source = readFileSync(
      resolve(process.cwd(), "src/lib/methodology.ts"),
      "utf-8",
    );
    // It loads and hands back a string. Turning that string into a page is
    // somebody else's file, and the warning lives here because here is where
    // the next person arrives when they go looking for how to render it.
    expect(source).not.toMatch(/innerHTML\s*=/);
    expect(source).not.toMatch(/dangerouslySetInnerHTML=/);
    expect(source).toContain("dangerouslySetInnerHTML");
    expect(source).toContain(".semgrep/frontend.yml");
  });
});
