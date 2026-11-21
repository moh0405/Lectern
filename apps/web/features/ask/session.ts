import type { Chunk, components } from "@ai-study-mentor/api-client";

export type CitationCheck = components["schemas"]["CitationCheck"];

export type Mode = "eli5" | "technical" | "interview" | "summary";
export type TurnStatus = "streaming" | "done" | "error" | "stopped";
export interface AgentStep {
  name: string;
  detail: string;
}

export interface Guided {
  params: { question: string; mode?: Mode; k: number; temperature: number; model?: string; showPrompt?: boolean; local?: boolean; agent?: boolean };
  hints?: string[];
  revealed: number;
  evidenceStarted: boolean;
}

export interface Turn {
  id: string;
  question: string;
  mode?: Mode;
  answer: string;
  chunks: Chunk[];
  model?: string;
  /** The exact prompt sent to the model, when the user asked to see it. */
  prompt?: string;
  /** Citations in the answer, checked by the server against the passages the model was given. */
  citations?: CitationCheck[];
  uncited?: boolean;
  cached?: boolean;
  /** Set for answers from the agentic (LangGraph) workflow: what it did, in order. */
  agent?: boolean;
  steps?: AgentStep[];
  /** True when the first answer cited unknown sources and the workflow rewrote it. */
  rewritten?: boolean;
  llmCalls?: number;
  /** Answered from documents kept in this browser (public demo), not the shared index. */
  local?: boolean;
  guided?: Guided;
  status: TurnStatus;
  error?: { code: string; message: string };
}

export type Action =
  | { type: "start"; id: string; question: string; mode?: Mode; agent?: boolean; local?: boolean; guided?: Guided }
  | { type: "resume"; id: string; evidence: boolean; agent?: boolean }
  | { type: "hints"; id: string; hints: string[] }
  | { type: "next-hint"; id: string }
  | { type: "step"; id: string; step: AgentStep }
  /** The agentic workflow discards the answer streamed so far; a corrected one follows. */
  | { type: "replace"; id: string }
  | { type: "meta"; id: string; chunks: Chunk[]; prompt?: string }
  | { type: "token"; id: string; text: string }
  | { type: "done"; id: string; model?: string; citations?: CitationCheck[]; uncited?: boolean; cached?: boolean; llmCalls?: number; rewritten?: boolean }
  | { type: "error"; id: string; code: string; message: string }
  | { type: "stop"; id: string }
  | { type: "remove"; id: string }
  | { type: "clear" }
  | { type: "hydrate"; turns: Turn[] }
  /** Turns loaded from the server; applied only while this browser has none of its own. */
  | { type: "restore"; turns: Turn[] };

const update = (turns: Turn[], id: string, fn: (t: Turn) => Turn) => turns.map((t) => (t.id === id ? fn(t) : t));

/** Newest turn first. */
export function reducer(turns: Turn[], action: Action): Turn[] {
  switch (action.type) {
    case "start":
      return [
        { id: action.id, question: action.question, mode: action.mode, answer: "", chunks: [], status: "streaming", guided: action.guided, ...(action.agent ? { agent: true, steps: [] } : {}), ...(action.local ? { local: true } : {}) },
        ...turns,
      ];
    case "resume":
      return update(turns, action.id, (t) => ({ ...t, status: "streaming", error: undefined, agent: action.agent ?? t.agent,
        guided: t.guided ? { ...t.guided, evidenceStarted: t.guided.evidenceStarted || action.evidence } : undefined }));
    case "hints":
      return update(turns, action.id, (t) => ({ ...t, status: "done", guided: t.guided ? { ...t.guided, hints: action.hints, revealed: Math.min(1, action.hints.length) } : undefined }));
    case "next-hint":
      return update(turns, action.id, (t) => ({ ...t, guided: t.guided ? { ...t.guided, revealed: Math.min(t.guided.revealed + 1, t.guided.hints?.length ?? 0) } : undefined }));
    case "step":
      return update(turns, action.id, (t) => ({ ...t, steps: [...(t.steps ?? []), action.step] }));
    case "replace":
      return update(turns, action.id, (t) => ({ ...t, answer: "", rewritten: true }));
    case "meta":
      return update(turns, action.id, (t) => ({ ...t, chunks: action.chunks, prompt: action.prompt ?? t.prompt }));
    case "token":
      return update(turns, action.id, (t) => ({ ...t, answer: t.answer + action.text }));
    case "done":
      return update(turns, action.id, (t) => ({
        ...t,
        status: "done",
        model: action.model ?? t.model,
        citations: action.citations ?? t.citations,
        uncited: action.uncited ?? t.uncited,
        cached: action.cached ?? t.cached,
        llmCalls: action.llmCalls ?? t.llmCalls,
        rewritten: action.rewritten ?? t.rewritten,
      }));
    case "error":
      return update(turns, action.id, (t) => ({ ...t, status: "error", error: { code: action.code, message: action.message } }));
    case "stop":
      return update(turns, action.id, (t) => (t.status === "streaming" ? { ...t, status: "stopped" } : t));
    case "remove":
      return turns.filter((t) => t.id !== action.id);
    case "clear":
      return [];
    case "hydrate":
      return action.turns;
    case "restore":
      return turns.length === 0 ? action.turns : turns;
  }
}

export interface SessionState {
  turns: Turn[];
  /** False until stored turns have been applied; nothing may be saved before then. */
  hydrated: boolean;
}

export const initialSession: SessionState = { turns: [], hydrated: false };

export function sessionReducer(state: SessionState, action: Action): SessionState {
  if (action.type === "hydrate") return { turns: action.turns, hydrated: true };
  return { ...state, turns: reducer(state.turns, action) };
}

const STORAGE_KEY = "asm.ask.turns.v1";
const MAX_SAVED = 20;

/** Persist finished turns only; a reload must never resurrect a half-streamed answer. */
export function saveTurns(turns: Turn[]): void {
  try {
    const finished = turns.filter((t) => t.status !== "streaming").slice(0, MAX_SAVED);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(finished));
  } catch {
    /* storage unavailable (private mode, quota): the session just is not remembered */
  }
}

export function loadTurns(): Turn[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (t): t is Turn => typeof t?.id === "string" && typeof t?.question === "string" && typeof t?.answer === "string" && Array.isArray(t?.chunks),
    );
  } catch {
    return [];
  }
}

type SavedTurn = components["schemas"]["SavedTurn"];
type HistoryTurn = components["schemas"]["HistoryTurn"];

/** The body that saves a finished turn on the server. */
export function toHistoryTurn(t: Turn): HistoryTurn {
  return {
    question: t.question,
    answer: t.answer,
    mode: t.mode ?? null,
    model: t.model ?? null,
    cached: t.cached ?? false,
    chunks: t.chunks,
    citations: t.citations ?? [],
    unverified_citations: (t.citations ?? []).filter((c) => c.status !== "ok").length,
    uncited: t.uncited ?? false,
  };
}

/** A turn restored from the server. Ids are prefixed so they cannot collide with locally made ones. */
export function fromSavedTurn(s: SavedTurn): Turn {
  return {
    id: `srv-${s.id}`,
    question: s.question,
    answer: s.answer ?? "",
    mode: (s.mode as Mode | null) ?? undefined,
    model: s.model ?? undefined,
    cached: s.cached ?? false,
    chunks: s.chunks ?? [],
    citations: s.citations ?? [],
    uncited: s.uncited ?? false,
    status: "done",
  };
}
