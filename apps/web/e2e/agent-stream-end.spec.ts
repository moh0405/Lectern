import { expect, test } from "./test";

/**
 * Live-eval defect: an agent run streamed its tool steps and then the page waited forever for a `done` that never
 * came, with Run disabled. However the stream ends, the page must say so and let you run again.
 */

const RUN = "**/api/v1/agent/run/stream";
const frame = (event: string, data: object) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const steps =
  ": stream open\n\n" +
  frame("tool_call", { name: "search_documents", arguments: { query: "binary heap" } }) +
  frame("tool_result", { name: "search_documents", summary: "4 passages from heaps.pdf", error: false }) +
  ": keep-alive\n\n" +
  frame("tool_call", { name: "search_documents", arguments: { query: "heap property" } });

async function runTask(page: import("@playwright/test").Page) {
  await page.goto("/agent");
  await page.getByLabel("Task").fill("What is a binary heap?");
  await page.getByLabel("Most steps").selectOption("3");
  await page.getByRole("button", { name: "Run agent" }).click();
}

test("a stream that stops without done shows an error and re-enables Run", async ({ page }) => {
  let calls = 0;
  await page.route(RUN, (route) => {
    calls++;
    return route.fulfill({ contentType: "text/event-stream", body: steps }); // closes with no done or error
  });
  await runTask(page);

  await expect(page.getByRole("alert").filter({ hasText: "The connection closed before the agent finished" })).toBeVisible();
  const trace = page.getByTestId("tool-step");
  await expect(trace).toHaveCount(2);
  await expect(trace.first()).toContainText("4 passages from heaps.pdf");
  await expect(trace.nth(1)).toContainText("did not finish"); // no spinner left running
  await expect(page.getByTestId("run-cost")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0);
  const runAgain = page.getByRole("button", { name: "Run agent" });
  await expect(runAgain).toBeEnabled();
  await runAgain.click();
  await expect(page.getByRole("alert").filter({ hasText: "The connection closed before the agent finished" })).toBeVisible();
  expect(calls).toBe(2);
});

test("a typed server error (timeout) is shown and Run comes back", async ({ page }) => {
  await page.route(RUN, (route) =>
    route.fulfill({
      contentType: "text/event-stream",
      body: steps + frame("error", { code: "timeout", message: "The agent took longer than 100 seconds and was stopped. Try fewer steps or a simpler task." }),
    }),
  );
  await runTask(page);
  await expect(page.getByRole("alert").filter({ hasText: "took longer than 100 seconds" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run agent" })).toBeEnabled();
});

test("if nothing arrives for a long time the page stops waiting", async ({ page }) => {
  await page.clock.install();
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => (release = resolve));
  await page.route(RUN, async (route) => {
    await held; // the API never answers
    await route.abort().catch(() => {});
  });
  await runTask(page);
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible();
  await page.clock.fastForward(151_000);
  await expect(page.getByRole("alert").filter({ hasText: "Nothing arrived from the agent for 150 seconds" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run agent" })).toBeEnabled();
  release();
});
