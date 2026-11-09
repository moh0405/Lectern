import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

const routes = [
  ["/ask", "Ask"],
  ["/sources", "Sources"],
  ["/study", "Flashcards"],
  ["/leetcode", "LeetCode"],
  ["/agent", "Agent"],
  ["/tutor", "Tutor tools"],
  ["/math", "Math"],
  ["/visualize", "Embedding map"],
  ["/analytics", "Analytics"],
] as const;

async function setReadingTheme(page: Page, theme: "light" | "dark") {
  const toggle = page.getByRole("button", { name: `Switch to ${theme} theme`, exact: true });
  if (await toggle.isVisible()) await toggle.click();
  await expect(page.getByRole("button", { name: `Switch to ${theme === "light" ? "dark" : "light"} theme`, exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme ?? "dark")).toBe(theme);
  // Theme foreground/background transitions last150ms; compare their settled colors.
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
}

async function withinViewport(locator: Locator) {
  return locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && box.left >= -1 && box.right <= innerWidth + 1 && box.top >= -1 && box.bottom <= innerHeight + 1;
  });
}

// These checks navigate and inspect only. The existing configured API is the isolated scripted fixture;
// no corpus, history, provider configuration or model output is modified by this file. Theme
// preferences live in a fresh isolated browser context for each test.
for (const theme of ["dark", "light"] as const) {
for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844], [320, 640]] as const) {
  test(`all learning destinations fit the ${width}px ${theme} workspace`, async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width, height });
    await page.goto("/ask");
    await setReadingTheme(page, theme);
    for (const [url, name] of routes) {
      if (new URL(page.url()).pathname !== url) await page.goto(url);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(200);
      const heading = page.getByRole("heading", { level: 1, name, exact: true });
      await expect(heading).toBeVisible();
      await expect(page.getByRole("main").locator(".animate-pulse"), `${url} finishes loading its actual content`).toHaveCount(0, { timeout: 15_000 });
      await expect(page).toHaveTitle(`${name} · Lectern`);
      await expect(page.getByRole("main")).toHaveCount(1);
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), { message: `${url} overflows the ${width}px ${theme} workspace` }).toBe(true);
      await expect.poll(() => withinViewport(heading), { message: `${url} heading is clipped in the ${width}px ${theme} workspace` }).toBe(true);
    }
  });
}
}

test("the question remains reachable and unobscured after keyboard focus on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/ask");
  const question = page.getByLabel("Your question", { exact: true });
  await question.focus();
  await expect(question).toBeFocused();
  await expect.poll(() => question.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const target = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return box.left >= -1 && box.right <= innerWidth + 1 && box.top >= 0 && box.bottom <= innerHeight + 1 && (target === element || element.contains(target));
  })).toBe(true);
});


test("all phone tools are discoverable, keyboard reachable and close on navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ask");
  const open = page.getByRole("button", { name: "All tools", exact: true });
  await expect(open).toBeVisible();
  await expect.poll(() => open.evaluate(e => { const b = e.getBoundingClientRect(); return b.width >= 44 && b.height >= 44; })).toBe(true);
  const nav = page.getByRole("navigation", { name: "Main", exact: true });
  await expect(nav.getByRole("link", { name: "Ask", exact: true })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Sources", exact: true })).toBeVisible();
  await open.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Close tools", exact: true })).toHaveAttribute("aria-expanded", "true");
  for (const name of ["Flashcards", "Tutor tools", "Math", "LeetCode", "Agent", "Embedding map", "Analytics"]) {
    const link = nav.getByRole("link", { name, exact: true });
    await expect(link).toBeVisible();
    await link.focus();
    await expect.poll(() => withinViewport(link)).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(open).toBeFocused();
  await expect(open).toHaveAttribute("aria-expanded", "false");
  await open.click();
  await nav.getByRole("link", { name: "Embedding map", exact: true }).click();
  await expect(page).toHaveURL(/\/visualize$/);
  await expect(open).toHaveAttribute("aria-expanded", "false");
});

test("reading theme survives navigation and reload and can be changed from the keyboard", async ({ page }) => {
  await page.goto("/ask");
  await setReadingTheme(page, "light");
  await page.getByRole("navigation", { name: "Main", exact: true }).getByRole("link", { name: "Sources", exact: true }).click();
  await expect(page).toHaveURL(/\/sources$/);
  await page.reload();
  await expect(page.getByRole("button", { name: "Switch to dark theme", exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
  await page.getByRole("button", { name: "Switch to dark theme", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme)).toBe("dark");
});

test("light reading theme retains WCAG A and AA across every learning destination", async ({ page }) => {
  test.setTimeout(120_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/ask");
  await setReadingTheme(page, "light");
  for (const [url, name] of routes) {
    if (new URL(page.url()).pathname !== url) await page.goto(url);
    await expect(page.getByRole("heading", { level: 1, name, exact: true })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(200);
    await expect(page.getByRole("main").locator(".animate-pulse")).toHaveCount(0, { timeout: 15_000 });
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(result.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), name).toEqual([]);
  }
});
