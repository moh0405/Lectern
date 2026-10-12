import { expect, test } from "@playwright/test";
import { API, indexFixture, removeFixture } from "./helpers";

test.describe.configure({ mode: "serial" });

test("shows an empty state, then usage after questions, then can clear it", async ({ page, request }) => {
  await request.delete(`${API}/api/v1/analytics`);
  await page.goto("/analytics");
  await expect(page.getByText("No questions yet")).toBeVisible();

  await indexFixture(request);
  for (const question of ["What is a binary heap?", "How fast is heap insert?"]) {
    const res = await request.post(`${API}/api/v1/ask`, { data: { question } });
    expect(res.ok()).toBeTruthy();
  }
  await page.reload();
  await expect(page.getByText("Questions", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "How fast is heap insert?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Most used sources" })).toBeVisible();
  await expect(page.getByText("heaps.pdf").first()).toBeVisible();

  const csv = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV" }).click();
  expect((await csv).suggestedFilename()).toBe("analytics.csv");

  await page.getByRole("button", { name: "Clear" }).click();
  await page.getByRole("button", { name: "Confirm clear" }).click();
  await expect(page.getByText("No questions yet")).toBeVisible();
  await removeFixture(request);
});
