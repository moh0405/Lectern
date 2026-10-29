import { expect, test } from "@playwright/test";
import path from "node:path";

const PDF = path.join(import.meta.dirname, "../e2e/fixtures/graphs.pdf");

test("add a PDF in the browser, ask about it, and only its passages go to the server", async ({ page }) => {
  const refused: string[] = [];
  page.on("response", (r) => r.status() === 403 && refused.push(new URL(r.url()).pathname));
  const uploads: string[] = [];
  page.on("request", (r) => r.method() === "POST" && r.url().includes("/sources/") && uploads.push(r.url()));
  let askBody: { context?: { doc: string; text: string }[]; question?: string } | null = null;
  page.on("request", (r) => {
    if (r.url().includes("/ask/stream")) askBody = r.postDataJSON();
  });

  // 1) the Sources page offers browser-side documents, not a server upload
  await page.goto("/sources");
  await expect(page.getByRole("heading", { name: "My documents" })).toBeVisible();
  await expect(page.getByLabel("Upload files")).toHaveCount(0);

  await page.getByLabel("Add my documents").setInputFiles(PDF);
  const list = page.getByRole("list", { name: "Your documents" });
  await expect(list).toContainText("graphs.pdf", { timeout: 60_000 });
  await expect(list).toContainText(/passages?/);

  // 2) it survives a reload (IndexedDB) and is the default place to search on the Ask page
  await page.reload();
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf");
  await page.goto("/ask");
  await expect(page.getByLabel("Search in")).toHaveValue("mine");

  // 3) ask: the answer streams, and the request carries only the passages found in the browser
  await page.getByLabel("Your question").fill("How are graphs represented?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".md-body").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/graphs\.pdf · pp?\.\d/).first()).toBeVisible();
  expect(askBody).not.toBeNull();
  expect(askBody!.context!.length).toBeGreaterThan(0);
  expect(askBody!.context!.every((c) => c.doc === "graphs.pdf")).toBe(true);

  // 4) nothing was uploaded, and nothing was refused
  expect(uploads).toEqual([]);
  expect(refused).toEqual([]);

  // 5) with keyword search a question that matches nothing says so, instead of silently searching the shared textbooks
  //    (with meaning search on, the nearest passages are always returned, as on the server)
  if (!process.env.E2E_REAL_EMBEDDINGS) {
    await page.getByLabel("Your question").fill("zzzzqqqq xxyyzz");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText(/Nothing in your documents matches/)).toBeVisible();
  }

  // 6) removing the document returns the page to the shared textbooks
  await page.goto("/sources");
  await page.getByRole("button", { name: "Remove graphs.pdf" }).click();
  await expect(page.getByRole("list", { name: "Your documents" })).toHaveCount(0);
});
