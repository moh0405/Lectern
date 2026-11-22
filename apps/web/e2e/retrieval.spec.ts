import { expect, test } from "./test";
import { indexFixture, removeFixture } from "./helpers";

// Three one-topic PDFs: dfs-storage.pdf is about distributed file systems and says "DFS" over and over;
// depth-first.pdf and breadth-first.pdf spell the graph searches out and never use the acronyms. The live site
// answered "Difference between BFS and DFS" from distributed-file-system passages. Query expansion
// (backend/query_expansion.py) spells the acronyms out, picking the graph sense because BFS is in the question.
const FIXTURES = ["dfs-storage.pdf", "depth-first.pdf", "breadth-first.pdf"];

test("an acronym question retrieves the sense it means: BFS vs DFS finds the graph searches", async ({ page, request }) => {
  for (const name of FIXTURES) await indexFixture(request, name);
  try {
    await page.goto("/ask");
    await page.getByLabel("Your question").fill("Difference between BFS and DFS");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.locator(".md-body").first()).toContainText("From your material", { timeout: 20_000 });

    await page.getByText("Sources (").first().click();
    const sources = page.getByRole("article");
    await expect(sources.first()).toBeVisible();
    const docs = (await sources.allInnerTexts()).map((t) => FIXTURES.find((f) => t.includes(f)));
    expect(docs.slice(0, 2).sort()).toEqual(["breadth-first.pdf", "depth-first.pdf"]);
  } finally {
    for (const name of FIXTURES) await removeFixture(request, name);
  }
});
