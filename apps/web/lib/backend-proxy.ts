/**
 * The hosted app never lets the browser talk to the API directly. Requests go to /api/backend/*, and this
 * module forwards them from the server, adding the API key, which therefore never reaches a visitor.
 *
 * A public demo also must not let strangers change anything or read each other's data, so by default only
 * read and "ask" routes pass. The owner can lift that with BACKEND_ALLOW_WRITES=1 on a private deployment.
 */

import { DEMO_DISABLED_MESSAGE } from "./demo-message";

const ALLOWED: Array<[method: string, pattern: RegExp]> = [
  ["GET", /^documents$/],
  ["GET", /^stats$/],
  ["GET", /^suggestions$/],
  ["GET", /^models$/],
  ["GET", /^search$/],
  ["GET", /^embeddings\/projection$/],
  ["GET", /^leetcode\/(search|stats)$/],
  ["GET", /^leetcode\/problems\/[^/]+$/],
  ["POST", /^leetcode\/problems\/[^/]+\/explain$/],
  ["POST", /^(ask|ask\/stream|ask\/agent\/stream|agent\/run\/stream|adaptive|concept-map|math|socratic|synthesis)$/],
];

export interface ProxyConfig {
  backendUrl?: string;
  apiKey?: string;
  allowWrites?: boolean;
}

export function configFromEnv(env: Record<string, string | undefined> = process.env): ProxyConfig {
  return { backendUrl: env.BACKEND_URL, apiKey: env.BACKEND_API_KEY, allowWrites: env.BACKEND_ALLOW_WRITES === "1" };
}

/** `path` is what follows /api/v1/ (for example "ask/stream"). */
export function isAllowed(method: string, path: string, allowWrites = false): boolean {
  if (allowWrites) return true;
  const m = method.toUpperCase();
  return ALLOWED.some(([method_, re]) => method_ === m && re.test(path));
}

function errorResponse(status: number, code: string, message: string): Response {
  return Response.json({ error: { code, message } }, { status });
}

/** Headers worth passing on in each direction; everything else (cookies, host, hop-by-hop) is dropped. */
const REQUEST_HEADERS = ["content-type", "accept", "accept-language"];
const RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control", "retry-after"];

/** The visitor's address as the hosting platform saw it (Vercel sets these and overwrites client-supplied values). */
export function visitorIp(req: Request): string | null {
  const forwarded = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || req.headers.get("x-real-ip")?.trim() || null;
}

const METADATA_PATHS = new Set(["stats", "documents", "models", "suggestions"]);
const METADATA_TTL_MS = 10_000;
const MAX_CACHE_ENTRIES = 64;
const MAX_CACHE_BYTES = 1024 * 1024;
const MAX_ENTRY_BYTES = 256 * 1024;

interface MetadataEntry {
  response: Response;
  expiresAt: number;
  bytes: number;
}

/** Read only a bounded clone; oversized responses still stream normally to their callers. */
async function metadataCopy(response: Response): Promise<{ response: Response; bytes: number } | null> {
  if (!response.ok) return null;
  const declaredSize = Number(response.headers.get("content-length"));
  if (declaredSize > MAX_ENTRY_BYTES) return null;
  if (!response.body) return { response: response.clone(), bytes: 0 };
  const reader = response.clone().body!.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_ENTRY_BYTES) {
        // Awaiting cancellation of one tee branch can wait for the caller's branch to finish.
        void reader.cancel().catch(() => {});
        return null;
      }
      chunks.push(value);
    }
    const body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    return { response: new Response(body, { status: response.status, headers: response.headers }), bytes: size };
  } catch {
    return null;
  } finally {
    reader.releaseLock();
  }
}

/** Each visitor can stop waiting without aborting a metadata request shared with other visitors. */
function waitForMetadata(pending: Promise<Response>, signal: AbortSignal): Promise<Response> {
  return new Promise((resolve) => {
    const onAbort = () => resolve(errorResponse(502, "upstream_unreachable", "Could not reach the API."));
    if (signal.aborted) { onAbort(); return; }
    signal.addEventListener("abort", onAbort, { once: true });
    void pending.then((response) => {
      signal.removeEventListener("abort", onAbort);
      if (!signal.aborted) resolve(response.clone());
    }, () => {
      signal.removeEventListener("abort", onAbort);
      resolve(errorResponse(502, "upstream_unreachable", "Could not reach the API."));
    });
  });
}

