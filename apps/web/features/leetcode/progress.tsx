"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleDot } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/ui/feedback";
import { Label, Textarea } from "@/components/ui/field";
import { useDemo } from "@/lib/demo";
import { api, errorMessage, unwrap } from "@/lib/api";
import { loadLocalProgress, saveLocalProgress, type ProblemMeta } from "@/lib/local-progress";
import { cn } from "@/lib/utils";

export type Status = "todo" | "attempted" | "solved";

export const STATUS_LABEL: Record<Status, string> = { todo: "To do", attempted: "Attempted", solved: "Solved" };

/** How long typing pauses before notes save themselves. */
export const NOTES_AUTOSAVE_MS = 1500;

/** Everything you have marked, by problem id. Shared by the list, the detail panel and the plan. */
export function useProgress() {
  const demo = useDemo();
  return useQuery({
    queryKey: ["lc-progress"],
    // In the public demo the marks live in this browser; the shared server database stays off.
    queryFn: async () => (demo ? loadLocalProgress() : unwrap(await api.http.GET("/api/v1/leetcode/progress"))),
  });
}

export function StatusIcon({ status, className }: { status?: Status; className?: string }) {
  if (status === "solved") return <CheckCircle2 aria-label="Solved" className={cn("h-4 w-4 text-good", className)} />;
  if (status === "attempted") return <CircleDot aria-label="Attempted" className={cn("h-4 w-4 text-warn", className)} />;
  return null;
}

export function ProgressPanel({ problem }: { problem: ProblemMeta }) {
  const { pid } = problem;
  const demo = useDemo();
  const qc = useQueryClient();
  const progress = useProgress();
  const current = progress.data?.items.find((i) => i.pid === pid);
  const notesField = useRef<HTMLTextAreaElement>(null);
  const saveButton = useRef<HTMLButtonElement>(null);
  // `draft` is what is typed; `savedNotes` what this panel last saved (the list may not have refetched yet).
  // The panel is remounted per problem (key={pid}).
  const [draft, setDraft] = useState<string | null>(null);
  const [savedNotes, setSavedNotes] = useState<string | null>(null);
  const [saved, setSaved] = useState("");
  const serverNotes = savedNotes ?? current?.notes ?? "";
  const notes = draft ?? serverNotes;
  const dirty = notes !== serverNotes;

  const save = useMutation({
    mutationFn: async (v: { status: Status; notes?: string }) =>
      demo ? saveLocalProgress(problem, v) : unwrap(await api.http.PUT("/api/v1/leetcode/progress/{pid}", { params: { path: { pid } }, body: v })),
    onSuccess: (_row, v) => {
      if (v.notes !== undefined) {
        setSavedNotes(v.notes);
        setSaved("Notes saved.");
        // The Save button disappears once saved; keep keyboard focus in the notes rather than losing it.
        if (document.activeElement === document.body || document.activeElement === null) notesField.current?.focus();
      }
      void qc.invalidateQueries({ queryKey: ["lc-progress"] });
      void qc.invalidateQueries({ queryKey: ["lc-plan"] });
    },
  });
  const status: Status = current?.status ?? "todo";
  const saveNotes = () => { if (dirty && !save.isPending) save.mutate({ status, notes }); };

  // Notes save themselves after a pause in typing (and when the field is left), so a reload never loses them.
  const latest = useRef(saveNotes);
  useEffect(() => { latest.current = saveNotes; });
  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(() => latest.current(), NOTES_AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [notes, dirty]);

  return (
    <div className="space-y-3 rounded-lg border border-border bg-bg/40 p-3" aria-label="Your progress" role="group">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Status">
        {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
          <Button
            key={s}
            size="sm"
            variant={status === s ? "primary" : "secondary"}
            aria-pressed={status === s}
            disabled={save.isPending}
            onClick={() => save.mutate(dirty ? { status: s, notes } : { status: s })}
          >
            {STATUS_LABEL[s]}
          </Button>
        ))}
        {current && current.attempts > 0 ? <span className="text-xs text-muted">{current.attempts} {current.attempts === 1 ? "attempt" : "attempts"}</span> : null}
      </div>
      <div>
        <Label htmlFor={`notes-${pid}`}>Notes</Label>
        <Textarea
          ref={notesField}
          id={`notes-${pid}`}
          rows={2}
          maxLength={4000}
          value={notes}
          onChange={(e) => { setDraft(e.target.value); setSaved(""); }}
          onBlur={(e) => { if (e.relatedTarget !== saveButton.current) saveNotes(); }}
          placeholder="What tripped you up? What was the key idea?"
        />
        <div className="mt-2 flex min-h-10 flex-wrap items-center gap-3">
          {dirty ? (
            <Button ref={saveButton} size="sm" disabled={save.isPending} onClick={saveNotes}>
              Save notes
            </Button>
          ) : null}
          <p className="text-xs text-muted" role="status">{save.isPending && dirty ? "Saving…" : dirty ? "Notes save automatically when you pause." : saved}</p>
        </div>
      </div>
      {save.isError ? <ErrorNotice>{errorMessage(save.error)}. Your notes are still here; they will save when you try again.</ErrorNotice> : null}
    </div>
  );
}
