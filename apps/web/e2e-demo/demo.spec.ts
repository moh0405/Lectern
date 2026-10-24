import { expect, test } from "@playwright/test";

test("flashcards: add, review and delete, all in the browser, with no refused requests", async ({ page }) => {
  const refused: string[] = [];
  page.on("response", (r) => r.status() === 403 && refused.push(new URL(r.url()).pathname));

  await page.goto("/study");
  await expect(page.getByText("No flashcards yet")).toBeVisible();

  await page.getByLabel("Front (question)").fill("What is a hash table?");
  await page.getByLabel("Back (answer)").fill("A key-value map with O(1) average lookup.");
  await page.getByRole("button", { name: "Add card" }).click();
  await expect(page.getByRole("region", { name: "Deck" })).toContainText("What is a hash table?");

  await page.getByRole("button", { name: "Show answer" }).click();
  await expect(page.getByTestId("card-back")).toContainText("O(1)");
  await page.getByRole("button", { name: "Good" }).click();
  await expect(page.getByText("All caught up")).toBeVisible();

  await page.reload(); // survives a reload because it lives in localStorage
  await expect(page.getByRole("region", { name: "Deck" })).toContainText("What is a hash table?");
  await expect(page.getByText("All caught up")).toBeVisible();

  await page.getByRole("button", { name: /Delete card/ }).click();
  await expect(page.getByText("No flashcards yet")).toBeVisible();
  expect(refused).toEqual([]);
});

test("LeetCode: marks and notes are kept in the browser; the plan explains it is off", async ({ page }) => {
  const refused: string[] = [];
  page.on("response", (r) => r.status() === 403 && refused.push(new URL(r.url()).pathname));

  await page.goto("/leetcode?p=1");
  const panel = page.getByLabel("Your progress");
  await panel.getByRole("button", { name: "Solved" }).click();
  await expect(panel.getByRole("button", { name: "Solved" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("progress-summary")).toContainText("1 solved");

  await page.reload();
  await expect(page.getByLabel("Your progress").getByRole("button", { name: "Solved" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/saved in this browser only/)).toBeVisible();
  expect(refused).toEqual([]);
});
