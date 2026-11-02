import type { AgentRunEvent, Chunk, components } from "@ai-study-mentor/api-client";

type Done = components["schemas"]["SseAgentRunDone"];

export type StepStatus = "running" | "ok" | "failed";

/** One thing the agent did: a thought, or a tool call with its result once it arrives. */
export type TraceItem =
  | { kind: "thought"; text: string }
  | { kind: "tool"; name: string; arguments: Record<string, unknown>; status: StepStatus; summary?: string };

export type RunStatus = "idle" | "running" | "done" | "error" | "stopped";

export interface RunState {
  status: RunStatus;
  task: string;
  trace: TraceItem[];
  answer: string;
  chunks: Chunk[];
  done?: Done;
  error?: { code: string; message: string };
}

export const idle: RunState = { status: "idle", task: "", trace: [], answer: "", chunks: [] };

export type RunAction = { type: "start"; task: string } | { type: "event"; event: AgentRunEvent } | { type: "stop" } | { type: "fail"; code: string; message: string } | { type: "reset" };

/** Fold the agent's event stream into what the page shows. Pure, so the page's behaviour is easy to test. */
export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case "start":
      return { ...idle, status: "running", task: action.task };
    case "reset":
      return idle;
    case "stop":
      return state.status === "running" ? { ...state, status: "stopped" } : state;
    case "fail":
      return { ...state, status: "error", error: { code: action.code, message: action.message } };
    case "event": {
      const ev = action.event;
      switch (ev.event) {
        case "thought":
          return { ...state, trace: [...state.trace, { kind: "thought", text: ev.data.text }] };
        case "tool_call":
          return { ...state, trace: [...state.trace, { kind: "tool", name: ev.data.name, arguments: ev.data.arguments, status: "running" }] };
        case "tool_result": {
          // Results arrive in the order of the calls, so the first call of this tool still waiting for one is the match.
          const at = state.trace.findIndex((t) => t.kind === "tool" && t.name === ev.data.name && t.status === "running");
          if (at === -1) return state;
          const trace = state.trace.map((t, i) => (i === at && t.kind === "tool" ? { ...t, status: ev.data.error ? ("failed" as const) : ("ok" as const), summary: ev.data.summary } : t));
          return { ...state, trace };
        }
        case "meta":
          return { ...state, chunks: ev.data.chunks };
        case "token":
          return { ...state, answer: state.answer + ev.data.text };
        case "done":
          return { ...state, status: "done", done: ev.data };
        case "error":
          return { ...state, status: "error", error: { code: ev.data.code, message: ev.data.message } };
      }
    }
  }
}
