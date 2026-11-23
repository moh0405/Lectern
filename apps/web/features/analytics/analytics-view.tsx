"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Download, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { useDemo } from "@/lib/demo";
import { api, errorMessage, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { plural } from "@/lib/format";
import { useFocusAfterRender } from "@/features/tutor/pending";
import { relativeTime, seriesRange, sparkline, toCsv, toReport, type AnalyticsEvent } from "./report";

const RELEVANCE_SCALE = "0 to 1: how closely the retrieved passages matched each question. Higher is closer; 0.3 can still be the right passage.";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}

const ms = (n: number) => `${Math.round(n).toLocaleString()} ms`;
const askHref = (q: string) => `/ask?q=${encodeURIComponent(q)}`;


function Result({ ok }: { ok: boolean }) {
  return ok ? <span className="text-good">answered</span> : <span className="text-bad">failed</span>;
}

function RecentTable({ events }: { events: AnalyticsEvent[] }) {
  const [now] = useState(() => Date.now() / 1000); // fixed per render pass of the list
  return (
    <>
      {/* Wide screens: a table. */}
      <div className="hidden sm:block">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="pb-2 pr-3 font-medium">Question</th>
              <th className="whitespace-nowrap pb-2 pr-3 font-medium">Asked</th>
              <th className="pb-2 pr-3 font-medium">Relevance</th>
              <th className="whitespace-nowrap pb-2 pr-3 font-medium">Response time</th>
              <th className="pb-2 font-medium">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {events.map((e) => (
              <tr key={e.id}>
                <td className="max-w-md py-2 pr-3">
                  <Link href={askHref(e.question)} className="line-clamp-2 hover:text-accent-2 hover:underline" title="Ask this again">
                    {e.question}
                  </Link>
                </td>
                <td className="whitespace-nowrap py-2 pr-3 text-muted">
                  <time dateTime={new Date(e.ts * 1000).toISOString()}>{relativeTime(e.ts, now)}</time>
                </td>
                <td className="py-2 pr-3 tabular-nums">{e.avg_score.toFixed(2)}</td>
                <td className="whitespace-nowrap py-2 pr-3 tabular-nums">{ms(e.latency_ms)}</td>
                <td className="py-2">
                  <Result ok={e.ok} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Phones: one stacked row per question. */}
      <ul className="divide-y divide-border sm:hidden" data-testid="recent-stacked">
        {events.map((e) => (
          <li key={e.id} className="py-2.5 text-sm">
            <Link href={askHref(e.question)} className="line-clamp-3 font-medium hover:text-accent-2 hover:underline">
              {e.question}
            </Link>
            <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
              <time dateTime={new Date(e.ts * 1000).toISOString()}>{relativeTime(e.ts, now)}</time>
              <span className="whitespace-nowrap">relevance {e.avg_score.toFixed(2)}</span>
              <span className="whitespace-nowrap">{ms(e.latency_ms)}</span>
              <Result ok={e.ok} />
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}

function DemoExplainer() {
  return (
    <section className="rounded-xl border border-dashed border-border p-6 text-sm" data-testid="analytics-demo">
      <h2 className="eyebrow mb-2">
        <BarChart3 aria-hidden /> Not in the public demo
      </h2>
      <p className="max-w-prose text-muted">
        On a private deployment this page shows your questions, response times and most-used sources, with a CSV and a study report to
        download. The demo shares one server between visitors, so it keeps no history here.
      </p>
      <p className="mt-3">
        <Link href="/ask" className="text-accent-2 underline">
          Ask a question
        </Link>
      </p>
    </section>
  );
}

export function AnalyticsView() {
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const demo = useDemo();
  const focusAfterRender = useFocusAfterRender();
  const data = useQuery({
    queryKey: ["analytics"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/analytics", { params: { query: { limit: 50 } } })),
    enabled: !demo, // the demo proxy refuses this route: do not send it
  });
  const clear = useMutation({
    mutationFn: async () => unwrap(await api.http.DELETE("/api/v1/analytics")),
    onSuccess: () => {
      setConfirm(false);
      void qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });

  const s = data.data;
  const usage = Object.entries(s?.doc_usage ?? {});
  const maxUse = Math.max(1, ...usage.map(([, n]) => n));
  const latencies = [...(s?.recent ?? [])].reverse().map((e) => e.latency_ms);
  const range = seriesRange(latencies);

  return (
    <>
      <PageHeader
        eyebrow="Library"
        title="Insights"
        description="See what you have asked, how fast it was answered and which sources did the work."
        actions={
          !demo && s && s.queries > 0 ? (
            <div className="flex flex-wrap gap-1">
              <Button variant="ghost" size="sm" onClick={() => downloadBlob(new Blob([toReport(s)], { type: "text/markdown" }), "study-report.md")}>
                <Download className="h-4 w-4" aria-hidden /> Report
              </Button>
              <Button variant="ghost" size="sm" onClick={() => downloadBlob(new Blob([toCsv(s.recent)], { type: "text/csv" }), "analytics.csv")}>
                <Download className="h-4 w-4" aria-hidden /> CSV
              </Button>
              {confirm ? (
                <>
                  <Button id="analytics-confirm-clear" variant="danger" size="sm" disabled={clear.isPending} onClick={() => clear.mutate()}>
                    Confirm clear
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setConfirm(false);
                      focusAfterRender("analytics-clear");
                    }}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  id="analytics-clear"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setConfirm(true);
                    focusAfterRender("analytics-confirm-clear");
                  }}
                >
                  <Trash2 className="h-4 w-4" aria-hidden /> Clear
                </Button>
              )}
            </div>
          ) : undefined
        }
      />

      {demo ? <DemoExplainer /> : null}
      {data.isError ? <ErrorNotice>{errorMessage(data.error)}</ErrorNotice> : null}
      {clear.isError ? <ErrorNotice className="mt-2">{errorMessage(clear.error)}</ErrorNotice> : null}

      {demo ? null : data.isPending ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : s && s.queries === 0 ? (
        <EmptyState title="No questions yet">Ask something on the Ask page and your usage will show up here.</EmptyState>
      ) : s ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Questions" value={s.queries.toLocaleString()} />
            <Stat label="Avg relevance" value={s.avg_score.toFixed(2)} hint="0–1 scale; higher means closer passages" />
            <Stat label="Avg response" value={ms(s.avg_latency_ms)} />
            <Stat label="Streak" value={plural(s.streak_days, "day")} hint="consecutive days with a question" />
          </div>
          <p className="text-xs text-muted">Relevance runs from {RELEVANCE_SCALE}</p>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardTitle className="mb-3">Most used sources</CardTitle>
              {usage.length ? (
                <ul className="space-y-2.5">
                  {usage.slice(0, 8).map(([doc, n]) => (
                    <li key={doc}>
                      <div className="mb-1 flex justify-between gap-2 text-sm">
                        <span className="min-w-0 truncate" title={doc}>
                          {doc}
                        </span>
                        <span className="tabular-nums text-muted">{n}</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-surface-2" role="presentation">
                        <div className="h-1.5 rounded-full bg-accent" style={{ width: `${(n / maxUse) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">No sources were retrieved yet.</p>
              )}
            </Card>

            <Card>
              <CardTitle className="mb-1">Response time</CardTitle>
              <p className="mb-3 text-xs text-muted">Last {plural(latencies.length, "question")}, oldest to newest, in milliseconds</p>
              {latencies.length > 1 && range ? (
                <>
                  <div className="flex gap-2">
                    <div className="flex flex-col justify-between text-right font-mono text-[10px] text-muted" aria-hidden>
                      <span>{ms(range.max)}</span>
                      <span>{ms(Math.min(range.min, 0))}</span>
                    </div>
                    <svg
                      viewBox="0 0 120 28"
                      className="h-20 min-w-0 flex-1 border-b border-l border-border"
                      role="img"
                      aria-label={`Response time trend: fastest ${ms(range.min)}, slowest ${ms(range.max)}, latest ${ms(range.latest)}`}
                      preserveAspectRatio="none"
                    >
                      <polyline points={sparkline(latencies)} fill="none" stroke="var(--color-accent-2)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                    </svg>
                  </div>
                  <p className="mt-2 flex flex-wrap gap-x-4 text-xs text-muted" data-testid="latency-range">
                    <span>Fastest <span className="tabular-nums text-fg">{ms(range.min)}</span></span>
                    <span>Slowest <span className="tabular-nums text-fg">{ms(range.max)}</span></span>
                    <span>Latest <span className="tabular-nums text-fg">{ms(range.latest)}</span></span>
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted">Ask a couple more questions to see a trend.</p>
              )}
              <p className="mt-2 text-xs text-muted">
                Tokens (estimated): {s.tokens_prompt.toLocaleString()} in · {s.tokens_answer.toLocaleString()} out
              </p>
            </Card>
          </div>

          <Card>
            <CardTitle className="mb-3">Recent questions</CardTitle>
            <RecentTable events={s.recent} />
          </Card>
        </div>
      ) : null}
    </>
  );
}
