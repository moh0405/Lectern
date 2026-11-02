import { expect, test, type Page } from "@playwright/test";

/**
 * Opt-in. Every test here talks to a REAL Gemini model through the real API, so they check structure and
 * behaviour (a streamed answer, verified citations, the tool steps, a valid concept map), never exact wording.
 * A transient model failure (overload, timeout) is retried; anything else fails the test.
 */
// Tests run in file order (one worker) but a failure does not skip the rest: each is a separate real-model check.
test.describe.configure({ mode: "default" });

// The free Gemini tier allows 5 requests a minute per model, and several of these tests make 3-6 calls each. The
// server waits out short rate limits, but spacing the tests keeps the suite about the app, not about the quota.
test.beforeEach(async ({ page }) => {
  await page.waitForTimeout(Number(process.env.REAL_E2E_PAUSE_MS ?? 25_000));
});

const TRANSIENT = /UNAVAILABLE|DEADLINE_EXCEEDED|high demand|overloaded|503|504|timed out|temporarily/i;

/** Run `attempt`; if the page shows a transient model error instead of a result, run it again (up to 3 times). */
async function withModelRetries(page: Page, attempt: () => Promise<void>, done: () => Promise<boolean>) {
  for (let i = 1; i <= 3; i++) {
    await attempt();
    const deadline = Date.now() + 120_000;
    while (Date.now() < deadline) {
      if (await done()) return;
      const alerts = (await page.getByRole("alert").allInnerTexts()).join(" ");
      if (TRANSIENT.test(alerts) && i < 3) break;
      if (alerts.trim() && !TRANSIENT.test(alerts)) throw new Error(`The app showed an error: ${alerts.trim().slice(0, 300)}`);
      await page.waitForTimeout(1500);
    }
    if (i === 3) throw new Error("The model never produced a result (3 attempts)");
  }
}

const answerShown = (page: Page) => async () => (await page.locator(".md-body").first().innerText().catch(() => "")).trim().length > 20;

test("Ask streams a real answer from the indexed material, with verified citations and its sources", async ({ page }) => {
  await page.goto("/ask");
  await expect(page.getByText(/chunks · /).first()).toBeVisible(); // the synthetic corpus is indexed
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Your question").fill("How do hash tables handle collisions?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
    },
    answerShown(page),
  );
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0, { timeout: 120_000 }); // finished streaming
  const answer = page.locator(".md-body").first();
  await expect(answer).toContainText(/chaining|open addressing|probing|bucket/i);
  await expect(page.getByText("Sources (").first()).toBeVisible();
  await expect(page.getByText(/\[1\] hashing\.md/)).toBeVisible();
  await expect(page.locator("span", { hasText: /^gemini/ }).first()).toBeVisible(); // the real model's name on the answer
  await expect.soft(page.getByRole("status").filter({ hasText: "cites" }), "the model cited a source it was not given").toHaveCount(0);
});

test("a repeated question is served from the cache, and Fresh answer asks the model again", async ({ page }) => {
  await page.goto("/ask");
  await page.getByLabel("Your question").fill("How do hash tables handle collisions?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByText("cached", { exact: true })).toBeVisible({ timeout: 60_000 });
  await withModelRetries(
    page,
    async () => void (await page.getByRole("button", { name: "Fresh answer" }).first().click()),
    async () => (await page.getByRole("heading", { name: /hash tables handle collisions/i }).count()) >= 2 && (await page.getByRole("button", { name: "Stop" }).count()) === 0,
  );
});

test("style and passage options change what is asked", async ({ page }) => {
  await page.goto("/ask");
  await page.locator("#mode").selectOption("eli5");
  await page.locator("#k").selectOption("2");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Your question").fill("What is a binary heap?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
    },
    answerShown(page),
  );
  await expect(page.getByText("ELI5", { exact: true }).first()).toBeVisible();
  await page.getByText("Sources (").first().click();
  expect(await page.getByRole("article").count()).toBeLessThanOrEqual(2);
});

test("agentic mode shows the rewrite, retrieve, grade, answer and verify steps with a real model", async ({ page }) => {
  await page.goto("/ask");
  await page.getByRole("checkbox", { name: /Agentic mode/ }).check();
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Your question").fill("Why is merge sort stable, and how does it compare with quicksort?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
    },
    answerShown(page),
  );
  await expect(page.getByRole("button", { name: "Stop" })).toHaveCount(0, { timeout: 150_000 });
  const how = page.getByLabel("How it answered");
  await how.locator("summary").click();
  for (const step of ["rewrite", "retrieve", "grade", "answer", "verify"]) await expect(how.getByText(step, { exact: true }).first()).toBeVisible(); // retrieve can appear twice: the grader may ask for a second search
  await expect(how).toContainText(/model calls/);
});

test("the Agent page: the model picks tools, you see each call, and the answer cites what the tools returned", async ({ page }) => {
  await page.goto("/agent");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Task").fill("Which of my documents covers graph traversal, and what do they say about BFS? Cite them.");
      await page.getByRole("button", { name: "Run agent" }).click();
    },
    async () => (await page.getByRole("region", { name: "Answer" }).count()) > 0,
  );
  const steps = page.getByTestId("tool-step");
  expect(await steps.count()).toBeGreaterThanOrEqual(1);
  await expect(steps.first()).toContainText(/search_documents|list_documents/);
  await expect(page.getByTestId("run-cost")).toContainText(/tool calls? · \d+ model calls?/);
  await expect(page.getByRole("region", { name: "Answer" })).toContainText(/BFS|breadth/i);
  await expect.soft(page.getByRole("status").filter({ hasText: "never returned" })).toHaveCount(0);
});

