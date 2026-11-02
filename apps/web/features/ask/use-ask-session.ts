"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { api, ApiError, errorMessage, unwrap } from "@/lib/api";
import { retrieveLocal } from "@/lib/browser-rag/retrieve";
import { useDemo } from "@/lib/demo";
import { fromSavedTurn, initialSession, loadTurns, saveTurns, sessionReducer, toHistoryTurn, type Mode, type Turn } from "./session";

export interface AskParams {
  question: string;
  mode?: Mode;
  k: number;
  temperature: number;
  model?: string;
  showPrompt?: boolean;
  /** Ask the model again instead of reusing a cached answer. */
  noCache?: boolean;
  /** Skip the model: just list the passages that match. */
  retrievalOnly?: boolean;
  /** Search the visitor's own documents (kept in this browser) instead of the server's index. */
  local?: boolean;
  /** Use the agentic (LangGraph) workflow: rewrite the search, grade the passages, verify the citations. */
  agent?: boolean;
}

/** Run a server call whose failure must never disturb the UI (a sync or throw is swallowed too). */
async function bestEffort(call: () => unknown): Promise<void> {
  try {
    await call();
  } catch {
    /* offline or unavailable */
  }
}

async function saveRemote(turn: Turn, ids: Map<string, number>): Promise<void> {
  try {
    const res = await api.http.POST("/api/v1/history", { body: toHistoryTurn(turn) });
    if (res?.data) ids.set(turn.id, res.data.id);
  } catch {
    /* offline: the turn stays in this browser only */
  }
}

let counter = 0;
const newId = () => `${Date.now().toString(36)}-${(counter++).toString(36)}`;

