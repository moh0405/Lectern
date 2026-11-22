import { expect, test } from "@playwright/test";
import { PHONE, smallTouchTargets } from "../e2e/touch-targets";

test.use(PHONE);

// The Ask composer's Answer/Guided switch is being redesigned separately, so it is left out here.
const SKIP = ['input[name="approach"]'];

for (const url of ["/ask", "/leetcode", "/concept-map", "/study", "/sources"]) {
  test(`demo strip and page touch targets on ${url} are at least 44px at 390px wide`, async ({ page }) => {
    await page.goto(url);
    const strip = page.getByRole("region", { name: "About this demo" });
    for (const name of ["How it works", "Source code"]) {
      const box = await strip.getByRole("link", { name }).boundingBox();
      expect(box?.height, name).toBeGreaterThanOrEqual(43.5);
    }
    await page.getByRole("heading", { level: 1 }).first().waitFor();
    expect(await smallTouchTargets(page, SKIP)).toEqual([]);
  });
}

test.describe("with a mouse", () => {
  test.use({ viewport: { width: 1280, height: 800 }, hasTouch: false, isMobile: false });
  test("the demo strip stays one 36px line on a desktop", async ({ page }) => {
    await page.goto("/ask");
    const box = await page.getByRole("region", { name: "About this demo" }).boundingBox();
    expect(box?.height).toBeLessThanOrEqual(37);
  });
});
