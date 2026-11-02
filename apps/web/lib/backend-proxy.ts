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
  ["POST", /^(ask|ask\/stream|ask\/agent\/stream|adaptive|concept-map|math|socratic|synthesis)$/],
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

/** `segments` is the URL after /api/backend, as the API client builds it: ["api", "v1", "ask", "stream"]. */
export async function forward(req: Request, segments: string[], config: ProxyConfig): Promise<Response> {
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

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
      signal: req.signal,
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
