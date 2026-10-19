"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { useDemo, demoDisabled } from "@/lib/demo";
import { api, errorMessage, unwrap } from "@/lib/api";
import { DifficultyBadge } from "./difficulty-badge";
import { useProgress } from "./progress";

export function StudyPlan({ onOpen }: { onOpen: (pid: string) => void }) {
  const progress = useProgress();
  const demo = useDemo();
  const plan = useQuery({
    queryKey: ["lc-plan"],
    queryFn: async () => (demo ? demoDisabled() : unwrap(await api.http.GET("/api/v1/leetcode/plan", { params: { query: { size: 8 } } }))),
  });
  const s = progress.data?.summary;

  return (
    <Card className="mb-4 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <CardTitle>Your study plan</CardTitle>
        {s ? (
          <p className="text-sm text-muted" data-testid="progress-summary">
            {s.solved} solved · {s.attempted} attempted
          </p>
        ) : null}
      </div>
      {plan.isPending ? (
        <Skeleton className="h-20" />
      ) : plan.isError ? (
        <ErrorNotice>{errorMessage(plan.error)}</ErrorNotice>
      ) : (
        <>
          {plan.data.weak_topics.length > 0 ? (
            <p className="text-sm">
              <span className="text-muted">Weak topics (under half solved): </span>
              {plan.data.weak_topics.slice(0, 6).map((t) => (
                <Badge key={t} className="mr-1">{t}</Badge>
              ))}
            </p>
          ) : (
            <p className="text-sm text-muted">Mark problems as attempted or solved and this plan will focus on the topics you struggle with.</p>
          )}
          <ol className="grid gap-2 sm:grid-cols-2">
            {plan.data.items.map((i) => (
              <li key={i.pid}>
                <button
                  type="button"
                  onClick={() => onOpen(i.pid)}
                  className="block w-full rounded-lg border border-border bg-surface-2/60 p-2.5 text-left text-sm transition-colors hover:border-accent/60"
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate font-medium">{i.pid}. {i.title}</span>
                    <DifficultyBadge difficulty={i.difficulty} />
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">{i.reason}</span>
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </Card>
  );
}
