import { defineConfig } from "@playwright/test";

/**
 * Browser end-to-end test against a REAL SAT-SA backend (no mocked API).
 *
 * Local (default): e2e/global-setup.ts starts the API server and the analysis
 * worker on a throwaway SQLite database via scripts/local_stack.py, and the
 * web server below is the production Next.js build pointed at it.
 *
 *   npm run build && npm run test:e2e
 *
 * Deployed stack: set SATSA_E2E_BASE_URL (for example https://satsa.example.org)
 * and SATSA_E2E_CREDENTIALS (a JSON file with organization_id, admin, analyst,
 * supervisor credentials); nothing is started locally. Set
 * SATSA_E2E_IGNORE_HTTPS_ERRORS=true only for a certificate from a local CA.
 *
 * PLAYWRIGHT_CHANNEL selects an installed browser (for example msedge or
 * chrome); without it, run `npx playwright install chromium` once.
 */
export const E2E_API_PORT = Number(process.env.SATSA_E2E_API_PORT ?? 8765);
const WEB_PORT = Number(process.env.SATSA_E2E_WEB_PORT ?? 3107);
const external = process.env.SATSA_E2E_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  timeout: 8 * 60 * 1000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: external ?? `http://localhost:${WEB_PORT}`,
    ignoreHTTPSErrors: process.env.SATSA_E2E_IGNORE_HTTPS_ERRORS === "true",
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: external
    ? undefined
    : {
        command: `npx next start -p ${WEB_PORT}`,
        url: `http://localhost:${WEB_PORT}/login`,
        reuseExistingServer: false,
        timeout: 120_000,
        env: { SATSA_API_BASE_URL: `http://127.0.0.1:${E2E_API_PORT}` },
      },
});
