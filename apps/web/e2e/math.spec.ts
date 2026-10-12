import { expect, test } from "@playwright/test";

test("computes and typesets a result, with steps", async ({ page }) => {
  await page.goto("/math");
  await page.getByLabel("Expression").fill("differentiate sin(x)");
  await page.getByRole("button", { name: "Compute" }).click();
  const result = page.getByTestId("math-result").first();
  await expect(result.locator(".katex")).toBeVisible();
  await expect(result).toContainText("cos");
  await expect(result).toContainText("Differentiated with respect to x");
});

test("example chips run immediately and results stack newest first", async ({ page }) => {
  await page.goto("/math");
  await page.getByRole("button", { name: "integrate x^2 + 3x" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(1);
  await page.getByRole("button", { name: "factor x^3 - x" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(2);
  await expect(page.getByTestId("math-result").first()).toContainText("factor");
});

test("rejected input shows the server's message, not a crash", async ({ page }) => {
  await page.goto("/math");
  await page.getByLabel("Expression").fill("__import__('os').system('id')");
  await page.getByRole("button", { name: "Compute" }).click();
  // Next.js adds its own (empty) role=alert route announcer, so match on the message.
  await expect(page.getByRole("alert").filter({ hasText: /Only numbers|not allowed/i })).toBeVisible();
  await expect(page.getByTestId("math-result")).toHaveCount(0);
});
