import assert from "node:assert/strict";
import { test } from "node:test";
import { createApiClient } from "./index";

const sse = (...frames: [string, object][]) => frames.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");

test("askAgentStream posts to the agent endpoint and yields typed events in order", async () => {
  let url = "";
  let sent: unknown;
  const client = createApiClient({
    baseUrl: "http://api.test/",
    fetch: (async (u: string, init: RequestInit) => {
      url = u;
      sent = JSON.parse(String(init.body));
      return new Response(sse(["step", { name: "rewrite", detail: "Searching for: heap" }], ["token", { text: "Hi" }], ["replace", { reason: "x" }], ["done", { llm_calls: 3 }]), { status: 200 });
    }) as unknown as typeof fetch,
  });
  const seen: string[] = [];
  for await (const ev of client.askAgentStream({ question: "what is a heap" })) seen.push(ev.event);
  assert.equal(url, "http://api.test/api/v1/ask/agent/stream");
  assert.deepEqual(sent, { question: "what is a heap" });
  assert.deepEqual(seen, ["step", "token", "replace", "done"]);
});

test("askAgentStream throws an ApiError for an HTTP failure before streaming", async () => {
  const client = createApiClient({
    baseUrl: "http://api.test",
    fetch: (async () => new Response(JSON.stringify({ error: { code: "agent_unavailable", message: "no" } }), { status: 503 })) as unknown as typeof fetch,
  });
  await assert.rejects(client.askAgentStream({ question: "what is a heap" }).next(), (e: { status?: number; code?: string }) => e.status === 503 && e.code === "agent_unavailable");
});
