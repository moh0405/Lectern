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
  await expect(page.getByRole("heading", { name: "Your documents (this browser)" })).toBeVisible();
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

  // 4) the passages are tagged as coming from this browser; saving a flashcard and writing notes stay in the browser too
  await expect(page.getByText("Sources (").first()).toContainText("In this browser");
  await page.getByRole("button", { name: "Save as flashcard" }).click();
  await expect(page.getByRole("button", { name: "Saved as flashcard" })).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByText("Saved to this browser").first()).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("ai-study-mentor:cards:v1"))).toContain("How are graphs represented?");
  await page.getByRole("button", { name: /Generate from this session/ }).click();
  const notes = page.waitForEvent("download");
  await page.getByRole("button", { name: "MD", exact: true }).click();
  expect((await notes).suggestedFilename()).toBe("study-notes.md");
  await expect(page.getByRole("button", { name: "PDF", exact: true })).toHaveCount(0); // server-only export

  // nothing was uploaded, and nothing was refused
  expect(uploads).toEqual([]);
  expect(refused).toEqual([]);

  // 5) with keyword search a question that matches nothing says so, instead of silently searching the shared textbooks
  //    (with meaning search on, the nearest passages are always returned, as on the server)
  if (!process.env.E2E_REAL_EMBEDDINGS) {
    await page.getByLabel("Your question").fill("zzzzqqqq xxyyzz");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText(/Nothing in your documents matches/)).toBeVisible();
    // a neutral notice, not an error, with a way to search the shared textbooks instead
    // (scoped to the page content: Next.js keeps its own route announcer, role=alert, outside it)
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Search the shared textbooks instead" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Add material", exact: true }).first()).toBeVisible();
  }
  expect(refused).toEqual([]);

  // 6) removing the document returns the page to the shared textbooks
  await page.goto("/sources");
  await page.getByRole("button", { name: "Remove graphs.pdf" }).click();
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf");
  await page.getByRole("group", { name: "Remove graphs.pdf?", exact: true }).getByRole("button", { name: "Confirm remove" }).click();
  await expect(page.getByRole("list", { name: "Your documents" })).toHaveCount(0);
});

test("Guided hints use selected browser passages, then reveal evidence in the same turn", async ({ page }) => {
  const calls: { route: string; body: { context?: { doc: string; text: string }[] } }[] = [];
  const uploads: string[] = [];
  page.on("request", request => {
    if (request.method() !== "POST") return;
    if (request.url().includes("/sources/")) uploads.push(request.url());
    if (/\/(socratic|ask\/stream)$/.test(request.url())) calls.push({ route: request.url(), body: request.postDataJSON() });
  });
  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf", { timeout: 60_000 });
  await page.goto("/ask");
  await expect(page.getByLabel("Search in")).toHaveValue("mine");
  await page.getByRole("radio", { name: "Guided", exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill("How are graphs represented?");
  const response = page.waitForResponse(r => r.url().endsWith("/socratic"));
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const body = await (await response).json();
  expect(body.chunks.length).toBeGreaterThan(0);
  expect(body.chunks.every((c: { doc: string }) => c.doc === "graphs.pdf")).toBe(true);
  await expect(page.getByText("h1", { exact: true })).toBeVisible();
  expect(calls).toHaveLength(1);
  expect(calls[0]!.body.context?.every(c => c.doc === "graphs.pdf" && c.text.length > 0)).toBe(true);
  await page.getByRole("button", { name: "Next hint" }).click();
  expect(calls).toHaveLength(1);
  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  expect(calls).toHaveLength(2);
  expect(calls[1]!.body.context).toEqual(calls[0]!.body.context);
  await expect(page.getByText("Sources (").first()).toContainText("In this browser");
  expect(uploads).toEqual([]);
});

test("an answer citing a browser document in prose parentheses shows chips and counts as cited", async ({ page }) => {
  // Live evaluation, defect 1: "A binary heap is used to implement a priority queue (heaps.pdf, page 1)." on a
  // browser-stored document showed no chips and "Not found in your material".
  await page.goto("/sources");
  await page.getByLabel("Add my documents").setInputFiles(PDF);
  await expect(page.getByRole("list", { name: "Your documents" })).toContainText("graphs.pdf", { timeout: 60_000 });
  await page.goto("/ask");
  await expect(page.getByLabel("Search in")).toHaveValue("mine");
  await page.getByLabel("Your question", { exact: true }).fill("How are graphs represented? Answer in prose");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const answer = page.locator(".md-body").first();
  await expect(answer).toContainText("From your material", { timeout: 30_000 });
  const chips = answer.getByRole("button", { name: /^Citation graphs\.pdf/ });
  await expect(chips).toHaveCount(2);
  await expect(chips.first()).toHaveText("01");
  await expect(answer).not.toContainText("graphs.pdf");
  await expect(answer).not.toContainText(/\(\s*01/);
  await expect(page.getByText("does not cite any of the sources")).toHaveCount(0);
  await expect(page.getByText("Not found in your material")).toHaveCount(0);
  await expect(page.getByText("2 citations checked against your material")).toBeVisible();
  await answer.screenshot({ path: test.info().outputPath("prose-citations-demo.png") });
});
