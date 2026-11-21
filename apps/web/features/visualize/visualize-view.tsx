"use client";

import type { components } from "@ai-study-mentor/api-client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Notice, Skeleton } from "@/components/ui/feedback";
import { Label, Select } from "@/components/ui/field";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";
import { groupByDoc, Scatter3D, TRACE_TOKENS } from "./scatter3d";

type Point = components["schemas"]["ProjectionPoint"];

const LIMITS = [100, 200, 400, 700, 1000];
const PAGE = 25;
/** Below this many points the map says little: say so. */
export const FEW_POINTS = 20;

const excerpt = (text: string, n = 160) => (text.length > n ? `${text.slice(0, n - 1).trimEnd()}…` : text);

/** Every plotted passage as a list: the map's keyboard and screen-reader alternative. */
function PassageIndex({ points, selected, onSelect }: { points: Point[]; selected: Point | null; onSelect: (p: Point) => void }) {
  const [shown, setShown] = useState(PAGE);
  return (
    <Card>
      <h2 className="mb-1 text-sm font-semibold text-muted">Passage list</h2>
      <p className="mb-3 text-xs text-muted">The same passages as the map. Choose one to read it.</p>
      <ol className="divide-y divide-border" data-testid="passage-index">
        {points.slice(0, shown).map((p) => (
          <li key={p.index}>
            <button
              type="button"
              aria-pressed={selected?.index === p.index}
              onClick={() => onSelect(p)}
              className={cn(
                "block min-h-11 w-full px-1 py-2 text-left text-sm hover:bg-surface-2",
                selected?.index === p.index && "bg-surface-2",
              )}
            >
              <span className="block font-mono text-xs text-muted">
                {p.doc}
                {p.page ? ` · page ${p.page}` : ""}
              </span>
              <span className="block">{excerpt(p.text)}</span>
            </button>
          </li>
        ))}
      </ol>
      {shown < points.length ? (
        <Button variant="secondary" size="sm" className="mt-3" onClick={() => setShown((n) => n + PAGE)}>
          Show {Math.min(PAGE, points.length - shown)} more of {points.length - shown} left
        </Button>
      ) : null}
    </Card>
  );
}

export function VisualizeView() {
  const [limit, setLimit] = useState(400);
  const [selected, setSelected] = useState<Point | null>(null);
  const q = useQuery({
    queryKey: ["projection", limit],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/embeddings/projection", { params: { query: { limit } } })),
    // One retry at most for a heavy query; client errors (including 429 throttling) are not retried.
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });
  const d = q.data;
  const docs = d ? [...groupByDoc(d.points)] : [];
  const variance = d ? Math.round(d.explained_variance.reduce((a, b) => a + b, 0) * 100) : 0;

  return (
    <>
      <PageHeader title="Embedding map" description="See which passages in the library are about the same thing: similar meaning sits close together." />
      {q.isError ? <div className="mb-4 space-y-3"><ErrorNotice>{errorMessage(q.error)}</ErrorNotice><Button variant="secondary" disabled={q.isFetching} onClick={() => void q.refetch()}>{q.isFetching ? "Checking…" : "Try loading the map again"}</Button></div> : null}

      {q.isPending ? (
        <Skeleton className="h-[30rem]" />
      ) : d && d.points.length === 0 ? (
        <EmptyState title="Nothing to plot yet">
          <Link href="/sources" className="text-accent-2 underline">
            Add some sources
          </Link>{" "}
          first.
        </EmptyState>
      ) : d ? (
        <div className="space-y-4">
          {!d.semantic ? (
            <Notice>
              <p>Closeness on this map reflects shared words, not meaning: this library was indexed with the simple hashing embedder.</p>
              <details className="mt-1">
                <summary className="cursor-pointer">For the site owner</summary>
                <p className="mt-1">
                  Install the <code>embeddings</code> extra and re-index for a semantic map.
                </p>
              </details>
            </Notice>
          ) : null}

          <Card className="space-y-3 p-3">
            <div className="flex flex-wrap items-end justify-between gap-3 px-2">
              <p className="text-sm text-muted">
                Showing {plural(d.points.length, "passage")} of {d.total_chunks.toLocaleString()}
              </p>
              {d.total_chunks > LIMITS[0]! ? (
                <div className="w-40">
                  <Label htmlFor="limit">Passages</Label>
                  <Select id="limit" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                    {LIMITS.map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : null}
            </div>
            {d.points.length < FEW_POINTS ? (
              <p className="px-2 text-sm text-muted" data-testid="few-points">
                With only {plural(d.points.length, "passage")} there is not much to see yet. Clusters appear once more material is indexed.
              </p>
            ) : null}
            <Scatter3D points={d.points} onSelect={setSelected} />
            <p className="px-2 text-xs text-muted">Drag to rotate, scroll to zoom, click a point to read it. Click a legend entry to hide a document.</p>
            <details className="px-2 text-xs text-muted">
              <summary className="inline-flex min-h-8 cursor-pointer items-center hover:text-fg pointer-coarse:min-h-11">About this map</summary>
              <p className="mt-1 max-w-prose">
                Each passage&apos;s meaning is a long list of numbers (an embedding). The map squeezes those into three axes, which keep{" "}
                {variance}% of the differences between passages ({d.explained_variance.map((v) => `${Math.round(v * 100)}%`).join(" / ")} per axis), so
                distances are approximate.
              </p>
            </details>
          </Card>

          {selected ? (
            <Card aria-live="polite" data-testid="selected-passage">
              <p className="mb-1 font-mono text-xs text-muted">
                {selected.doc}
                {selected.page ? ` · page ${selected.page}` : ""}
              </p>
              <p className="paper-serif text-[15px] leading-relaxed">{selected.text}</p>
            </Card>
          ) : null}

          <Card>
            <h2 className="mb-2 text-sm font-semibold text-muted">Documents</h2>
            <ul className="grid gap-x-12 gap-y-1.5 text-sm sm:grid-cols-2">
              {docs.map(([doc, pts], i) => (
                <li key={doc} className="flex justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2" title={doc}>
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: `var(${TRACE_TOKENS[i % TRACE_TOKENS.length]})` }} aria-hidden />
                    <span className="truncate">{doc}</span>
                  </span>
                  <span className="tabular-nums text-muted">{plural(pts.length, "passage")}</span>
                </li>
              ))}
            </ul>
          </Card>

          <PassageIndex points={d.points} selected={selected} onSelect={setSelected} />
        </div>
      ) : null}
    </>
  );
}
