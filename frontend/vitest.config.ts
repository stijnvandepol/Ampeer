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
        statements: 95,
        branches: 91,
        functions: 94,
        lines: 96,
      },
    },
  },
});
