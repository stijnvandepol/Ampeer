import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // The site is statically built, so the tests run against the built output
  // rather than a dev server. That is what ships, and a dev server behaves
  // differently enough that testing it proves less than it looks.
  webServer: {
    command: "pnpm exec serve out -l 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
  },
  use: { baseURL: "http://127.0.0.1:4173", ...devices["Desktop Chrome"] },
  forbidOnly: true,
  reporter: [["list"]],
});
