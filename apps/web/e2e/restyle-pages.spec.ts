import AxeBuilder from "@axe-core/playwright";
import { indexFixture, removeFixture } from "./helpers";
import { expect, test } from "./test";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

test("Library keeps the new copy and shows the indexed shelf on paper", async ({ page }) => {
  await page.goto("/sources");
  await expect(page.getByText("Material to learn. Lectern teaches it, with sources.")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "On this page" })).toBeVisible();
  await expect(page.locator("#library-shared")).toHaveClass(/paper-tokens/);
});

for (const theme of ["dark", "light"] as const) {
  test(`${theme}: the paper shelf with indexed sources passes axe`, async ({ page, request }) => {
    await indexFixture(request, "heaps.pdf");
    try {
      await page.addInitScript((t) => { try { localStorage.setItem("lectern-reading-theme", t); } catch { /* default theme */ } }, theme);
      await page.goto("/sources");
      await expect(page.locator("#library-shared").getByText("heaps.pdf").first()).toBeVisible();
      await page.waitForTimeout(200);
      const axe = await new AxeBuilder({ page }).withTags(WCAG).analyze();
      expect(axe.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
    } finally {
      await removeFixture(request, "heaps.pdf");
    }
  });
}

test("LeetCode Try first checks an attempt only on click and keeps the guide hidden until asked", async ({ page }) => {
  const calls = { feedback: 0, explain: 0 };
  page.on("request", (r) => {
    if (r.url().endsWith("/attempt/feedback")) calls.feedback++;
    if (r.url().endsWith("/explain")) calls.explain++;
  });
  await page.goto("/leetcode?q=two+sum&p=1");
  const detail = page.getByLabel("Problem detail");
  await expect(detail.getByRole("heading", { name: /Two Sum/ })).toBeVisible();
  await detail.getByRole("button", { name: "Try first" }).click();
  await detail.getByRole("radio", { name: "Steps" }).check();
  await detail.getByLabel("Your attempt", { exact: true }).fill("Given an array of integers, return two indices.\nHeaps were invented in 1964.");
  expect(calls).toEqual({ feedback: 0, explain: 0 });

  // Escape must not close the problem and lose the draft.
  await detail.getByLabel("Your attempt", { exact: true }).press("Escape");
  await expect(page).toHaveURL(/p=1(&|$)/);
  await expect(detail.getByLabel("Your attempt", { exact: true })).toHaveValue(/Heaps were invented/);

  await detail.getByRole("button", { name: "Check my attempt" }).click();
  await expect(detail.getByRole("list", { name: "Your attempt, step by step" })).toBeVisible();
  expect(calls).toEqual({ feedback: 1, explain: 0 });

  // A verified verdict opens the problem statement it cites.
  await detail.getByRole("button", { name: /Step 1: Supported.*Open passage 1/ }).click();
  await expect(detail.getByRole("heading", { name: /Passage 1: LeetCode 1\. Two Sum/ })).toBeVisible();
  const axe = await new AxeBuilder({ page }).withTags(WCAG).analyze();
  expect(axe.violations.map((v) => v.id)).toEqual([]);

  await detail.getByRole("button", { name: "Show the study guide" }).click();
  await expect(detail.getByRole("heading", { name: "Approach" })).toBeVisible();
  expect(calls).toEqual({ feedback: 1, explain: 1 });
});

test("Similar examples saved by Ask appear in Practice and only prefill the composer", async ({ page }) => {
  const models: string[] = [];
  page.on("request", (r) => { if (r.method() === "POST" && /\/(ask|practice|attempt)/.test(r.url())) models.push(r.url()); });
  await page.addInitScript(() => {
    if (localStorage.getItem("asm.ask.turns.v1")) return;
    localStorage.setItem("asm.ask.turns.v1", JSON.stringify([{ id: "t1", question: "What is a heap?", answer: "A tree.", chunks: [], status: "done", similar: [{ question: "How does a min-heap insert work?", citations: [] }] }]));
  });
  await page.goto("/study");
  const panel = page.getByTestId("similar-history");
  await expect(panel).toContainText("How does a min-heap insert work?");
  await panel.getByRole("link", { name: /Practise on Ask/ }).click();
  await expect(page.getByLabel("Your question", { exact: true })).toHaveValue("How does a min-heap insert work?");
  expect(models).toEqual([]);
});
