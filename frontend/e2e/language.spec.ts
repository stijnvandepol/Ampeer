import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import ts from "typescript";
import fixture from "../tests/fixtures/advice-response.json";

/**
 * The language boundary, checked twice, by two checks that judge no meaning.
 *
 * Spec chapter 10 point 3 and the definition of done both ask for a test that
 * no Dutch advice text lives in frontend source. Nobody wrote one, and the
 * reason it stayed unwritten is sound: nearly every string in `src/` is
 * legitimately Dutch, and no lexical rule separates "Verfijn uw antwoord" from
 * "Vraag nu een offerte aan". A keyword heuristic would be a check that reads
 * as a gate and is not one.
 *
 * So neither check below reads a word.
 *
 * **A** walks `src/**` with the TypeScript compiler API, collects every string
 * that can reach a DOM text node or an accessible name, and compares the sorted
 * set byte for byte against `tests/ui-strings.txt`. It cannot tell advice from
 * navigation. It does not have to: a sentence about a household's electricity
 * cannot appear in the frontend without appearing in that file, in a diff,
 * beside a header saying what a line there is allowed to be.
 *
 * **B** serves the advice page an API response in which every Dutch field has
 * been replaced by a unique sentinel, opens every disclosure, and reads the
 * body text. Each sentinel must appear exactly once, which catches text the
 * frontend dropped or rewrote; and what is left after removing the sentinels,
 * the other API values and the allowlist must contain no letters at all, which
 * catches a sentence the frontend supplied instead. B sees what A cannot: a
 * lookup table living in a file an extractor was told to treat as data.
 *
 * Regenerating the allowlist is deliberate and never silent:
 *
 *     UPDATE_UI_STRINGS=1 pnpm e2e language
 *
 * That run rewrites `tests/ui-strings.txt` and then fails, so a regeneration
 * can never be the thing that made a build green.
 */

/** frontend/, whether playwright was started there or at the repository root. */
function frontendRoot(): string {
  const here = process.cwd();
  if (existsSync(join(here, "src", "lib", "types.ts"))) return here;
  const nested = join(here, "frontend");
  if (existsSync(join(nested, "src", "lib", "types.ts"))) return nested;
  throw new Error(`cannot find the frontend tree from ${here}`);
}

const ROOT = frontendRoot();
const SOURCE_DIR = join(ROOT, "src");
const ALLOWLIST = join(ROOT, "tests", "ui-strings.txt");

/**
 * The attributes whose value a screen reader announces, plus `href`, which is
 * navigation and is the one other thing the header of the allowlist permits.
 */
const NAMING_ATTRIBUTES = new Set([
  "aria-label",
  "aria-description",
  "aria-placeholder",
  "aria-valuetext",
  "alt",
  "title",
  "placeholder",
  "label",
  "href",
]);

/**
 * A CSS custom property name. These are identifiers the styling system selects
 * between and cannot become text, and dropping them by shape rather than by
 * meaning keeps the allowlist readable without teaching it a vocabulary.
 */
const CSS_CUSTOM_PROPERTY = /^--[a-z0-9-]+$/;

/**
 * Elements whose children are not text a visitor reads. `<script>` in
 * app/layout.tsx carries the inline theme setter, which is code and would
 * otherwise arrive in the allowlist in fragments.
 */
const NOT_TEXT_ELEMENTS = new Set(["script", "style"]);

/** The named entities JSX text may carry, as the visitor sees them. */
const ENTITIES: ReadonlyMap<string, string> = new Map([
  ["&euro;", "€"],
  ["&quot;", '"'],
  ["&apos;", "'"],
  ["&nbsp;", " "],
  ["&amp;", "&"],
]);

function decodeEntities(value: string): string {
  let decoded = value;
  for (const [entity, character] of ENTITIES)
    decoded = decoded.split(entity).join(character);
  return decoded;
}

/** The tag an expression container is a child of, lowercased, or null. */
function enclosingTag(node: ts.Node, source: ts.SourceFile): string | null {
  const parent = node.parent;
  if (parent !== undefined && ts.isJsxElement(parent)) {
    return parent.openingElement.tagName.getText(source).toLowerCase();
  }
  return null;
}

