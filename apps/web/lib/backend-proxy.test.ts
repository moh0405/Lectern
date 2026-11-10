import { afterEach, describe, expect, it, vi } from "vitest";
import { configFromEnv, createForwarder, forward, isAllowed, visitorIp } from "./backend-proxy";

const cfg = { backendUrl: "https://api.example.com", apiKey: "k" };

afterEach(() => vi.unstubAllGlobals());

describe("isAllowed", () => {
  it("lets reading and asking through", () => {
    for (const [m, p] of [["GET", "search"], ["GET", "documents"], ["POST", "ask"], ["POST", "ask/stream"], ["POST", "ask/agent/stream"], ["POST", "agent/run/stream"], ["GET", "leetcode/problems/12"], ["POST", "leetcode/problems/12/explain"]]) {
      expect(isAllowed(m!, p!)).toBe(true);
    }
  });
  it("blocks anything that changes or reveals shared data", () => {
    for (const [m, p] of [["DELETE", "sources"], ["POST", "sources/files"], ["POST", "sources/urls"], ["GET", "history"], ["POST", "history"], ["DELETE", "history"], ["GET", "cards"], ["POST", "cards/generate"], ["PUT", "leetcode/progress/3"], ["GET", "analytics"], ["DELETE", "analytics"], ["GET", "jobs/abc"], ["POST", "export"]]) {
      expect(isAllowed(m!, p!), `${m} ${p}`).toBe(false);
    }
  });
  it("does not match on a prefix", () => {
    expect(isAllowed("GET", "search/../history")).toBe(false);
    expect(isAllowed("GET", "documents/extra")).toBe(false);
  });
  it("allows everything when writes are enabled", () => {
    expect(isAllowed("DELETE", "sources", true)).toBe(true);
  });
});

describe("configFromEnv", () => {
  it("reads the three settings", () => {
    expect(configFromEnv({ BACKEND_URL: "u", BACKEND_API_KEY: "k", BACKEND_ALLOW_WRITES: "1" })).toEqual({ backendUrl: "u", apiKey: "k", allowWrites: true });
    expect(configFromEnv({}).allowWrites).toBe(false);
  });
});

describe("forward", () => {
  it("adds the key, keeps the query string and streams the body back", async () => {
    const fetchMock = vi.fn(async () => new Response("data", { status: 200, headers: { "content-type": "text/event-stream", "set-cookie": "x=1" } }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await forward(new Request("https://app.example/api/backend/search?query=hash&k=2", { headers: { cookie: "secret=1", accept: "application/json" } }), ["api", "v1", "search"], cfg);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(String(url)).toBe("https://api.example.com/api/v1/search?query=hash&k=2");
    const sent = init.headers as Headers;
    expect(sent.get("x-api-key")).toBe("k");
    expect(sent.get("cookie")).toBeNull();
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("text/event-stream");
    expect(res.headers.get("set-cookie")).toBeNull();
    expect(await res.text()).toBe("data");
  });

  it("sends the body of a POST", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await forward(new Request("https://app.example/x", { method: "POST", headers: { "content-type": "application/json" }, body: '{"question":"q"}' }), ["api", "v1", "ask"], cfg);
    const init = (fetchMock.mock.calls[0] as unknown as [URL, RequestInit])[1];
    expect(new TextDecoder().decode(init.body as ArrayBuffer)).toBe('{"question":"q"}');
  });

  it("refuses blocked routes without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const res = await forward(new Request("https://app.example/x", { method: "DELETE" }), ["api", "v1", "sources"], cfg);
    expect(res.status).toBe(403);
    expect((await res.json()).error.code).toBe("disabled_in_demo");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses path tricks and a missing address", async () => {
    vi.stubGlobal("fetch", vi.fn());
    expect((await forward(new Request("https://app.example/x"), ["api", "v1", "search", ".."], cfg)).status).toBe(400);
    expect((await forward(new Request("https://app.example/x"), ["api", "v1", "search"], { apiKey: "k" })).status).toBe(503);
  });

  it("only serves the versioned API path", async () => {
    vi.stubGlobal("fetch", vi.fn());
    expect((await forward(new Request("https://app.example/x"), ["history"], cfg)).status).toBe(404);
    expect((await forward(new Request("https://app.example/x"), ["api", "v2", "search"], cfg)).status).toBe(404);
  });

  it("serves the health check, and only as a GET", async () => {
    const fetchMock = vi.fn(async () => Response.json({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
    const ok = await forward(new Request("https://app.example/x"), ["health"], cfg);
    expect(ok.status).toBe(200);
    expect(String((fetchMock.mock.calls[0] as unknown as [URL])[0])).toBe("https://api.example.com/health");
    expect((await forward(new Request("https://app.example/x", { method: "POST" }), ["health"], cfg)).status).toBe(404);
  });

  it("reports an unreachable API as 502", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    expect((await forward(new Request("https://app.example/x"), ["api", "v1", "search"], cfg)).status).toBe(502);
  });

  it("passes the API's own errors through unchanged", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ error: { code: "daily_limit", message: "m" } }, { status: 429 })));
    const res = await forward(new Request("https://app.example/x", { method: "POST", body: "{}" }), ["api", "v1", "ask"], cfg);
    expect(res.status).toBe(429);
    expect((await res.json()).error.code).toBe("daily_limit");
  });
});

