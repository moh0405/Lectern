"use client";

import { AlertTriangle, Info, RotateCcw } from "lucide-react";
import { describeError, type ErrorInfo } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { Notice } from "@/components/ui/feedback";
import { cn } from "@/lib/utils";

/** Kinds that are a state of the server rather than something that broke; shown calmly (warning, not alert). */
const CALM = new Set<ErrorInfo["kind"]>(["llm_unavailable", "daily_limit", "demo", "busy", "quota"]);

export interface LlmErrorProps {
  error: unknown;
  /** Shows a "Try again" button that calls this. */
  onRetry?: () => void;
  retryLabel?: string;
  /** Disables the retry button while a retry is running. */
  retrying?: boolean;
  /** Overrides the title chosen for the kind of error. */
  title?: string;
  className?: string;
}

/**
 * Error display for anything that calls the API (especially the language model): a titled, student-facing
 * explanation, an optional retry, and the technical detail tucked into a disclosure. On the public demo
 * the detail is left out (it can name server configuration).
 */
export function LlmError({ error, onRetry, retryLabel = "Try again", retrying = false, title, className }: LlmErrorProps) {
  const demo = useDemo();
  const info = describeError(error);
  const calm = CALM.has(info.kind);
  const Icon = calm ? Info : AlertTriangle;
  return (
    <div
      role={calm ? "status" : "alert"}
      data-error-kind={info.kind}
      className={cn(
        "flex items-start gap-3 rounded-lg border p-3 text-sm",
        calm ? "border-warn/40 bg-warn/10" : "border-bad/40 bg-bad/10",
        className,
      )}
    >
      <Icon aria-hidden="true" className={cn("mt-0.5 h-4 w-4 shrink-0", calm ? "text-warn" : "text-bad")} />
      <div className="min-w-0 flex-1 space-y-1">
        <p className={cn("font-semibold", calm ? "text-warn" : "text-bad")}>{title ?? info.title}</p>
        <p className="text-fg">{info.message}</p>
        {onRetry || (info.detail && !demo) ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                disabled={retrying}
                className="lectern-button inline-flex min-h-10 items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 text-sm font-medium text-fg hover:border-accent/60 disabled:opacity-50"
              >
                <RotateCcw aria-hidden="true" className="h-3.5 w-3.5" />
                {retrying ? "Trying again…" : retryLabel}
              </button>
            ) : null}
            {info.detail && !demo ? (
              <details className="text-xs text-muted">
                <summary className="cursor-pointer select-none py-2">Technical details</summary>
                <code className="block whitespace-pre-wrap break-words font-mono">{info.detail}</code>
              </details>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** Shown when the API answered with a built-in offline fallback instead of the model. */
export function FallbackNotice({ warning }: { warning?: string | null }) {
  if (!warning) return null;
  return (
    <Notice>
      This is a basic offline fallback, not a model answer. Reason: <span className="font-mono text-xs">{warning}</span>
    </Notice>
  );
}
