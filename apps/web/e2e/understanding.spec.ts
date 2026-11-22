import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { test, expect } from "./test";
import { API, indexFixture } from "./helpers";

/** The Understanding step end to end against the real API with the scripted model (tests/fake_gemini.py). */
const QUESTION = "Why is a binary heap fast?";
const SHOTS = process.env.UNDERSTANDING_SCREENSHOTS ?? "test-results/understanding";

function count(page: Page) {
  const n = { similar: 0, adaptive: 0, feedback: 0 };
  page.on("request", (r) => {
    if (r.url().endsWith("/practice/similar")) n.similar++;
    if (r.url().endsWith("/adaptive")) n.adaptive++;
    if (r.url().endsWith("/attempt/feedback")) n.feedback++;
  });
  return n;
}

const tools = (page: Page) => page.locator('[data-step="understanding"]');
const open = (page: Page, name: string) => tools(page).locator("summary").filter({ hasText: name }).click();

async function askQuestion(page: Page, approach: "Answer" | "Guided" | "Try first" = "Answer") {
  await page.getByRole("radio", { name: approach, exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill(QUESTION);
  if (approach === "Answer") await page.getByRole("button", { name: "Ask", exact: true }).click();
  if (approach === "Guided") await page.getByRole("button", { name: "Ask", exact: true }).click();
  if (approach === "Try first") {
    await page.getByLabel(/Your attempt/).fill("A binary heap is a complete binary tree.");
    await page.getByRole("button", { name: "Check my attempt" }).click();
  }
  if (approach !== "Answer") await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(tools(page)).toBeVisible();
}

async function audit(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
}

test.beforeAll(async ({ request }) => { await indexFixture(request); });

test("the whole loop: note, flashcard, similar question through Try first, different explanation", async ({ page, request }) => {
  const n = count(page);
  await page.goto("/ask");
  await askQuestion(page);
  await page.waitForTimeout(300);
  expect(n).toEqual({ similar: 0, adaptive: 0, feedback: 0 }); // nothing is prefetched

  await open(page, "In your own words");
  const note = page.getByLabel("Your note");
  await expect(note).not.toHaveValue(""); // seeded from the answer, with no model call
  const mine = `A heap stays shallow, so swaps are few ${Date.now()}.`;
  await note.fill(mine);
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(tools(page).getByText("In your history.")).toBeVisible();
  await expect.poll(async () => (await (await request.get(`${API}/api/v1/history`)).json()).turns[0].note).toBe(mine);

  await page.getByRole("button", { name: "Save note as flashcard" }).click();
  await expect(page.getByRole("button", { name: "Flashcard saved" })).toBeVisible();
  const cards = (await (await request.get(`${API}/api/v1/cards`)).json()).cards as { front: string; back: string }[];
  expect(cards.some((c) => c.front === QUESTION && c.back === mine)).toBe(true);

  await open(page, "Different explanation");
  await page.getByLabel("Level").selectOption("ELI5");
  await page.getByRole("button", { name: "Explain it this way" }).click();
  await expect(page.getByTestId("different-explanation")).toContainText("From the same passages");
  expect(n.adaptive).toBe(1);

  await open(page, "Similar example");
  const similarResponse = page.waitForResponse("**/api/v1/practice/similar");
  await page.getByRole("button", { name: "Write a similar question" }).click();
  const body = await (await similarResponse).text();
  expect(body).not.toContain("SCRIPTED-HIDDEN-ANSWER");
  const similar = page.getByTestId("similar-question");
  await expect(similar).toContainText("Practice 1");
  const practice = (await similar.textContent())!;
  await expect(page.getByText("SCRIPTED-HIDDEN-ANSWER")).toHaveCount(0);

  await page.getByRole("button", { name: "Try this question" }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toHaveValue(practice);
  const attempt = page.getByLabel(/Your attempt/);
  await expect(attempt).toBeFocused();
  await attempt.fill("A binary heap is a complete binary tree.");
  const feedback = page.waitForRequest("**/api/v1/attempt/feedback");
  await page.getByRole("button", { name: "Check my attempt" }).click();
  const sent = (await feedback).postDataJSON();
  expect(sent.question).toBe(practice);
  expect(sent.context.length).toBeGreaterThan(0); // the same passages, not a new search
  await expect(page.getByRole("list", { name: "Your attempt, sentence by sentence" })).toBeVisible();
  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(tools(page)).toBeVisible();
  expect(n).toEqual({ similar: 1, adaptive: 1, feedback: 1 });
});

test("a saved note, example and explanation survive a reload without refetching", async ({ page }) => {
  const n = count(page);
  await page.goto("/ask");
  await askQuestion(page);
  await open(page, "In your own words");
  await page.getByLabel("Your note").fill("Kept across a reload.");
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(tools(page).getByText("In your history.")).toBeVisible();
  await open(page, "Similar example");
  await page.getByRole("button", { name: "Write a similar question" }).click();
  await expect(page.getByTestId("similar-question")).toBeVisible();
  await page.reload();
  await expect(tools(page)).toBeVisible();
  await open(page, "In your own words");
  await expect(page.getByLabel("Your note")).toHaveValue("Kept across a reload.");
  await open(page, "Similar example");
  await expect(page.getByTestId("similar-question")).toBeVisible();
  expect(n.similar).toBe(1);
});

for (const approach of ["Guided", "Try first"] as const) test(`${approach}: Understanding appears only after the evidence`, async ({ page }) => {
  await page.goto("/ask");
  await page.getByRole("radio", { name: approach, exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill(QUESTION);
  if (approach === "Try first") {
    await page.getByLabel(/Your attempt/).fill("A binary heap is a complete binary tree.");
    await page.getByRole("button", { name: "Check my attempt" }).click();
  } else await page.getByRole("button", { name: "Ask", exact: true }).click();
  const evidence = page.getByRole("button", { name: "Show me the evidence" });
  await expect(evidence).toBeVisible();
  await expect(tools(page)).toHaveCount(0); // no seed can reveal the answer early
  await evidence.click();
  await expect(tools(page)).toBeVisible();
  await open(page, "In your own words");
  await expect(page.getByLabel("Your note")).not.toHaveValue("");
});

test("a failed similar question can be retried", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/v1/practice/similar", (route) => (++calls === 1 ? route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ error: { code: "llm_error", message: "Lectern could not write a practice question from these passages. Try again." } }) }) : route.continue()));
  await page.goto("/ask");
  await askQuestion(page);
  await open(page, "Similar example");
  await page.getByRole("button", { name: "Write a similar question" }).click();
  await expect(tools(page).getByText(/could not write a practice question/)).toBeVisible();
  await page.getByRole("button", { name: "Write a similar question" }).click();
  await expect(page.getByTestId("similar-question")).toBeVisible();
});

test("keyboard: the tools open and work without a pointer", async ({ page }) => {
  await page.goto("/ask");
  await askQuestion(page);
  const summary = tools(page).locator("summary").filter({ hasText: "In your own words" });
  await summary.focus();
  await page.keyboard.press("Enter");
  const note = page.getByLabel("Your note");
  await expect(note).toBeVisible();
  await note.focus();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Save note", exact: true })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Note saved" })).toBeFocused(); // focus is not lost when it is saved
});

for (const theme of ["dark", "light"] as const) for (const width of [390, 768, 1024, 1440]) test(`${theme} ${width}: compact, fits, and passes axe with every tool open`, async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width, height: width < 768 ? 844 : 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/ask");
  const toggle = page.getByRole("button", { name: `Switch to ${theme} theme`, exact: true });
  if (await toggle.isVisible()) await toggle.click();
  await askQuestion(page);

  // Closed, the tools sit below the answer and take three short rows.
  const answer = (await page.locator('[data-step="evidence"]').first().boundingBox())!;
  const rows = tools(page).locator("details");
  await expect(rows).toHaveCount(3);
  const first = (await rows.first().boundingBox())!;
  expect(first.y).toBeGreaterThanOrEqual(answer.y + answer.height);
  for (const row of await rows.all()) expect((await row.boundingBox())!.height).toBeLessThanOrEqual(50);

  await open(page, "In your own words");
  await open(page, "Similar example");
  await page.getByRole("button", { name: "Write a similar question" }).click();
  await expect(page.getByTestId("similar-question")).toBeVisible();
  await open(page, "Different explanation");
  await page.getByRole("button", { name: "Explain it this way" }).click();
  await expect(page.getByTestId("different-explanation")).toBeVisible();
  await page.getByTestId("similar-question").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${SHOTS}/${width}-${theme}.png` });
  await audit(page);
});