/**
 * Below this the extraction has stopped working and check A has become
 * decoration. Set under the count on 2026-08-21 rather than at it, so adding a
 * label is not a failure and losing the walk is.
 */
const MINIMUM_UI_STRINGS = 60;

/** The files check A must have read, so a broken walk cannot pass quietly. */
const FILES_THE_WALK_MUST_REACH = [
  join("app", "advies", "page.tsx"),
  join("app", "_flow", "messages.ts"),
  join("components", "band", "RouteSection.tsx"),
  join("components", "band", "ScenarioBandFigure.tsx"),
];

function sourceFiles(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const full = join(directory, entry.name);
    if (entry.isDirectory()) found.push(...sourceFiles(full));
    else if (/\.tsx?$/.test(entry.name)) found.push(full);
  }
  return found.sort();
}

/** One space between words, none at the ends. Nothing else is changed. */
function normalise(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

/**
 * Every string in one file that can reach a DOM text node or an accessible
 * name.
 *
 * The rule is structural: a literal counts when it sits in a text position, and
 * a text position is a JSX text node, a JSX child expression, the value of one
 * of the naming attributes above, the initialiser of a variable, or the
 * expression of a return. From there it propagates through the operators that
 * can carry a string to the same place: parentheses, a conditional, `+`, `||`,
 * `??`, the right half of `&&`, array elements, object property values, and the
 * literal spans of a template.
 *
 * `===` is deliberately not on that list. `copyState === "copied"` puts a
 * string beside a rendering decision without ever rendering it, and treating
 * every binary expression alike would have pulled state names into a file whose
 * header says a line in it is something a visitor reads.
 */
function uiStrings(file: string): string[] {
  const source = ts.createSourceFile(
    file,
    readFileSync(file, "utf-8"),
    ts.ScriptTarget.Latest,
    true,
    file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const found: string[] = [];

  const record = (value: string): void => {
    const text = normalise(decodeEntities(value));
    if (text.length === 0) return;
    if (CSS_CUSTOM_PROPERTY.test(text)) return;
    found.push(text);
  };

  const harvest = (node: ts.Node): void => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      record(node.text);
    } else if (ts.isTemplateExpression(node)) {
      record(node.head.text);
      for (const span of node.templateSpans) record(span.literal.text);
    } else if (ts.isParenthesizedExpression(node)) {
      harvest(node.expression);
    } else if (ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) {
      harvest(node.expression);
    } else if (ts.isConditionalExpression(node)) {
      harvest(node.whenTrue);
      harvest(node.whenFalse);
    } else if (ts.isBinaryExpression(node)) {
      const operator = node.operatorToken.kind;
      if (
        operator === ts.SyntaxKind.PlusToken ||
        operator === ts.SyntaxKind.BarBarToken ||
        operator === ts.SyntaxKind.QuestionQuestionToken
      ) {
        harvest(node.left);
        harvest(node.right);
      } else if (operator === ts.SyntaxKind.AmpersandAmpersandToken) {
        harvest(node.right);
      }
    } else if (ts.isArrayLiteralExpression(node)) {
      for (const element of node.elements) harvest(element);
    } else if (ts.isObjectLiteralExpression(node)) {
      for (const property of node.properties) {
        if (ts.isPropertyAssignment(property)) harvest(property.initializer);
      }
    } else if (ts.isJsxExpression(node) && node.expression !== undefined) {
      harvest(node.expression);
    }
  };

  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node)) {
      if (
        enclosingTag(node, source) === null ||
        !NOT_TEXT_ELEMENTS.has(enclosingTag(node, source) ?? "")
      ) {
        record(node.text);
      }
    } else if (ts.isJsxAttribute(node)) {
      const name = node.name.getText(source);
      if (NAMING_ATTRIBUTES.has(name) && node.initializer !== undefined) {
        harvest(node.initializer);
      }
    } else if (ts.isJsxExpression(node) && !ts.isJsxAttribute(node.parent)) {
      const tag = enclosingTag(node, source);
      if (
        node.expression !== undefined &&
        (tag === null || !NOT_TEXT_ELEMENTS.has(tag))
      ) {
        harvest(node.expression);
      }
    } else if (
      ts.isVariableDeclaration(node) &&
      node.initializer !== undefined
    ) {
      harvest(node.initializer);
    } else if (ts.isReturnStatement(node) && node.expression !== undefined) {
      harvest(node.expression);
    }
    ts.forEachChild(node, visit);
  };

  visit(source);
  return found;
}

