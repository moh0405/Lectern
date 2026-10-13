import { expect, test } from "./test";

test("search with filters, open a problem, read it and get a study guide", async ({ page }) => {
  await page.goto("/leetcode");
  await expect(page.getByText(/1,825 problems/)).toBeVisible();

  await page.getByLabel("Search problems").fill("two sum");
  await page.getByRole("button", { name: "Easy", exact: true }).click();
  await expect(page).toHaveURL(/q=two\+sum/);
  await expect(page).toHaveURL(/d=Easy/);

  const first = page.getByRole("region", { name: "Results" }).getByRole("button").first();
  await expect(first).toContainText("Two Sum");
  await first.click();
  await expect(page).toHaveURL(/p=1(&|$)/);

  const detail = page.getByLabel("Problem detail");
  await expect(detail.getByRole("heading", { name: /Two Sum/ })).toBeVisible();
  await expect(detail).toContainText("Given an array of integers");
  await expect(detail.getByText("Hash Table")).toBeVisible(); // topics now come through

  await detail.getByRole("button", { name: "Study guide" }).click();
  await expect(detail.getByRole("heading", { name: "Approach" })).toBeVisible();
  await expect(detail).toContainText("hash map");
});

test("the filter state survives a reload and topics narrow the results", async ({ page }) => {
  await page.goto("/leetcode?d=Hard&t=Tree");
  await expect(page.getByRole("button", { name: "Hard", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Tree", exact: true })).toHaveAttribute("aria-pressed", "true");
  const results = page.getByRole("region", { name: "Results" }).getByRole("button");
  await expect(results.first()).toBeVisible();
  for (const row of await results.all()) {
    await expect(row).toContainText("Tree");
  }
  await page.reload();
  await expect(page.getByRole("button", { name: "Hard", exact: true })).toHaveAttribute("aria-pressed", "true");
});

test("no matches shows a helpful message", async ({ page }) => {
  await page.goto("/leetcode?q=zzzzzzqqqq");
  await expect(page.getByText("No problems match")).toBeVisible();
});

test("mark a problem solved, keep notes, and see it in the list and the summary", async ({ page, request }) => {
  try {
    await page.goto("/leetcode?q=two+sum&p=1");
    const detail = page.getByLabel("Problem detail");
    await expect(detail.getByRole("heading", { name: /Two Sum/ })).toBeVisible();

    await detail.getByLabel("Notes").fill("hash map in one pass");
    await detail.getByRole("button", { name: "Save notes" }).click();
    await detail.getByRole("button", { name: "Solved", exact: true }).click();
    await expect(detail.getByRole("button", { name: "Solved", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("progress-summary")).toContainText("1 solved");
    await expect(page.getByRole("region", { name: "Results" }).getByLabel("Solved").first()).toBeVisible();

    await page.reload();
    await expect(page.getByLabel("Problem detail").getByLabel("Notes")).toHaveValue("hash map in one pass");
  } finally {
    await request.delete("http://127.0.0.1:8100/api/v1/leetcode/progress/1");
  }
});

test("the study plan focuses on topics you struggle with", async ({ page, request }) => {
  try {
    await request.put("http://127.0.0.1:8100/api/v1/leetcode/progress/1", { data: { status: "attempted" } });
    await page.goto("/leetcode");
    const plan = page.getByText("Your study plan").locator("..").locator("..");
    await expect(plan).toContainText("Weak topics");
    await expect(plan).toContainText("Weak topic:");
  } finally {
    await request.delete("http://127.0.0.1:8100/api/v1/leetcode/progress/1");
  }
});
