import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(import.meta.dirname, "../../../docs/images");
const API = "http://127.0.0.1:8200";
const shot = (page: Page, name: string, opts: { fullPage?: boolean } = {}) =>
  page.screenshot({ path: path.join(OUT, `${name}.png`), ...opts });

async function ask(page: Page, question: string) {
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy answer" }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0, { timeout: 30_000 }); // the newest answer has finished
}

test("capture the app", async ({ page, request }) => {
  test.setTimeout(240_000);

  // seed the analytics page with a few real questions
  for (const question of [
    "How does a hash table handle collisions?",
    "What is the difference between BFS and DFS?",
    "What is a binary heap?",
    "Compare quicksort and merge sort",
    "How does a distributed file system replicate data?",
  ]) {
    await request.post(`${API}/api/v1/ask`, { data: { question, k: 3 } });
  }

  // 1. Ask: a streamed answer with checked citations and the passages behind it
  await page.setViewportSize({ width: 1440, height: 1240 });
  await page.goto("/ask");
  await ask(page, "How do hash tables deal with collisions?"); // different wording from the seeded questions: a live answer, not a cached one
  await page.getByText("Sources (").first().click();
  await page.waitForTimeout(600);
  await shot(page, "ask");
  await page.setViewportSize({ width: 1440, height: 900 });

  // 2. Sources: what is indexed
  await page.goto("/sources");
  await expect(page.getByText("hashing.md").first()).toBeVisible();
  await page.waitForTimeout(500);
  await shot(page, "sources");

  // 3. Tutor tools: concept map
  await page.goto("/tutor");
  await page.getByLabel("Topic").fill("Hash tables");
  await page.getByRole("button", { name: "Generate map" }).click();
  await expect(page.getByTestId("concept-graph").locator(".react-flow__node").first()).toBeVisible();
  await page.waitForTimeout(800);
  await shot(page, "concept-map");

  // 4. Socratic tutor with one hint revealed
  await page.goto("/tutor?tool=socratic");
  await page.getByLabel("What are you trying to work out?").fill("Why do hash tables need a collision strategy?");
  await page.getByRole("button", { name: "Guide me" }).click();
  await expect(page.getByText("What does a hash function turn a key into")).toBeVisible();
  await page.getByRole("button", { name: /Show hint 1/ }).click();
  await page.waitForTimeout(300);
  await shot(page, "socratic");

  // 5. Embedding map: the real MiniLM embeddings of the indexed passages, projected to 3D
  await page.goto("/visualize");
  await expect(page.getByTestId("scatter3d")).toHaveClass(/js-plotly-plot/, { timeout: 30_000 });
  await page.waitForTimeout(2500);
  await shot(page, "embedding-map");

  // 6. LeetCode: filter, open a problem, generate a study guide
  await page.goto("/leetcode?q=two+sum&d=Easy&p=1");
  await page.getByLabel("Problem detail").getByRole("button", { name: "Study guide" }).click();
  await expect(page.getByRole("heading", { name: "Key observation" })).toBeVisible();
  await page.waitForTimeout(500);
  await shot(page, "leetcode");

  // 7. Math
  await page.goto("/math");
  await page.getByRole("button", { name: "solve x^2 - 5x + 6 = 0" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(1, { timeout: 30_000 }); // the first call starts the math worker
  await page.getByRole("button", { name: "integrate x^2 + 3x" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(2, { timeout: 30_000 });
  await expect(page.getByTestId("math-result").nth(1).locator(".katex")).toBeVisible();
  await page.waitForTimeout(400);
  await shot(page, "math");

  // 7b. Flashcards: a due card with its answer shown
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/study");
  await page.getByLabel("Front (question)").fill("What does a hash table trade for O(1) average lookup?");
  await page.getByLabel("Back (answer)").fill("Extra memory and unordered keys; worst case is O(n) when many keys collide.");
  await page.getByRole("button", { name: "Add card" }).click();
  await page.getByRole("button", { name: "Show answer" }).click();
  await expect(page.getByTestId("card-back")).toBeVisible();
  await page.waitForTimeout(400);
  await shot(page, "flashcards");

  // 8. Analytics
  await page.goto("/analytics");
  await expect(page.getByText("Most used sources")).toBeVisible();
  await page.waitForTimeout(500);
  await shot(page, "analytics");

  // 9. Command palette
  await page.goto("/ask");
  await page.keyboard.press("Control+K");
  await page.getByPlaceholder(/Go to a page/).fill("t");
  await page.waitForTimeout(400);
  await shot(page, "command-palette");

  // 10. Phone layout
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ask");
  await ask(page, "What is the heap property?");
  await page.waitForTimeout(500);
  await shot(page, "mobile", { fullPage: true });
});
