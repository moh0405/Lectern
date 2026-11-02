"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Layers, Square, Trash2 } from "lucide-react";
import { useState } from "react";
import { ChunkCard } from "@/components/chunk-card";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge, ErrorNotice, Notice } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { pageLabel } from "@/lib/format";
import { plainText } from "./flashcards";
import type { Turn } from "./session";

/** What the agentic workflow did, stage by stage. Open while it runs; collapsed once it is done. */
function AgentSteps({ turn }: { turn: Turn }) {
  const steps = turn.steps ?? [];
  if (!turn.agent) return null;
  return (
    <details open={turn.status === "streaming"} className="rounded-lg border border-border bg-bg/40 px-3 py-2 text-sm" aria-label="How it answered">
      <summary className="cursor-pointer select-none text-muted hover:text-fg">
        How it answered ({steps.length} {steps.length === 1 ? "step" : "steps"}
        {turn.llmCalls ? `, ${turn.llmCalls} model calls` : ""})
      </summary>
      <ol className="mt-2 space-y-1">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-2">
            <Badge className="shrink-0 font-mono">{s.name}</Badge>
            <span>{s.detail}</span>
          </li>
        ))}
      </ol>
      {turn.rewritten ? <p className="mt-2 text-xs text-muted">The first answer cited sources it was not given, so it was rewritten.</p> : null}
    </details>
  );
}

const MODE_LABEL = { eli5: "ELI5", technical: "Technical", interview: "Interview", summary: "Summary" } as const;

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Copy answer"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? <Check className="h-4 w-4 text-good" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}

/** Adds this question and answer to the spaced-repetition deck. */
function SaveCardButton({ turn }: { turn: Turn }) {
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.http.POST("/api/v1/cards", {
          body: { front: turn.question.slice(0, 1200), back: plainText(turn.answer).slice(0, 1200), source: turn.chunks[0]?.doc ?? null },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["cards"] }),
  });
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={save.isSuccess ? "Saved as flashcard" : save.isError ? `Could not save: ${errorMessage(save.error)}` : "Save as flashcard"}
      title={save.isError ? errorMessage(save.error) : "Save as flashcard"}
      disabled={save.isPending || save.isSuccess}
      onClick={() => save.mutate()}
    >
      {save.isSuccess ? <Check className="h-4 w-4 text-good" /> : <Layers className="h-4 w-4" />}
    </Button>
  );
}

const CITE_PROBLEM: Record<string, string> = {
  unknown_source: "that source was not among the passages it was given",
  page_not_retrieved: "that page was not among the passages it was given",
};

function CitationWarnings({ turn }: { turn: Turn }) {
  const bad = (turn.citations ?? []).filter((c) => c.status !== "ok");
  if (bad.length === 0 && !turn.uncited) return null;
  return (
    <Notice>
      {bad.length > 0 ? (
        <>
          <p className="font-medium">
            {bad.length === 1 ? "This answer cites something it was not given." : "This answer cites things it was not given."} Check
            before relying on it.
          </p>
          <ul className="mt-1 list-disc pl-5">
            {bad.map((c) => (
              <li key={c.label}>
                <span className="font-mono text-xs">[{c.label}]</span>: {CITE_PROBLEM[c.status]}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>This answer does not cite any of the sources it was given, so you cannot tell where it came from.</p>
      )}
    </Notice>
  );
}

export function TurnCard({
  turn,
  onStop,
  onRemove,
  onFresh,
}: {
  turn: Turn;
  onStop: () => void;
  onRemove: () => void;
  onFresh?: () => void;
}) {
  const streaming = turn.status === "streaming";
  const noKey = turn.error?.code === "llm_unavailable";
  return (
    <Card className="space-y-4" aria-busy={streaming}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold leading-snug">{turn.question}</h2>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {turn.mode ? <Badge>{MODE_LABEL[turn.mode]}</Badge> : null}
            {turn.model ? <Badge>{turn.model}</Badge> : null}
            {turn.cached ? <Badge title="Served from the cache; nothing new was sent to the model">cached</Badge> : null}
            {turn.agent ? <Badge title="Answered by the agentic workflow (LangGraph)">agentic</Badge> : null}
            {turn.status === "stopped" ? <Badge>stopped</Badge> : null}
          </div>
        </div>
        <div className="flex shrink-0 gap-1">
          {streaming ? (
            <Button variant="secondary" size="sm" onClick={onStop}>
              <Square className="h-3.5 w-3.5" /> Stop
            </Button>
          ) : (
            <>
              {turn.cached && onFresh ? (
                <Button variant="ghost" size="sm" onClick={onFresh}>
                  Fresh answer
                </Button>
              ) : null}
              {turn.answer ? <CopyButton text={turn.answer} /> : null}
              {turn.answer && turn.status === "done" ? <SaveCardButton turn={turn} /> : null}
              <Button variant="ghost" size="icon" aria-label="Remove" onClick={onRemove}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      </div>

      {noKey ? (
        <Notice>
          The server has no language-model key configured, so it cannot write an answer. Retrieval still works: the sources
          below are the passages it found.
        </Notice>
      ) : turn.error ? (
        <ErrorNotice>{turn.error.message}</ErrorNotice>
      ) : null}

      <AgentSteps turn={turn} />

      {turn.answer || streaming ? (
        <div aria-live="polite">
          {turn.answer ? <Markdown streaming={streaming}>{turn.answer}</Markdown> : <p className="text-sm text-muted">Thinking…</p>}
        </div>
      ) : null}

      {turn.status === "done" ? <CitationWarnings turn={turn} /> : null}

      {turn.prompt ? (
        <details>
          <summary className="cursor-pointer select-none text-sm text-muted hover:text-fg">Prompt sent to the model</summary>
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-bg/60 p-3 font-mono text-xs">{turn.prompt}</pre>
        </details>
      ) : null}

      {turn.chunks.length > 0 ? (
        <details open={!turn.answer || turn.status === "error"} className="group">
          <summary className="cursor-pointer select-none list-none text-sm text-muted hover:text-fg [&::-webkit-details-marker]:hidden">
            <span className="mr-2">Sources ({turn.chunks.length})</span>
            <span className="inline-flex flex-wrap gap-1.5 align-middle">
              {turn.chunks.map((c, i) => (
                <Badge key={i} title={`Relevance ${c.score.toFixed(2)}`} className="font-mono">
                  [{i + 1}] {c.doc}
                  {c.page ? ` · ${pageLabel(c.page, c.end_page, true)}` : ""}
                </Badge>
              ))}
            </span>
          </summary>
          <div className="mt-3 grid gap-2">
            {turn.chunks.map((c, i) => (
              <ChunkCard key={i} chunk={c} query={turn.question} index={i} />
            ))}
          </div>
        </details>
      ) : turn.status !== "streaming" && !turn.error ? (
        <p className="text-sm text-muted">No matching passages were found in your sources.</p>
      ) : null}
    </Card>
  );
}
