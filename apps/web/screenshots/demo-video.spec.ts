import { expect, test, type Page } from "@playwright/test";

/**
 * A scripted walkthrough, recorded as video. It runs against scripts/demo_server.py: real chunking, real
 * MiniLM embeddings and real hybrid retrieval, but a scripted stand-in for the language model, and the
 * captions say so.
 */

const pause = (page: Page, ms: number) => page.waitForTimeout(ms);

async function caption(page: Page, text: string) {
  await page.evaluate((t) => {
    let el = document.getElementById("demo-caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "demo-caption";
      el.style.cssText =
        "position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:99999;max-width:86%;padding:10px 18px;border-radius:12px;" +
        "background:rgba(10,10,20,.88);color:#fff;font:600 18px Inter,system-ui,sans-serif;text-align:center;border:1px solid rgba(255,255,255,.18);pointer-events:none";
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
}

async function type(page: Page, label: string, text: string) {
  const box = page.getByLabel(label);
  await box.click();
  await box.pressSequentially(text, { delay: 35 });
}

test("walkthrough", async ({ page }) => {
  test.setTimeout(240_000);

  await page.goto("/ask");
  await caption(page, "AI Study Mentor: ask your own CS material, get answers with checked citations");
  await pause(page, 3000);

  await caption(page, "Hybrid search (embeddings + BM25) finds the passages; the answer streams in");
  await type(page, "Your question", "How do hash tables deal with collisions?");
  await pause(page, 600);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("button", { name: "Copy answer" }).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0, { timeout: 30_000 });
  await caption(page, "Every citation is verified against the passages the model actually saw (demo uses a scripted model)");
  await pause(page, 3500);
  await page.getByText("Sources (").first().click();
  await caption(page, "The retrieved passages and their scores are always shown");
  await pause(page, 3500);

  await page.goto("/visualize");
  await caption(page, "A 3D map of the real embeddings: passages from the same topic cluster together");
  await expect(page.getByTestId("scatter3d")).toHaveClass(/js-plotly-plot/, { timeout: 30_000 });
  await pause(page, 4500);

  await page.goto("/leetcode?q=two+sum&d=Easy&p=1");
  await caption(page, "LeetCode mentor: 1,825 problems, filters, a study guide, and your own progress");
  await pause(page, 2500);
  await page.getByLabel("Your progress").getByRole("button", { name: "Solved" }).click();
  await page.getByLabel("Problem detail").getByRole("button", { name: "Study guide" }).click();
  await expect(page.getByRole("heading", { name: "Key observation" })).toBeVisible();
  await pause(page, 3500);

  await page.goto("/study");
  await caption(page, "Flashcards with SM-2 spaced repetition, exportable to Anki");
  await type(page, "Front (question)", "What does a hash table trade for O(1) lookup?");
  await type(page, "Back (answer)", "Extra memory and ordering; worst case O(n) on collisions.");
  await page.getByRole("button", { name: "Add card" }).click();
  await pause(page, 1200);
  await page.getByRole("button", { name: "Show answer" }).click();
  await pause(page, 1800);
  await page.getByRole("button", { name: "Good" }).click();
  await pause(page, 2500);

  await page.goto("/math");
  await caption(page, "Symbolic math in a sandboxed worker: no eval, with steps");
  await page.getByRole("button", { name: "integrate x^2 + 3x" }).click();
  await expect(page.getByTestId("math-result")).toHaveCount(1, { timeout: 30_000 });
  await pause(page, 3500);

  await page.goto("/tutor");
  await caption(page, "Tutor tools: concept maps, a Socratic tutor that gives hints, source comparison");
  await page.getByLabel("Topic").fill("Hash tables");
  await page.getByRole("button", { name: "Generate map" }).click();
  await expect(page.getByTestId("concept-graph").locator(".react-flow__node").first()).toBeVisible();
  await pause(page, 4500);

  await page.goto("/ask");
  await caption(page, "Python/FastAPI on AWS Lambda  |  Next.js on Vercel  |  94% hit@3 on a measured retrieval eval");
  await pause(page, 4000);
});
