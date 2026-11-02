"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiError, api, errorMessage } from "@/lib/api";
import { idle, runReducer } from "./trace";

/** Run the tool-using agent and follow it live. One run at a time; starting another replaces it. */
export function useAgentRun() {
  const [state, dispatch] = useReducer(runReducer, idle);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(async (task: string, maxSteps: number) => {
    controller.current?.abort();
    const mine = (controller.current = new AbortController());
    dispatch({ type: "start", task });
    try {
      for await (const event of api.agentRunStream({ task, max_steps: maxSteps }, mine.signal)) dispatch({ type: "event", event });
    } catch (err) {
      if (mine.signal.aborted) dispatch({ type: "stop" });
      else dispatch({ type: "fail", code: err instanceof ApiError ? err.code : "network_error", message: errorMessage(err) });
    }
  }, []);

  const stop = useCallback(() => controller.current?.abort(), []);
  const reset = useCallback(() => {
    controller.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  return { state, run, stop, reset };
}
