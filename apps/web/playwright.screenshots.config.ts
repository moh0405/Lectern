import { defineConfig, devices } from "@playwright/test";

/**
 * Captures the screenshots used in the README (docs/images). Not part of the test suite.
 *
 *   cd apps/web && E2E_PYTHON=$(which python) npx playwright test -c playwright.screenshots.config.ts
 *
 * Boots scripts/demo_server.py (real retrieval, scripted model) and a production build of the web app.
 */
const API_PORT = 8200;
const WEB_PORT = 3200;
const python = process.env.E2E_PYTHON ?? "python";

export default defineConfig({
  testDir: "./screenshots",
  workers: 1,
  reporter: "list",
  use: { baseURL: `http://localhost:${WEB_PORT}`, viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `${python} ../../scripts/demo_server.py ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: { DEMO_WEB_ORIGIN: `http://localhost:${WEB_PORT}` },
    },
    {
      command: `npm run build && npm run start -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      timeout: 240_000,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});
