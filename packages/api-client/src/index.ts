import createClient, { type Client } from "openapi-fetch";
import type { components, paths } from "./schema";
import { readSse } from "./sse";

export type { components, paths } from "./schema";
export { readSse } from "./sse";
export type { SseFrame } from "./sse";

type Schemas = components["schemas"];
export type AskRequest = Schemas["AskRequest"];
export type AgentAskRequest = Schemas["AgentAskRequest"];
export type Chunk = Schemas["Chunk"];
export type ErrorResponse = Schemas["ErrorResponse"];

/** Events emitted by POST /api/v1/ask/stream, in order: meta, token*, then done or error. */
export type AskStreamEvent =
  | { event: "meta"; data: Schemas["SseMeta"] }
  | { event: "token"; data: Schemas["SseToken"] }
  | { event: "done"; data: Schemas["SseDone"] }
  | { event: "error"; data: Schemas["SseError"] };

/** Events from POST /api/v1/ask/agent/stream: step*, meta, token*, replace?, token*, step, then done or error. */
export type AgentStreamEvent =
  | { event: "step"; data: Schemas["SseStep"] }
  | { event: "meta"; data: Schemas["SseMeta"] }
  | { event: "token"; data: Schemas["SseToken"] }
  /** Discard the answer streamed so far; a corrected one follows. */
  | { event: "replace"; data: Schemas["SseReplace"] }
  | { event: "done"; data: Schemas["SseAgentDone"] }
  | { event: "error"; data: Schemas["SseError"] };

export interface ApiClientOptions {
  /** e.g. "http://localhost:8000" */
  baseUrl: string;
  /** Sent as X-API-Key when the server has API_KEY set. */
  apiKey?: string;
  fetch?: typeof fetch;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface AiStudyMentorClient {
  /** Typed openapi-fetch client: `api.http.GET("/api/v1/stats")`, `api.http.POST("/api/v1/ask", { body })`, ... */
  http: Client<paths>;
  /** Stream an answer. Yields typed events; throws ApiError for HTTP-level failures (4xx/5xx before streaming starts). */
  askStream(body: AskRequest, signal?: AbortSignal): AsyncGenerator<AskStreamEvent>;
  /** Stream an answer from the agentic (LangGraph) workflow: the same transport, plus `step` and `replace` events. */
  askAgentStream(body: AgentAskRequest, signal?: AbortSignal): AsyncGenerator<AgentStreamEvent>;
}

export function createApiClient(options: ApiClientOptions): AiStudyMentorClient {
  const baseUrl = options.baseUrl.replace(/\/$/, "");
  const doFetch = options.fetch ?? fetch;
  const headers: Record<string, string> = options.apiKey ? { "X-API-Key": options.apiKey } : {};
  const http = createClient<paths>({ baseUrl, headers, fetch: doFetch });

  async function* postSse<T>(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<T> {
    const res = await doFetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...headers },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok || !res.body) throw await toApiError(res);
    for await (const frame of readSse(res.body)) {
      yield { event: frame.event, data: JSON.parse(frame.data) } as T;
    }
  }

  const askStream = (body: AskRequest, signal?: AbortSignal) => postSse<AskStreamEvent>("/api/v1/ask/stream", body, signal);
  const askAgentStream = (body: AgentAskRequest, signal?: AbortSignal) => postSse<AgentStreamEvent>("/api/v1/ask/agent/stream", body, signal);

  return { http, askStream, askAgentStream };
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const { error } = (await res.json()) as ErrorResponse;
    return new ApiError(res.status, error.code, error.message, error.details);
  } catch {
    return new ApiError(res.status, "http_error", `${res.status} ${res.statusText}`);
  }
}
