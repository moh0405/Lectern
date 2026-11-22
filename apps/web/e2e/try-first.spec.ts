import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { test, expect } from "./test";
import { indexFixture } from "./helpers";

/**
 * Try first, end to end against the real API with the scripted model (tests/fake_gemini.py `scripted_attempt_feedback`):
 * a step sharing words with a passage is supported (contradicted when negated, unchecked when it hedges with "I think"),
 * anything else is not covered.
 */
const SHOTS = process.env.TRY_FIRST_SCREENSHOTS ?? "test-results/try-first";
const QUESTION = "Why is a binary heap fast?";
const ATTEMPT = [
  "A binary heap is a complete binary tree.",
  "In a min-heap a parent is never smaller than its children.",
  "I think insert takes O(log n) time.",
  "Heaps were invented in 1964.",
].join("\n");

function count(page: Page) {
  const n = { feedback: 0, ask: 0, socratic: 0 };
  page.on("request", (r) => {
    if (r.url().endsWith("/attempt/feedback")) n.feedback++;
    if (r.url().includes("/ask/stream")) n.ask++;
    if (r.url().endsWith("/socratic")) n.socratic++;
  });
  return n;
}

async function setTheme(page: Page, theme: "dark" | "light") {
  const toggle = page.getByRole("button", { name: `Switch to ${theme} theme`, exact: true });
  if (await toggle.isVisible()) await toggle.click();
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme ?? "dark")).toBe(theme);
}

