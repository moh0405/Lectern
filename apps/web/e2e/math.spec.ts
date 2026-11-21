import { expect, test } from "./test";

test("computes and typesets a result, with steps", async ({ page }) => {
  await page.goto("/math");
  await page.getByLabel("Expression").fill("differentiate sin(x)");
  await page.getByRole("button", { name: "Compute" }).click();
  const result = page.getByTestId("math-result").first();
  await expect(result.locator(".katex")).toBeVisible();
  await expect(result).toContainText("cos");
  await expect(result).toContainText("Differentiated with respect to x");
});

test("example chips fill the input, results stack newest first and can be cleared", async ({ page }) => {
  await page.goto("/math");
  await page.getByRole("button", { name: "Use example: integrate x^2 + 3x" }).click();
  await expect(page.getByLabel("Expression")).toHaveValue("integrate x^2 + 3x");
  await expect(page.getByTestId("math-result")).toHaveCount(0); // nothing runs until you compute
  await expect(page.getByRole("button", { name: "Compute" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("math-result")).toHaveCount(1);
  await page.getByRole("button", { name: "Use example: factor x^3 - x" }).click();
  await page.getByRole("button", { name: "Compute" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(2);
  await expect(page.getByTestId("math-result").first()).toContainText("factor");
  await page.getByRole("button", { name: "Clear history" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(0);
});

test("a typing mistake is explained in plain words and pointed at", async ({ page }) => {
  await page.goto("/math");
  await page.getByLabel("Expression").fill("x^2 + (3");
  await page.getByRole("button", { name: "Compute" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Unbalanced parentheses" })).toBeVisible();
  await expect(page.getByTestId("math-error-at").locator("mark")).toHaveText("(");
  await expect(page.getByLabel("Expression")).toHaveAttribute("aria-invalid", "true");
  await page.getByLabel("Expression").fill("integrate(((");
  await page.getByRole("button", { name: "Compute" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Unbalanced parentheses" })).toBeVisible();
  await expect(page.getByText(/not an allowed name|EOF|<string>/)).toHaveCount(0);
});

test("rejected input shows the server's message, not a crash", async ({ page }) => {
  await page.goto("/math");
  await page.getByLabel("Expression").fill("__import__('os').system('id')");
  await page.getByRole("button", { name: "Compute" }).click();
  // Next.js adds its own (empty) role=alert route announcer, so match on the message.
  await expect(page.getByRole("alert").filter({ hasText: /Only numbers|not allowed/i })).toBeVisible();
  await expect(page.getByTestId("math-result")).toHaveCount(0);
});
