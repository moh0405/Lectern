import { expect, test } from "@playwright/test";

test("Library separates the read-only textbook from this browser's documents", async ({ page }) => {
  await page.goto("/sources");
  await expect(page.getByText("Material to learn. Lectern teaches it, with sources.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your documents (this browser)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Shared textbook (read-only)" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Delete / })).toHaveCount(0);
});

test("LeetCode Try first works in the demo without writing to the server", async ({ page }) => {
  const refused: string[] = [];
  const posts: string[] = [];
  page.on("response", (r) => { if (r.status() === 403) refused.push(new URL(r.url()).pathname); });
  page.on("request", (r) => { if (r.method() !== "GET" && r.url().includes("/api/backend/")) posts.push(new URL(r.url()).pathname.split("/api/v1/")[1] ?? r.url()); });
  await page.goto("/leetcode?q=two+sum&p=1");
  const detail = page.getByLabel("Problem detail");
  await expect(detail.getByRole("heading", { name: /Two Sum/ })).toBeVisible();
  expect(posts).toEqual([]);
  await detail.getByRole("button", { name: "Try first" }).click();
  await detail.getByRole("radio", { name: "Steps" }).check();
  await detail.getByLabel("Your attempt", { exact: true }).fill("Given an array of integers, return two indices.");
  await detail.getByRole("button", { name: "Check my attempt" }).click();
  await expect(detail.getByRole("list", { name: "Your attempt, step by step" })).toBeVisible();
  expect(posts).toEqual(["attempt/feedback"]);
  expect(refused).toEqual([]);
});
