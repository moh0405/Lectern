// Read-only UI checks against an already-running, explicitly local preview.
// Start the isolated tests/e2e_server.py fixture and frontend separately; this config starts neither.
import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
const baseURL = process.env.LECTERN_UX_URL || "http://127.0.0.1:3420";
if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(baseURL).hostname)) {
  throw new Error("Use a loopback preview with the isolated scripted API; this is not a production write test.");
}
export default defineConfig({
  testDir: fileURLToPath(new URL("../../apps/web/e2e/", import.meta.url)),
  testMatch: "ui-refresh.spec.ts",
  workers: 1,
  reporter: "list",
  outputDir: process.env.LECTERN_UX_OUTPUT || path.join(tmpdir(), "lectern-ui-refresh-results"),
  use: { baseURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
});
