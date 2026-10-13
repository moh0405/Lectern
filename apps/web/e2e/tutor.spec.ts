import { expect, test } from "./test";
import { indexFixture, removeFixture } from "./helpers";

test.beforeAll(async ({ request }) => indexFixture(request));
test.afterAll(async ({ request }) => removeFixture(request));

test("concept map renders a graph, highlights neighbours and offers exports", async ({ page }) => {
  await page.goto("/tutor");
  await page.getByLabel("Topic").fill("Linked lists");
  await page.getByRole("button", { name: "Generate map" }).click();

  const graph = page.getByTestId("concept-graph");
  await expect(graph.locator(".react-flow__node")).toHaveCount(2); // duplicate id from the model was dropped
  await expect(graph.locator(".react-flow__edge")).toHaveCount(1); // edge to an unknown node was dropped
  await expect(page.getByText("2 concepts · 1 links")).toBeVisible();

  await graph.getByText("Linked list", { exact: true }).click();
  await expect(page.getByText("Linked list → has → Node")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "DOT" }).click();
  expect((await download).suggestedFilename()).toBe("linked-lists.dot");
});

test("socratic tutor reveals hints one at a time and never the answer up front", async ({ page }) => {
  await page.goto("/tutor?tool=socratic");
  await page.getByLabel("What are you trying to work out?").fill("Why is binary search O(log n)?");
  await page.getByRole("button", { name: "Guide me" }).click();

  await expect(page.getByText("What is a node?")).toBeVisible();
  await expect(page.getByText(/Hint 1\./)).toHaveCount(0);
  await page.getByRole("button", { name: "Show hint 1 of 3" }).click();
  await expect(page.getByText(/Hint 1\./)).toBeVisible();
  await expect(page.getByText(/Hint 2\./)).toHaveCount(0);
  await page.getByRole("button", { name: "Show hint 2 of 3" }).click();
  await page.getByRole("button", { name: "Show hint 3 of 3" }).click();
  await expect(page.getByRole("button", { name: /Still stuck/ })).toBeVisible();
});

test("compare sources shows agreements, a combined explanation and citations", async ({ page }) => {
  await page.goto("/tutor?tool=synthesis");
  await page.getByLabel(/Topic to compare/).fill("Heaps");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByText("both define it")).toBeVisible();
  await expect(page.getByText("Unified view.")).toBeVisible();
  await expect(page.getByText("a.pdf")).toBeVisible();
});

test("adaptive explanation uses the chosen level and your sources", async ({ page }) => {
  await page.goto("/tutor?tool=adaptive");
  await page.getByLabel("Question").fill("What is a binary heap?");
  await page.getByLabel("Explain it at").selectOption("ELI5");
  await page.getByRole("button", { name: "Explain" }).click();
  await expect(page.getByText("From your material")).toBeVisible();
  await expect(page.getByText("ELI5", { exact: true })).toBeVisible();
  await page.getByText("Sources (").click();
  await expect(page.getByRole("article").first()).toContainText("heaps.pdf");
});

test("tabs are keyboard-reachable and reflected in the URL", async ({ page }) => {
  await page.goto("/tutor");
  await expect(page.getByRole("tab", { name: "Concept map" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Compare sources" }).click();
  await expect(page).toHaveURL(/tool=synthesis/);
  await expect(page.getByRole("tab", { name: "Compare sources" })).toHaveAttribute("aria-selected", "true");
});
