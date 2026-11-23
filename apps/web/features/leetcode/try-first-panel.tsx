"use client";

import { useMutation } from "@tanstack/react-query";
import type { Chunk } from "@ai-study-mentor/api-client";
import { PenLine } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Notice, Spinner } from "@/components/ui/feedback";
import { Label, Select, Textarea } from "@/components/ui/field";
import { Segmented } from "@/components/ui/segmented";
import { ATTEMPT_FORMATS, CODE_LANGUAGES, MAX_ATTEMPT } from "@/features/ask/attempt";
import { AttemptFeedbackView } from "@/features/ask/attempt-feedback";
import type { Selection } from "@/features/ask/citation-chip";
import { InlinePassage } from "@/features/ask/inline-passage";
import type { AttemptFormat, Turn } from "@/features/ask/session";
import { ApiError, api, errorMessage, unwrap } from "@/lib/api";
import { attemptContext, attemptQuestion, LIBRARY_PASSAGES, librarySearch, type TryFirstProblem } from "./try-first";

/**
 * Write an attempt before reading the study guide. The check is one model call, made only by "Check my attempt"; the
 * library search before it is not a model call, and if it fails the attempt is still judged against the statement.
 */
export function TryFirstPanel({ problem, guideShown, guideBusy, onShowGuide }: { problem: TryFirstProblem; guideShown: boolean; guideBusy: boolean; onShowGuide: () => void }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<AttemptFormat>("code");
  const [language, setLanguage] = useState("Python");
  const [text, setText] = useState("");
  const [selection, setSelection] = useState<Selection | null>(null);
  const question = attemptQuestion(problem);
  const check = useMutation({
    mutationFn: async () => {
      let library: Chunk[] = [];
      try {
        library = unwrap(await api.http.GET("/api/v1/search", { params: { query: { query: librarySearch(problem), k: LIBRARY_PASSAGES } } })).chunks;
      } catch { /* The statement alone is still something to judge against. */ }
      return unwrap(await api.http.POST("/api/v1/attempt/feedback", {
        body: { question, attempt: text, format, language: format === "code" ? language : undefined, context: attemptContext(problem, library) },
      }));
    },
    onMutate: () => setSelection(null),
  });
  const noKey = check.error instanceof ApiError && check.error.code === "llm_unavailable";
  const blocked = !text.trim() || check.isPending;
  const hint = ATTEMPT_FORMATS.find((f) => f.value === format)?.hint;
  const feedback = check.data;
  const turn: Turn | null = feedback ? {
    id: `leetcode-${problem.pid}`,
    question,
    answer: "",
    chunks: feedback.chunks,
    status: "done",
    attempt: { params: { question, k: LIBRARY_PASSAGES, temperature: 0.2 }, text, format: feedback.format, language: feedback.format === "code" ? language : undefined, feedback, evidenceStarted: guideShown },
  } : null;

  if (!open) {
    return <Button variant="secondary" aria-expanded={false} onClick={() => setOpen(true)}><PenLine className="h-4 w-4" aria-hidden="true" /> Try first</Button>;
  }
  return (
    <div className="space-y-3">
      <Button variant="secondary" aria-expanded onClick={() => setOpen(false)}><PenLine className="h-4 w-4" aria-hidden="true" /> Try first</Button>
      <form
        className="space-y-3 rounded-lg border border-border p-4"
        aria-label="Your attempt at this problem"
        noValidate
        onSubmit={(event) => { event.preventDefault(); if (!blocked) check.mutate(); }}
      >
        <Segmented legend="Attempt format" name={`${id}-format`} options={ATTEMPT_FORMATS.map((f) => ({ value: f.value, label: f.label }))} value={format} onChange={setFormat} />
        {format === "code" ? (
          <div className="max-w-56">
            <Label htmlFor={`${id}-language`}>Language</Label>
            <Select id={`${id}-language`} value={language} onChange={(event) => setLanguage(event.target.value)}>
              {CODE_LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
            </Select>
          </div>
        ) : null}
        <div>
          <Label htmlFor={`${id}-attempt`}>Your attempt</Label>
          <p id={`${id}-hint`} className="mb-1 text-xs text-muted">{hint}</p>
          <Textarea id={`${id}-attempt`} aria-describedby={`${id}-hint`} rows={6} maxLength={MAX_ATTEMPT} value={text} className={format === "code" ? "font-mono" : undefined} onChange={(event) => setText(event.target.value)} />
        </div>
        <Button type="submit" aria-disabled={blocked || undefined}>
          {check.isPending ? <Spinner /> : null}
          {check.isPending ? "Checking…" : feedback ? "Check again" : "Check my attempt"}
        </Button>
        <p className="text-xs text-muted">Uses one model call. Checked against the problem statement and your library, without giving the solution.</p>
      </form>
      {noKey ? <Notice>The server has no language-model key configured, so it cannot check attempts.</Notice> : check.isError ? <ErrorNotice>{errorMessage(check.error)}</ErrorNotice> : null}
      {turn ? (
        <AttemptFeedbackView
          turn={turn}
          selection={selection ?? undefined}
          onSelect={setSelection}
          onEvidence={onShowGuide}
          blocked={guideBusy}
          narrow
          evidenceLabel="Show the study guide"
          evidenceNote="The full approach and a Python solution, when you are ready."
          inlinePassage={selection ? <InlinePassage turn={turn} refs={[]} selection={selection} onClose={() => setSelection(null)} /> : null}
        />
      ) : null}
    </div>
  );
}
