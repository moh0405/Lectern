"use client";

import { useMutation } from "@tanstack/react-query";
import { Download, NotebookPen } from "lucide-react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { downloadBlob } from "@/lib/download";
import { toFlashcardsCsv, toNotesMarkdown } from "./flashcards";
import type { Turn } from "./session";
import styles from "./ask.module.css";

type Format = "pdf" | "html" | "md";

export function NotesPanel({ turns }: { turns: Turn[] }) {
  // The public demo refuses /notes and /export, so notes are written in the browser and downloaded as Markdown.
  const demo = useDemo();
  const finished = turns
    .filter((t) => t.status === "done" && t.answer)
    .slice(0, 20)
    .reverse();

  const notes = useMutation({
    mutationFn: async () =>
      demo
        ? { markdown: toNotesMarkdown(finished) }
        : unwrap(
        await api.http.POST("/api/v1/notes", {
          body: {
            history: finished.map((t) => ({ q: t.question, answer: t.answer })),
          },
        }),
      ),
  });

  const exportAs = useMutation({
    mutationFn: async (format: Format) => {
      if (demo) {
        downloadBlob(new Blob([notes.data?.markdown ?? ""], { type: "text/markdown" }), "study-notes.md");
        return;
      }
      const result = await api.http.POST("/api/v1/export", {
        body: {
          markdown: notes.data?.markdown ?? "",
          format,
          filename: "study-notes",
        },
        parseAs: "blob",
      });
      if (result.error !== undefined || !result.data)
        unwrap({ ...result, data: undefined } as never);
      downloadBlob(result.data as Blob, `study-notes.${format}`);
    },
  });

  if (finished.length === 0) return null;
  return (
    <Card className={styles.notes}>
      <div className={styles.notesHeading}>
        <div>
          <p className={styles.eyebrow}>KEEP WHAT YOU LEARN</p>
          <CardTitle>Study notes</CardTitle>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              downloadBlob(
                new Blob([toFlashcardsCsv(turns)], { type: "text/csv" }),
                "flashcards.csv",
              )
            }
          >
            <Download className="h-4 w-4" />
            Flashcards (CSV)
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => notes.mutate()}
            disabled={notes.isPending}
          >
            {notes.isPending ? (
              <Spinner />
            ) : (
              <NotebookPen className="h-4 w-4" />
            )}
            Generate from this session ({finished.length})
          </Button>
        </div>
      </div>
      {notes.isError ? (
        <ErrorNotice>{errorMessage(notes.error)}</ErrorNotice>
      ) : null}
      {notes.data ? (
        <>
          <Markdown className={styles.notesContent}>
            {notes.data.markdown}
          </Markdown>
          <div className="mt-3 flex flex-wrap gap-2">
            {(demo ? (["md"] as const) : (["md", "html", "pdf"] as const)).map((f) => (
              <Button
                key={f}
                variant="ghost"
                size="sm"
                onClick={() => exportAs.mutate(f)}
                disabled={exportAs.isPending}
              >
                <Download className="h-4 w-4" />
                {f.toUpperCase()}
              </Button>
            ))}
          </div>
          {demo ? <p className="mt-2 text-xs text-muted">Written in this browser from your answers. HTML and PDF exports need a private Lectern server.</p> : null}
          {exportAs.isError ? (
            <ErrorNotice className="mt-2">
              {errorMessage(exportAs.error)}
            </ErrorNotice>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-muted">
          Turn the questions and answers above into Markdown notes you can
          download.
        </p>
      )}
    </Card>
  );
}
