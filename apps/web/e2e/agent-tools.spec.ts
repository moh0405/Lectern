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
  await expect(step).toContainText(/Searched your material for “.*binary heap.*”/, { timeout: 30_000 }); // in words, with the arguments the model chose
  await expect(step).toContainText(/\d+ passages? from heaps\.pdf/); // what the tool returned
  await step.getByText("Details").click();
  await expect(step).toContainText("search_documents"); // the raw call stays available

  const answer = page.getByRole("region", { name: "Answer" });
  await expect(answer).toContainText("From your material", { timeout: 30_000 });
  await expect(answer).toContainText("[heaps.pdf (page 1)]");
  await expect(page.getByTestId("run-cost")).toContainText("1 tool call · 2 model calls");
  const passages = page.getByTestId("agent-passages");
  await expect(passages.getByRole("heading", { name: /Passages the tools returned/ })).toBeVisible();
  await expect(passages.getByTestId("passage").first()).toContainText("heaps.pdf · page 1");
  await expect(page.getByRole("status").filter({ hasText: /This answer cites .* the tools never returned/ })).toHaveCount(0); // no citation warning
});

test("it is in the navigation and an example prompt fills the task", async ({ page }) => {
  await page.goto("/ask");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Tools" }).click();
  await page.getByRole("navigation", { name: "Tools pages" }).getByRole("link", { name: "Agent" }).click();
  await expect(page).toHaveURL(/\/agent$/);
  await page.getByRole("button", { name: /Use example: Explain how hash tables handle collisions/ }).click();
  // an example only fills the task (running costs model calls) and moves focus to Run agent
  await expect(page.getByLabel("Task")).toHaveValue(/Explain how hash tables handle collisions/);
  await expect(page.getByTestId("tool-step")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Run agent" })).toBeFocused();
  await page.keyboard.press("Enter");
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

test("when the model runs out of quota part-way, the next model finishes and both are named", async ({ page }) => {
  // Live, 2026-11-22: turn 2 got a 429 and the run ended with an error. The scripted model's "busy model" trigger
  // switches models after the first turn, as GeminiToolChat now does (tests/test_tool_chat.py covers the real move).
  await page.goto("/agent");
  await page.getByLabel("Task").fill("What is a binary heap used for? (busy model)");
  await page.getByRole("button", { name: "Run agent" }).click();

  await expect(page.getByTestId("tool-step").first()).toContainText(/passages? from heaps\.pdf/, { timeout: 30_000 });
  await expect(page.getByText(/was unavailable \(busy or out of quota\), so gemini-3\.1-flash-lite continued with the tool results gathered so far/)).toBeVisible();
  const answer = page.getByRole("region", { name: "Answer" });
  await expect(answer).toContainText("[heaps.pdf (page 1)]", { timeout: 30_000 });
  await expect(page.getByTestId("run-cost")).toContainText("1 tool call · 2 model calls · fake-model → gemini-3.1-flash-lite");
  await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveCount(0); // no error (Next's route announcer is an empty alert)
});

test("a valid citation written without parentheses is not reported as unverified", async ({ page }) => {
  // Live, 2026-11-22: a flash-lite run reported its citations as unverified. "[doc page N]" was read as an unknown source.
  await page.goto("/agent");
  await page.getByLabel("Task").fill("What is a binary heap used for? (bare page)");
  await page.getByRole("button", { name: "Run agent" }).click();
  const answer = page.getByRole("region", { name: "Answer" });
  await expect(answer).toContainText("[heaps.pdf page 1]", { timeout: 30_000 });
  await expect(page.getByTestId("run-cost")).toContainText("1 tool call");
  await expect(page.getByRole("status").filter({ hasText: /This answer cites .* the tools never returned/ })).toHaveCount(0);
});
