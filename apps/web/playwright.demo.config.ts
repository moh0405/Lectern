import { defineConfig, devices } from "@playwright/test";

/**
 * The public-demo mode: BACKEND_URL set (as on Vercel), so the app talks through the proxy and the shared
 * database routes are refused. Checks that the browser-stored features work there.
 *
 *   cd apps/web && E2E_PYTHON=$(which python) npx playwright test -c playwright.demo.config.ts
 */
const API_PORT = 8300;
const WEB_PORT = 3300;
const python = process.env.E2E_PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e-demo",
  workers: 1,
  reporter: "list",
  use: { baseURL: `http://localhost:${WEB_PORT}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} ../../tests/e2e_server.py ${API_PORT}`,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: { E2E_WEB_ORIGIN: `http://localhost:${WEB_PORT}` },
    },
    {
      command: `npm run dev -- --port ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { BACKEND_URL: `http://127.0.0.1:${API_PORT}`, NEXT_PUBLIC_API_URL: `http://localhost:${WEB_PORT}/api/backend` },
    },
  ],
});