export function useAskSession() {
  const demo = useDemo(); // the public demo keeps no server-side history, so do not ask it to
  const [{ turns, hydrated }, dispatch] = useReducer(sessionReducer, initialSession);
  const controllers = useRef(new Map<string, AbortController>());
  // Saving is gated on `hydrated` (state, not a ref): the first commit must not write the empty
  // initial list over what is in storage before the restored turns have been applied.
  // History is also kept on the server, so it survives clearing the browser. Server calls are best-effort:
  // if the API is unreachable the session still works from this browser's own storage.
  const synced = useRef(new Set<string>());
  const serverIds = useRef(new Map<string, number>());

  useEffect(() => {
    const loaded = loadTurns();
    loaded.forEach((t) => synced.current.add(t.id));
    dispatch({ type: "hydrate", turns: loaded });
    if (loaded.length > 0 || demo) return;
    void (async () => {
      try {
        const res = await api.http.GET("/api/v1/history", { params: { query: { limit: 20 } } });
        const restored = res?.data?.turns?.map(fromSavedTurn) ?? [];
        restored.forEach((t) => {
          synced.current.add(t.id);
          serverIds.current.set(t.id, Number(t.id.slice(4)));
        });
        if (restored.length > 0) dispatch({ type: "restore", turns: restored });
      } catch {
        /* offline: nothing to restore */
      }
    })();
  }, [demo]);

  useEffect(() => {
    if (!hydrated) return;
    for (const t of turns) {
      if (t.status !== "done" || synced.current.has(t.id)) continue;
      synced.current.add(t.id);
      if (!t.answer) continue; // retrieval-only lookups are not history
      if (!demo) void saveRemote(t, serverIds.current);
    }
  }, [turns, hydrated, demo]);

  useEffect(() => {
    if (hydrated) saveTurns(turns);
  }, [turns, hydrated]);

  useEffect(() => {
    const map = controllers.current;
    return () => map.forEach((c) => c.abort());
  }, []);

  const ask = useCallback(async (p: AskParams) => {
    const id = newId();
    const controller = new AbortController();
    controllers.current.set(id, controller);
    const agent = Boolean(p.agent) && !p.local && !p.retrievalOnly;
    dispatch({ type: "start", id, question: p.question, mode: p.mode, agent });
    try {
      let context: Awaited<ReturnType<typeof retrieveLocal>> | undefined;
      if (p.local) {
        context = await retrieveLocal(p.question, p.k);
        if (context.length === 0) {
          // Never fall through to the shared index: the question was about the visitor's own documents.
          dispatch({ type: "meta", id, chunks: [] });
          dispatch({ type: "error", id, code: "no_local_match", message: "Nothing in your documents matches that question. Try other words, or add more material on the Sources page." });
          return;
        }
        if (p.retrievalOnly) {
          dispatch({ type: "meta", id, chunks: context });
          dispatch({ type: "done", id });
          return;
        }
      }
      if (p.retrievalOnly) {
        const res = unwrap(await api.http.GET("/api/v1/search", { params: { query: { query: p.question, k: p.k } }, signal: controller.signal }));
        dispatch({ type: "meta", id, chunks: res.chunks });
        dispatch({ type: "done", id });
        return;
      }
      const body = {
        question: p.question,
        k: p.k,
        mode: p.mode,
        temperature: p.temperature,
        model: p.model || undefined,
        include_prompt: p.showPrompt || undefined,
        no_cache: p.noCache || undefined,
        context,
      };
      if (agent) {
        const agentBody = { question: p.question, k: Math.min(p.k, 10), mode: p.mode, temperature: p.temperature, model: p.model || undefined };
        for await (const ev of api.askAgentStream(agentBody, controller.signal)) {
          if (ev.event === "step") dispatch({ type: "step", id, step: ev.data });
          else if (ev.event === "meta") dispatch({ type: "meta", id, chunks: ev.data.chunks });
          else if (ev.event === "token") dispatch({ type: "token", id, text: ev.data.text });
          else if (ev.event === "replace") dispatch({ type: "replace", id });
          else if (ev.event === "done")
            dispatch({ type: "done", id, model: ev.data.model ?? undefined, citations: ev.data.citations, uncited: ev.data.uncited, cached: false, llmCalls: ev.data.llm_calls, rewritten: ev.data.regenerated });
          else dispatch({ type: "error", id, code: ev.data.code, message: ev.data.message });
        }
        return;
      }
      for await (const ev of api.askStream(body, controller.signal)) {
        if (ev.event === "meta") dispatch({ type: "meta", id, chunks: ev.data.chunks, prompt: ev.data.prompt ?? undefined });
        else if (ev.event === "token") dispatch({ type: "token", id, text: ev.data.text });
        else if (ev.event === "done")
          dispatch({
            type: "done",
            id,
            model: ev.data.model ?? undefined,
            citations: ev.data.citations,
            uncited: ev.data.uncited,
            cached: ev.data.cached,
          });
        else dispatch({ type: "error", id, code: ev.data.code, message: ev.data.message });
      }
    } catch (err) {
      if (controller.signal.aborted) dispatch({ type: "stop", id });
      else
        dispatch({
          type: "error",
          id,
          code: err instanceof ApiError ? err.code : "network_error",
          message: errorMessage(err),
        });
    } finally {
      controllers.current.delete(id);
    }
  }, []);

  const stop = useCallback((id: string) => controllers.current.get(id)?.abort(), []);
  const remove = useCallback((id: string) => {
    dispatch({ type: "remove", id });
    const serverId = serverIds.current.get(id);
    if (serverId !== undefined) {
      serverIds.current.delete(id);
      if (!demo) void bestEffort(() => api.http.DELETE("/api/v1/history/{turn_id}", { params: { path: { turn_id: serverId } } }));
    }
  }, [demo]);
  const clear = useCallback(() => {
    controllers.current.forEach((c) => c.abort());
    dispatch({ type: "clear" });
    serverIds.current.clear();
    if (!demo) void bestEffort(() => api.http.DELETE("/api/v1/history"));
  }, [demo]);

  return { turns, ask, stop, remove, clear, busy: turns.some((t) => t.status === "streaming") };
}
