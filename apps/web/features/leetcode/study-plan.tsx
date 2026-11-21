"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { useState, type MouseEvent } from "react";
import { Badge, Skeleton } from "@/components/ui/feedback";
import { QueryError } from "@/features/shared/query-error";
import { useDemo } from "@/lib/demo";
import { api, unwrap } from "@/lib/api";
import { DifficultyBadge } from "./difficulty-badge";
import { useProgress } from "./progress";
import { useWideLayout } from "./use-media-query";

/** The plan, collapsible so it never pushes the search out of view; open by default on wide screens. */
export function StudyPlan({ onOpen }: { onOpen: (pid: string, trigger: HTMLElement) => void }) {
  const progress = useProgress();
  const demo = useDemo();
  const wide = useWideLayout();
  const [openChoice, setOpenChoice] = useState<boolean | null>(null);
  const open = openChoice ?? wide;
  const plan = useQuery({
    queryKey: ["lc-plan"],
    enabled: !demo, // the plan is computed on the server from the shared database, so it is off in the demo
    queryFn: async () => unwrap(await api.http.GET("/api/v1/leetcode/plan", { params: { query: { size: 8 } } })),
  });
  const s = progress.data?.summary;

  return (
    <details
      className="lectern-card group mb-4 rounded-xl border border-border bg-surface"
      data-testid="study-plan"
      open={open}
      onToggle={(event) => setOpenChoice(event.currentTarget.open)}
    >
      <summary
        className="flex min-h-11 cursor-pointer list-none flex-wrap items-center justify-between gap-2 rounded-xl px-5 py-3 [&::-webkit-details-marker]:hidden"
        onClick={(event: MouseEvent) => { event.preventDefault(); setOpenChoice(!open); }}
      >
        <span className="flex items-center gap-2 text-base font-semibold tracking-tight">
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" aria-hidden="true" />
          Your study plan
        </span>
        {s ? (
          <span className="text-sm text-muted" data-testid="progress-summary">
            {s.solved} solved · {s.attempted} attempted
          </span>
        ) : null}
      </summary>
      <div className="space-y-3 px-5 pb-5">
        {demo ? (
          <p className="text-sm text-muted">
            Your marks and notes are saved in this browser only. The personalised plan needs a private deployment; run the project locally to use it.
          </p>
        ) : plan.isPending ? (
          <div role="status"><Skeleton className="h-20" /><p className="mt-2 text-sm text-muted">Loading your study plan…</p></div>
        ) : plan.isError ? (
          <QueryError error={plan.error} what="your study plan" onRetry={() => void plan.refetch()} retrying={plan.isFetching} />
        ) : (
          <>
            {plan.data.weak_topics.length > 0 ? (
              <p className="text-sm">
                <span className="text-muted">Weak topics (2 or more tried, under half solved): </span>
                {plan.data.weak_topics.slice(0, 6).map((t) => (
                  <Badge key={t} className="mr-1">{t}</Badge>
                ))}
              </p>
            ) : (
              <p className="text-sm text-muted">Mark problems as attempted or solved and this plan will focus on the topics you struggle with. Until then, it starts with well-known fundamentals.</p>
            )}
            <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {plan.data.items.map((i) => (
                <li key={i.pid} className="min-w-0">
                  <button
                    type="button"
                    onClick={(event) => onOpen(i.pid, event.currentTarget)}
                    className="block min-h-11 w-full rounded-lg border border-border bg-surface-2/60 p-2.5 text-left text-sm transition-colors hover:border-accent/60"
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span className="line-clamp-2 min-w-0 font-medium" title={`${i.pid}. ${i.title}`}>{i.pid}. {i.title}</span>
                      <DifficultyBadge difficulty={i.difficulty} />
                    </span>
                    <span className="mt-0.5 block text-xs text-muted">{i.reason}</span>
                  </button>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </details>
  );
}
