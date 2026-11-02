"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Globe, GitBranch, Mic, Trash2, Video, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { useDemo } from "@/lib/demo";
import { api, errorMessage, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";

const ICONS: Record<string, LucideIcon> = { pdf: FileText, youtube: Video, github: GitBranch, web: Globe, audio: Mic };

export function DocumentsTable() {
  const qc = useQueryClient();
  const demo = useDemo(); // the public demo shares one index, so visitors cannot delete from it
  const [confirm, setConfirm] = useState<string | null>(null);

  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: async () => unwrap(await api.http.GET("/api/v1/documents")),
  });
  const remove = useMutation({
    mutationFn: async (key: string) => unwrap(await api.http.DELETE("/api/v1/sources", { params: { query: { key } } })),
    onSuccess: () => {
      setConfirm(null);
      for (const k of ["documents", "stats", "health"]) void qc.invalidateQueries({ queryKey: [k] });
    },
  });

  return (
    <Card>
      <CardTitle className="mb-3">Indexed sources</CardTitle>
      {docs.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : docs.isError ? (
        <ErrorNotice>{errorMessage(docs.error)}</ErrorNotice>
      ) : docs.data.documents.length === 0 ? (
        <EmptyState title="Nothing indexed yet">Upload a PDF or add a link above.</EmptyState>
      ) : (
        <ul className="divide-y divide-border">
          {docs.data.documents.map((d) => {
            const Icon = ICONS[d.source_type ?? ""] ?? FileText;
            const sure = confirm === d.source_key;
            return (
              <li key={d.source_key} className="flex items-center gap-3 py-2.5">
                <Icon className="h-4 w-4 shrink-0 text-muted" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium" title={d.source_key}>
                    {d.docs[0] ?? d.source_key}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {plural(d.chunks, "chunk")}{d.docs.length > 1 ? ` · ${plural(d.docs.length, "document")}` : ""}
                    {d.source_key !== d.docs[0] ? ` · ${d.source_key}` : ""}
                  </p>
                </div>
                {demo ? null : sure ? (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button variant="danger" size="sm" disabled={remove.isPending} onClick={() => remove.mutate(d.source_key)}>
                      Confirm delete
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setConfirm(null)}>
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <Button variant="ghost" size="icon" aria-label={`Delete ${d.source_key}`} onClick={() => setConfirm(d.source_key)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {remove.isError ? <ErrorNotice className="mt-3">{errorMessage(remove.error)}</ErrorNotice> : null}
    </Card>
  );
}
