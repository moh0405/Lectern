"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Sparkles, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge, ErrorNotice, Notice, Skeleton, Spinner } from "@/components/ui/feedback";
import { QueryError } from "@/features/shared/query-error";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { DifficultyBadge } from "./difficulty-badge";
import { ProgressPanel } from "./progress";

export function ProblemDetail({ pid, onClose, focusTitle = false, showClose = true }: {
  pid: string;
  onClose: () => void;
  /** Move keyboard focus to the title once it loads (when the problem was opened by the student). */
  focusTitle?: boolean;
  /** The phone sheet has its own "Back to results" control instead. */
  showClose?: boolean;
}) {
  const title = useRef<HTMLHeadingElement>(null);
  const problem = useQuery({
    queryKey: ["lc-problem", pid],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/leetcode/problems/{pid}", { params: { path: { pid } } })),
  });
  const guide = useMutation({
    mutationFn: async () =>
      unwrap(await api.http.POST("/api/v1/leetcode/problems/{pid}/explain", { params: { path: { pid } } })),
  });
  const noKey = guide.error instanceof ApiError && guide.error.code === "llm_unavailable";
  const loaded = problem.isSuccess;
  useEffect(() => { if (focusTitle && loaded) title.current?.focus({ preventScroll: true }); }, [focusTitle, loaded]);

  return (
    <Card
      className="space-y-4"
      aria-label="Problem detail"
      onKeyDown={(event) => { if (event.key === "Escape" && showClose) { event.stopPropagation(); onClose(); } }}
    >
      {problem.isPending ? (
        <div className="space-y-3" role="status">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-40" />
          <p className="text-sm text-muted">Loading the problem…</p>
        </div>
      ) : problem.isError ? (
        <QueryError error={problem.error} what="this problem" onRetry={() => void problem.refetch()} retrying={problem.isFetching} />
      ) : (
        <>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 ref={title} tabIndex={-1} className="text-lg font-semibold leading-snug [overflow-wrap:anywhere]">
                {problem.data.pid}. {problem.data.title}
              </h2>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <DifficultyBadge difficulty={problem.data.difficulty} />
                {problem.data.topics.map((t) => (
                  <Badge key={t}>{t}</Badge>
                ))}
                {problem.data.acceptance != null ? <Badge>{problem.data.acceptance}% accepted</Badge> : null}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {problem.data.url ? (
                <a
                  href={problem.data.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Open on LeetCode (new tab)"
                  className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
                >
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                </a>
              ) : null}
              {showClose ? (
                <Button variant="ghost" size="icon" aria-label="Close problem" aria-keyshortcuts="Escape" onClick={onClose}>
                  <X className="h-4 w-4" aria-hidden="true" />
                </Button>
              ) : null}
            </div>
          </div>

          {/* Scrollable, so it must be reachable by keyboard (WCAG 2.1.1) */}
          <div
            tabIndex={0}
            role="region"
            aria-label="Problem statement"
            className="max-h-[22rem] overflow-y-auto rounded-lg border border-border bg-bg/40 p-4 text-sm [overflow-wrap:anywhere]"
          >
            <Markdown breaks>{problem.data.description}</Markdown>
          </div>

          <div>
            <Button onClick={() => guide.mutate()} disabled={guide.isPending}>
              {guide.isPending ? <Spinner /> : <Sparkles className="h-4 w-4" aria-hidden="true" />}
              {guide.data ? "Regenerate study guide" : "Study guide"}
            </Button>
            <p className="mt-1.5 text-xs text-muted">Approach, complexity, pitfalls, hints and a Python solution, written by the model.</p>
          </div>

          {noKey ? (
            <Notice>The server has no language-model key configured, so it cannot write study guides.</Notice>
          ) : guide.isError ? (
            <ErrorNotice>{errorMessage(guide.error)}</ErrorNotice>
          ) : null}
          {guide.data ? (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-muted">Study guide</h3>
              <Markdown className="rounded-lg border border-border bg-bg/40 p-4">{guide.data.markdown}</Markdown>
            </div>
          ) : null}

          <div>
            <h3 className="mb-2 text-sm font-semibold text-muted">Your progress</h3>
            <ProgressPanel problem={{ pid, title: problem.data.title, difficulty: problem.data.difficulty, topics: problem.data.topics }} />
          </div>
        </>
      )}
    </Card>
  );
}