test("the agent combines tools: exact math plus a LeetCode search", async ({ page }) => {
  await page.goto("/agent");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Task").fill("Integrate x^2 + 3x, then find an Easy LeetCode problem that uses a hash table.");
      await page.getByRole("button", { name: "Run agent" }).click();
    },
    async () => (await page.getByRole("region", { name: "Answer" }).count()) > 0,
  );
  const trace = page.getByRole("region", { name: "What the agent did" });
  await expect(trace).toContainText("solve_math");
  await expect(trace).toContainText("find_leetcode_problem");
  await expect(page.getByRole("region", { name: "Answer" })).toContainText(/x\^?\{?3|x³/); // the exact integral, from the solver
});

test("the agent saves a flashcard when the deployment allows writes, and it appears in the deck", async ({ page }) => {
  await page.goto("/agent");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Task").fill("Save one flashcard about the load factor of a hash table, based on my material.");
      await page.getByRole("button", { name: "Run agent" }).click();
    },
    async () => (await page.getByRole("region", { name: "Answer" }).count()) > 0,
  );
  await expect(page.getByRole("region", { name: "What the agent did" })).toContainText("save_flashcard");
  await page.goto("/study");
  await expect(page.getByRole("region", { name: "Deck" }).locator("li").first()).toBeVisible();
});

test("tutor: concept map, Socratic hints, comparison and level-adaptive explanation all work with a real model", async ({ page }) => {
  await page.goto("/tutor");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Topic").fill("Hash tables");
      await page.getByRole("button", { name: "Generate map" }).click();
    },
    async () => (await page.getByTestId("concept-graph").locator(".react-flow__node").count()) >= 3,
  );
  expect(await page.getByTestId("concept-graph").locator(".react-flow__edge").count()).toBeGreaterThanOrEqual(2);

  await page.goto("/tutor?tool=socratic");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("What are you trying to work out?").fill("Why do hash tables need a collision strategy?");
      await page.getByRole("button", { name: "Guide me" }).click();
    },
    async () => (await page.getByRole("button", { name: /Show hint 1/ }).count()) > 0,
  );
  await expect(page.getByText(/Hint 1\./)).toHaveCount(0); // hints stay hidden until asked
  await page.getByRole("button", { name: /Show hint 1/ }).click();
  await expect(page.getByText(/Hint 1\./)).toBeVisible();

  await page.goto("/tutor?tool=synthesis");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel(/Topic to compare/).fill("Sorting algorithms");
      await page.getByRole("button", { name: "Compare" }).click();
    },
    async () => (await page.getByText(/Agreements|Similarities|Combined|Unified/i).count()) > 0,
  );

  await page.goto("/tutor?tool=adaptive");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Question").fill("What is a binary heap?");
      await page.getByLabel("Explain it at").selectOption("ELI5");
      await page.getByRole("button", { name: "Explain" }).click();
    },
    async () => (await page.locator(".md-body").first().innerText().catch(() => "")).trim().length > 20,
  );
  await expect(page.getByText("ELI5", { exact: true })).toBeVisible();
});

test("flashcards: the model writes cards from the material, they can be reviewed and exported", async ({ page }) => {
  await page.goto("/study");
  const deck = page.getByRole("region", { name: "Deck" });
  const before = await deck.locator("li").count();
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Topic (optional)").fill("graph traversal");
      await page.getByRole("button", { name: "Generate cards" }).click();
    },
    async () => (await deck.locator("li").count()) > before,
  );
  await page.getByRole("button", { name: "Show answer" }).first().click();
  await expect(page.getByTestId("card-back")).toBeVisible();
  await page.getByRole("button", { name: "Good" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "CSV" }).click();
  expect((await download).suggestedFilename()).toBe("flashcards.csv");
});

test("LeetCode: a real study guide for a problem", async ({ page }) => {
  await page.goto("/leetcode?q=two+sum&d=Easy&p=1");
  const detail = page.getByLabel("Problem detail");
  await expect(detail.getByRole("heading", { name: /Two Sum/ })).toBeVisible();
  await withModelRetries(
    page,
    async () => void (await detail.getByRole("button", { name: "Study guide" }).click()),
    async () => (await detail.locator(".md-body").first().innerText().catch(() => "")).length > 80,
  );
  await expect(detail).toContainText(/hash/i);
});

test("notes: a study-notes document is generated from the session", async ({ page }) => {
  await page.goto("/ask");
  await withModelRetries(
    page,
    async () => {
      await page.getByLabel("Your question").fill("What is a priority queue?");
      await page.getByRole("button", { name: "Ask", exact: true }).click();
    },
    answerShown(page),
  );
  await withModelRetries(
    page,
    async () => void (await page.getByRole("button", { name: /Generate from this session/ }).click()),
    async () => (await page.getByRole("button", { name: "MD", exact: true }).count()) > 0,
  );
  const md = page.waitForEvent("download");
  await page.getByRole("button", { name: "MD", exact: true }).click();
  expect((await md).suggestedFilename()).toBe("study-notes.md");
});

test("analytics reflect what was asked in this run", async ({ page }) => {
  await page.goto("/analytics");
  await expect(page.getByText("Most used sources")).toBeVisible();
  await expect(page.getByText(/hash tables handle collisions/i).first()).toBeVisible();
});
