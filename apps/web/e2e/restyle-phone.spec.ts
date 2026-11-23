import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./test";
import { PHONE, smallTouchTargets } from "./touch-targets";

test.use(PHONE);

for (const theme of ["dark", "light"] as const) {
  for (const width of [320, 390] as const) {
    test(`${theme} ${width}: LeetCode Try first feedback fits, has 44px targets and passes axe`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.addInitScript((t) => { try { localStorage.setItem("lectern-reading-theme", t); } catch { /* default theme */ } }, theme);
      await page.goto("/leetcode?q=two+sum&p=1");
      await expect.poll(() => page.evaluate(() => document.documentElement.dataset.theme ?? "dark")).toBe(theme);
      const sheet = page.getByRole("dialog", { name: "Problem" });
      await expect(sheet.getByRole("heading", { name: /Two Sum/ })).toBeVisible();
      await sheet.getByRole("button", { name: "Try first" }).click();
      await sheet.getByRole("radio", { name: "Steps" }).check();
      await sheet.getByLabel("Your attempt", { exact: true }).fill("Given an array of integers, return two indices.\nHeaps were invented in 1964.");
      await sheet.getByRole("button", { name: "Check my attempt" }).click();
      await expect(sheet.getByRole("list", { name: "Your attempt, step by step" })).toBeVisible();

      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect(await sheet.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
      expect(await smallTouchTargets(page)).toEqual([]);
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(axe.violations.map((v) => `${v.id}: ${v.nodes[0]?.target.join(" ")}`)).toEqual([]);
    });
  }
}
