import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**"],
      reporter: ["text", "json-summary"],
      // Measured on 2026-08-21, once there was something to measure, and
      // written down rounded to the whole percent below what was actually
      // reached: 95.75 statements, 91.62 branches, 94.77 functions, 96.33
      // lines. A floor invented before the first line is written is a number
      // nobody derived from anything.
      //
      // This may rise and may never fall, the same rule the Python floor in
      // pyproject.toml follows. Lowering it to make a build pass is deleting
      // the gate and calling it a configuration change; the fix is a test.
      //
      // Four numbers rather than one, because they fail on different things.
      // Statements and lines catch code nothing runs at all; branches catch
      // the half of an if nobody took, which on this page is every error path;
      // functions catch a handler that is wired up and never fired.
      thresholds: {
        // Raised 95/91/94/96 -> 96/93/96/97 on 2026-08-21, from a measurement
        // of 96.94 / 93.03 / 96.04 / 97.52 rounded down. The fix rounds after
        // the audits added seventy-five tests and every number rose. Ratcheting
        // is the point: a floor left where it was is a floor that stops noticing
        // regressions the moment the tree gets better than it.
        //
        // Raised again 96/93/96/97 -> 97/94/96/98 on 2026-09-06, at the end of
        // the accounts frontend branch, from a measurement of 97.27 / 94.76 /
        // 96.63 / 98.14 rounded down. Functions stays at 96 because the
        // rounded-down measurement is 96 too: equal is not lower.
        statements: 97,
        branches: 94,
        functions: 96,
        lines: 98,
      },
    },
  },
});
