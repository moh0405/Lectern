import { expect, test } from "@playwright/test";
import path from "node:path";

// Opt-in: downloads the real MiniLM model (about 25 MB) from the Hugging Face CDN.
//   E2E_REAL_EMBEDDINGS=1 npx playwright test -c playwright.demo.config.ts real-embeddings
test.skip(!process.env.E2E_REAL_EMBEDDINGS, "needs network access to download the model");

const PDF = path.join(import.meta.dirname, "../e2e/fixtures/graphs.pdf");

test("meaning search runs in the browser with the real model", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  const list = page.getByRole("list", { name: "Your documents" });
  await expect(list).toContainText("graphs.pdf", { timeout: 200_000 });
  await expect(list).toContainText("meaning + keyword search"); // the model loaded and every passage has a vector

  await page.goto("/ask");
  // No word in common with the passage text, so only the vectors can connect them
  await page.getByLabel("Your question").fill("ways of storing connections between nodes");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/graphs\.pdf · pp?\.\d/).first()).toBeVisible({ timeout: 60_000 });
});

test("when the model cannot be downloaded, the document still works with keyword search and says so", async ({ page }) => {
  test.setTimeout(120_000);
  await page.route(/huggingface\.co|hf\.co|jsdelivr/, (route) => route.abort());
  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  const list = page.getByRole("list", { name: "Your documents" });
  await expect(list).toContainText("graphs.pdf", { timeout: 100_000 });
  await expect(list).toContainText("keyword search");
  await expect(list).not.toContainText("meaning + keyword search");
  await expect(page.getByText(/could not be downloaded/)).toBeVisible();

  await page.goto("/ask");
  await page.getByLabel("Your question").fill("How are graphs represented?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText(/graphs\.pdf · pp?\.\d/).first()).toBeVisible({ timeout: 30_000 }); // keyword search still finds it
});
