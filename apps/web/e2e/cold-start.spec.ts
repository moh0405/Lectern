import AxeBuilder from "@axe-core/playwright";
import type { Page, Route } from "@playwright/test";
import { expect, test } from "./test";

const SCREENSHOTS = process.env.COLD_START_SCREENSHOTS;
const STARTING = { status: "starting", version: "1.0.0", semantic_search: null, chunks: null };
const READY = { status: "ok", version: "1.0.0", semantic_search: true, chunks: 3867 };

/** The API answers `starting` until `ready()` is called, then reports the real index. */
async function coldApi(page: Page, first: (route: Route, call: number) => Promise<void> | void) {
  let up = false;
  let calls = 0;
  await page.route("**/health", (route) => {
    calls += 1;
    if (up) return route.fulfill({ json: READY });
    return first(route, calls);
  });
  return { ready: () => { up = true; }, calls: () => calls };
}

function collectProblems(page: Page) {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(e.message));
  return problems;
}

async function axeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return results.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`);
}

for (const theme of ["light", "dark"] as const) {
  for (const [label, width, height] of [["desktop", 1440, 900], ["phone", 390, 844]] as const) {
    test(`cold start is calm, then shows the real status (${label}, ${theme})`, async ({ page }) => {
      const problems = collectProblems(page);
      await page.addInitScript((t) => localStorage.setItem("lectern-reading-theme", t), theme);
      await page.setViewportSize({ width, height });
      const api = await coldApi(page, (route) => route.fulfill({ json: STARTING, headers: { "cache-control": "no-store" } }));
      await page.goto("/ask");

      const status = page.locator(".api-status");
      await expect(status).toHaveAttribute("data-state", "starting");
      await expect(page.locator(".api-status-text")).toHaveText("Starting up…");
      expect((await page.locator(".api-status-text").boundingBox())?.width).toBeGreaterThan(40); // readable on a phone too
      await expect(page.getByRole("status").filter({ hasText: "starting up" })).toBeAttached();
      await expect(page.getByText("Offline", { exact: true })).toHaveCount(0);
      await expect(page.getByRole("heading", { name: "Something went wrong" })).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect(await axeViolations(page)).toEqual([]);
      if (SCREENSHOTS) await page.screenshot({ path: `${SCREENSHOTS}/starting-${width}-${theme}.png` });

      api.ready();
      await expect(status).toHaveAttribute("data-state", "online", { timeout: 6_000 });
      await expect(page.locator(".api-status-text")).toHaveText("3,867 passages indexed · meaning search");
      await expect(page.getByRole("status").filter({ hasText: "Connected to the study service again" })).toBeAttached();
      expect(await axeViolations(page)).toEqual([]);
      if (SCREENSHOTS) await page.screenshot({ path: `${SCREENSHOTS}/ready-${width}-${theme}.png` });
      expect(problems).toEqual([]);
    });
  }
}

test("a dropped first request shows Starting up, not Offline, and recovers on its own", async ({ page }) => {
  const problems = collectProblems(page);
  const seen: (string | null)[] = [];
  const api = await coldApi(page, (route, call) => {
    if (call >= 2) api.ready();
    return route.fulfill({ status: 502, json: { error: { code: "upstream_unreachable", message: "Could not reach the API." } } });
  });
  await page.goto("/ask");
  const status = page.locator(".api-status");
  await expect(status).toHaveAttribute("data-state", "starting");
  seen.push(await status.getAttribute("data-state"));
  await expect(status).toHaveAttribute("data-state", "online", { timeout: 8_000 });
  await expect(page.locator(".api-status-text")).toContainText("3,867 passages");
  expect(seen).not.toContain("offline");
  expect(problems).toEqual([]);
});

test("while the library is still loading, the page does not claim it is empty", async ({ page }) => {
  await coldApi(page, (route) => route.fulfill({ json: STARTING, headers: { "cache-control": "no-store" } }));
  let release = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  // The API holds these until startup finishes.
  await page.route(/\/api\/v1\/(documents|stats)/, async (route) => { await held; await route.fallback().catch(() => {}); });
  await page.goto("/ask");
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "starting");
  await page.waitForTimeout(500); // long enough for a wrong empty state to render
  await expect(page.getByText("No study material yet")).toHaveCount(0);
  release();
});

test("a service that never comes up is reported as Offline", async ({ page }) => {
  await coldApi(page, (route) => route.fulfill({ status: 502, json: { error: { code: "upstream_unreachable", message: "Could not reach the API." } } }));
  await page.goto("/ask");
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "offline", { timeout: 10_000 });
  await expect(page.locator(".api-status-text")).toHaveText("Offline");
});
