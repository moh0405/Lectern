import { API, indexFixture, removeFixture } from "./helpers";
import { expect, test } from "./test";

test.describe.configure({ mode: "serial" });

test.afterEach(async ({ request }) => {
  const { cards } = await (await request.get(`${API}/api/v1/cards?limit=1000`)).json();
  for (const c of cards) await request.delete(`${API}/api/v1/cards/${c.id}`);
});

test("add a card, review it, and it leaves the due queue", async ({ page }) => {
  await page.goto("/study");
  await expect(page.getByText("No flashcards yet")).toBeVisible();

  await page.getByLabel("Front (question)").fill("What does LIFO stand for?");
  await page.getByLabel("Back (answer)").fill("Last in, first out: how a stack behaves.");
  await page.getByRole("button", { name: "Add card" }).click();

  const review = page.getByRole("region", { name: "Review session" });
  await expect(review).toContainText("What does LIFO stand for?");
  await expect(review.getByTestId("card-back")).toHaveCount(0); // the answer stays hidden until asked for
  await review.getByRole("button", { name: "Show answer" }).click();
  await expect(review.getByTestId("card-back")).toContainText("Last in, first out");

  await review.getByRole("button", { name: "Good", exact: true }).click();
  await expect(review.getByText("All caught up")).toBeVisible();
  await expect(review).toContainText("Next review tomorrow");

  const deck = page.getByRole("region", { name: "Deck" });
  await expect(deck).toContainText("What does LIFO stand for?");
  await expect(deck).toContainText("interval 1d");
});

test("the model writes cards from indexed material; they can be exported and deleted", async ({ page, request }) => {
  await indexFixture(request, "heaps.pdf");
  try {
    await page.goto("/study");
    await page.getByLabel("Topic (optional)").fill("heaps");
    await page.getByRole("button", { name: "Generate cards" }).click();

    const deck = page.getByRole("region", { name: "Deck" });
    await expect(deck).toContainText("What is a binary heap?");
    await expect(deck).toContainText("What is a heap used for?");

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "CSV" }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe("flashcards.csv");

    await page.getByRole("button", { name: /Delete card: What is a heap used for/ }).click();
    await expect(deck).not.toContainText("What is a heap used for?");
  } finally {
    await removeFixture(request, "heaps.pdf");
  }
});

test("generating without any material explains what to do", async ({ page }) => {
  await page.goto("/study");
  await page.getByRole("button", { name: "Generate cards" }).click();
  await expect(page.getByRole("status")).toContainText("Add some sources first");
});

test("an answer from Ask can be saved as a flashcard", async ({ page, request }) => {
  await indexFixture(request, "heaps.pdf");
  try {
    await page.goto("/ask");
    await page.getByLabel("Your question").fill("What is a binary heap used for?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByRole("button", { name: "Copy answer" })).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "Save as flashcard" }).click();
    await expect(page.getByRole("button", { name: "Saved as flashcard" })).toBeDisabled();

    await page.goto("/study");
    await expect(page.getByRole("region", { name: "Review session" })).toContainText("What is a binary heap used for?");
  } finally {
    await removeFixture(request, "heaps.pdf");
  }
});

test("Ask history is kept on the server and restored in a fresh browser", async ({ page, request }) => {
  await indexFixture(request, "heaps.pdf");
  try {
    await page.goto("/ask");
    await page.getByLabel("Your question").fill("What is a binary heap used for?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByRole("button", { name: "Copy answer" })).toBeVisible({ timeout: 20_000 });
    await expect.poll(async () => (await (await request.get(`${API}/api/v1/history`)).json()).turns.length).toBe(1);

    await page.evaluate(() => localStorage.clear()); // as if the browser data were wiped
    await page.reload();
    await expect(page.getByRole("heading", { name: "What is a binary heap used for?" })).toBeVisible();
  } finally {
    await removeFixture(request, "heaps.pdf");
  }
});
