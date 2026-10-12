import { expect, test } from "@playwright/test";

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
