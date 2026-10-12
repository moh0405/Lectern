import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { indexFixture, removeFixture } from "./helpers";

test.beforeAll(async ({ request }) => {
  await indexFixture(request, "heaps.pdf");
  await indexFixture(request, "graphs.pdf");
});
test.afterAll(async ({ request }) => {
  await removeFixture(request, "heaps.pdf");
  await removeFixture(request, "graphs.pdf");
});

async function violations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
}

const PAGES: [string, string, (page: Page) => Promise<void>][] = [
  ["Ask", "/ask", async () => {}],
  ["Sources", "/sources", async (p) => void (await p.getByText("Indexed sources").waitFor())],
  ["LeetCode", "/leetcode?q=two+sum&p=1", async (p) => void (await p.getByLabel("Problem detail").getByRole("heading").first().waitFor())],
  ["Tutor tools", "/tutor", async () => {}],
  ["Math", "/math", async () => {}],
  ["Embedding map", "/visualize", async (p) => void (await p.getByText(/Showing \d+/).waitFor())],
  ["Analytics", "/analytics", async () => {}],
];

for (const [name, url, ready] of PAGES) {
  test(`${name} page has no WCAG A/AA violations`, async ({ page }) => {
    await page.goto(url);
    await ready(page);
    await page.waitForTimeout(300);
    expect(await violations(page)).toEqual([]);
  });
}

test("Ask page with an answer, sources and the command palette open", async ({ page }) => {
  await page.goto("/ask");
  await page.getByLabel("Your question").fill("What is a binary heap?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await page.getByText("From your material").waitFor();
  await page.getByText("Sources (").first().click();
  expect(await violations(page)).toEqual([]);
  await page.keyboard.press("Control+K");
  await page.getByRole("dialog").waitFor();
  expect(await violations(page)).toEqual([]);
});
