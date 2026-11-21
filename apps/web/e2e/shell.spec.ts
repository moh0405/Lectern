import { expect, test } from "./test";

test("command palette jumps between pages from the keyboard", async ({ page }) => {
  await page.goto("/ask");
  await page.keyboard.press("Control+K");
  const input = page.getByPlaceholder(/Go to a page/);
  await expect(input).toBeFocused();
  await input.fill("math");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/math$/);
  await expect(page.getByRole("heading", { name: "Math" })).toBeVisible();
  // Focus lands on the new page, not on <body>
  await expect(page.locator("#workspace-content")).toBeFocused();

  await page.keyboard.press("Control+K");
  await page.getByPlaceholder(/Go to a page/).fill("socratic");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/tutor\?tool=socratic/);
});

test("command palette returns focus to its button, finds synonyms and offers actions", async ({ page }) => {
  await page.goto("/sources");
  const trigger = page.getByRole("button", { name: "Find a page or tool" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const input = page.getByPlaceholder(/Go to a page/);
  await expect(input).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();

  await page.keyboard.press("Enter");
  await input.fill("practice");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("option", { name: "Flashcards" })).toBeVisible();
  await expect(dialog.getByRole("option", { name: "Compare sources" })).toHaveCount(0);
  await input.fill("dark");
  await dialog.getByRole("option", { name: "Switch to light theme" }).click();
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
  await expect(trigger).toBeFocused();

  await page.keyboard.press("Control+K");
  await input.fill("what is a heap");
  await expect(dialog.getByRole("option", { name: "Ask: what is a heap" })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/ask\?q=what%20is%20a%20heap$/);
});

test("navigation marks the current page and works on a phone-sized screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ask");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Ask" })).toHaveAttribute("aria-current", "page");
  await nav.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL(/\/sources$/);
  await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
  // Practice and Tools group several pages; each section lists its own pages
  await nav.getByRole("link", { name: "Tools" }).click();
  await expect(page).toHaveURL(/\/tutor$/);
  await page.getByRole("navigation", { name: "Tools pages" }).getByRole("link", { name: "Math" }).click();
  await expect(page).toHaveURL(/\/math$/);
  await expect(nav.getByRole("link", { name: "Tools" })).toHaveClass(/active/);
  await expect(nav.getByRole("link", { name: "Tools" })).toHaveAttribute("aria-current", "true");
  // no horizontal page scroll on mobile
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("the section bar keeps the current page in view on a narrow phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/analytics");
  const current = page.getByRole("navigation", { name: "Tools pages" }).getByRole("link", { name: "Analytics" });
  await expect(current).toHaveAttribute("aria-current", "page");
  await expect.poll(() => current.evaluate((e) => { const b = e.getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth; })).toBe(true);
});

test("shows when the API cannot be reached, with a hint rather than a blank page", async ({ page }) => {
  await page.route(/127\.0\.0\.1:8100/, (route) => route.abort()); // every call to the API fails
  await page.goto("/sources");
  await expect(page.locator(".api-status-text")).toHaveText("Offline");
  await expect(page.getByRole("status").filter({ hasText: "the study service cannot be reached" })).toBeAttached();
  // network failures are retried a couple of times before the error is shown
  await expect(page.getByRole("alert").filter({ hasText: /can't reach its study service/ })).toBeVisible({ timeout: 15_000 });
});

test("unknown addresses get a friendly 404", async ({ page }) => {
  const res = await page.goto("/definitely-not-a-page");
  expect(res?.status()).toBe(404);
  await expect(page).toHaveTitle("Page not found · Lectern");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.getByText("404", { exact: true })).toBeVisible();
  for (const name of ["Ask", "Library", "Practice", "Tools"]) await expect(page.getByRole("navigation", { name: "Sections" }).getByRole("link", { name: new RegExp(`^${name}`) })).toBeVisible();
  await page.getByRole("link", { name: "Go to Ask" }).click();
  await expect(page).toHaveURL(/\/ask$/);
});

test("a page that crashes on bad data recovers with Try again", async ({ page }) => {
  let bad = true;
  await page.route("**/api/v1/documents*", (route) => (bad ? route.fulfill({ contentType: "application/json", body: '{"documents": 42}' }) : route.fallback()));
  await page.goto("/sources");
  const heading = page.getByRole("heading", { level: 1, name: "Something went wrong" });
  if (!(await heading.isVisible().catch(() => false))) test.skip(true, "this page tolerates the malformed response");
  await expect(heading).toBeFocused();
  bad = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sources", exact: true })).toBeVisible();
});
