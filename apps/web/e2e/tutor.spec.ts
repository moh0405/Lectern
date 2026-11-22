import { expect, test } from "./test";
import { indexFixture, removeFixture } from "./helpers";

test.beforeAll(async ({ request }) => indexFixture(request));
test.afterAll(async ({ request }) => removeFixture(request));

test("concept map renders a graph, highlights neighbours and offers exports", async ({ page }) => {
  await page.goto("/concept-map");
  await page.getByLabel("Topic").fill("Linked lists");
  await page.getByRole("button", { name: "Generate map" }).click();

  const graph = page.getByTestId("concept-graph");
  await expect(graph.locator(".react-flow__node")).toHaveCount(2); // duplicate id from the model was dropped
  await expect(graph.locator(".react-flow__edge")).toHaveCount(1); // edge to an unknown node was dropped
  await expect(page.getByText("2 concepts · 1 link ·")).toBeVisible();
  await expect(graph.locator(".react-flow__handle").first()).toHaveCSS("opacity", "0"); // read-only map: no connection handles

  await graph.getByText("Linked list", { exact: true }).click();
  await expect(page.getByTestId("concept-neighbours")).toContainText("Linked list → has → Node");

  // keyboard: Enter on a focused node shows its neighbours; the list view is the text alternative
  const nodeEl = graph.locator(".react-flow__node", { hasText: /^Node$/ });
  await expect(nodeEl).toHaveAttribute("aria-label", /Node, 1 connection/);
  await nodeEl.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("concept-neighbours")).toContainText(/^Node/);
  await page.getByRole("button", { name: "List view" }).click();
  await expect(page.getByTestId("concept-list")).toContainText("Linked list → has → Node");
  await page.getByRole("button", { name: "Map", exact: true }).click();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "DOT" }).click();
  expect((await download).suggestedFilename()).toBe("linked-lists.dot");
});

test("work it out reveals hints one at a time and never the answer up front", async ({ page }) => {
  await page.goto("/work-it-out");
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
  await page.goto("/compare");
  await page.getByLabel(/Topic to compare/).fill("Heaps");
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByText("both define it")).toBeVisible();
  await expect(page.getByText("Unified view.")).toBeVisible();
  await expect(page.getByText("a.pdf")).toBeVisible();
  await expect(page.getByTestId("syn-passages")).toBeVisible(); // the passages compared
});

test("adaptive explanation uses the chosen level and your sources", async ({ page }) => {
  await page.goto("/explain");
  await page.getByLabel("Question").fill("What is a binary heap?");
  await page.getByLabel("Explain it at").selectOption("ELI5");
  await page.getByRole("button", { name: "Explain" }).click();
  await expect(page.getByText("From your material")).toBeVisible();
  await expect(page.getByTestId("answer-meta")).toContainText("ELI5");
  const passages = page.getByTestId("adaptive-passages");
  await expect(passages.getByRole("heading", { name: /Built from \d+ passages?/ })).toBeVisible();
  await expect(passages.getByTestId("passage").first()).toContainText("heaps.pdf");
  await expect(passages.getByTestId("relevance").first()).toContainText("relevance"); // neutral, not a red badge
});

test("old tutor addresses redirect to each tool's own page", async ({ page }) => {
  const cases = [
    ["/tutor", "/concept-map", "Concept map"],
    ["/tutor?tool=map", "/concept-map", "Concept map"],
    ["/work-it-out", "/work-it-out", "Work it out"],
    ["/compare", "/compare", "Compare sources"],
    ["/explain", "/explain", "Explain at my level"],
  ] as const;
  for (const [from, to, h1] of cases) {
    await page.goto(from);
    expect(new URL(page.url()).pathname, from).toBe(to);
    await expect(page.getByRole("heading", { level: 1, name: h1, exact: true })).toBeVisible();
    await expect(page).toHaveTitle(`${h1} · Lectern`);
    await expect(page.getByRole("tab")).toHaveCount(0); // the old inner tab row is gone
  }
});

test("a redirect keeps the other query parameters", async ({ page }) => {
  await page.goto("/tutor?tool=synthesis&topic=Heaps");
  expect(new URL(page.url()).pathname).toBe("/compare");
  expect(new URL(page.url()).search).toBe("?topic=Heaps"); // the old `tool` parameter is dropped
  await expect(page.getByLabel(/Topic to compare/)).toHaveValue("Heaps");
});

test("a redirect drops the old tool parameter", async ({ page, request }) => {
  const response = await request.get("/tutor?tool=map", { maxRedirects: 0 });
  expect(response.status()).toBe(307);
  const location = new URL(response.headers().location ?? "", "http://localhost");
  expect(location.pathname + location.search).toBe("/concept-map");
  await page.goto("/tutor?tool=map");
  expect(page.url()).toMatch(/\/concept-map$/);
});

test("Ask's Go further links open each tool prefilled, without running it", async ({ page }) => {
  const question = "What is a binary heap used for?";
  const toolCalls: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/api\/v1\/(concept-map|synthesis|socratic)$/.test(r.url())) toolCalls.push(r.url());
  });
  const links = [
    ["Concept map of this topic", /\/concept-map\?topic=/, "Topic"],
    ["Compare your sources", /\/compare\?topic=/, /Topic to compare/],
    ["Work it out with hints", /\/work-it-out\?question=/, "What are you trying to work out?"],
  ] as const;
  await page.goto("/ask");
  await page.getByLabel("Your question", { exact: true }).fill(question);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  const further = page.getByTestId("go-further");
  await expect(further).toBeVisible({ timeout: 15_000 });
  for (const [name, url, label] of links) {
    await further.getByRole("link", { name }).click();
    await expect(page).toHaveURL(url);
    await expect(page.getByLabel(label)).toHaveValue(question);
    await page.goBack();
    await expect(page.getByTestId("go-further")).toBeVisible({ timeout: 15_000 });
  }
  expect(toolCalls).toEqual([]);
});

test("/ask?q= prefills the composer and does not send it", async ({ page }) => {
  let asked = false;
  page.on("request", (r) => {
    if (r.method() === "POST" && /\/api\/v1\/ask/.test(r.url())) asked = true;
  });
  await page.goto("/ask?q=What%20is%20a%20heap%3F");
  const box = page.getByLabel("Your question", { exact: true });
  await expect(box).toHaveValue("What is a heap?");
  await expect(box).toBeFocused();
  expect(asked).toBe(false);
});

test("an idle tool says what you will get and which documents it reads", async ({ page }) => {
  await page.goto("/concept-map");
  const idle = page.getByTestId("idle-preview");
  await expect(idle).toContainText("What you'll get");
  await expect(idle.getByTestId("library-line")).toContainText("heaps.pdf");
  await idle.getByRole("button", { name: "Heaps" }).click(); // a topic from the library fills the input
  await expect(page.getByLabel("Topic")).toHaveValue("Heaps");
});

test("socratic hints say whether they came from your material", async ({ page }) => {
  await page.goto("/work-it-out");
  await page.getByLabel("What are you trying to work out?").fill("Why use a binary heap?");
  await page.getByRole("button", { name: "Guide me" }).click();
  await expect(page.getByTestId("socratic-source")).toContainText(/Based on \d+ passages? from your material/);
  await expect(page.getByTestId("socratic-passages")).toBeVisible();
});
