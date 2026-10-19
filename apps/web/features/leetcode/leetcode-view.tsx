"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { useDebounced } from "@/lib/use-debounced";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { DifficultyBadge } from "./difficulty-badge";
import { ProblemDetail } from "./problem-detail";
import { StatusIcon, useProgress, type Status } from "./progress";
import { StudyPlan } from "./study-plan";

const DIFFICULTIES = ["Easy", "Medium", "Hard"] as const;

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs transition-colors",
        active ? "border-accent bg-accent/20 text-fg" : "border-border bg-surface-2 text-muted hover:border-accent/60 hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

export function LeetCodeView() {
  const url = useUrlParams();
  const urlQuery = url.get("q");
  const difficulty = url.getList("d");
  const topics = url.getList("t");
  const selected = url.get("p");

  const [text, setText] = useState(urlQuery);
  const debounced = useDebounced(text, 300);
  useEffect(() => {
    if (debounced !== urlQuery) url.set({ q: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to the debounced text
  }, [debounced]);

  const stats = useQuery({
    queryKey: ["lc-stats"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/leetcode/stats")),
    staleTime: 10 * 60_000,
  });
  const search = useQuery({
    queryKey: ["lc-search", urlQuery, difficulty.join(","), topics.join(",")],
    queryFn: async () =>
      unwrap(
        await api.http.GET("/api/v1/leetcode/search", {
          params: {
            query: {
              query: urlQuery,
              top_k: 20,
              difficulty: difficulty.length ? difficulty : undefined,
              topic: topics.length ? topics : undefined,
            },
          },
        }),
      ),
    placeholderData: (prev) => prev,
  });

  const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const topTopics = (stats.data?.top_topics ?? []).slice(0, 14).map((t) => String(t[0]));
  const results = search.data?.problems ?? [];
  const progress = useProgress();
  const statusOf = new Map((progress.data?.items ?? []).map((i) => [i.pid, i.status as Status]));

  return (
    <>
      <PageHeader
        title="LeetCode"
        description="Search a bank of coding problems and get an AI study guide for any of them."
      />

      {stats.data ? (
        <div className="mb-4 flex flex-wrap gap-2 text-sm text-muted">
          <span>{plural(stats.data.total, "problem")}</span>
          {Object.entries(stats.data.by_difficulty).map(([d, n]) => (
            <span key={d}>
              · {n.toLocaleString()} {d}
            </span>
          ))}
        </div>
      ) : null}

      <StudyPlan onOpen={(pid) => url.set({ p: pid })} />

      <Card className="mb-4 space-y-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" />
          <Input
            aria-label="Search problems"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Search by idea, e.g. “two pointers on a sorted array”"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2" role="group" aria-label="Difficulty">
          {DIFFICULTIES.map((d) => (
            <Chip key={d} active={difficulty.includes(d)} onClick={() => url.set({ d: toggle(difficulty, d) })}>
              {d}
            </Chip>
          ))}
        </div>
        {topTopics.length ? (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Topics">
            {topTopics.map((t) => (
              <Chip key={t} active={topics.includes(t)} onClick={() => url.set({ t: toggle(topics, t) })}>
                {t}
              </Chip>
            ))}
          </div>
        ) : null}
      </Card>

      {search.isError ? <ErrorNotice>{errorMessage(search.error)}</ErrorNotice> : null}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section aria-label="Results" className="space-y-2">
          {search.isPending ? (
            Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-16" />)
          ) : results.length === 0 ? (
            <EmptyState title="No problems match">Try fewer filters or different words.</EmptyState>
          ) : (
            results.map((p) => (
              <button
                key={p.pid}
                type="button"
                onClick={() => url.set({ p: p.pid })}
                aria-current={selected === p.pid ? "true" : undefined}
                className={cn(
                  "block w-full rounded-xl border bg-surface/80 p-3 text-left transition-colors hover:border-accent/60",
                  selected === p.pid ? "border-accent" : "border-border",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-1.5 text-sm font-medium">
                    <StatusIcon status={statusOf.get(p.pid)} className="shrink-0" />
                    <span className="truncate">{p.pid}. {p.title}</span>
                  </span>
                  <DifficultyBadge difficulty={p.difficulty} />
                </div>
                {p.topics.length ? <p className="mt-1 truncate text-xs text-muted">{p.topics.join(" · ")}</p> : null}
              </button>
            ))
          )}
        </section>

        <div className="lg:sticky lg:top-6 lg:self-start">
          {selected ? (
            <ProblemDetail key={selected} pid={selected} onClose={() => url.set({ p: null })} />
          ) : (
            <EmptyState title="Pick a problem">Open one to read it and generate a study guide.</EmptyState>
          )}
        </div>
      </div>
    </>
  );
}
