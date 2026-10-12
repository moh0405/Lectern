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

test("a source can be deleted (with confirmation)", async ({ page }) => {
  await page.goto("/sources");
  await page.getByRole("button", { name: "Delete heaps.pdf" }).click();
  await page.getByRole("button", { name: "Confirm delete" }).click();
  await expect(page.getByText("Nothing indexed yet")).toBeVisible();
});