async function tryFirst(page: Page, attempt = ATTEMPT) {
  await page.getByRole("radio", { name: "Try first", exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill(QUESTION);
  await page.getByLabel(/Your attempt/).fill(attempt);
  await page.getByRole("button", { name: "Check my attempt" }).click();
  await expect(page.getByRole("list", { name: "Your attempt, step by step" })).toBeVisible();
}

async function audit(page: Page, name?: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  // An earlier axe run can leave the skip link focused; keep it out of the picture.
  await page.evaluate(() => { const el = document.activeElement as HTMLElement | null; if (el?.classList.contains("workspace-skip")) el.blur(); });
  if (name) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
}

/** The rendered height of each segment of a segmented control (its label, which the radio covers). */
async function segmentHeights(page: Page, group: string) {
  return page.getByRole("group", { name: group }).locator("label").evaluateAll((labels) => labels.map((l) => Math.round(l.getBoundingClientRect().height)));
}

test.beforeAll(async ({ request }) => { await indexFixture(request); });

test("Try first: one feedback call, per-step verdicts that open their passage, evidence in the same turn", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const n = count(page);
  await page.goto("/ask");
  const feedbackRequest = page.waitForRequest("**/api/v1/attempt/feedback");
  await tryFirst(page);
  expect((await feedbackRequest).postDataJSON()).toEqual({ question: QUESTION, attempt: ATTEMPT, format: "steps", k: 3, temperature: 0.2 });

  const rows = page.getByRole("list", { name: "Your attempt, step by step" }).getByRole("listitem");
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0)).toHaveAttribute("data-verdict", "supported");
  await expect(rows.nth(1)).toHaveAttribute("data-verdict", "contradicted");
  await expect(rows.nth(2)).toHaveAttribute("data-verdict", "unchecked");
  await expect(rows.nth(2)).toContainText("not checked against your sources");
  await expect(rows.nth(3)).toHaveAttribute("data-verdict", "not_covered");
  await expect(page.getByText("Look at step 2 first.")).toBeFocused();
  // Feedback only: no answer, no answer actions, and no answer request yet.
  await expect(page.getByRole("button", { name: "Copy answer" })).toHaveCount(0);
  expect(n).toEqual({ feedback: 1, ask: 0, socratic: 0 });

  // A verdict opens its passage in the source margin, highlighted against the step.
  await page.getByRole("button", { name: /^Step 2: Contradicted by your sources\. Open passage 1 in the source margin$/ }).click();
  const margin = page.getByRole("complementary", { name: "Source margin" });
  await expect(margin).toContainText("heaps.pdf");
  await expect(margin.locator("mark")).toContainText("parent is smaller than or equal to its children");
  await expect(margin).toContainText("the sentence closest to your attempt");
  await audit(page, "1440-dark-feedback");

  await page.getByRole("button", { name: "Show me the evidence" }).click();
  await expect(page.getByRole("button", { name: "Save as flashcard" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Feedback on your steps" })).toBeVisible(); // still in the turn
  await expect(page.getByRole("list", { name: "This session" }).getByRole("button")).toHaveCount(1);
  await page.locator(".cite-chip").first().click();
  await expect(margin).toContainText("heaps.pdf");
  expect(n).toEqual({ feedback: 1, ask: 1, socratic: 0 });
  await audit(page, "1440-dark-evidence");

  // Reload: the feedback and answer come back from this browser, nothing is refetched.
  await page.reload();
  await expect(page.getByRole("list", { name: "Your attempt, step by step" }).getByRole("listitem")).toHaveCount(4);
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toHaveCount(0);
  expect(n).toEqual({ feedback: 1, ask: 1, socratic: 0 });
});

test("the mode control is a keyboard radio group; Answer stays the unchanged default", async ({ page }) => {
  const n = count(page);
  await page.goto("/ask");
  const answer = page.getByRole("radio", { name: "Answer", exact: true });
  await expect(answer).toBeChecked();
  await answer.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Guided", exact: true })).toBeChecked();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "Try first", exact: true })).toBeChecked();
  await expect(page.getByLabel(/Your attempt/)).toBeVisible();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await expect(answer).toBeChecked();
  await expect(page.getByLabel(/Your attempt/)).toHaveCount(0);
  await page.getByLabel("Your question", { exact: true }).fill("Why use a heap?");
  const request = page.waitForRequest("**/api/v1/ask/stream");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  expect((await request).postDataJSON()).toEqual({ question: "Why use a heap?", k: 3, temperature: 0.2 });
  expect(n.feedback).toBe(0);
});

test("code attempts are judged line by line and carry their language", async ({ page }) => {
  await page.goto("/ask");
  await page.getByRole("radio", { name: "Try first", exact: true }).check();
  await page.getByRole("radio", { name: "Code", exact: true }).check();
  await page.getByLabel("Language").selectOption("Python");
  await page.getByLabel("Your question", { exact: true }).fill("Insert into a min-heap");
  await page.getByLabel(/Your attempt/).fill("def insert(heap, key):\n\n    # every parent is smaller than or equal to its children\n    heap.append(key)");
  const request = page.waitForRequest("**/api/v1/attempt/feedback");
  await page.getByRole("button", { name: "Check my attempt" }).click();
  expect((await request).postDataJSON()).toMatchObject({ format: "code", language: "Python" });
  const lines = page.getByRole("list", { name: "Your attempt, line by line" });
  await expect(lines).toBeVisible();
  await expect(page.getByRole("heading", { name: /Feedback on your code/ })).toContainText("Python");
  await expect(lines.getByRole("listitem").filter({ hasText: "every parent is smaller" })).toHaveAttribute("data-verdict", "supported");
  await expect(lines.getByRole("listitem").filter({ hasText: "heap.append(key)" })).toHaveAttribute("data-verdict", "not_covered");
});

test("a failed feedback request can be retried or skipped straight to the evidence", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/v1/attempt/feedback", (route) => (++calls === 1 ? route.fulfill({ status: 429, body: "Too Many Requests" }) : route.continue()));
  await page.goto("/ask");
  await page.getByRole("radio", { name: "Try first", exact: true }).check();
  await page.getByLabel("Your question", { exact: true }).fill(QUESTION);
  await page.getByLabel(/Your attempt/).fill(ATTEMPT);
  await page.getByRole("button", { name: "Check my attempt" }).click();
  await expect(page.getByText(/The study service is busy/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Show me the evidence" })).toBeVisible();
  await audit(page);
  await page.getByRole("button", { name: "Try this question again" }).click();
  await expect(page.getByRole("list", { name: "Your attempt, step by step" })).toBeVisible();
  expect(calls).toBe(2);
  await expect(page.getByRole("list", { name: "This session" }).getByRole("button")).toHaveCount(1);
});

for (const theme of ["dark", "light"] as const) for (const width of [390, 768, 1024, 1440]) test(`${theme} ${width}: mode control and Try first fit, have 44px phone targets and pass axe`, async ({ page }) => {
  test.setTimeout(90_000);
  await page.setViewportSize({ width, height: width < 768 ? 844 : 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/ask");
  await setTheme(page, theme);
  const phone = width < 768;
  for (const h of await segmentHeights(page, "How Lectern responds")) expect(h).toBeGreaterThanOrEqual(phone ? 44 : 36);
  await audit(page, `${width}-${theme}-composer`);
  await page.getByRole("radio", { name: "Try first", exact: true }).check();
  for (const h of await segmentHeights(page, "Attempt format")) expect(h).toBeGreaterThanOrEqual(phone ? 44 : 36);
  await page.getByLabel("Your question", { exact: true }).fill(QUESTION);
  await page.getByLabel(/Your attempt/).fill(ATTEMPT);
  await audit(page, `${width}-${theme}-attempt`);
  await page.getByRole("button", { name: "Check my attempt" }).click();
  await expect(page.getByRole("list", { name: "Your attempt, step by step" })).toBeVisible();
  const verdict = page.getByRole("button", { name: /^Step 1: Supported by your sources/ });
  if (phone) expect((await verdict.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await verdict.click();
  if (width < 1180) {
    // Stacked layout: the passage opens just below the feedback, and "Back to feedback" returns.
    await expect(page.getByRole("button", { name: "Back to feedback" })).toBeVisible();
  } else {
    await expect(page.getByRole("complementary", { name: "Source margin" })).toContainText("heaps.pdf");
  }
  await audit(page, `${width}-${theme}-feedback`);
});
