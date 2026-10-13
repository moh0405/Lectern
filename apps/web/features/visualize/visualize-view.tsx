"use client";

import type { components } from "@ai-study-mentor/api-client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Notice, Skeleton } from "@/components/ui/feedback";
import { Label, Select } from "@/components/ui/field";
import { api, errorMessage, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import { groupByDoc, Scatter3D } from "./scatter3d";

type Point = components["schemas"]["ProjectionPoint"];

export function VisualizeView() {
  const [limit, setLimit] = useState(400);
  const [selected, setSelected] = useState<Point | null>(null);
  const q = useQuery({
    queryKey: ["projection", limit],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/embeddings/projection", { params: { query: { limit } } })),
  });
  const d = q.data;
  const docs = d ? [...groupByDoc(d.points)] : [];

  return (
    <>
      <PageHeader
        title="Embedding map"
        description="Every passage you indexed, placed in 3D by how similar its meaning is. Passages from the same topic should cluster."
      />
      {q.isError ? <ErrorNotice>{errorMessage(q.error)}</ErrorNotice> : null}

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
              This index was built with the simple <code>hashing</code> embedder, so closeness here reflects shared words, not meaning.
              Install the <code>embeddings</code> extra and re-index for a semantic map.
            </Notice>
          ) : null}

          <Card className="space-y-3 p-3">
            <div className="flex flex-wrap items-end justify-between gap-3 px-2">
              <p className="text-sm text-muted">
                Showing {plural(d.points.length, "passage")} of {d.total_chunks.toLocaleString()} · axes keep{" "}
                {Math.round(d.explained_variance.reduce((a, b) => a + b, 0) * 100)}% of the variation (
                {d.explained_variance.map((v) => `${Math.round(v * 100)}%`).join(" / ")})
              </p>
              <div className="w-40">
                <Label htmlFor="limit">Passages</Label>
                <Select id="limit" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
                  {[100, 200, 400, 700, 1000].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <Scatter3D points={d.points} onSelect={setSelected} />
            <p className="px-2 text-xs text-muted">Drag to rotate, scroll to zoom, click a point to read it. Click a legend entry to hide a document.</p>
          </Card>

          {selected ? (
            <Card aria-live="polite">
              <p className="mb-1 text-xs text-muted">
                {selected.doc}
                {selected.page ? ` · page ${selected.page}` : ""}
              </p>
              <p className="text-sm">{selected.text}</p>
            </Card>
          ) : null}

          <Card>
            <h2 className="mb-2 text-sm font-semibold text-muted">Documents</h2>
            <ul className="grid gap-x-12 gap-y-1.5 text-sm sm:grid-cols-2">
              {docs.map(([doc, pts]) => (
                <li key={doc} className="flex justify-between gap-2">
                  <span className="min-w-0 truncate" title={doc}>
                    {doc}
                  </span>
                  <span className="tabular-nums text-muted">{plural(pts.length, "passage")}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : null}
    </>
  );
}