function extractAll(): {
  readonly strings: string[];
  readonly files: string[];
} {
  const files = sourceFiles(SOURCE_DIR);
  const strings = new Set<string>();
  for (const file of files)
    for (const value of uiStrings(file)) strings.add(value);
  return { strings: [...strings].sort(), files };
}

/**
 * The file split into its header and its data.
 *
 * The header is the run of `#` lines at the top plus the blank line under it,
 * and nothing else. "Every line that starts with #" would have been wrong, and
 * was: `#` is itself one of the extracted strings, so it was swallowed by its
 * own comment rule and the check failed on a string it had thrown away. A rule
 * about the shape of a line cannot survive a line whose content is that shape,
 * so the boundary is a position instead.
 */
function allowlistFile(): {
  readonly header: string[];
  readonly lines: string[];
} {
  const all = readFileSync(ALLOWLIST, "utf-8").split(/\r?\n/);
  let cut = 0;
  while (cut < all.length && (all[cut] ?? "").startsWith("#")) cut += 1;
  while (cut < all.length && (all[cut] ?? "").length === 0) cut += 1;
  return {
    header: all.slice(0, cut).filter((line) => line.startsWith("#")),
    lines: all.slice(cut).filter((line) => line.length > 0),
  };
}

function allowlistLines(): string[] {
  return allowlistFile().lines;
}

test.describe("the language boundary", () => {
  test("every string the frontend can put on a screen is in the allowlist", () => {
    const { strings, files } = extractAll();

    if (process.env["UPDATE_UI_STRINGS"] !== undefined) {
      const header = allowlistFile().header.join("\n");
      writeFileSync(ALLOWLIST, `${header}\n\n${strings.join("\n")}\n`, "utf-8");
      throw new Error(
        "ui-strings.txt rewritten; read the diff and run again without the flag",
      );
    }

    // Non-vacuity first, and explicitly. A walk that found nothing, or a
    // regular expression that matched no file, would otherwise agree with an
    // allowlist somebody had emptied.
    expect(files.length, "no source files were walked").toBeGreaterThan(20);
    for (const required of FILES_THE_WALK_MUST_REACH) {
      expect(
        files.map((file) => file.slice(SOURCE_DIR.length + 1)),
        `${required} was not walked`,
      ).toContain(required);
    }
    expect(strings.length, "the extraction collapsed").toBeGreaterThanOrEqual(
      MINIMUM_UI_STRINGS,
    );

    const committed = allowlistLines();
    expect(committed.length, "the allowlist is empty").toBeGreaterThanOrEqual(
      MINIMUM_UI_STRINGS,
    );

    // Both directions, named separately, because they are different mistakes.
    const added = strings.filter((value) => !committed.includes(value));
    const stale = committed.filter((value) => !strings.includes(value));
    expect(
      added,
      "new user-visible strings in src/. Read the header of tests/ui-strings.txt: " +
        "a line there is navigation, a form label, or a message about the request, " +
        "never a sentence about the household's electricity.",
    ).toEqual([]);
    expect(
      stale,
      "allowlist lines that match nothing in src/ any more",
    ).toEqual([]);

    // Byte for byte, so ordering and duplicates cannot drift either.
    expect(strings).toEqual(committed);
  });

  test("the advice page says nothing about the household that the API did not say", async ({
    page,
  }) => {
    const { payload, sentinels } = stubbed();

    await page.route("**/api/advice/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify(payload),
      }),
    );

    await page.goto(`/advies/${fixture.token}/`);
    await expect(page.locator('[data-band-kind="percentile"]')).toBeVisible();
    const opened = await openEveryDisclosure(page);
    expect(
      opened,
      "no disclosure was opened, so the panels were never read",
    ).toBeGreaterThan(3);

    // Lowercased, because `innerText` returns what CSS renders and four of the
    // headings on this page carry `text-transform: uppercase`. Comparing case
    // sensitively made the check fail on its own stylesheet. Check A pins the
    // exact casing of every one of these strings, so nothing is lost here.
    const body = (await page.locator("body").innerText()).toLowerCase();

    // Direction one: everything the API said is on the page, once. A sentinel
    // that is missing is text the frontend dropped; one that appears twice is
    // text it rendered in two places, which for advice is two claims.
    const wrong = sentinels
      .map((sentinel) => ({ sentinel, count: body.split(sentinel).length - 1 }))
      .filter((entry) => entry.count !== 1);
    expect(wrong, "sentinels that did not appear exactly once").toEqual([]);

    // Direction two: nothing else on the page is a sentence. Everything the
    // API sent is removed, then every allowlisted string, longest first so a
    // short entry cannot eat part of a longer one, then the page's own URL,
    // then every digit and every mark that is not a letter. What is left must
    // contain no letter at all.
    let residue = body;
    // The page's own address first. It is rendered as text, it is the one
    // string on the page that neither side wrote, and removing it after the
    // allowlist left "ttp" behind: a one letter allowlist entry had already
    // eaten the "h" out of "http", so the longest-first ordering only holds
    // within one pass.
    residue = residue.split(page.url().toLowerCase()).join(" ");
    for (const value of apiText(payload))
      residue = residue.split(value.toLowerCase()).join(" ");
    for (const value of [...allowlistLines()].sort(
      (a, b) => b.length - a.length,
    )) {
      residue = residue.split(value.toLowerCase()).join(" ");
    }
    residue = residue.replace(/[^\p{L}]+/gu, " ").trim();

    expect(
      residue,
      "text on the advice page that came from neither the API nor the allowlist",
    ).toBe("");
  });
});

