import { expect, test } from "./test";
import { indexFixture, removeFixture } from "./helpers";

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ request }) => indexFixture(request));
test.afterEach(async ({ request }) => removeFixture(request));

test("agentic mode shows what the workflow did and answers from the passages it found", async ({ page }) => {
  await page.goto("/ask");
  await page.locator('summary[aria-label="Advanced"]').click();
  await page.getByRole("checkbox", { name: /Agentic mode/ }).check();
  await page.getByLabel("Your question").fill("What is a binary heap used for?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  const answer = page.locator(".md-body").first();
  await expect(answer).toContainText("From your material", { timeout: 30_000 });
  await expect(answer).toContainText("[heaps.pdf (page 1)]");
  await expect(page.getByText("agentic", { exact: true })).toBeVisible();

  const how = page.getByLabel("How it answered");
  await how.locator("summary").click(); // collapsed once finished
  await expect(how).toContainText(/How it answered \(5 steps, 3 model calls\)/);
  for (const step of ["rewrite", "retrieve", "grade", "answer", "verify"]) await expect(how.getByText(step, { exact: true })).toBeVisible();
  await expect(how).toContainText("Searching for: binary heap priority queue data structure");
  await expect(how).toContainText("Every citation is in the retrieved passages");
  await expect(page.getByText("[1] heaps.pdf · p.1")).toBeVisible();
});

test("an answer that invents a source is rewritten, and the result is clean", async ({ page }) => {
  await page.goto("/ask");
  await page.locator('summary[aria-label="Advanced"]').click();
  await page.getByRole("checkbox", { name: /Agentic mode/ }).check();
  await page.getByLabel("Your question").fill("Please hallucinate about binary heaps");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  const answer = page.locator(".md-body").first();
  await expect(answer).toContainText("[heaps.pdf (page 1)]", { timeout: 30_000 });
  await expect(page.getByText(/cited sources it was not given, so it was rewritten/)).toBeAttached();
  await expect(answer).not.toContainText("Invented Notes.pdf");
  await expect(page.getByRole("status").filter({ hasText: "cites something it was not given" })).toHaveCount(0); // no warning: the final answer is clean
  const how = page.getByLabel("How it answered");
  await how.locator("summary").click();
  await expect(how.getByText("regenerate", { exact: true })).toBeVisible();
  await expect(how).toContainText(/4 model calls/);
});

test("plain questions are unaffected, and the toggle is off by default", async ({ page }) => {
  await page.goto("/ask");
  await page.locator('summary[aria-label="Advanced"]').click();
  await expect(page.getByRole("checkbox", { name: /Agentic mode/ })).not.toBeChecked();
  await page.locator('summary[aria-label="Advanced"]').click();
  await page.getByLabel("Your question").fill("What is a binary heap used for?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".md-body").first()).toContainText("From your material", { timeout: 30_000 });
  await expect(page.getByLabel("How it answered")).toHaveCount(0);
  await expect(page.getByText("agentic", { exact: true })).toHaveCount(0);
});
