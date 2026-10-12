"use client";

import { useMutation } from "@tanstack/react-query";
import { Download, NotebookPen } from "lucide-react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import type { Turn } from "./session";

type Format = "pdf" | "html" | "md";

export function NotesPanel({ turns }: { turns: Turn[] }) {
  const finished = turns.filter((t) => t.status === "done" && t.answer).slice(0, 20).reverse();

  const notes = useMutation({
    mutationFn: async () =>
      unwrap(await api.http.POST("/api/v1/notes", { body: { history: finished.map((t) => ({ q: t.question, answer: t.answer })) } })),
  });

  const exportAs = useMutation({
    mutationFn: async (format: Format) => {
      const result = await api.http.POST("/api/v1/export", {
        body: { markdown: notes.data?.markdown ?? "", format, filename: "study-notes" },
        parseAs: "blob",
      });
      if (result.error !== undefined || !result.data) unwrap({ ...result, data: undefined } as never);
      downloadBlob(result.data as Blob, `study-notes.${format}`);
    },
  });

  if (finished.length === 0) return null;
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <CardTitle>Study notes</CardTitle>
        <Button variant="secondary" size="sm" onClick={() => notes.mutate()} disabled={notes.isPending}>
          {notes.isPending ? <Spinner /> : <NotebookPen className="h-4 w-4" />}
          Generate from this session ({finished.length})
        </Button>
      </div>
      {notes.isError ? <ErrorNotice>{errorMessage(notes.error)}</ErrorNotice> : null}
      {notes.data ? (
        <>
          <Markdown className="rounded-lg border border-border bg-bg/40 p-4">{notes.data.markdown}</Markdown>
          <div className="mt-3 flex flex-wrap gap-2">
            {(["md", "html", "pdf"] as const).map((f) => (
              <Button key={f} variant="ghost" size="sm" onClick={() => exportAs.mutate(f)} disabled={exportAs.isPending}>
                <Download className="h-4 w-4" />
                {f.toUpperCase()}
              </Button>
            ))}
          </div>
          {exportAs.isError ? <ErrorNotice className="mt-2">{errorMessage(exportAs.error)}</ErrorNotice> : null}
        </>
      ) : (
        <p className="text-sm text-muted">Turn the questions and answers above into Markdown notes you can download.</p>
      )}
    </Card>
  );
}