/** A unique, letter-bearing marker that survives innerText unchanged. */
function sentinelFor(index: number): string {
  return `zqmarker${String(index).padStart(4, "0")}zq`;
}

/** Every Dutch field of the response, replaced by a sentinel of its own. */
function stubbed(): {
  readonly payload: unknown;
  readonly sentinels: string[];
} {
  const sentinels: string[] = [];
  const next = (): string => {
    const sentinel = sentinelFor(sentinels.length);
    sentinels.push(sentinel);
    return sentinel;
  };
  // Every key whose value is a sentence or a name written for a reader. The
  // list is the language boundary itself: these are exactly the fields
  // ampeer_advice/nl.py fills in.
  const DUTCH_KEYS = new Set([
    "confidence_label",
    "title",
    "text",
    "basis_text",
    "varied_text",
    "pinned_text",
    "production_source_text",
  ]);

  const walk = (node: unknown, key: string | null): unknown => {
    if (Array.isArray(node)) {
      return node.map((item) =>
        key !== null && DUTCH_KEYS.has(key) && typeof item === "string"
          ? next()
          : walk(item, key),
      );
    }
    if (node !== null && typeof node === "object") {
      return Object.fromEntries(
        Object.entries(node as Record<string, unknown>).map(([name, value]) => [
          name,
          DUTCH_KEYS.has(name) && typeof value === "string"
            ? next()
            : walk(value, name),
        ]),
      );
    }
    return node;
  };

  return { payload: walk(fixture, null), sentinels };
}

/** Every string value in the response, longest first. */
function apiText(payload: unknown): string[] {
  const values: string[] = [];
  const walk = (node: unknown): void => {
    if (typeof node === "string") values.push(node);
    else if (Array.isArray(node)) for (const item of node) walk(item);
    else if (node !== null && typeof node === "object") {
      for (const value of Object.values(node as Record<string, unknown>))
        walk(value);
    }
  };
  walk(payload);
  return values
    .filter((value) => value.length > 0)
    .sort((a, b) => b.length - a.length);
}

/** Clicks every closed disclosure until none is left, and says how many. */
async function openEveryDisclosure(page: Page): Promise<number> {
  let opened = 0;
  for (let guard = 0; guard < 100; guard += 1) {
    const closed = page.locator('button[aria-expanded="false"]');
    if ((await closed.count()) === 0) break;
    await closed.first().click();
    opened += 1;
  }
  return opened;
}
