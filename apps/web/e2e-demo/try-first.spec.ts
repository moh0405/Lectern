import { expect, test } from "@playwright/test";
import path from "node:path";

const PDF = path.join(import.meta.dirname, "../e2e/fixtures/graphs.pdf");

test("Try first in the public demo: feedback through the proxy, judged only against the visitor's browser documents", async ({ page }) => {
  const refused: string[] = [];
  page.on("response", (r) => r.status() === 403 && refused.push(new URL(r.url()).pathname));
  let body: { context?: { doc: string }[]; attempt?: string; format?: string } | null = null;
  let feedbackCalls = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/attempt/feedback")) {
      feedbackCalls++;
      body = r.postDataJSON();
    }
  });

  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf", { timeout: 60_000 });
  await page.goto("/ask");
  await expect(page.getByLabel("Search in")).toHaveValue("mine");

  await page.getByRole("radio", { name: "Try first", exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill("How does breadth-first search explore a graph?");
  const attempt = "Breadth-first search explores a graph level by level.\nBreadth-first search never uses a queue.";
  await page.getByLabel(/Your attempt/).fill(attempt);
  const response = page.waitForResponse("**/api/backend/api/v1/attempt/feedback");
  await page.getByRole("button", { name: "Check my attempt" }).click();
  expect((await response).status()).toBe(200);

  expect(feedbackCalls).toBe(1);
  expect(body!.attempt).toBe(attempt);
  expect(body!.context!.length).toBeGreaterThan(0);
  expect(body!.context!.every((c) => c.doc === "graphs.pdf")).toBe(true);

  const rows = page.getByRole("list", { name: "Your attempt, step by step" }).getByRole("listitem");
  await expect(rows.nth(0)).toHaveAttribute("data-verdict", "supported");
  await expect(rows.nth(1)).toHaveAttribute("data-verdict", "contradicted");
  await page.getByRole("button", { name: /^Step 2: Contradicted by your sources/ }).click();
  await expect(page.getByRole("complementary", { name: "Source margin" })).toContainText("graphs.pdf");

  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible({ timeout: 30_000 });
  expect(feedbackCalls).toBe(1);
  expect(refused).toEqual([]);
});
