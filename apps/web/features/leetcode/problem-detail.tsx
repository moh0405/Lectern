"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, Sparkles, X } from "lucide-react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge, ErrorNotice, Notice, Skeleton, Spinner } from "@/components/ui/feedback";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { DifficultyBadge } from "./difficulty-badge";

export function ProblemDetail({ pid, onClose }: { pid: string; onClose: () => void }) {
  const problem = useQuery({
    queryKey: ["lc-problem", pid],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/leetcode/problems/{pid}", { params: { path: { pid } } })),
  });
  const guide = useMutation({
    mutationFn: async () =>
      unwrap(await api.http.POST("/api/v1/leetcode/problems/{pid}/explain", { params: { path: { pid } } })),
  });
  const noKey = guide.error instanceof ApiError && guide.error.code === "llm_unavailable";

  return (
    <Card className="space-y-4" aria-label="Problem detail">
      {problem.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-40" />
        </div>
      ) : problem.isError ? (
        <ErrorNotice>{errorMessage(problem.error)}</ErrorNotice>
      ) : (
        <>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold leading-snug">
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
                  aria-label="Open on LeetCode"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              ) : null}
              <Button variant="ghost" size="icon" aria-label="Close problem" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <Markdown breaks className="max-h-[22rem] overflow-y-auto rounded-lg border border-border bg-bg/40 p-4 text-sm">
            {problem.data.description}
          </Markdown>

          <div>
            <Button onClick={() => guide.mutate()} disabled={guide.isPending}>
              {guide.isPending ? <Spinner /> : <Sparkles className="h-4 w-4" />}
              {guide.data ? "Regenerate study guide" : "Study guide"}
            </Button>
            <p className="mt-1.5 text-xs text-muted">Approach, complexity, pitfalls, hints and a Python solution, written by the model.</p>
          </div>

          {noKey ? (
            <Notice>The server has no <code>GEMINI_API_KEY</code>, so it cannot write study guides.</Notice>
          ) : guide.isError ? (
            <ErrorNotice>{errorMessage(guide.error)}</ErrorNotice>
          ) : null}
          {guide.data ? (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-muted">Study guide</h3>
              <Markdown className="rounded-lg border border-border bg-bg/40 p-4">{guide.data.markdown}</Markdown>
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}
