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

test("public demo: a proxy answering 503 for 8 s shows Starting up, never Offline, then the real status", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    const w = window as unknown as { __apiStates: string[] };
    w.__apiStates = [];
    new MutationObserver(() => {
      const state = document.querySelector(".api-status")?.getAttribute("data-state");
      if (state && w.__apiStates.at(-1) !== state) w.__apiStates.push(state);
    }).observe(document, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-state"] });
  });
  let up = false;
  await page.route("**/api/backend/health", (route) => up
    ? route.fulfill({ json: { status: "ok", version: "1.0.0", semantic_search: true, chunks: 3867 } })
    : route.fulfill({ status: 503, json: { error: { code: "upstream_unavailable", message: "The API is starting." } } }));
  await page.goto("/ask");
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "starting");
  await page.waitForTimeout(8_000);
  up = true;
  const back = Date.now();
  await expect(page.locator(".api-status-text")).toHaveText("3,867 passages indexed · meaning search", { timeout: 4_000 });
  expect(Date.now() - back).toBeLessThan(3_500);
  expect(await page.evaluate(() => (window as unknown as { __apiStates: string[] }).__apiStates)).not.toContain("offline");
  expect(errors).toEqual([]);
});