describe("visitor address", () => {
  it("takes the first forwarded address, else x-real-ip, else none", () => {
    expect(visitorIp(new Request("https://a/", { headers: { "x-forwarded-for": "9.9.9.9, 10.0.0.1" } }))).toBe("9.9.9.9");
    expect(visitorIp(new Request("https://a/", { headers: { "x-real-ip": "8.8.8.8" } }))).toBe("8.8.8.8");
    expect(visitorIp(new Request("https://a/"))).toBeNull();
  });
  it("passes it to the API, and a client-supplied x-visitor-ip is not trusted", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await forward(new Request("https://app.example/api/backend/stats", { headers: { "x-forwarded-for": "9.9.9.9", "x-visitor-ip": "6.6.6.6" } }), ["api", "v1", "stats"], cfg);
    const [, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect((init.headers as Headers).get("x-visitor-ip")).toBe("9.9.9.9");
  });
});


describe("public metadata request sharing", () => {
  const metadataRequest = (query = "", init?: RequestInit) => new Request(`https://app.example/api/backend/api/v1/stats${query}`, init);

  it("coalesces requests with independently readable bodies, caches all five metadata routes, and expires after ten seconds", async () => {
    let clock = 100;
    const send = createForwarder({ now: () => clock });
    let release!: (response: Response) => void;
    const fetchMock = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { release = resolve; }))
      .mockImplementation(async () => Response.json({ version: 2 }));
    vi.stubGlobal("fetch", fetchMock);
    const first = send(metadataRequest(), ["api", "v1", "stats"], cfg);
    const second = send(metadataRequest(), ["api", "v1", "stats"], cfg);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    release(Response.json({ version: 1 }));
    const responses = await Promise.all([first, second]);
    expect(await Promise.all(responses.map((response) => response.json()))).toEqual([{ version: 1 }, { version: 1 }]);
    expect(await (await send(metadataRequest(), ["api", "v1", "stats"], cfg)).json()).toEqual({ version: 1 });
    clock += 10_000;
    expect(await (await send(metadataRequest(), ["api", "v1", "stats"], cfg)).json()).toEqual({ version: 2 });
    for (const segments of [["health"], ["api", "v1", "documents"], ["api", "v1", "models"], ["api", "v1", "suggestions"]]) {
      for (let n = 0; n < 2; n++) await (await send(metadataRequest(), segments, cfg)).text();
    }
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("does not retain 429, other upstream errors, or unreachable responses", async () => {
    const send = createForwarder();
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response("busy", { status: 429, headers: { "retry-after": "4" } }))
      .mockResolvedValueOnce(new Response("unavailable", { status: 503 }))
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockImplementation(async () => Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const limited = await send(metadataRequest(), ["api", "v1", "stats"], cfg);
    expect(limited.status).toBe(429);
    expect(limited.headers.get("retry-after")).toBe("4");
    expect(await limited.text()).toBe("busy");
    expect((await send(metadataRequest(), ["api", "v1", "stats"], cfg)).status).toBe(503);
    expect((await send(metadataRequest(), ["api", "v1", "stats"], cfg)).status).toBe(502);
    expect((await send(metadataRequest(), ["api", "v1", "stats"], cfg)).status).toBe(200);
    await send(metadataRequest(), ["api", "v1", "stats"], cfg);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("never caches private/write-enabled requests, search or questions, and still blocks public history", async () => {
    const send = createForwarder();
    const fetchMock = vi.fn(async () => Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const abort = new AbortController();
    for (let n = 0; n < 2; n++) {
      await send(metadataRequest(), ["api", "v1", "stats"], { ...cfg, allowWrites: true });
      await send(metadataRequest(), ["health"], { ...cfg, allowWrites: true });
      await send(metadataRequest(), ["api", "v1", "history"], { ...cfg, allowWrites: true });
      await send(metadataRequest("", { signal: abort.signal }), ["api", "v1", "search"], cfg);
      await send(metadataRequest("", { method: "POST", body: "{}" }), ["api", "v1", "ask"], cfg);
      expect((await send(metadataRequest(), ["api", "v1", "history"], cfg)).status).toBe(403);
    }
    expect(fetchMock).toHaveBeenCalledTimes(10);
    const init = fetchMock.mock.calls[3] as unknown as [URL, RequestInit];
    expect(init[1].signal).toBeInstanceOf(AbortSignal);
    abort.abort();
    expect(init[1].signal?.aborted).toBe(true);
  });

  it("isolates backend identity, API-key rotations, exact queries and representation headers", async () => {
    const send = createForwarder();
    const fetchMock = vi.fn(async () => Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await send(metadataRequest("?a=1&b=2"), ["api", "v1", "stats"], cfg);
    await send(metadataRequest("?a=1&b=2"), ["api", "v1", "stats"], cfg);
    await send(metadataRequest("?b=2&a=1"), ["api", "v1", "stats"], cfg);
    await send(metadataRequest("?a=1&b=2"), ["api", "v1", "stats"], { ...cfg, apiKey: "rotated-test-key" });
    await send(metadataRequest("?a=1&b=2"), ["api", "v1", "stats"], { ...cfg, backendUrl: "https://other.example.com" });
    await send(metadataRequest("?a=1&b=2", { headers: { "accept-language": "fr" } }), ["api", "v1", "stats"], cfg);
    await createForwarder()(metadataRequest("?a=1&b=2"), ["api", "v1", "stats"], cfg);
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("lets an aborted caller leave without cancelling another waiter or poisoning the cache", async () => {
    const send = createForwarder();
    let release!: (response: Response) => void;
    const fetchMock = vi.fn(() => new Promise<Response>((resolve) => { release = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    const abort = new AbortController();
    const first = send(metadataRequest("", { signal: abort.signal }), ["api", "v1", "stats"], cfg);
    const second = send(metadataRequest(), ["api", "v1", "stats"], cfg);
    abort.abort();
    expect((await first).status).toBe(502);
    const [, init] = fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(init.signal?.aborted).toBe(false);
    release(Response.json({ ok: true }));
    expect(await (await second).json()).toEqual({ ok: true });
    expect(await (await send(metadataRequest(), ["api", "v1", "stats"], cfg)).json()).toEqual({ ok: true });
    expect((await send(metadataRequest("?new=1", { signal: abort.signal }), ["api", "v1", "stats"], cfg)).status).toBe(502);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("bounds retained entries and bytes and does not cache oversized responses", async () => {
    const send = createForwarder();
    const fetchMock = vi.fn(async () => new Response("ok"));
    vi.stubGlobal("fetch", fetchMock);
    for (let n = 0; n < 65; n++) await send(metadataRequest(`?entry=${n}`), ["api", "v1", "stats"], cfg);
    await send(metadataRequest("?entry=0"), ["api", "v1", "stats"], cfg);
    expect(fetchMock).toHaveBeenCalledTimes(66);
    fetchMock.mockImplementation(async () => new Response("x".repeat(256 * 1024)));
    for (let n = 0; n < 5; n++) await send(metadataRequest(`?bytes=${n}`), ["api", "v1", "stats"], cfg);
    await send(metadataRequest("?bytes=0"), ["api", "v1", "stats"], cfg);
    expect(fetchMock).toHaveBeenCalledTimes(72);
    fetchMock.mockImplementation(async () => new Response("x".repeat(256 * 1024 + 1)));
    for (let n = 0; n < 2; n++) expect(await (await send(metadataRequest("?large=1"), ["api", "v1", "stats"], cfg)).text()).toHaveLength(256 * 1024 + 1);
    expect(fetchMock).toHaveBeenCalledTimes(74);
  });
});
