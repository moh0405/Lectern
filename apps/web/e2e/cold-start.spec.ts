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

/** Record every state the status light passes through, however briefly. */
async function recordStates(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __apiStates: string[] };
    w.__apiStates = [];
    new MutationObserver(() => {
      const state = document.querySelector(".api-status")?.getAttribute("data-state");
      if (state && w.__apiStates.at(-1) !== state) w.__apiStates.push(state);
    }).observe(document, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-state"] });
  });
  return () => page.evaluate(() => (window as unknown as { __apiStates: string[] }).__apiStates);
}

const UNAVAILABLE = { status: 503, json: { error: { code: "upstream_unavailable", message: "The API is starting." } } };

test("an API that answers 503 for 8 s stays Starting up, never Offline, and shows the index soon after it is back", async ({ page }) => {
  const problems = collectProblems(page);
  const states = await recordStates(page);
  const api = await coldApi(page, (route) => route.fulfill(UNAVAILABLE));
  await page.goto("/ask");
  const status = page.locator(".api-status");
  await expect(status).toHaveAttribute("data-state", "starting");
  await page.waitForTimeout(8_000);
  await expect(status).toHaveAttribute("data-state", "starting");
  api.ready();
  const back = Date.now();
  await expect(page.locator(".api-status-text")).toHaveText("3,867 passages indexed · meaning search", { timeout: 4_000 });
  expect(Date.now() - back).toBeLessThan(3_500);
  expect(await states()).not.toContain("offline");
  expect(api.calls()).toBeGreaterThanOrEqual(4); // quick re-checks, not one every 30 s
  expect(problems).toEqual([]);
});

test("a service that stays down past the cold-start window is reported as Offline, then recovers by itself", async ({ page }) => {
  await page.clock.install();
  const states = await recordStates(page);
  const api = await coldApi(page, (route) => route.fulfill(UNAVAILABLE));
  await page.goto("/ask");
  const status = page.locator(".api-status");
  await expect(status).toHaveAttribute("data-state", "starting");
  await page.clock.fastForward(30_000);
  await page.clock.fastForward(10_000);
  await expect(status).toHaveAttribute("data-state", "starting"); // 40 s in: still a plausible cold start
  await page.clock.fastForward(25_000);
  await expect(status).toHaveAttribute("data-state", "offline");
  await expect(page.locator(".api-status-text")).toHaveText("Offline");
  expect((await states()).filter((s) => s !== "checking")).toEqual(["starting", "offline"]);
  api.ready();
  await page.clock.fastForward(15_000); // it keeps checking after showing Offline
  await expect(status).toHaveAttribute("data-state", "online");
  await expect(page.locator(".api-status-text")).toHaveText("3,867 passages indexed · meaning search");
});

test("Offline recovers at once when the window regains focus", async ({ page }) => {
  await page.clock.install();
  const api = await coldApi(page, (route) => route.fulfill(UNAVAILABLE));
  await page.goto("/ask");
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "starting");
  await page.clock.fastForward(70_000);
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "offline");
  api.ready();
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page.locator(".api-status")).toHaveAttribute("data-state", "online");
});
