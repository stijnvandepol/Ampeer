/**
 * Dutch amounts, produced without the amount ever becoming a number.
 *
 * `CLAUDE.md` makes Dutch the language of everything a visitor reads, and
 * "1684.85" is not Dutch. `frontend/CLAUDE.md` makes the amount a string that
 * stays a string, and `.semgrep/frontend.yml` fails the build on parsing one.
 * Both hold at once only if the formatter is a transformation of the
 * characters, so the test that matters most here is the one with more digits
 * than a double can carry: a formatter that went through a number would round
 * it, and the output would still look like an amount.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { dutchAmount } from "@/components/band/format";

describe("a Dutch amount", () => {
  it("uses a comma for the decimal and a point for the thousands", () => {
    expect(dutchAmount("1684.85")).toBe("1.684,85");
    expect(dutchAmount("1395.51")).toBe("1.395,51");
    expect(dutchAmount("105.08")).toBe("105,08");
    expect(dutchAmount("6.99")).toBe("6,99");
  });

  it("groups every three digits, however long the number is", () => {
    expect(dutchAmount("1000")).toBe("1.000");
    expect(dutchAmount("1234567")).toBe("1.234.567");
    expect(dutchAmount("12345678.9")).toBe("12.345.678,9");
  });

  it("keeps a leading sign and a bare fraction as they were", () => {
    expect(dutchAmount("-1234.5")).toBe("-1.234,5");
    expect(dutchAmount("0.5")).toBe("0,5");
    expect(dutchAmount("0")).toBe("0");
  });

  it("adds no digit and drops no digit, at a precision no double can hold", () => {
    // 12345678901234567890.123456789 through parseFloat comes back as
    // 12345678901234567000, and the result still looks like an amount. This is
    // the assertion that separates a transformation of the characters from a
    // trip through a number.
    expect(dutchAmount("12345678901234567890.123456789")).toBe(
      "12.345.678.901.234.567.890,123456789",
    );
  });

  it("hands back anything that is not a plain decimal, unchanged", () => {
    // Never guess. An amount the API sent in a shape this does not recognise
    // reaches the screen as it arrived rather than as something invented.
    expect(dutchAmount("")).toBe("");
    expect(dutchAmount("1e3")).toBe("1e3");
    expect(dutchAmount("onbekend")).toBe("onbekend");
    expect(dutchAmount("1.2.3")).toBe("1.2.3");
  });

  it("never parses the amount it is given", () => {
    // The semgrep rule names two field names; this names the module, which is
    // the only place an amount is allowed to be taken apart at all.
    // Comments stripped first. The file's own docstring names the tools it
    // refuses to use, and a check that matched prose would be a check that
    // could only be satisfied by deleting the explanation.
    const source = readFileSync("src/components/band/format.ts", "utf-8")
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "");
    expect(source).not.toMatch(
      /parseFloat|parseInt|Number\(|toFixed|toLocaleString|Intl\./,
    );
  });
});
