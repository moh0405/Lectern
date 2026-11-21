import { createApiClient, ApiError } from "@ai-study-mentor/api-client";

/**
 * Where the browser sends API calls. Locally this is the FastAPI server itself; on the hosted app it is
 * "/api/backend", a server-side proxy that holds the API key (see lib/backend-proxy.ts).
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** One typed client for the whole app. */
export const api = createApiClient({ baseUrl: API_URL });

export { ApiError };

export const BUSY_MESSAGE = "The study service is busy right now. Wait a moment, then try again.";
export const OFFLINE_MESSAGE = "Lectern can't reach its study service right now. Check your connection, then try again.";
export const DAILY_LIMIT_MESSAGE = "Today's limit for model answers has been reached. It resets at midnight UTC; you can still search and read your sources.";
export const LLM_UNAVAILABLE_MESSAGE = "Answers are switched off on this server right now; you can still search your sources.";
export const SERVER_ERROR_MESSAGE = "Something went wrong on the server. Try again in a moment.";

export type ErrorKind = "offline" | "busy" | "daily_limit" | "quota" | "llm_unavailable" | "llm_error" | "unavailable" | "server" | "validation" | "not_found" | "demo" | "other";

/** A failure described for a student: a short title, a sentence to show, and the technical detail behind it. */
export interface ErrorInfo {
  kind: ErrorKind;
  title: string;
  message: string;
  /** What the server or browser actually said, for a "Technical details" disclosure. Not for the main text. */
  detail?: string;
  /** Seconds the server asked us to wait (Retry-After), when it said. */
  retryAfter?: number;
}

const GENERIC_429 = /^(429(?: too many requests)?|rate limit exceeded|too many requests)$/i;
/** "500 Internal Server Error" and friends: the status line, not a message written for anyone. */
const STATUS_LINE = /^\d{3}(?:\s+[A-Za-z][A-Za-z ]*)?$/;

/** Seconds from a Retry-After header value (seconds or an HTTP date); undefined when absent or unreadable. */
export function parseRetryAfter(value: string | null | undefined, now = Date.now()): number | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (/^\d+$/.test(trimmed)) return Number(trimmed);
  const at = Date.parse(trimmed);
  return Number.isNaN(at) ? undefined : Math.max(0, Math.ceil((at - now) / 1000));
}

function retryAfterOf(err: ApiError): number | undefined {
  const own = (err as ApiError & { retryAfter?: number }).retryAfter;
  if (typeof own === "number") return own;
  const details = err.details as { retry_after?: unknown } | undefined;
  return typeof details?.retry_after === "number" ? details.retry_after : undefined;
}

function waitPhrase(seconds: number): string {
  if (seconds <= 1) return "in a second";
  if (seconds < 90) return `in ${seconds} seconds`;
  const minutes = Math.round(seconds / 60);
  return `in about ${minutes} minute${minutes === 1 ? "" : "s"}`;
}

function validationMessage(err: ApiError): string {
  const first = Array.isArray(err.details) ? (err.details[0] as { field?: string; message?: string } | undefined) : undefined;
  if (first?.message) {
    const field = first.field?.split(".").pop();
    return `Check what you entered${field ? ` in “${field.replace(/_/g, " ")}”` : ""}: ${first.message}.`;
  }
  return err.message && !STATUS_LINE.test(err.message) && err.message !== "Request validation failed" ? err.message : "Check what you entered, then try again.";
}

/** Map anything a request can throw to wording for a student (see `ErrorInfo`). */
export function describeError(err: unknown): ErrorInfo {
  if (err instanceof ApiError) {
    const detail = `${err.status} ${err.code}: ${err.message}`.trim();
    const message = err.message.trim();
    if (err.code === "disabled_in_demo") return { kind: "demo", title: "Not available in the demo", message, detail };
    if (err.status === 429) {
      const retryAfter = retryAfterOf(err);
      if (err.code === "daily_limit") return { kind: "daily_limit", title: "Daily limit reached", message: DAILY_LIMIT_MESSAGE, detail, retryAfter };
      if (!message || message === BUSY_MESSAGE || GENERIC_429.test(message) || STATUS_LINE.test(message)) {
        const text = retryAfter !== undefined ? `The study service is busy right now. Try again ${waitPhrase(retryAfter)}.` : BUSY_MESSAGE;
        return { kind: "busy", title: "Busy right now", message: text, detail, retryAfter };
      }
      // Provider quota messages from the API are already written for people (and say how long to wait).
      return { kind: "quota", title: "The model is out of capacity", message, detail, retryAfter };
    }
    if (err.code === "llm_unavailable") return { kind: "llm_unavailable", title: "Answers are switched off", message: LLM_UNAVAILABLE_MESSAGE, detail };
    if (err.status === 422 && (err.code === "validation_error" || err.code === "http_error")) return { kind: "validation", title: "Check your input", message: validationMessage(err), detail };
    if (err.status === 502 || err.code === "llm_error") return { kind: "llm_error", title: "The model didn't answer", message: "The model couldn't finish this request. Try again in a moment.", detail };
    if (err.status === 503) return { kind: "unavailable", title: "Not available on this server", message: "This feature isn't available on this server right now.", detail };
    if (err.status === 401) return { kind: "other", title: "Access refused", message: "This server needs an access key that the app doesn't have.", detail };
    if (err.status >= 500) return { kind: "server", title: "Server error", message: SERVER_ERROR_MESSAGE, detail };
    if (err.status === 404 && (!message || STATUS_LINE.test(message))) return { kind: "not_found", title: "Not found", message: "That item could not be found. It may have been removed.", detail };
    if (!message || STATUS_LINE.test(message)) return { kind: "other", title: "Request failed", message: `The request failed (error ${err.status}). Try again.`, detail };
    return { kind: err.status === 404 ? "not_found" : "other", title: "Something went wrong", message, detail };
  }
  // fetch() rejects with a TypeError when the network or the server is unreachable.
  if (err instanceof TypeError) return { kind: "offline", title: "Can't reach Lectern", message: OFFLINE_MESSAGE, detail: `${err.message} (${API_URL})` };
  if (err instanceof Error && err.message) return { kind: "other", title: "Something went wrong", message: err.message };
  return { kind: "other", title: "Something went wrong", message: "Something went wrong. Try again." };
}

/** Human-readable message for anything a request can throw or return. */
export function errorMessage(err: unknown): string {
  return describeError(err).message;
}

type ErrorBody = { error?: { code?: string; message?: string; details?: unknown } };

/**
 * Unwrap an openapi-fetch result: return `data` or throw an ApiError that carries the
 * server's error code and message (so UIs can branch on `err.code`), plus `retryAfter` seconds when sent.
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const body = (result.error ?? {}) as ErrorBody;
    const status = result.response.status;
    const error = new ApiError(
      status,
      body.error?.code ?? "http_error",
      body.error?.message || (status === 429 ? BUSY_MESSAGE : `${status} ${result.response.statusText}`.trim()),
      body.error?.details,
    );
    const retryAfter = parseRetryAfter(result.response.headers.get("retry-after"));
    if (retryAfter !== undefined) Object.assign(error, { retryAfter });
    throw error;
  }
  return result.data;
}
