"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Search } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/field";
import { EmptyState, Skeleton } from "@/components/ui/feedback";
import { QueryError } from "@/features/shared/query-error";
import { api, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { useDebounced } from "@/lib/use-debounced";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { DifficultyBadge } from "./difficulty-badge";
import { ProblemDetail } from "./problem-detail";
import { StatusIcon, useProgress, type Status } from "./progress";
import { StudyPlan } from "./study-plan";
import { useWideLayout } from "./use-media-query";

const DIFFICULTIES = ["Easy", "Medium", "Hard"] as const;
const PAGE = 20;
const MAX_RESULTS = 50; // the API's top_k limit

const resultId = (pid: string) => `lc-result-${pid}`;

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        // 36px with a mouse; 44px on touch screens (WCAG 2.5.5 target size).
        "inline-flex min-h-9 shrink-0 items-center rounded-full border px-3 text-xs whitespace-nowrap transition-colors pointer-coarse:min-h-11 pointer-coarse:px-4",
        active ? "border-accent bg-accent/20 text-fg" : "border-border bg-surface-2 text-muted hover:border-accent/60 hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

/** Below `lg` the problem opens as a full-screen sheet: a modal dialog, so focus is held in it and Escape closes it. */
function ProblemSheet({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
    return () => element?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      aria-label="Problem"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      className="m-0 h-dvh max-h-none w-full max-w-none overflow-y-auto bg-bg p-0 text-fg backdrop:bg-black/60"
    >
      <div className="sticky top-0 z-10 border-b border-border bg-bg/95 px-4 py-2 backdrop-blur">
        <Button variant="ghost" onClick={onClose} aria-keyshortcuts="Escape" autoFocus>
          <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to results
        </Button>
      </div>
      <div className="p-4">{children}</div>
    </dialog>
  );
}

export function LeetCodeView() {
  const url = useUrlParams();
  const urlQuery = url.get("q");
  const difficulty = url.getList("d");
  const topics = url.getList("t");
  const selected = url.get("p");
  const wide = useWideLayout();

  const [text, setText] = useState(urlQuery);
  const debounced = useDebounced(text, 300);
  useEffect(() => {
    if (debounced !== urlQuery) url.set({ q: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only react to the debounced text
  }, [debounced]);

  // "Show more" grows the list for this search only; a new search starts again at one page.
  const searchKey = [urlQuery, difficulty.join(","), topics.join(",")].join("|");
  const [more, setMore] = useState({ key: "", limit: PAGE });
  const limit = more.key === searchKey ? more.limit : PAGE;

  const stats = useQuery({
    queryKey: ["lc-stats"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/leetcode/stats")),
    staleTime: 10 * 60_000,
  });
  const search = useQuery({
    queryKey: ["lc-search", urlQuery, difficulty.join(","), topics.join(","), limit],
    queryFn: async () =>
      unwrap(
        await api.http.GET("/api/v1/leetcode/search", {
          params: {
            query: {
              query: urlQuery,
              top_k: limit,
              difficulty: difficulty.length ? difficulty : undefined,
              topic: topics.length ? topics : undefined,
            },
          },
        }),
      ),
    placeholderData: (prev) => prev,
  });

  // Where focus returns when the problem closes: the result (or plan entry) that opened it.
  const trigger = useRef<HTMLElement | null>(null);
  const [openedByUser, setOpenedByUser] = useState(false);
  const open = (pid: string, from: HTMLElement) => {
    trigger.current = from;
    setOpenedByUser(true);
    url.set({ p: pid });
  };
  // Focus is returned once the problem has actually closed (the URL update is async, and a modal sheet
  // keeps the rest of the page inert until it is gone).
  const returnTo = useRef<string | null>(null);
  const close = () => {
    returnTo.current = selected;
    url.set({ p: null });
  };
  useEffect(() => {
    if (selected || returnTo.current === null) return;
    const back = returnTo.current;
    returnTo.current = null;
    const target = trigger.current?.isConnected ? trigger.current : document.getElementById(resultId(back));
    target?.focus();
  }, [selected]);

  const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const topTopics = (stats.data?.top_topics ?? []).slice(0, 14).map((t) => String(t[0]));
  const results = search.data?.problems ?? [];
  const progress = useProgress();
  const statusOf = new Map((progress.data?.items ?? []).map((i) => [i.pid, i.status as Status]));
  const canShowMore = results.length >= limit && limit < MAX_RESULTS;
  const countText = search.isPending || search.isError ? "" : results.length === 0 ? "0 results."
    : `Showing ${plural(results.length, urlQuery ? "closest match" : "problem", urlQuery ? "closest matches" : "problems")}${canShowMore ? "" : results.length >= limit ? " (the most a search returns)" : ""}.`;

  const detail = selected ? (
    <ProblemDetail key={selected} pid={selected} onClose={close} focusTitle={openedByUser && wide} showClose={wide} />
  ) : null;

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

      <Card className="mb-4 min-w-0 space-y-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-muted" aria-hidden="true" />
          <Input
            type="search"
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
          // One scrolling row on phones (so 14 topics do not push the results down); wrapped on wider screens.
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 py-1 sm:flex-wrap sm:overflow-visible" role="group" aria-label="Topics">
            {topTopics.map((t) => (
              <Chip key={t} active={topics.includes(t)} onClick={() => url.set({ t: toggle(topics, t) })}>
                {t}
              </Chip>
            ))}
          </div>
        ) : null}
      </Card>

      <StudyPlan onOpen={open} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section aria-label="Results" className="min-w-0 space-y-2">
          <p className="text-sm text-muted" role="status">{countText}</p>
          {search.isError ? (
            <QueryError error={search.error} what="search results" onRetry={() => void search.refetch()} retrying={search.isFetching} />
          ) : search.isPending ? (
            <div role="status">
              {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="mb-2 h-16" />)}
              <p className="text-sm text-muted">Loading problems…</p>
            </div>
          ) : results.length === 0 ? (
            <EmptyState title="No problems match">Try fewer filters or different words.</EmptyState>
          ) : (
            <>
              {results.map((p) => (
                <button
                  key={p.pid}
                  id={resultId(p.pid)}
                  type="button"
                  onClick={(event) => open(p.pid, event.currentTarget)}
                  aria-current={selected === p.pid ? "true" : undefined}
                  title={`${p.pid}. ${p.title}`}
                  className={cn(
                    "block w-full rounded-xl border bg-surface/80 p-3 text-left transition-colors hover:border-accent/60",
                    selected === p.pid ? "border-accent" : "border-border",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="flex min-w-0 items-start gap-1.5 text-sm font-medium">
                      <StatusIcon status={statusOf.get(p.pid)} className="mt-0.5 shrink-0" />
                      <span className="line-clamp-2 [overflow-wrap:anywhere]">{p.pid}. {p.title}</span>
                    </span>
                    <DifficultyBadge difficulty={p.difficulty} />
                  </div>
                  {p.topics.length ? <p className="mt-1 truncate text-xs text-muted">{p.topics.join(" · ")}</p> : null}
                </button>
              ))}
              {canShowMore ? (
                <Button
                  variant="secondary"
                  className="w-full"
                  disabled={search.isFetching}
                  onClick={() => setMore({ key: searchKey, limit: Math.min(limit + PAGE, MAX_RESULTS) })}
                >
                  {search.isFetching ? "Loading…" : "Show more problems"}
                </Button>
              ) : null}
            </>
          )}
        </section>

        {wide ? (
          // Sticky below the 72px app header, and scrollable on its own when taller than the window.
          <div className="sticky top-[calc(72px+1rem)] max-h-[calc(100dvh-72px-2rem)] min-w-0 self-start overflow-y-auto rounded-xl">
            {detail ?? <EmptyState title="Pick a problem">Open one to read it and generate a study guide.</EmptyState>}
          </div>
        ) : detail ? (
          <ProblemSheet onClose={close}>{detail}</ProblemSheet>
        ) : null}
      </div>
    </>
  );
}
