import { defineConfig, devices } from "@playwright/test";

/**
 * Opt-in: drives the whole app with a REAL Gemini model (no scripted stand-in). Needs a key with quota.
 *
 *   cd apps/web && GEMINI_API_KEY=... GEMINI_MODEL=gemini-3.6-flash E2E_PYTHON=$(which python) \
 *     npx playwright test -c playwright.real.config.ts
 *
 * Real model calls are slow and sometimes fail (overload, quota), so the timeouts are long and these tests are
 * not part of CI.
 */
const API_PORT = 8500;
const WEB_PORT = 3500;
const python = process.env.E2E_PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e-real",
  workers: 1,
  fullyParallel: false,
  timeout: 240_000,
  expect: { timeout: 90_000 },
  reporter: "list",
  use: { baseURL: `http://localhost:${WEB_PORT}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} ../../tests/real_server.py ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 180_000,
      env: { E2E_WEB_ORIGIN: `http://localhost:${WEB_PORT}` },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}`, NEXT_PUBLIC_BROWSER_EMBEDDINGS: "off" },
    },
  ],
});
