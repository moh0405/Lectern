import { expect, test } from "@playwright/test";
import path from "node:path";

const PDF = path.join(import.meta.dirname, "../e2e/fixtures/graphs.pdf");
const QUESTION = "How does breadth-first search explore a graph?";

test("Understanding in the public demo: everything stays in the browser and uses the visitor's own passages", async ({ page }) => {
  const refused: string[] = [];
  const writes: string[] = [];
  page.on("response", (r) => r.status() === 403 && refused.push(new URL(r.url()).pathname));
  page.on("request", (r) => {
    const url = r.url();
    if (url.includes("/history") && r.method() !== "GET") writes.push(url);
    if (url.includes("/cards") && r.method() !== "GET") writes.push(url);
  });

  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf", { timeout: 60_000 });
  await page.goto("/ask");
  await expect(page.getByLabel("Search in")).toHaveValue("mine");
  await page.getByLabel("Your question", { exact: true }).fill(QUESTION);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const tools = page.locator('[data-step="understanding"]');
  await expect(tools).toBeVisible({ timeout: 30_000 });

  // Note and flashcard: browser storage only.
  await tools.locator("summary").filter({ hasText: "In your own words" }).click();
  await page.getByLabel("Your note").fill("BFS goes level by level.");
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(tools.getByText("In this browser.")).toBeVisible();
  await page.getByRole("button", { name: "Save note as flashcard" }).click();
  await expect(page.getByRole("button", { name: "Flashcard saved" })).toBeVisible();
  const cards = await page.evaluate(() => JSON.parse(localStorage.getItem("ai-study-mentor:cards:v1") ?? "[]"));
  expect(cards).toEqual([expect.objectContaining({ front: QUESTION, back: "BFS goes level by level." })]);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("asm.ask.turns.v1") ?? "[]")[0].note)).toBe("BFS goes level by level.");

  // Different explanation: from the visitor's passages, not the shared index.
  await tools.locator("summary").filter({ hasText: "Different explanation" }).click();
  const adaptive = page.waitForRequest("**/api/v1/adaptive");
  await page.getByRole("button", { name: "Explain it this way" }).click();
  const adaptiveBody = (await adaptive).postDataJSON() as { context: { doc: string }[] };
  expect(adaptiveBody.context.every((c) => c.doc === "graphs.pdf")).toBe(true);
  await expect(page.getByTestId("different-explanation")).toBeVisible();

  // Similar example through the proxy, answered through Try first against the same passages.
  await tools.locator("summary").filter({ hasText: "Similar example" }).click();
  const similar = page.waitForResponse("**/api/backend/api/v1/practice/similar");
  await page.getByRole("button", { name: "Write a similar question" }).click();
  const response = await similar;
  expect(response.status()).toBe(200);
  expect(await response.text()).not.toContain("SCRIPTED-HIDDEN-ANSWER");
  const practice = (await page.getByTestId("similar-question").textContent())!;
  await page.getByRole("button", { name: "Try this question" }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toHaveValue(practice);
  await page.getByLabel(/Your attempt/).fill("Breadth-first search explores a graph level by level.");
  const feedback = page.waitForRequest("**/api/v1/attempt/feedback");
  await page.getByRole("button", { name: "Check my attempt" }).click();
  const sent = (await feedback).postDataJSON() as { question: string; context: { doc: string }[] };
  expect(sent.question).toBe(practice);
  expect(sent.context.every((c) => c.doc === "graphs.pdf")).toBe(true);
  await expect(page.getByRole("list", { name: "Your attempt, sentence by sentence" })).toBeVisible();

  expect(refused).toEqual([]);
  expect(writes).toEqual([]);
});
