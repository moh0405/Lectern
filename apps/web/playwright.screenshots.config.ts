import { defineConfig, devices } from "@playwright/test";

/**
 * Captures the screenshots used in the README (docs/images). Not part of the test suite.
 *
 *   cd apps/web && E2E_PYTHON=$(which python) npx playwright test -c playwright.screenshots.config.ts capture
 *
 * Boots tests/screenshot_server.py (the real API with a scripted model, no key or network) and a production build of the web app.
 * Run it a second time with SCREENSHOT_SERVER=demo for the two pages that need a larger library (embedding map, Insights):
 * that run boots scripts/demo_server.py, which indexes the committed sample corpus and also uses a scripted model.
 */
const API_PORT = 8970;
const WEB_PORT = 3970;
const python = process.env.E2E_PYTHON ?? "python";
const apiScript = process.env.SCREENSHOT_SERVER === "demo" ? "scripts/demo_server.py" : "tests/screenshot_server.py";

export default defineConfig({
  testDir: "./screenshots",
  workers: 1,
  reporter: "list",
  use: { baseURL: `http://localhost:${WEB_PORT}`, viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: `${python} ../../${apiScript} ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: { E2E_WEB_ORIGIN: `http://localhost:${WEB_PORT}`, DEMO_WEB_ORIGIN: `http://localhost:${WEB_PORT}` },
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
