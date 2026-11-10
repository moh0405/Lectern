import { expect, test } from "@playwright/test";

test("capacity is shown as busy rather than an offline API", async ({ page }) => {
  let calls=0;
  await page.route("**/health",route=>{calls++;return route.fulfill({status:429,contentType:"text/plain",body:"Too Many Requests"});});
  await page.goto("/ask");
  await expect(page.getByRole("status").filter({hasText:"Service busy"})).toBeVisible();
  await expect(page.getByText("API offline",{exact:true})).toHaveCount(0);
  expect(calls).toBe(1);
});

test("the map explains raw throttling and supports an explicit retry", async ({ page }) => {
  let calls=0;
  await page.route("**/api/v1/embeddings/projection?*",route=>{
    calls++;
    return calls===1?route.fulfill({status:429,contentType:"text/plain",body:"Too Many Requests"}):route.fulfill({json:{points:[],total_chunks:0,semantic:true,explained_variance:[]}});
  });
  await page.goto("/visualize");
  await expect(page.getByRole("alert").filter({hasText:"The study service is busy"})).toBeVisible();
  await page.getByRole("button",{name:"Try loading the map again"}).click();
  await expect(page.getByText("Nothing to plot yet")).toBeVisible();
  expect(calls).toBe(2);
});

test("a failed answer keeps its question and retries on request", async ({ page }) => {
  let calls=0;
  await page.route("**/api/v1/ask/stream",route=>{
    calls++;
    return calls===1?route.fulfill({status:429,contentType:"text/plain",body:"Too Many Requests"}):route.fulfill({contentType:"text/event-stream",body:'event: meta\ndata: {"chunks":[]}\n\nevent: token\ndata: {"text":"Illustrative recovered answer."}\n\nevent: done\ndata: {"model":"test-model","citations":[],"uncited":true,"cached":false}\n\n'});
  });
  await page.goto("/ask");
  const question="A synthetic capacity recovery question";
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button",{name:"Ask",exact:true}).click();
  await expect(page.getByRole("heading",{name:question,exact:true})).toBeVisible();
  await expect(page.getByRole("alert").filter({hasText:"The study service is busy"})).toBeVisible();
  await page.getByRole("button",{name:"Try this question again"}).click();
  await expect(page.locator(".md-body").first()).toContainText("Illustrative recovered answer.");
  expect(calls).toBe(2);
});
