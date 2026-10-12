import { expect, test } from "@playwright/test";
import path from "node:path";

const PDF = path.join(import.meta.dirname, "fixtures", "heaps.pdf");

test.describe.configure({ mode: "serial" });

test("shows the empty state before anything is indexed", async ({ page }) => {
  await page.goto("/ask");
  await expect(page.getByRole("heading", { name: "No study material yet" }).or(page.getByText("No study material yet"))).toBeVisible();
  await expect(page.getByRole("link", { name: /Add a PDF/ })).toHaveAttribute("href", "/sources");
});

test("upload a PDF, ask a question, get a streamed answer with a citation", async ({ page }) => {
  // 1) upload and wait for the background indexing job
  await page.goto("/sources");
  await page.getByLabel("Upload files").setInputFiles(PDF);
  const job = page.getByTestId("job-card");
  await expect(job).toContainText("heaps.pdf");
  await expect(job).toContainText("done", { timeout: 30_000 });
  await expect(job).toContainText(/chunks? added/);
  await expect(page.getByRole("list").getByText("heaps.pdf")).toBeVisible();

  // 2) ask about it
  await page.goto("/ask");
  await page.getByLabel("Your question").fill("What is a binary heap used for?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();

  const answer = page.locator(".md-body").first();
  await expect(answer).toContainText("From your material", { timeout: 20_000 });
  await expect(answer).toContainText("[heaps.pdf (page 1)]");

  // 3) the retrieved passage is listed as a source, with the query term highlighted
  const summary = page.getByText("Sources (").first();
  await expect(summary).toBeVisible();
  await expect(page.getByText("[1] heaps.pdf · p.1")).toBeVisible(); // citation chip visible without expanding
  await summary.click(); // expand the passages
  const source = page.getByRole("article").first();
  await expect(source).toContainText("heaps.pdf · page 1");
  await expect(source.locator("mark").first()).toHaveText(/binary|heap|used/i);
  expect(await source.locator("mark").count()).toBeGreaterThanOrEqual(2);

  // 4) the finished session survives a reload, and can be cleared
  const heading = page.getByRole("heading", { name: "What is a binary heap used for?" });
  await page.reload();
  await expect(heading).toBeVisible();
  await expect(page.locator(".md-body").first()).toContainText("[heaps.pdf (page 1)]");
  await page.getByRole("button", { name: /Clear session/ }).click();
  await expect(heading).toHaveCount(0);
});

test("advanced options: pick a model, see the prompt, skip the model, export flashcards and notes", async ({ page }) => {
  await page.goto("/ask");
  await page.getByText("Advanced").click();

  // model list comes from the API (scripted here)
  const model = page.getByLabel("Model", { exact: true });
  await expect(model.locator("option", { hasText: "gemini-3.7-flash" })).toHaveCount(1);
  await model.selectOption("gemini-3.7-flash");

  await page.getByLabel("Show the prompt sent to the model").check();
  await page.getByLabel("Your question").fill("What is a priority queue?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const first = page.locator(".md-body").first();
  await expect(first).toContainText("From your material", { timeout: 20_000 });
  await expect(page.locator("span:text-is('gemini-3.7-flash')")).toBeVisible(); // the model badge on the answer
  await page.locator("summary", { hasText: "Prompt sent to the model" }).click();
  await expect(page.locator("pre").first()).toContainText("What is a priority queue?");

  // retrieval only: passages, no model call, no answer text
  await page.getByLabel("Only show matching passages (skip the model)").check();
  await page.getByLabel("Your question").fill("binary heap complete tree");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const retrievalTurn = page.getByRole("heading", { name: "binary heap complete tree" }).locator("xpath=ancestor::div[contains(@class,'space-y-4')][1]");
  await expect(retrievalTurn.getByText("Sources (1)")).toBeVisible();
  await expect(retrievalTurn.locator(".md-body")).toHaveCount(0);

  // exports
  const cards = page.waitForEvent("download");
  await page.getByRole("button", { name: "Flashcards (CSV)" }).click();
  expect((await cards).suggestedFilename()).toBe("flashcards.csv");
  await page.getByRole("button", { name: /Generate from this session/ }).click();
  const md = page.waitForEvent("download");
  await page.getByRole("button", { name: "MD", exact: true }).click();
  expect((await md).suggestedFilename()).toBe("study-notes.md");
});

test("a source can be deleted (with confirmation)", async ({ page }) => {
  await page.goto("/sources");
  await page.getByRole("button", { name: "Delete heaps.pdf" }).click();
  await page.getByRole("button", { name: "Confirm delete" }).click();
  await expect(page.getByText("Nothing indexed yet")).toBeVisible();
});
