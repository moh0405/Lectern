"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, X } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Seconds since `running` became true; 0 when not running. */
export function useElapsed(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const id = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => {
      window.clearInterval(id);
      setSeconds(0);
    };
  }, [running]);
  return running ? seconds : 0;
}

/** One AbortController per request: `signal()` starts a new one (aborting the last), `abort()` cancels. */
export function useAbortable() {
  const ref = useRef<AbortController | null>(null);
  useEffect(() => () => ref.current?.abort(), []);
  const signal = useCallback(() => {
    ref.current?.abort();
    ref.current = new AbortController();
    return ref.current.signal;
  }, []);
  const abort = useCallback(() => ref.current?.abort(), []);
  return { signal, abort };
}

export const isAbort = (err: unknown) => err instanceof DOMException && err.name === "AbortError";

/**
 * A model-backed tool request that can be cancelled. `cancel()` aborts the fetch and returns the tool to
 * its last result, with `cancelled` set until the next run.
 */
export function useToolRequest<V, R>(fn: (vars: V, signal: AbortSignal) => Promise<R>, options: { onMutate?: () => void; onSuccess?: (data: R) => void } = {}) {
  const abort = useAbortable();
  const [cancelled, setCancelled] = useState(false);
  const run = useMutation({
    mutationFn: (vars: V) => fn(vars, abort.signal()),
    onMutate: () => {
      setCancelled(false);
      options.onMutate?.();
    },
    onSuccess: options.onSuccess,
  });
  const cancel = () => {
    abort.abort();
    run.reset();
    setCancelled(true);
  };
  const error = run.isError && !isAbort(run.error) ? run.error : null;
  return { run, cancel, cancelled, error };
}

/**
 * `focusAfterRender(id)` focuses that element once React has committed the next render (for a button
 * that is only enabled, or only exists, after the state change that asks for focus).
 */
export function useFocusAfterRender() {
  const pending = useRef<string | null>(null);
  const [tick, setTick] = useState(0);
  useLayoutEffect(() => {
    const id = pending.current;
    if (!id) return;
    pending.current = null;
    document.getElementById(id)?.focus();
  }, [tick]);
  return useCallback((id: string) => {
    pending.current = id;
    setTick((t) => t + 1);
  }, []);
}

/** A spinner that screen readers skip (the button or panel text says what is happening). */
export function BusyIcon({ className }: { className?: string }) {
  return <Loader2 aria-hidden className={cn("h-4 w-4 animate-spin", className)} />;
}

/**
 * What a model call looks like while it runs (it can take up to 90 s): what is happening, how long it
 * has taken, and a way out.
 */
export function PendingPanel({
  running,
  label = "Reading your material…",
  onCancel,
  children,
}: {
  running: boolean;
  label?: string;
  onCancel?: () => void;
  children?: ReactNode;
}) {
  const seconds = useElapsed(running);
  if (!running) return null;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-4" data-testid="pending-panel">
      <BusyIcon className="text-accent-2" />
      <div className="min-w-0 flex-1">
        <p role="status" className="text-sm font-medium">
          {label}
        </p>
        <p className="text-xs text-muted" aria-hidden>
          <span className="tabular-nums">{seconds} s</span>
          {seconds >= 15 ? " · busy models can take up to a minute and a half" : ""}
        </p>
        {children}
      </div>
      {onCancel ? (
        <Button variant="secondary" size="sm" onClick={onCancel}>
          <X className="h-4 w-4" aria-hidden /> Cancel
        </Button>
      ) : null}
    </div>
  );
}

/** A polite, visually hidden announcement (results arriving, a request cancelled). */
export function Announce({ children }: { children?: ReactNode }) {
  return (
    <p role="status" aria-live="polite" className="sr-only">
      {children}
    </p>
  );
}
