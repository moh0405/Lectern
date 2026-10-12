"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { api, ApiError, errorMessage } from "@/lib/api";
import { initialSession, loadTurns, saveTurns, sessionReducer, type Mode } from "./session";

export interface AskParams {
  question: string;
  mode?: Mode;
  k: number;
  temperature: number;
  model?: string;
}

let counter = 0;
const newId = () => `${Date.now().toString(36)}-${(counter++).toString(36)}`;

export function useAskSession() {
  const [{ turns, hydrated }, dispatch] = useReducer(sessionReducer, initialSession);
  const controllers = useRef(new Map<string, AbortController>());
  // Saving is gated on `hydrated` (state, not a ref): the first commit must not write the empty
  // initial list over what is in storage before the restored turns have been applied.
  useEffect(() => {
    dispatch({ type: "hydrate", turns: loadTurns() });
  }, []);

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
    dispatch({ type: "start", id, question: p.question, mode: p.mode });
    try {
      const body = { question: p.question, k: p.k, mode: p.mode, temperature: p.temperature, model: p.model || undefined };
      for await (const ev of api.askStream(body, controller.signal)) {
        if (ev.event === "meta") dispatch({ type: "meta", id, chunks: ev.data.chunks });
        else if (ev.event === "token") dispatch({ type: "token", id, text: ev.data.text });
        else if (ev.event === "done") dispatch({ type: "done", id, model: ev.data.model ?? undefined });
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
  const remove = useCallback((id: string) => dispatch({ type: "remove", id }), []);
  const clear = useCallback(() => {
    controllers.current.forEach((c) => c.abort());
    dispatch({ type: "clear" });
  }, []);

  return { turns, ask, stop, remove, clear, busy: turns.some((t) => t.status === "streaming") };
}
