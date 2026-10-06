import { defineConfig, devices } from "@playwright/test";

/**
 * Percorsi end-to-end sull'app web (seduta 24). Prima va avviato l'ambiente completo:
 *   cd services/api && uv run python -m tests.e2e_target
 * (vedi e2e/README.md). Un solo worker: i percorsi condividono lo stesso database.
 */
export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: {
    locale: "it-IT",
    timezoneId: "Europe/Rome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "app",
      testIgnore: /admin-.*\.spec\.ts/,
      use: { baseURL: "http://localhost:8081", ...devices["iPhone 13"], browserName: "chromium" },
    },
    {
      // Pannello dello staff (next dev con accesso a token: lo avvia run-local.sh con WEARX_E2E_ADMIN=1).
      name: "admin",
      testMatch: /admin-.*\.spec\.ts/,
      use: { baseURL: "http://localhost:3000", ...devices["Desktop Chrome"] },
    },
  ],
});
