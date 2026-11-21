"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Globe, GitBranch, LockKeyhole, Mic, Search, Trash2, Video, type LucideIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge, EmptyState, ErrorNotice, Skeleton } from "@/components/ui/feedback";
import { Input } from "@/components/ui/field";
import { useDemo } from "@/lib/demo";
import { api, errorMessage, unwrap } from "@/lib/api";
import { plural } from "@/lib/format";
import styles from "./sources.module.css";

const ICONS: Record<string, LucideIcon> = { pdf: FileText, youtube: Video, github: GitBranch, web: Globe, audio: Mic };

export function DocumentsTable({ onDeleted }: { onDeleted?: (sourceKey: string) => void } = {}) {
  const qc = useQueryClient();
  const demo = useDemo();
  const [confirm, setConfirm] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [announcement, setAnnouncement] = useState("");
  // After a delete: the source whose delete button gets focus once the list refreshes ("" = the heading).
  const [focusAfterDelete, setFocusAfterDelete] = useState<string | null>(null);
  const controlId = useId();
  useEffect(() => { if (confirm) document.getElementById(`${controlId}-confirm`)?.focus(); }, [confirm, controlId]);
  const docs = useQuery({ queryKey: ["documents"], queryFn: async () => unwrap(await api.http.GET("/api/v1/documents")) });
  const documents = docs.data?.documents ?? [];
  const query = filter.trim().toLowerCase();
  const filtered = documents.filter((document) => [document.source_key, ...document.docs].some((name) => name.toLowerCase().includes(query)));
  const visible = useRef(filtered);
  useEffect(() => { visible.current = filtered; });

  const remove = useMutation({
    mutationFn: async (key: string) => unwrap(await api.http.DELETE("/api/v1/sources", { params: { query: { key } } })),
    onSuccess: async (_data, key) => {
      const index = visible.current.findIndex((d) => d.source_key === key);
      const next = visible.current[index + 1] ?? visible.current[index - 1];
      setConfirm(null);
      setAnnouncement(`Deleted ${key} and its indexed passages.`);
      onDeleted?.(key);
      await Promise.all(["documents", "stats", "health"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
      setFocusAfterDelete(next ? next.source_key : "");
    },
  });

  useEffect(() => {
    if (focusAfterDelete === null) return;
    const target = focusAfterDelete ? document.getElementById(`${controlId}-${encodeURIComponent(focusAfterDelete)}`) : null;
    (target ?? document.getElementById(`${controlId}-heading`))?.focus();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a one-shot focus request, cleared once handled
    setFocusAfterDelete(null);
  }, [focusAfterDelete, controlId, docs.data]);

  function cancelDelete(key: string) {
    setConfirm(null);
    remove.reset();
    requestAnimationFrame(() => document.getElementById(`${controlId}-${encodeURIComponent(key)}`)?.focus());
  }

  return (
    <Card className="sources-shared-card">
      <div className={styles.sectionHead}>
        <div>
          {demo ? <p className={`${styles.eyebrow} mb-2`}>Indexed sources</p> : null}
          <div className={styles.titleRow}><CardTitle id={`${controlId}-heading`} tabIndex={-1}>{demo ? "Shared textbooks" : "Indexed sources"}</CardTitle>{demo ? <span className={styles.scope}><LockKeyhole className="h-3 w-3" aria-hidden="true" />Read-only collection</span> : null}</div>
          <p className="text-muted">{demo ? "Explore the collection already available to everyone. Your own documents live separately in this browser and never change this shared index." : "Source material available to search and cite. Review the original source name and its indexed passage count."}</p>
        </div>
      </div>
      {docs.isPending ? <div className="space-y-3" role="status" aria-label="Loading indexed sources"><Skeleton className="h-16" /><Skeleton className="h-16" /><span className="sr-only">Loading indexed sources…</span></div> : docs.isError ? (
        <div className="space-y-3"><ErrorNotice>{errorMessage(docs.error)}</ErrorNotice><Button variant="secondary" disabled={docs.isFetching} onClick={() => void docs.refetch()}>{docs.isFetching ? "Retrying…" : "Retry loading sources"}</Button></div>
      ) : documents.length === 0 ? (
        <EmptyState title={demo ? "No shared textbooks yet" : "Nothing indexed yet"}>{demo ? "There are no shared textbooks in this index yet. You can still add your own files to My documents above." : "Upload a PDF or add a link above. It will appear here when indexing finishes."}</EmptyState>
      ) : <>
        <div className={styles.libraryToolbar}>
          <div className={styles.filter}><Search aria-hidden="true" /><Input type="search" aria-label="Filter indexed sources" placeholder="Find a source by name…" value={filter} onChange={(event) => setFilter(event.target.value)} /></div>
          <p className={styles.libraryCount} role="status">{query ? `${filtered.length} of ${documents.length} sources` : plural(documents.length, "source")}</p>
        </div>
        {filtered.length === 0 ? <div className="space-y-3 py-4"><p className="text-sm text-muted">No sources match “{filter}”. Try another name or clear the filter.</p><Button variant="secondary" size="sm" onClick={() => setFilter("")}>Clear filter</Button></div> : <ul className="divide-y divide-border">
          {filtered.map((document) => {
            const Icon = ICONS[document.source_type ?? ""] ?? FileText;
            const sure = confirm === document.source_key;
            return <li key={document.source_key} className={styles.row}>
              <span className={styles.rowIcon}><Icon className="h-4 w-4" aria-hidden="true" /></span>
              <div className={styles.rowBody}>
                <p className={styles.rowName} title={document.source_key}>{document.docs[0] ?? document.source_key}</p>
                <div className={styles.rowMeta}><span>{plural(document.chunks, "passage")}{document.docs.length > 1 ? ` · ${plural(document.docs.length, "document")}` : ""}</span><Badge>{document.source_type?.toUpperCase() || "Source"}</Badge></div>
                {document.source_key !== document.docs[0] ? <span className={styles.sourceKey}>{document.source_key}</span> : null}
              </div>
              {demo ? null : <div className={styles.rowActions}>{sure ? <div className={styles.confirm} role="group" aria-label={`Delete ${document.source_key}?`} onKeyDown={(event) => { if (event.key === "Escape" && !remove.isPending) cancelDelete(document.source_key); }}>
                <p>Delete this source and its indexed passages from the shared library?</p>
                <div className={styles.confirmActions}><Button id={`${controlId}-confirm`} variant="danger" size="sm" disabled={remove.isPending} onClick={() => remove.mutate(document.source_key)}>{remove.isPending ? "Deleting…" : "Confirm delete"}</Button><Button variant="ghost" size="sm" disabled={remove.isPending} onClick={() => cancelDelete(document.source_key)}>Cancel</Button></div>
              </div> : <Button id={`${controlId}-${encodeURIComponent(document.source_key)}`} variant="ghost" size="icon" aria-label={`Delete ${document.source_key}`} onClick={() => { remove.reset(); setConfirm(document.source_key); }}><Trash2 className="h-4 w-4" aria-hidden="true" /></Button>}</div>}
            </li>;
          })}
        </ul>}
      </>}
      <p className={announcement ? "mt-3 text-sm text-good" : "sr-only"} role="status">{announcement}</p>
      {remove.isError ? <ErrorNotice className="mt-3">{errorMessage(remove.error)}. The source has not been marked as deleted; retry or cancel above.</ErrorNotice> : null}
    </Card>
  );
}