/** A factory keeps test/deployment caches isolated. The exported forwarder below is process-local. */
export function createForwarder({ now = Date.now }: { now?: () => number } = {}) {
  const cache = new Map<string, MetadataEntry>();
  const inflight = new Map<string, Promise<Response>>();
  let cacheBytes = 0;
  function discard(key: string) {
    const entry = cache.get(key);
    if (entry) cacheBytes -= entry.bytes;
    cache.delete(key);
  }
  function prune() {
    for (const [key, entry] of cache) if (entry.expiresAt <= now()) discard(key);
  }

  /** `segments` follows /api/backend, for example ["api", "v1", "ask", "stream"]. */
  return async function forward(req: Request, segments: string[], config: ProxyConfig): Promise<Response> {
    const isHealth = segments.length === 1 && segments[0] === "health" && req.method === "GET"; // the status light in the sidebar
    if (!isHealth && (segments[0] !== "api" || segments[1] !== "v1")) return errorResponse(404, "not_found", "Not found");
    segments = isHealth ? segments : segments.slice(2);
    const path = segments.join("/");
    if (!config.backendUrl) return errorResponse(503, "not_configured", "The API address (BACKEND_URL) is not set on this deployment.");
    if (segments.some((s) => s === ".." || s === "." || s === "")) return errorResponse(400, "bad_path", "Invalid path");
    if (!isHealth && !isAllowed(req.method, path, config.allowWrites)) {
      return errorResponse(403, "disabled_in_demo", DEMO_DISABLED_MESSAGE);
    }

    const url = new URL(isHealth ? "/health" : `/api/v1/${path}`, config.backendUrl);
    url.search = new URL(req.url).search;
    const headers = new Headers();
    for (const name of REQUEST_HEADERS) {
      const value = req.headers.get(name);
      if (value) headers.set(name, value);
    }
    if (config.apiKey) headers.set("x-api-key", config.apiKey);
    // Every call reaches the API from this server, so tell it which visitor it is for (its rate limit is per visitor).
    const visitor = visitorIp(req);
    if (visitor) headers.set("x-visitor-ip", visitor);

    async function requestUpstream(signal: AbortSignal): Promise<Response> {
      const hasBody = req.method !== "GET" && req.method !== "HEAD";
      let upstream: Response;
      try {
        upstream = await fetch(url, {
          method: req.method,
          headers,
          body: hasBody ? await req.arrayBuffer() : undefined,
          cache: "no-store",
          signal,
        });
      } catch {
        return errorResponse(502, "upstream_unreachable", "Could not reach the API.");
      }

      const out = new Headers();
      for (const name of RESPONSE_HEADERS) {
        const value = upstream.headers.get(name);
        if (value) out.set(name, value);
      }
      out.set("x-accel-buffering", "no"); // let streamed answers through unbuffered
      return new Response(upstream.body, { status: upstream.status, headers: out });
    }

    const cacheable = !config.allowWrites && req.method === "GET" && (isHealth || METADATA_PATHS.has(path));
    if (!cacheable) return requestUpstream(req.signal);
    if (req.signal.aborted) return errorResponse(502, "upstream_unreachable", "Could not reach the API.");
    // Configuration identity (including key rotations), exact query order, and representations stay separate.
    const key = JSON.stringify([config.backendUrl, config.apiKey ?? null, url.href, ...REQUEST_HEADERS.map((name) => headers.get(name))]);
    // Do not retain arbitrarily large attacker-controlled query strings or configurations.
    if (key.length > 8192) return requestUpstream(req.signal);
    prune();
    const cached = cache.get(key);
    if (cached) return waitForMetadata(Promise.resolve(cached.response), req.signal);
    const shared = inflight.get(key);
    if (shared) return waitForMetadata(shared, req.signal);
    // Pending requests count toward the same bounded entry budget. Saturation falls back to forwarding.
    while (cache.size + inflight.size >= MAX_CACHE_ENTRIES && cache.size) discard(cache.keys().next().value!);
    if (inflight.size >= MAX_CACHE_ENTRIES) return requestUpstream(req.signal);

    const pending = (async () => {
      // A shared fetch must not inherit its first caller's cancellation. Still bound a stalled upstream.
      const response = await requestUpstream(AbortSignal.timeout(60_000));
      const copy = await metadataCopy(response);
      if (copy) {
        prune();
        while (cacheBytes + copy.bytes > MAX_CACHE_BYTES && cache.size) discard(cache.keys().next().value!);
        cache.set(key, { ...copy, expiresAt: now() + METADATA_TTL_MS });
        cacheBytes += copy.bytes;
      }
      return response;
    })().finally(() => { inflight.delete(key); });
    inflight.set(key, pending);
    return waitForMetadata(pending, req.signal);
  };
}

export const forward = createForwarder();
