import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // The site is statically built, so the tests run against the built output
  // rather than a dev server. That is what ships, and a dev server behaves
  // differently enough that testing it proves less than it looks.
  webServer: {
    // -c ../serve.json, resolved relative to the directory being served, so
    // this is frontend/serve.json. It holds one rewrite and that rewrite is
    // the one line of configuration the reverse proxy in deelproject 2 needs
    // as well: /advies/<token>/ is not a file on disk, because the site is
    // statically exported and the token is read from the path at runtime.
    // Without it the shareable link 404s for everybody except the person who
    // computed the advice, so the end-to-end tests run against the same
    // arrangement production needs rather than a friendlier one.
    command: "pnpm exec serve out -l 4173 -c ../serve.json",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
  },
  use: { baseURL: "http://127.0.0.1:4173", ...devices["Desktop Chrome"] },
  forbidOnly: true,
  reporter: [["list"]],
});
