import { afterEach, describe, expect, it, vi } from "vitest";
import { configFromEnv, forward, isAllowed, visitorIp } from "./backend-proxy";

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
