"use client";

import { FileText, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type DragEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { chunkPages } from "@/lib/browser-rag/chunk";
import { EMBEDDING_DIM, embedTexts, loadEmbedder } from "@/lib/browser-rag/embed";
import { ACCEPT, extractPages } from "@/lib/browser-rag/extract";
import { deleteDoc, newDocId, saveDoc } from "@/lib/browser-rag/store";
import { LOCAL_DOCS_KEY, useLocalDocs } from "@/lib/browser-rag/use-local-docs";
import { errorMessage } from "@/lib/api";
import { plural } from "@/lib/format";
import { cn } from "@/lib/utils";

const MAX_PASSAGES = 8000;

/** Add documents that never leave this browser. Used in the public demo, where the shared index is read-only. */
export function MyDocumentsCard() {
  const qc = useQueryClient();
  const docs = useLocalDocs();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  async function addFile(file: File) {
    setBusy(`Reading ${file.name}…`);
    const pages = await extractPages(file, (n, total) => setBusy(`Reading ${file.name}: page ${n} of ${total}`));
    const passages = chunkPages(pages).slice(0, MAX_PASSAGES);
    setBusy(`Preparing ${file.name} for meaning search…`);
    await loadEmbedder((s) => setBusy(s));
    const vectors = await embedTexts(
      passages.map((p) => p.text),
      (done, total) => setBusy(`Indexing ${file.name}: ${done} of ${total} passages`),
    );
    const flat = vectors ? new Float32Array(vectors.length * EMBEDDING_DIM) : null;
    vectors?.forEach((v, i) => flat!.set(v, i * EMBEDDING_DIM));
    await saveDoc({ id: newDocId(), name: file.name, addedAt: Date.now(), pages: pages.length, passages, vectors: flat, dim: EMBEDDING_DIM });
    await qc.invalidateQueries({ queryKey: LOCAL_DOCS_KEY });
  }

  async function addFiles(list: FileList | File[] | null) {
    const files = Array.from(list ?? []);
    if (!files.length) return;
    setErrors([]);
    for (const f of files) {
      try {
        await addFile(f);
      } catch (e) {
        setErrors((prev) => [...prev, errorMessage(e)]);
      }
    }
    setBusy(null);
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    void addFiles(e.dataTransfer.files);
  };

  return (
    <Card aria-label="My documents">
      <CardTitle className="mb-1">My documents</CardTitle>
      <p className="mb-3 text-sm text-muted">
        Add your own PDF or notes. They are read and searched <strong className="font-medium text-fg">inside this browser</strong>: the file is never uploaded, and there is no size limit from the server. Only the few passages that match a question are sent to the model when you ask.
      </p>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn("flex flex-col items-center gap-2 rounded-lg border border-dashed p-6 text-center transition-colors", over ? "border-accent bg-accent/10" : "border-border")}
      >
        {busy ? <Spinner className="h-6 w-6" /> : <Upload className="h-6 w-6 text-muted" />}
        <p className="text-sm" role="status">{busy ?? "Drop PDFs, .txt or .md files here, or"}</p>
        <Button type="button" onClick={() => input.current?.click()} disabled={busy !== null}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          aria-label="Add my documents"
          className="sr-only"
          onChange={(e) => {
            void addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <p className="text-xs text-muted">The first one downloads a small search model (about 25 MB, then cached). Large books take a few minutes.</p>
      </div>
      {errors.map((m) => (
        <ErrorNotice key={m} className="mt-3">{m}</ErrorNotice>
      ))}
      {docs.data?.length ? (
        <ul className="mt-4 space-y-2" aria-label="Your documents">
          {docs.data.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface/80 p-3">
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="h-4 w-4 shrink-0 text-muted" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{d.name}</p>
                  <p className="text-xs text-muted">
                    {plural(d.pages, "page")} · {plural(d.passages.length, "passage")}
                  </p>
                </div>
                <Badge>{d.vectors ? "meaning + keyword search" : "keyword search"}</Badge>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove ${d.name}`}
                onClick={async () => {
                  await deleteDoc(d.id);
                  await qc.invalidateQueries({ queryKey: LOCAL_DOCS_KEY });
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {docs.data?.length ? (
        <p className="mt-3 text-sm">
          <Link href="/ask" className="text-accent-2 underline">Ask about your documents</Link>
        </p>
      ) : null}
    </Card>
  );
}
