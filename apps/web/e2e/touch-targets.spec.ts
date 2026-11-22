import type { Page } from "@playwright/test";
import { API, indexFixture, removeFixture } from "./helpers";
import { expect, test } from "./test";
import { PHONE, smallTouchTargets } from "./touch-targets";

test.use(PHONE);

let cardId: number | undefined;

test.beforeAll(async ({ request }) => {
  const card = await request.post(`${API}/api/v1/cards`, { data: { front: "What is a heap?", back: "A tree with the heap property." } });
  cardId = (await card.json()).id;
  await indexFixture(request, "heaps.pdf");
});
test.afterAll(async ({ request }) => {
  if (cardId) await request.delete(`${API}/api/v1/cards/${cardId}`);
  await removeFixture(request, "heaps.pdf");
});

// The Ask composer's Answer/Guided switch is being redesigned separately, so it is left out here.
const SKIP = ['input[name="approach"]'];

const PAGES: [string, (page: Page) => Promise<void>][] = [
  ["/ask", async (p) => {
    // The search settings too: open the panel so its controls are measured.
    await p.getByText("Advanced", { exact: true }).click();
    await p.getByLabel(/Temperature/).waitFor();
  }],
  ["/leetcode", async (p) => void (await p.getByRole("button", { name: /^1\. Two Sum/ }).waitFor())],
  ["/concept-map", async (p) => void (await p.getByTestId("idle-preview").waitFor())],
  ["/compare", async (p) => void (await p.getByTestId("idle-preview").waitFor())],
  ["/work-it-out", async () => {}],
  ["/explain", async () => {}],
  ["/sources", async (p) => void (await p.getByRole("heading", { name: "Indexed sources", exact: true }).waitFor())],
  ["/study", async (p) => void (await p.getByRole("button", { name: "Show answer" }).waitFor())],
  ["/math", async () => {}],
  ["/agent", async () => {}],
  ["/analytics", async () => {}],
];

for (const [url, ready] of PAGES) {
  test(`touch targets on ${url} are at least 44px at 390px wide`, async ({ page }) => {
    await page.goto(url);
    await page.getByRole("heading", { level: 1 }).first().waitFor();
    await ready(page);
    expect(await page.evaluate(() => matchMedia("(pointer: coarse)").matches)).toBe(true);
    expect(await smallTouchTargets(page, SKIP)).toEqual([]);
  });
}
