import { expect, test } from "./test";
import { indexFixture, removeFixture } from "./helpers";

test("explains an empty index", async ({ page }) => {
  await page.goto("/visualize");
  await expect(page.getByText("Nothing to plot yet")).toBeVisible();
});

test("plots indexed passages by document, warns that the test index is not semantic", async ({ page, request }) => {
  await indexFixture(request, "heaps.pdf");
  await indexFixture(request, "graphs.pdf");
  try {
    await page.goto("/visualize");
    await expect(page.getByText(/Showing \d+ passages? of \d+/)).toBeVisible();
    await expect(page.getByText(/hashing.*embedder/)).toBeVisible(); // honest about what the picture means
    await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
    await expect(page.getByText("graphs.pdf").first()).toBeVisible();

    // the WebGL plot itself (headless Chromium software-renders WebGL)
    const plot = page.getByTestId("scatter3d");
    await expect(plot).toHaveClass(/js-plotly-plot/, { timeout: 20_000 }); // Plotly marks its container
    await expect(plot.locator("canvas").first()).toBeVisible();
    await expect(plot.getByText("heaps.pdf").first()).toBeVisible(); // legend entry per document
  } finally {
    await removeFixture(request, "heaps.pdf");
    await removeFixture(request, "graphs.pdf");
  }
});
