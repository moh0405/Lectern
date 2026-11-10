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

/** Human-readable message for anything a request can throw or return. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429 && (!err.message.trim() || /^(429(?: too many requests)?|rate limit exceeded|too many requests)$/i.test(err.message.trim()))) return BUSY_MESSAGE;
    return err.message;
  }
  if (err instanceof TypeError) return `Cannot reach the API at ${API_URL}. Is the backend running?`;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}

type ErrorBody = { error?: { code?: string; message?: string; details?: unknown } };

/**
 * Unwrap an openapi-fetch result: return `data` or throw an ApiError that carries the
 * server's error code and message (so UIs can branch on `err.code`).
 */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const body = (result.error ?? {}) as ErrorBody;
    throw new ApiError(
      result.response.status,
      body.error?.code ?? "http_error",
      body.error?.message || (result.response.status === 429 ? BUSY_MESSAGE : `${result.response.status} ${result.response.statusText}`.trim()),
      body.error?.details,
    );
  }
  return result.data;
}
