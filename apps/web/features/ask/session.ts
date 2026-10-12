import type { Chunk } from "@ai-study-mentor/api-client";

export type Mode = "eli5" | "technical" | "interview" | "summary";
export type TurnStatus = "streaming" | "done" | "error" | "stopped";

export interface Turn {
  id: string;
  question: string;
  mode?: Mode;
  answer: string;
  chunks: Chunk[];
  model?: string;
  /** The exact prompt sent to the model, when the user asked to see it. */
  prompt?: string;
  status: TurnStatus;
  error?: { code: string; message: string };
}

export type Action =
  | { type: "start"; id: string; question: string; mode?: Mode }
  | { type: "meta"; id: string; chunks: Chunk[]; prompt?: string }
  | { type: "token"; id: string; text: string }
  | { type: "done"; id: string; model?: string }
  | { type: "error"; id: string; code: string; message: string }
  | { type: "stop"; id: string }
  | { type: "remove"; id: string }
  | { type: "clear" }
  | { type: "hydrate"; turns: Turn[] };

const update = (turns: Turn[], id: string, fn: (t: Turn) => Turn) => turns.map((t) => (t.id === id ? fn(t) : t));

/** Newest turn first. */
export function reducer(turns: Turn[], action: Action): Turn[] {
  switch (action.type) {
    case "start":
      return [
        { id: action.id, question: action.question, mode: action.mode, answer: "", chunks: [], status: "streaming" },
        ...turns,
      ];
    case "meta":
      return update(turns, action.id, (t) => ({ ...t, chunks: action.chunks, prompt: action.prompt ?? t.prompt }));
    case "token":
      return update(turns, action.id, (t) => ({ ...t, answer: t.answer + action.text }));
    case "done":
      return update(turns, action.id, (t) => ({ ...t, status: "done", model: action.model ?? t.model }));
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
