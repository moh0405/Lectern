"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { api, ApiError, errorMessage, unwrap } from "@/lib/api";
import { retrieveLocal } from "@/lib/browser-rag/retrieve";
import { useDemo } from "@/lib/demo";
import { fromSavedTurn, initialSession, loadTurns, saveTurns, sessionReducer, toHistoryTurn, type AttemptFormat, type Mode, type Turn } from "./session";

export interface AskParams {
  guided?: boolean;
  /** Try first: the student's own attempt, judged against the passages before any answer is shown. */
  attempt?: { text: string; format: AttemptFormat; language?: string };
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
    loaded.filter((t) => t.answer).forEach((t) => synced.current.add(t.id));
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
      if (!t.answer) continue; // Hints and retrieval-only lookups are not answers.
      synced.current.add(t.id);
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

  const evidenceRuns = useRef(new Set<string>());
  const ask = useCallback(async (p: AskParams, existing?: Turn, evidence = false) => {
    const id = existing?.id ?? newId();
    if (existing && !evidence && (existing.guided?.hints !== undefined || existing.attempt?.feedback !== undefined || controllers.current.has(id))) return;
    if (existing && [...controllers.current.keys()].some((key) => key !== id)) return;
    if (evidence && (evidenceRuns.current.has(id) || ((existing?.guided?.evidenceStarted || existing?.attempt?.evidenceStarted) && existing.status !== "error" && existing.status !== "stopped"))) return;
    if (evidence) evidenceRuns.current.add(id);
    controllers.current.get(id)?.abort();
    const controller = new AbortController();
    controllers.current.set(id, controller);
    const agent = Boolean(p.agent) && !p.local && !p.retrievalOnly;
    const guiding = Boolean(p.guided) && !evidence;
    const attempting = Boolean(p.attempt) && !guiding && !evidence;
    if (existing) dispatch({ type: "resume", id, evidence, agent: evidence && agent });
    else dispatch({ type: "start", id, question: p.question, mode: p.mode, agent: !guiding && !attempting && agent, local: Boolean(p.local),
      guided: guiding ? { params: p, revealed: 0, evidenceStarted: false } : undefined,
      attempt: attempting && p.attempt ? { params: p, text: p.attempt.text, format: p.attempt.format, language: p.attempt.language, evidenceStarted: false } : undefined });
    try {
      let context: Awaited<ReturnType<typeof retrieveLocal>> | undefined;
      if (p.local) {
        context = await retrieveLocal(p.question, p.k);
        if (controller.signal.aborted) {
          if (controllers.current.get(id) === controller) dispatch({ type: "stop", id });
          return;
        }
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
      if (controller.signal.aborted) {
        if (controllers.current.get(id) === controller) dispatch({ type: "stop", id });
        return;
      }
      if (guiding) {
        const result = unwrap(await api.http.POST("/api/v1/socratic", {
          body: { question: p.question, k: Math.min(p.k, 10), temperature: p.temperature, context }, signal: controller.signal,
        }));
        if (result.warning) throw new Error("Source-based hints are unavailable right now. Try again or show the evidence.");
        if (!controller.signal.aborted) dispatch({ type: "hints", id, hints: result.hints });
        return;
      }
      if (attempting && p.attempt) {
        // One model call; the passages come back with the feedback so each verdict can open its passage.
        const feedback = unwrap(await api.http.POST("/api/v1/attempt/feedback", {
          body: { question: p.question, attempt: p.attempt.text, format: p.attempt.format, language: p.attempt.language || undefined,
            k: Math.min(p.k, 10), temperature: p.temperature, model: p.model || undefined, context },
          signal: controller.signal,
        }));
        if (!controller.signal.aborted) dispatch({ type: "feedback", id, feedback });
        return;
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
      if (controllers.current.get(id) !== controller) return;
      if (controller.signal.aborted) dispatch({ type: "stop", id });
      else
        dispatch({
          type: "error",
          id,
          code: err instanceof ApiError ? err.code : "network_error",
          message: errorMessage(err),
        });
    } finally {
      if (controllers.current.get(id) === controller) {
        controllers.current.delete(id);
        evidenceRuns.current.delete(id);
      }
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

  const nextHint = (id: string) => dispatch({ type: "next-hint", id });
  const retryHints = (t: Turn) => t.guided && ask({ ...t.guided.params, guided: true }, t);
  const retryFeedback = (t: Turn) => t.attempt && ask(t.attempt.params, t);
  const showEvidence = (t: Turn) => {
    const params = t.attempt?.params ?? t.guided?.params;
    return params ? ask({ ...params, guided: false, attempt: undefined }, t, true) : undefined;
  };
  return { turns, ask, nextHint, retryHints, retryFeedback, showEvidence, stop, remove, clear, busy: turns.some((t) => t.status === "streaming") };
}
