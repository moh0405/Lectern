import { expect, test } from "./test";
import { indexFixture, removeFixture } from "./helpers";

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ request }) => indexFixture(request));
test.afterEach(async ({ request }) => removeFixture(request));

test("the agent chooses a tool, you see the call and its result, then a cited answer", async ({ page }) => {
  await page.goto("/agent");
  await page.getByLabel("Task").fill("What is a binary heap used for?");
  await page.getByRole("button", { name: "Run agent" }).click();

  const step = page.getByTestId("tool-step").first();
  await expect(step).toContainText("search_documents", { timeout: 30_000 });
  await expect(step).toContainText("binary heap"); // the arguments the model chose
  await expect(step).toContainText(/passages from heaps\.pdf/); // what the tool returned

  const answer = page.getByRole("region", { name: "Answer" });
  await expect(answer).toContainText("From your material", { timeout: 30_000 });
  await expect(answer).toContainText("[heaps.pdf (page 1)]");
  await expect(page.getByTestId("run-cost")).toContainText("1 tool call · 2 model calls");
  await page.getByText(/Passages the tools returned/).click();
  await expect(page.getByText(/heaps\.pdf · p\.1/)).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0); // no citation warning
});

test("it is in the navigation and the example prompts run the agent", async ({ page }) => {
  await page.goto("/ask");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Agent" }).click();
  await expect(page).toHaveURL(/\/agent$/);
  await page.getByRole("button", { name: /Explain how hash tables handle collisions/ }).click();
  await expect(page.getByTestId("tool-step").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("region", { name: "Answer" })).toBeVisible({ timeout: 30_000 });
});

test("the task needs a few characters before it can run", async ({ page }) => {
  await page.goto("/agent");
  await expect(page.getByRole("button", { name: "Run agent" })).toBeDisabled();
  await page.getByLabel("Task").fill("hi");
  await expect(page.getByRole("button", { name: "Run agent" })).toBeDisabled();
  await page.getByLabel("Task").fill("what is a heap");
  await expect(page.getByRole("button", { name: "Run agent" })).toBeEnabled();
});
