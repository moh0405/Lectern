import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./test";
import { indexFixture, removeFixture } from "./helpers";

const REASONED = "Reasoned from the problem, not from your sources";
const REJECT_FIRST = " [e2e: reject first draft]"; // tests/fake_gemini.py FORCE_REJECTION

test("LeetCode Try first labels reasoned verdicts apart from source-checked ones and still flags a wrong step", async ({ page }) => {
  let sent: { judge?: string } = {};
  page.on("request", (r) => { if (r.url().endsWith("/attempt/feedback")) sent = r.postDataJSON(); });
  await page.goto("/leetcode?q=two+sum&p=1");
  const detail = page.getByLabel("Problem detail");
  await detail.getByRole("button", { name: "Try first" }).click();
  await detail.getByRole("radio", { name: "Steps" }).check();
  await detail.getByLabel("Your attempt", { exact: true }).fill("Keep a hash map for the complement lookup.\nNever use a hash map for the complement lookup.");
  await detail.getByRole("button", { name: "Check my attempt" }).click();

  const rows = detail.getByRole("list", { name: "Your attempt, step by step" }).getByRole("listitem");
  await expect(rows.nth(0)).toHaveAttribute("data-verdict", "reasoned");
  await expect(rows.nth(1)).toHaveAttribute("data-verdict", "reasoned_wrong");
  expect(sent.judge).toBe("problem");
  for (const row of [rows.nth(0), rows.nth(1)]) {
    await expect(row).toContainText(REASONED);
    await expect(row.getByRole("button", { name: /Open passage/ })).toHaveCount(0); // no citation to open
  }
  await expect(rows.nth(0)).toContainText("Works for this problem");
  await expect(rows.nth(1)).toContainText("Does not hold for this problem");
  await expect(detail.getByText(/reasoned from the problem: 1 fine, 1 to re-check/)).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze()).violations).toEqual([]);
});

test.describe("Similar example", () => {
  test.beforeAll(async ({ request }) => { await indexFixture(request); });
  test.afterAll(async ({ request }) => { await removeFixture(request); });

  test("a draft the guard rejects is retried once and the student sees a question, not an error", async ({ page }) => {
    await page.route("**/api/v1/practice/similar", async (route) => {
      const body = route.request().postDataJSON() as { question: string };
      await route.continue({ postData: JSON.stringify({ ...body, question: body.question + REJECT_FIRST }) });
    });
    await page.goto("/ask");
    await page.getByLabel("Your question", { exact: true }).fill("Why is a binary heap fast?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    const tools = page.locator('[data-step="understanding"]');
    await expect(tools).toBeVisible();
    await expect(tools).toContainText("Similar example");
    await tools.locator("summary").filter({ hasText: "Similar example" }).click();
    await expect(tools.getByText("Uses up to two model calls.")).toBeVisible();
    const response = page.waitForResponse("**/api/v1/practice/similar");
    await page.getByRole("button", { name: "Write a similar question" }).click();
    const text = await (await response).text();
    expect(text).not.toContain("SCRIPTED-LEAKED-DRAFT");
    expect(text).not.toContain("SCRIPTED-HIDDEN-ANSWER");
    await expect(page.getByTestId("similar-question")).toContainText("Practice 1");
  });
});
