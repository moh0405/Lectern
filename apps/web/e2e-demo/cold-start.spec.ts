import { expect, test } from "@playwright/test";

test("public demo: a waking API shows Starting up through the proxy, then the real status", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let up = false;
  await page.route("**/api/backend/health", (route) => up
    ? route.fulfill({ json: { status: "ok", version: "1.0.0", semantic_search: true, chunks: 3867 } })
    : route.fulfill({ json: { status: "starting", version: "1.0.0", semantic_search: null, chunks: null }, headers: { "cache-control": "no-store" } }));
  await page.goto("/ask");
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "starting");
  await expect(page.locator(".api-status-text")).toHaveText("Starting up…");
  up = true;
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "online", { timeout: 6_000 });
  await expect(page.locator(".api-status-text")).toContainText("3,867 passages");
  expect(errors).toEqual([]);
});
