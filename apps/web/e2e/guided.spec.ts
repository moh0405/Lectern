import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { test, expect } from "./test";
import { indexFixture } from "./helpers";

const SHOTS = process.env.GUIDED_SCREENSHOTS ?? "test-results/guided";
async function submit(page: Page) {
  await page.getByRole("radio", { name: "Guided", exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill("Why use a binary heap?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}
async function audit(page: Page, name?: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze()).violations).toEqual([]);
  if (name) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}

test.beforeAll(async ({ request }) => { await indexFixture(request); });

test("Answer is default and sends the unchanged answer request", async ({ page }) => {
  let hints = 0;
  page.on("request", r => { if (r.url().endsWith("/socratic")) hints++; });
  await page.goto("/ask");
  await expect(page.getByRole("radio", { name: "Answer", exact: true })).toBeChecked();
  await page.getByLabel("Your question", { exact: true }).fill("Why use a heap?");
  const request = page.waitForRequest("**/api/v1/ask/stream");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  expect((await request).postDataJSON()).toEqual({ question: "Why use a heap?", k: 3, temperature: 0.2 });
  expect(hints).toBe(0);
});

for (const last of [false, true]) test(`hints are fetched once, evidence at ${last ? "last" : "first"} hint stays in the turn`, async ({ page }) => {
  let hints = 0, asks = 0;
  page.on("request", r => { if (r.url().endsWith("/socratic")) hints++; if (r.url().includes("/ask/stream")) asks++; });
  await page.goto("/ask");
  expect(hints + asks).toBe(0);
  await submit(page);
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await expect(page.getByText("h2", { exact: true })).toHaveCount(0);
  await expect(page.getByText("h3", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Copy answer" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toHaveCount(0);
  expect([hints, asks]).toEqual([1, 0]);
  if (last) {
    await page.getByRole("button", { name: "Next hint" }).click();
    await expect(page.getByText("h2", { exact: true })).toBeFocused();
    await expect(page.getByText("h3", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Next hint" }).click();
    await expect(page.getByText("Hint 3 of 3")).toBeVisible();
    await expect(page.getByRole("button", { name: "Next hint" })).toHaveCount(0);
  }
  expect([hints, asks]).toEqual([1, 0]);
  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await page.locator(".cite-chip").first().click();
  await expect(page.getByRole("complementary", { name: /Source/ })).toContainText("heaps.pdf");
  expect([hints, asks]).toEqual([1, 1]);
  await page.reload();
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toHaveCount(0);
  expect([hints, asks]).toEqual([1, 1]);
});

for (const status of [500, 429]) test(`Socratic ${status} offers retry and evidence`, async ({ page }) => {
  let count = 0;
  await page.route("**/api/v1/socratic", route => ++count === 1 ? route.fulfill({ status, body: status === 429 ? "Too Many Requests" : "Internal Server Error" }) : route.continue());
  await page.goto("/ask");
  await submit(page);
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toBeVisible();
  if (status === 429) await expect(page.getByText(/The study service is busy/)).toBeVisible();
  await audit(page, `error-${status}`);
  await page.getByRole("button", { name: "Try this question again" }).click();
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  expect(count).toBe(2);
  await expect(page.getByRole("list", { name: "This session" }).getByRole("button")).toHaveCount(1);
});

for (const evidence of [false, true]) test(`cancel pending hints ${evidence ? "by revealing evidence" : "then retry"}`, async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/socratic", async route => { await gate; await route.fulfill({ json: { hints: ["late hint"], questions: [] } }).catch(() => {}); });
  await page.goto("/ask");
  await submit(page);
  await expect(page.getByText("Preparing your hints…")).toBeVisible();
  await audit(page, "loading");
  if (evidence) {
    await page.getByRole("button", { name: "Show me the evidence" }).click();
    await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  } else {
    await page.getByRole("button", { name: "Stop", exact: true }).click();
    await expect(page.getByRole("button", { name: "Try this question again" })).toBeVisible();
    await audit(page, "cancelled");
  }
  release();
  await expect(page.getByText("late hint", { exact: true })).toHaveCount(0);
});

for (const hints of [[], ["Only one hint"]]) test(`handles ${hints.length} hints and reopens without fetching`, async ({ page }) => {
  let count = 0;
  await page.route("**/api/v1/socratic", route => { count++; return route.fulfill({ json: { questions: [], hints } }); });
  await page.goto("/ask");
  await submit(page);
  await expect(page.getByText(hints.length ? "Only one hint" : "No hints were returned. You can still explore the evidence.", { exact: true })).toBeVisible();
  await audit(page, `hints-${hints.length}`);
  await page.reload();
  await expect(page.getByRole("button", { name: "Next hint" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toBeVisible();
  expect(count).toBe(1);
});

test("keyboard flow and follow-up after an unrevealed Guided turn", async ({ page }) => {
  await page.goto("/ask");
  await page.getByRole("radio", { name: "Answer", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Guided", exact: true })).toBeChecked();
  await page.keyboard.press("Tab");
  await page.keyboard.type("Why use a binary heap?");
  await page.keyboard.press("Control+Enter");
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next hint" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("h2", { exact: true })).toBeFocused();
  await page.getByRole("radio", { name: "Guided", exact: true }).focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("Tab");
  await page.keyboard.type("How does a priority queue work?");
  await page.keyboard.press("Control+Enter");
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  await expect(page.getByRole("list", { name: "This session" }).getByRole("button")).toHaveCount(2);
  await page.getByRole("button", { name: "Why use a binary heap?", exact: true }).click();
  await expect(page.getByText("h2", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toBeVisible();
});

for (const theme of ["dark", "light"]) for (const width of [1440, 768, 390, 320]) test(`${theme} ${width}: all Guided states fit and pass axe`, async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width, height: 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/ask");
  const toggle = page.getByRole("button", { name: `Switch to ${theme} theme`, exact: true });
  if (await toggle.isVisible()) await toggle.click();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let attempts = 0;
  await page.route("**/api/v1/socratic", async route => {
    attempts++;
    if (attempts === 1) { await gate; await route.fulfill({ json: { hints: [], questions: [] } }).catch(() => {}); }
    else if (attempts === 2) await route.fulfill({ status: 429, body: "Too Many Requests" });
    else await route.continue();
  });
  await submit(page);
  await expect(page.getByText("Preparing your hints…")).toBeVisible();
  await audit(page, `${theme}-${width}-loading`);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(page.getByRole("button", { name: "Try this question again" })).toBeVisible();
  release();
  await audit(page, `${theme}-${width}-cancelled`);
  await page.getByRole("button", { name: "Try this question again" }).click();
  await expect(page.getByText(/The study service is busy/)).toBeVisible();
  await audit(page, `${theme}-${width}-error`);
  await page.getByRole("button", { name: "Try this question again" }).click();
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  for (let i = 1; i <= 3; i++) {
    await audit(page, `${theme}-${width}-hint-${i}`);
    if (i < 3) await page.getByRole("button", { name: "Next hint" }).click();
  }
  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  await audit(page, `${theme}-${width}-evidence`);
});

test("failed hints can go directly to evidence without retrying hints", async ({ page }) => {
  let hints = 0, answers = 0;
  await page.route("**/api/v1/socratic", route => { hints++; return route.fulfill({ status: 500, body: "Internal Server Error" }); });
  page.on("request", r => { if (r.url().includes("/ask/stream")) answers++; });
  await page.goto("/ask");
  await submit(page);
  await expect(page.getByRole("button", { name: "Try this question again" })).toBeVisible();
  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  expect([hints, answers]).toEqual([1, 1]);
});

test("evidence keeps the submitted retrieval settings and guards repeated activation", async ({ page }) => {
  await page.goto("/ask");
  await page.getByText("Advanced", { exact: true }).click();
  await page.getByLabel("Passages", { exact: true }).selectOption("2");
  await page.getByText("Advanced", { exact: true }).click();
  const hints = page.waitForRequest("**/api/v1/socratic");
  await submit(page);
  expect((await hints).postDataJSON().k).toBe(2);
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await page.getByText("Advanced", { exact: true }).click();
  await page.getByLabel("Passages", { exact: true }).selectOption("6");
  await page.getByText("Advanced", { exact: true }).click();
  let count = 0;
  page.on("request", r => { if (r.url().includes("/ask/stream")) count++; });
  const answer = page.waitForRequest("**/api/v1/ask/stream");
  await page.getByRole("button", { name: "Show me the evidence" }).evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
  expect((await answer).postDataJSON().k).toBe(2);
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  expect(count).toBe(1);
});

test("evidence capacity failures reuse answer retry and leave hints readable", async ({ page }) => {
  let count = 0, hints = 0;
  page.on("request", r => { if (r.url().endsWith("/socratic")) hints++; });
  await page.route("**/api/v1/ask/stream", route => ++count === 1 ? route.fulfill({ status: 429, body: "Too Many Requests" }) : route.continue());
  await page.goto("/ask");
  await submit(page);
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByText(/The study service is busy/)).toBeVisible();
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toHaveCount(0);
  await page.getByRole("button", { name: "Try this question again" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  expect([hints, count]).toEqual([1, 2]); // normal answer retry creates a new turn
});
