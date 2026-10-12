"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { plural } from "@/lib/format";
import { sparkline, toCsv, toReport } from "./report";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted">{hint}</p> : null}
    </Card>
  );
}

export function AnalyticsView() {
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const data = useQuery({
    queryKey: ["analytics"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/analytics", { params: { query: { limit: 50 } } })),
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

  return (
    <>
      <PageHeader
        title="Analytics"
        description="What you have asked and which sources answered. Stored on the server, so it survives restarts."
        actions={
          s && s.queries > 0 ? (
            <div className="flex flex-wrap gap-1">
              <Button variant="ghost" size="sm" onClick={() => downloadBlob(new Blob([toReport(s)], { type: "text/markdown" }), "study-report.md")}>
                <Download className="h-4 w-4" /> Report
              </Button>
              <Button variant="ghost" size="sm" onClick={() => downloadBlob(new Blob([toCsv(s.recent)], { type: "text/csv" }), "analytics.csv")}>
                <Download className="h-4 w-4" /> CSV
              </Button>
              {confirm ? (
                <>
                  <Button variant="danger" size="sm" disabled={clear.isPending} onClick={() => clear.mutate()}>
                    Confirm clear
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirm(false)}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => setConfirm(true)}>
                  <Trash2 className="h-4 w-4" /> Clear
                </Button>
              )}
            </div>
          ) : undefined
        }
      />

      {data.isError ? <ErrorNotice>{errorMessage(data.error)}</ErrorNotice> : null}
      {clear.isError ? <ErrorNotice className="mt-2">{errorMessage(clear.error)}</ErrorNotice> : null}

      {data.isPending ? (
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
            <Stat label="Avg relevance" value={s.avg_score.toFixed(2)} hint="similarity of retrieved passages" />
            <Stat label="Avg response" value={`${Math.round(s.avg_latency_ms).toLocaleString()} ms`} />
            <Stat label="Streak" value={plural(s.streak_days, "day")} hint="consecutive days with a question" />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
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
              <p className="mb-3 text-xs text-muted">Last {plural(latencies.length, "question")}, oldest to newest</p>
              {latencies.length > 1 ? (
                <svg viewBox="0 0 120 28" className="h-20 w-full" role="img" aria-label="Response time trend" preserveAspectRatio="none">
                  <polyline points={sparkline(latencies)} fill="none" stroke="var(--color-accent-2)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
                </svg>
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
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="pb-2 pr-3 font-medium">Question</th>
                    <th className="pb-2 pr-3 font-medium">Relevance</th>
                    <th className="pb-2 pr-3 font-medium">Time</th>
                    <th className="pb-2 font-medium">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {s.recent.map((e) => (
                    <tr key={e.id}>
                      <td className="max-w-md py-2 pr-3">
                        <span className="line-clamp-2">{e.question}</span>
                      </td>
                      <td className="py-2 pr-3 tabular-nums">{e.avg_score.toFixed(2)}</td>
                      <td className="py-2 pr-3 tabular-nums">{e.latency_ms} ms</td>
                      <td className="py-2">{e.ok ? <span className="text-good">answered</span> : <span className="text-bad">failed</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : null}
    </>
  );
}
