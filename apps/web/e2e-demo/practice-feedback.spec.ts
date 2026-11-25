import { expect, test } from "@playwright/test";
import path from "node:path";

const PDF = path.join(import.meta.dirname, "../e2e/fixtures/graphs.pdf");
const REASONED = "Reasoned from the problem, not from your sources";
const REJECT_FIRST = " [e2e: reject first draft]"; // tests/fake_gemini.py FORCE_REJECTION

test("demo: LeetCode Try first shows reasoned verdicts through the proxy, with nothing refused", async ({ page }) => {
  const refused: string[] = [];
  page.on("response", (r) => { if (r.status() === 403) refused.push(new URL(r.url()).pathname); });
  await page.goto("/leetcode?q=two+sum&p=1");
  const detail = page.getByLabel("Problem detail");
  await detail.getByRole("button", { name: "Try first" }).click();
  await detail.getByRole("radio", { name: "Steps" }).check();
  await detail.getByLabel("Your attempt", { exact: true }).fill("Keep a hash map for the complement lookup.\nNever use a hash map for the complement lookup.");
  await detail.getByRole("button", { name: "Check my attempt" }).click();
  const rows = detail.getByRole("list", { name: "Your attempt, step by step" }).getByRole("listitem");
  await expect(rows.nth(0)).toHaveAttribute("data-verdict", "reasoned");
  await expect(rows.nth(1)).toHaveAttribute("data-verdict", "reasoned_wrong");
  await expect(rows.nth(0)).toContainText(REASONED);
  expect(refused).toEqual([]);
});

test("demo: a Similar example draft the guard rejects is retried through the proxy", async ({ page }) => {
  await page.route("**/api/backend/api/v1/practice/similar", async (route) => {
    const body = route.request().postDataJSON() as { question: string };
    await route.continue({ postData: JSON.stringify({ ...body, question: body.question + REJECT_FIRST }) });
  });
  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf", { timeout: 60_000 });
  await page.goto("/ask");
  await expect(page.getByLabel("Search in")).toHaveValue("mine");
  await page.getByLabel("Your question", { exact: true }).fill("How does breadth-first search explore a graph?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const tools = page.locator('[data-step="understanding"]');
  await expect(tools).toBeVisible({ timeout: 30_000 });
  await tools.locator("summary").filter({ hasText: "Similar example" }).click();
  const response = page.waitForResponse("**/api/backend/api/v1/practice/similar");
  await page.getByRole("button", { name: "Write a similar question" }).click();
  const reply = await response;
  expect(reply.status()).toBe(200);
  const text = await reply.text();
  expect(text).not.toContain("SCRIPTED-LEAKED-DRAFT");
  expect(text).not.toContain("SCRIPTED-HIDDEN-ANSWER");
  await expect(page.getByTestId("similar-question")).toContainText("Practice 1");
});
