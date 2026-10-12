import { expect, test } from "@playwright/test";

test("command palette jumps between pages from the keyboard", async ({ page }) => {
  await page.goto("/ask");
  await page.keyboard.press("Control+K");
  const input = page.getByPlaceholder(/Go to a page/);
  await expect(input).toBeFocused();
  await input.fill("math");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/math$/);
  await expect(page.getByRole("heading", { name: "Math" })).toBeVisible();

  await page.keyboard.press("Control+K");
  await page.getByPlaceholder(/Go to a page/).fill("socratic");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/tutor\?tool=socratic/);
});

test("navigation marks the current page and works on a phone-sized screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ask");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Ask" })).toHaveAttribute("aria-current", "page");
  await nav.getByRole("link", { name: "Sources" }).click();
  await expect(page).toHaveURL(/\/sources$/);
  await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
  // no horizontal page scroll on mobile
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("shows when the API cannot be reached, with a hint rather than a blank page", async ({ page }) => {
  await page.route(/127\.0\.0\.1:8100/, (route) => route.abort()); // every call to the API fails
  await page.goto("/sources");
  await expect(page.getByText("API offline").first()).toBeVisible();
  // network failures are retried a couple of times before the error is shown
  await expect(page.getByRole("alert").filter({ hasText: /Cannot reach the API/ })).toBeVisible({ timeout: 15_000 });
});

test("unknown addresses get a friendly 404", async ({ page }) => {
  const res = await page.goto("/definitely-not-a-page");
  expect(res?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.getByRole("link", { name: "Go to Ask" }).click();
  await expect(page).toHaveURL(/\/ask$/);
});
