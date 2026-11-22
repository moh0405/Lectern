import type { Chunk, components } from "@ai-study-mentor/api-client";

export type CitationCheck = components["schemas"]["CitationCheck"];

export type Mode = "eli5" | "technical" | "interview" | "summary";
export type TurnStatus = "streaming" | "done" | "error" | "stopped";
export interface AgentStep {
  name: string;
  detail: string;
}

/** What a turn needs to ask for its cited answer later ("Show me the evidence"). */
export interface AskSettings { question: string; mode?: Mode; k: number; temperature: number; model?: string; showPrompt?: boolean; local?: boolean; agent?: boolean; passages?: components["schemas"]["ContextPassage"][] }

export interface Guided {
  params: AskSettings;
  hints?: string[];
  revealed: number;
  evidenceStarted: boolean;
}

export type AttemptFormat = components["schemas"]["AttemptFeedbackRequest"]["format"] & string;
export type AttemptFeedback = components["schemas"]["AttemptFeedback"];
export type AttemptItem = components["schemas"]["AttemptItem"];

/** Try first: the student's own attempt, the feedback on it, and whether the cited answer has been asked for. */
export interface Attempt {
  params: AskSettings;
  text: string;
  format: AttemptFormat;
  language?: string;
  feedback?: AttemptFeedback;
  evidenceStarted: boolean;
}

/** A practice question written from this turn's passages. Its answer is never sent to the browser. */
export interface SimilarExample { question: string; citations: CitationCheck[] }
/** The same idea explained at another level. */
export interface Explanation { answer: string; warning?: string }

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
  attempt?: Attempt;
  /** The learner's own-words note. */
  note?: string;
  /** This turn's row in the server's history, once saved. */
  serverId?: number;
  /** Kept on the turn so nothing is fetched twice. */
  similar?: SimilarExample[];
  explanations?: Record<string, Explanation>;
  status: TurnStatus;
  error?: { code: string; message: string };
}

export type Action =
  | { type: "start"; id: string; question: string; mode?: Mode; agent?: boolean; local?: boolean; guided?: Guided; attempt?: Attempt }
  | { type: "resume"; id: string; evidence: boolean; agent?: boolean }
  | { type: "hints"; id: string; hints: string[] }
  | { type: "next-hint"; id: string }
  | { type: "feedback"; id: string; feedback: AttemptFeedback }
  | { type: "step"; id: string; step: AgentStep }
  /** The agentic workflow discards the answer streamed so far; a corrected one follows. */
  | { type: "replace"; id: string }
  | { type: "meta"; id: string; chunks: Chunk[]; prompt?: string }
  | { type: "token"; id: string; text: string }
  | { type: "done"; id: string; model?: string; citations?: CitationCheck[]; uncited?: boolean; cached?: boolean; llmCalls?: number; rewritten?: boolean }
  | { type: "error"; id: string; code: string; message: string }
  | { type: "stop"; id: string }
  | { type: "remove"; id: string }
  | { type: "note"; id: string; note: string }
  | { type: "saved"; id: string; serverId: number }
  | { type: "similar"; id: string; example: SimilarExample }
  | { type: "explanation"; id: string; level: string; explanation: Explanation }
  | { type: "clear" }
  | { type: "hydrate"; turns: Turn[] }
  /** Turns loaded from the server; applied only while this browser has none of its own. */
  | { type: "restore"; turns: Turn[] };

const samePassage = (a: Chunk, b: Chunk) => a.doc === b.doc && a.page === b.page && a.text === b.text;

const update = (turns: Turn[], id: string, fn: (t: Turn) => Turn) => turns.map((t) => (t.id === id ? fn(t) : t));

/** Newest turn first. */
export function reducer(turns: Turn[], action: Action): Turn[] {
  switch (action.type) {
    case "start":
      return [
        { id: action.id, question: action.question, mode: action.mode, answer: "", chunks: [], status: "streaming", guided: action.guided, attempt: action.attempt, ...(action.agent ? { agent: true, steps: [] } : {}), ...(action.local ? { local: true } : {}) },
        ...turns,
      ];
    case "resume":
      return update(turns, action.id, (t) => ({ ...t, status: "streaming", error: undefined, agent: action.agent ?? t.agent,
        ...(action.evidence ? { answer: "", chunks: [], citations: undefined, uncited: undefined, cached: undefined, prompt: undefined, steps: [], model: undefined, llmCalls: undefined, rewritten: undefined } : {}),
        guided: t.guided ? { ...t.guided, evidenceStarted: t.guided.evidenceStarted || action.evidence } : undefined,
        attempt: t.attempt ? { ...t.attempt, evidenceStarted: t.attempt.evidenceStarted || action.evidence } : undefined }));
    case "feedback":
      return update(turns, action.id, (t) => ({ ...t, status: "done", chunks: action.feedback.chunks, model: action.feedback.model ?? undefined,
        attempt: t.attempt ? { ...t.attempt, feedback: action.feedback } : undefined }));
    case "hints":
      return update(turns, action.id, (t) => ({ ...t, status: "done", guided: t.guided ? { ...t.guided, hints: action.hints, revealed: Math.min(1, action.hints.length) } : undefined }));
    case "next-hint":
      return update(turns, action.id, (t) => ({ ...t, guided: t.guided ? { ...t.guided, revealed: Math.min(t.guided.revealed + 1, t.guided.hints?.length ?? 0) } : undefined }));
    case "step":
      return update(turns, action.id, (t) => ({ ...t, steps: [...(t.steps ?? []), action.step] }));
    case "replace":
      return update(turns, action.id, (t) => ({ ...t, answer: "", rewritten: true }));
    case "meta":
      return update(turns, action.id, (t) => {
        // After Try first, keep the passages the feedback cited reachable from its verdicts, after the answer's own.
        const fed = t.attempt?.evidenceStarted ? (t.attempt.feedback?.chunks ?? []) : [];
        const chunks = [...action.chunks, ...fed.filter((c) => !action.chunks.some((a) => samePassage(a, c)))];
        return { ...t, chunks, prompt: action.prompt ?? t.prompt };
      });
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
    case "note":
      return update(turns, action.id, (t) => ({ ...t, note: action.note || undefined }));
    case "saved":
      return update(turns, action.id, (t) => ({ ...t, serverId: action.serverId }));
    case "similar":
      return update(turns, action.id, (t) => ({ ...t, similar: [...(t.similar ?? []), action.example] }));
    case "explanation":
      return update(turns, action.id, (t) => ({ ...t, explanations: { ...t.explanations, [action.level]: action.explanation } }));
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
    ...(t.note ? { note: t.note } : {}),
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
    note: s.note ?? undefined,
    serverId: s.id,
    status: "done",
  };
}
