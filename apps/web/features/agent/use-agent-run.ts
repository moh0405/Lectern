"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiError, api, errorMessage } from "@/lib/api";
import { IDLE_TIMEOUT, IDLE_TIMEOUT_MS, idle, idleWatchdog, runReducer } from "./trace";

/**
 * Run the tool-using agent and follow it live. One run at a time; starting another replaces it.
 * A run always ends visibly: `done`, a server `error`, a stream that closes without either, or nothing arriving
 * for IDLE_TIMEOUT_MS all leave the page out of the running state with Run enabled again.
 */
export function useAgentRun(idleTimeoutMs = IDLE_TIMEOUT_MS) {
  const [state, dispatch] = useReducer(runReducer, idle);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(async (task: string, maxSteps: number) => {
    controller.current?.abort();
    const mine = (controller.current = new AbortController());
    dispatch({ type: "start", task });
    let timedOut = false;
    const watchdog = idleWatchdog(idleTimeoutMs, () => {
      timedOut = true;
      mine.abort();
    });
    try {
      for await (const event of api.agentRunStream({ task, max_steps: maxSteps }, mine.signal)) {
        watchdog.poke();
        dispatch({ type: "event", event });
      }
      dispatch({ type: "end" }); // an error if the stream closed without `done` or `error`
    } catch (err) {
      if (timedOut) dispatch({ type: "fail", ...IDLE_TIMEOUT });
      else if (mine.signal.aborted) dispatch({ type: "stop" });
      else dispatch({ type: "fail", code: err instanceof ApiError ? err.code : "network_error", message: errorMessage(err) });
    } finally {
      watchdog.cancel();
    }
  }, [idleTimeoutMs]);

  const stop = useCallback(() => controller.current?.abort(), []);
  const reset = useCallback(() => {
    controller.current?.abort();
    dispatch({ type: "reset" });
  }, []);

  return { state, run, stop, reset };
}
