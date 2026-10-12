import assert from "node:assert/strict";
import { test } from "node:test";
import { readSse } from "./sse.ts";

function streamOf(...parts: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      for (const p of parts) c.enqueue(enc.encode(p));
      c.close();
    },
  });
}

async function collect(body: ReadableStream<Uint8Array>) {
  const out = [];
  for await (const f of readSse(body)) out.push(f);
  return out;
}

test("parses typed frames", async () => {
  const frames = await collect(streamOf('event: meta\ndata: {"a":1}\n\nevent: token\ndata: {"text":"hi"}\n\n'));
  assert.deepEqual(frames, [
    { event: "meta", data: '{"a":1}' },
    { event: "token", data: '{"text":"hi"}' },
  ]);
});

test("handles frames split across chunks and CRLF", async () => {
  const frames = await collect(streamOf("event: tok", 'en\r\ndata: {"text":"a"}\r', "\n\r\nevent: done\ndata: {}\n", "\n"));
  assert.deepEqual(frames.map((f) => f.event), ["token", "done"]);
});

test("handles multi-byte characters split across chunks", async () => {
  const bytes = new TextEncoder().encode('event: token\ndata: {"text":"héllo"}\n\n');
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      c.enqueue(bytes.slice(0, 27)); // cuts the "é" in half
      c.enqueue(bytes.slice(27));
      c.close();
    },
  });
  const [frame] = await collect(body);
  assert.equal(JSON.parse(frame!.data).text, "héllo");
});

test("ignores comments and joins multi-line data; defaults event name", async () => {
  const frames = await collect(streamOf(": keep-alive\n\ndata: one\ndata: two\n\n"));
  assert.deepEqual(frames, [{ event: "message", data: "one\ntwo" }]);
});

test("yields a final frame without a trailing blank line", async () => {
  const frames = await collect(streamOf("event: done\ndata: {}"));
  assert.deepEqual(frames, [{ event: "done", data: "{}" }]);
});
