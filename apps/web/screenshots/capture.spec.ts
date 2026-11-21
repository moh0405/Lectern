import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve(import.meta.dirname, "../../../docs/images");
const FIXTURES = path.resolve(import.meta.dirname, "../e2e/fixtures");
const API = "http://127.0.0.1:8970";
const shot = (page: Page, name: string, opts: { fullPage?: boolean } = {}) =>
  page.screenshot({ path: path.join(OUT, `${name}.png`), ...opts });

async function indexFixture(request: APIRequestContext, name: string) {
  const res = await request.post(`${API}/api/v1/sources/files`, {
    multipart: { files: { name, mimeType: "application/pdf", buffer: fs.readFileSync(path.join(FIXTURES, name)) } },
  });
  const { job_id } = await res.json();
  await expect
    .poll(async () => (await (await request.get(`${API}/api/v1/jobs/${job_id}`)).json()).status, { timeout: 30_000 })
    .toBe("done");
}

async function ask(page: Page, question: string) {
  await page.getByLabel("Your question", { exact: true }).fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy answer" }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0, { timeout: 30_000 }); // the newest answer has finished
}

const DEMO = process.env.SCREENSHOT_SERVER === "demo";

test("capture the pages that need a larger library", async ({ page, request }) => {
  test.skip(!DEMO, "runs with SCREENSHOT_SERVER=demo");
  test.setTimeout(240_000);
  for (const question of [
    "How does a hash table handle collisions?",
    "What is the difference between BFS and DFS?",
    "What is a binary heap?",
    "Compare quicksort and merge sort",
    "How does a distributed file system replicate data?",
  ]) {
    await request.post(`${API}/api/v1/ask`, { data: { question, k: 3 } });
  }

  // Embedding map of the indexed passages, projected to 3D
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/visualize");
  const plot = page.getByTestId("scatter3d");
  await expect(plot).toHaveClass(/js-plotly-plot/, { timeout: 30_000 });
  await page.waitForTimeout(2500);
  await shot(page, "embedding-map");

  // Insights
  await page.goto("/analytics");
  await expect(page.getByText("Most used sources")).toBeVisible();
  await page.waitForTimeout(500);
  await shot(page, "analytics");
});

test("capture the app", async ({ page, request }) => {
  test.skip(DEMO, "runs without SCREENSHOT_SERVER=demo");
  test.setTimeout(240_000);
  await indexFixture(request, "heaps.pdf");
  await indexFixture(request, "graphs.pdf");

  // 1. Ask: a finished answer with citation chips and the source margin open
  await page.setViewportSize({ width: 1440, height: 1240 });
  await page.goto("/ask");
  await ask(page, "How does a binary heap implement a priority queue?");
  await expect(
    page.getByRole("complementary", { name: "Source margin" }).getByRole("region", { name: /Passage 1: heaps\.pdf/ }),
  ).toBeVisible();
  await page.waitForTimeout(600);
  await shot(page, "ask");

  // 2. Sources: what is indexed
  await page.setViewportSize({ width: 1440, height: 1180 });
  await page.goto("/sources");
  await expect(page.getByText("graphs.pdf").first()).toBeVisible();
  await page.waitForTimeout(500);
  await shot(page, "sources");

  // 3. Concept map
  await page.setViewportSize({ width: 1440, height: 940 });
  await page.goto("/concept-map");
  await page.getByLabel("Topic").fill("Binary heaps");
  await page.getByRole("button", { name: "Generate map" }).click();
  await expect(page.getByTestId("concept-graph").locator(".react-flow__node")).toHaveCount(8);
  await page.waitForTimeout(800);
  await shot(page, "concept-map");

  // 4. Work it out with one hint revealed
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/work-it-out");
  await page.getByLabel("What are you trying to work out?").fill("Why does heap insert take O(log n) time?");
  await page.getByRole("button", { name: "Guide me" }).click();
  await expect(page.getByText("what must be true of every parent")).toBeVisible();
  await page.getByRole("button", { name: /Show hint 1/ }).click();
  await page.waitForTimeout(300);
  await shot(page, "socratic");

  // 5. LeetCode: filter, open a problem, generate a study guide
  await page.setViewportSize({ width: 1440, height: 1180 });
  await page.goto("/leetcode?q=two+sum&d=Easy&p=1");
  await page.locator("summary", { hasText: "Your study plan" }).click(); // collapsed, so the problem and its guide fit
  const detail = page.getByLabel("Problem detail");
  await detail.getByRole("button", { name: "Study guide" }).click();
  await expect(page.getByRole("heading", { name: "Key observation" })).toBeVisible();
  await detail.evaluate((el) => window.scrollBy(0, el.getBoundingClientRect().top - 88));
  await page.waitForTimeout(500);
  await shot(page, "leetcode");

  // 7. Math
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/math");
  await page.getByRole("button", { name: "Use example: solve x^2 - 5x + 6 = 0" }).click(); // examples only fill the input
  await page.getByRole("button", { name: "Compute" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(1, { timeout: 30_000 }); // the first call starts the math worker
  await page.getByRole("button", { name: "Use example: integrate x^2 + 3x" }).click();
  await page.getByRole("button", { name: "Compute" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(2, { timeout: 30_000 });
  await expect(page.getByTestId("math-result").nth(1).locator(".katex")).toBeVisible();
  await page.waitForTimeout(400);
  await shot(page, "math");

  // 8. Flashcards: a due card with its answer shown
  await page.setViewportSize({ width: 1440, height: 1120 });
  await page.goto("/study");
  await page.getByLabel("Front (question)").fill("What does a min-heap guarantee about each parent?");
  await page.getByLabel("Back (answer)").fill("Every parent is smaller than or equal to its children.");
  await page.getByRole("button", { name: "Add card" }).click();
  await page.getByRole("button", { name: "Show answer" }).click();
  await expect(page.getByTestId("card-back")).toBeVisible();
  await page.waitForTimeout(400);
  await shot(page, "flashcards");

  // 10. Command palette
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/ask");
  await page.keyboard.press("Control+K");
  await page.getByPlaceholder(/Go to a page/).fill("practice");
  await expect(page.getByRole("dialog").getByRole("option", { name: "Flashcards" })).toBeVisible();
  await page.waitForTimeout(400);
  await shot(page, "command-palette");
  await page.keyboard.press("Escape");

  // 11. Phone layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ask");
  await ask(page, "What is the heap property?");
  // A viewport as tall as the page keeps the sticky bars at its edges; a full-page capture strands them mid-image.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: 390, height });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await shot(page, "mobile");
});
