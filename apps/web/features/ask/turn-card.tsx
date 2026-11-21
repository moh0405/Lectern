"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  Copy,
  Layers,
  Link2,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
import { useCallback, useId, useMemo, useState } from "react";
import { ChunkCard } from "@/components/chunk-card";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Badge, ErrorNotice, Notice } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { pageLabel } from "@/lib/format";
import { CITE_PREFIX, linkCitations, twoDigits, type CiteRef } from "./citations";
import { plainText } from "./flashcards";
import type { Turn } from "./session";
import styles from "./ask.module.css";

/** What the agentic workflow did, stage by stage. Open while it runs; collapsed once it is done. */
function AgentSteps({ turn }: { turn: Turn }) {
  const steps = turn.steps ?? [];
  if (!turn.agent) return null;
  return (
    <details
      open={turn.status === "streaming"}
      className="rounded-lg border border-border bg-bg/40 px-3 py-2 text-sm"
      aria-label="How it answered"
    >
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
      {turn.rewritten ? (
        <p className="mt-2 text-xs text-muted">
          The first answer cited sources it was not given, so it was rewritten.
        </p>
      ) : null}
    </details>
  );
}

const MODE_LABEL = {
  eli5: "ELI5",
  technical: "Technical",
  interview: "Interview",
  summary: "Summary",
} as const;

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const errorId = useId();
  return (
    <span className={styles.copyControl}>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Copy answer"
        aria-describedby={copyError ? errorId : undefined}
        onClick={async () => {
          setCopyError(false);
          try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            setCopyError(true);
          }
        }}
      >
        {copied ? (
          <Check className="h-4 w-4 text-good" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </Button>
      {copyError ? (
        <span id={errorId} role="status" className={styles.copyFeedback}>
          Copy is unavailable. Select the answer text to copy it manually.
        </span>
      ) : null}
    </span>
  );
}

/** Adds this question and answer to the spaced-repetition deck. */
function SaveCardButton({ turn }: { turn: Turn }) {
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.http.POST("/api/v1/cards", {
          body: {
            front: turn.question.slice(0, 1200),
            back: plainText(turn.answer).slice(0, 1200),
            source: turn.chunks[0]?.doc ?? null,
          },
        }),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["cards"] }),
  });
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={
        save.isSuccess
          ? "Saved as flashcard"
          : save.isError
            ? `Could not save: ${errorMessage(save.error)}`
            : "Save as flashcard"
      }
      title={save.isError ? errorMessage(save.error) : "Save as flashcard"}
      disabled={save.isPending || save.isSuccess}
      onClick={() => save.mutate()}
    >
      {save.isSuccess ? (
        <Check className="h-4 w-4 text-good" />
      ) : (
        <Layers className="h-4 w-4" />
      )}
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
            {bad.length === 1
              ? "This answer cites something it was not given."
              : "This answer cites things it was not given."}{" "}
            Check before relying on it.
          </p>
          <ul className="mt-1 list-disc pl-5">
            {bad.map((c) => (
              <li key={c.label}>
                <span className="font-mono text-xs">[{c.label}]</span>:{" "}
                {CITE_PROBLEM[c.status]}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>
          This answer does not cite any of the sources it was given, so you
          cannot tell where it came from.
        </p>
      )}
    </Notice>
  );
}

/** What the source margin is showing: a citation chip (ref) and/or a retrieved passage (chunk). */
export interface Selection {
  ref: number | null;
  chunk: number | null;
}

function CitationChip({ refInfo, active, onSelect }: { refInfo: CiteRef; active: boolean; onSelect: () => void }) {
  const verified = refInfo.chunk !== null;
  const label = verified
    ? `Citation ${refInfo.label}: show passage ${refInfo.chunk! + 1} in the source margin`
    : `Unverified citation ${refInfo.label}: ${CITE_PROBLEM[refInfo.status] ?? "it could not be matched to a passage"}`;
  return (
    <button
      type="button"
      className={verified ? "cite-chip" : "cite-chip unverified"}
      aria-pressed={active}
      aria-label={label}
      title={refInfo.label}
      data-cite-active={active ? "true" : undefined}
      onClick={onSelect}
    >
      {verified ? (
        <>
          {twoDigits(refInfo.chunk! + 1)}
          <ArrowUpRight aria-hidden="true" />
        </>
      ) : (
        <>
          <AlertTriangle aria-hidden="true" />?
        </>
      )}
    </button>
  );
}

export function TurnCard({
  turn,
  onStop,
  onRemove,
  onFresh,
  busy = false,
  selection,
  onSelect,
}: {
  turn: Turn;
  onStop: () => void;
  onRemove: () => void;
  onFresh?: () => void;
  busy?: boolean;
  /** On the Evidence Desk: which citation is open in the source margin, and how to open another. */
  selection?: Selection;
  onSelect?: (selection: Selection) => void;
}) {
  const streaming = turn.status === "streaming";
  const noKey = turn.error?.code === "llm_unavailable";
  // Citations become chips once the server has checked them (at the end of the stream).
  const linked = useMemo(
    () => (onSelect && turn.status === "done" ? linkCitations(turn.answer, turn.citations, turn.chunks) : null),
    [onSelect, turn.status, turn.answer, turn.citations, turn.chunks],
  );
  const renderLink = useCallback(
    (href: string) => {
      if (!linked || !href.startsWith(CITE_PREFIX)) return undefined;
      const ref = linked.refs[Number(href.slice(CITE_PREFIX.length))];
      if (!ref) return undefined;
      return <CitationChip refInfo={ref} active={selection?.ref === ref.id} onSelect={() => onSelect?.({ ref: ref.id, chunk: ref.chunk })} />;
    },
    [linked, selection?.ref, onSelect],
  );
  return (
    <div className={`space-y-4 ${styles.turn}`} aria-busy={streaming}>
      <div className={styles.turnHeading}>
        <div className="min-w-0">
          <p className={styles.eyebrow}>From a question to its evidence</p>
          <h2 className={styles.turnQuestion}>{turn.question}</h2>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {turn.mode ? <Badge>{MODE_LABEL[turn.mode]}</Badge> : null}
            {turn.model ? <Badge>{turn.model}</Badge> : null}
            {turn.cached ? (
              <Badge title="Served from the cache; nothing new was sent to the model">
                cached
              </Badge>
            ) : null}
            {turn.agent ? (
              <Badge title="Answered by the agentic workflow (LangGraph)">
                agentic
              </Badge>
            ) : null}
            {turn.status === "stopped" ? <Badge>stopped</Badge> : null}
          </div>
        </div>
        <div className={styles.turnActions}>
          {streaming ? (
            <Button variant="secondary" size="sm" onClick={onStop}>
              <Square className="h-3.5 w-3.5" /> Stop
            </Button>
          ) : (
            <>
              {turn.cached && onFresh ? (
                <Button variant="ghost" size="sm" onClick={onFresh} disabled={busy}>
                  Fresh answer
                </Button>
              ) : null}
              {turn.answer ? <CopyButton text={turn.answer} /> : null}
              {turn.answer && turn.status === "done" ? (
                <SaveCardButton turn={turn} />
              ) : null}
              <Button
                variant="ghost"
                size="icon"
                aria-label="Remove"
                onClick={onRemove}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      </div>

      {noKey ? (
        <Notice>
          The server has no language-model key configured, so it cannot write an
          answer. Retrieval still works: the sources below are the passages it
          found.
        </Notice>
      ) : turn.error ? (
        <div className="space-y-3"><ErrorNotice>{turn.error.message}</ErrorNotice>{onFresh ? <Button variant="secondary" onClick={onFresh} disabled={busy}>Try this question again</Button> : null}</div>
      ) : null}

      <AgentSteps turn={turn} />

      {turn.answer || streaming ? (
        <div className={styles.answer} aria-live="polite" data-step="evidence">
          <p className={styles.answerLabel}>
            <Sparkles aria-hidden="true" />
            {streaming ? "Building your answer" : "An explanation you can inspect"}
          </p>
          {turn.answer ? (
            <Markdown streaming={streaming} renderLink={linked?.refs.length ? renderLink : undefined}>
              {linked?.markdown ?? turn.answer}
            </Markdown>
          ) : (
            <p className="text-sm text-muted">Thinking…</p>
          )}
          {linked?.refs.some((r) => r.chunk !== null) ? (
            <p className={styles.traceHint}>
              <Link2 aria-hidden="true" />
              <span>
                <strong>Read the connection.</strong> Select a citation to open its passage in the source margin.
              </span>
            </p>
          ) : null}
        </div>
      ) : null}

      {turn.status === "done" ? <CitationWarnings turn={turn} /> : null}

      {turn.prompt ? (
        <details>
          <summary className="cursor-pointer select-none text-sm text-muted hover:text-fg">
            Prompt sent to the model
          </summary>
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-bg/60 p-3 font-mono text-xs">
            {turn.prompt}
          </pre>
        </details>
      ) : null}

      {turn.chunks.length > 0 ? (
        <details
          open={!turn.answer || turn.status === "error"}
          className={styles.evidence}
          data-step="evidence"
        >
          <summary className={styles.evidenceSummary}>
            <BookOpen aria-hidden="true" />
            <span className="mr-2">Sources ({turn.chunks.length})</span>
            <span className={styles.sourceBadges}>
              {turn.chunks.map((c, i) => (
                <Badge
                  key={i}
                  title={`Relevance ${c.score.toFixed(2)}`}
                  className="font-mono"
                >
                  [{i + 1}] {c.doc}
                  {c.page ? ` · ${pageLabel(c.page, c.end_page, true)}` : ""}
                </Badge>
              ))}
            </span>
            <ChevronDown
              className={styles.evidenceChevron}
              aria-hidden="true"
            />
          </summary>
          <div className={styles.passages}>
            {turn.chunks.map((c, i) => (
              <div key={i} className={styles.passage}>
                <ChunkCard chunk={c} query={turn.question} index={i} />
                {onSelect ? (
                  <button type="button" className={styles.passageOpen} aria-pressed={selection?.chunk === i && selection.ref === null} onClick={() => onSelect({ ref: null, chunk: i })}>
                    Open passage {i + 1} in the margin
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      ) : turn.status !== "streaming" && !turn.error ? (
        <p className="text-sm text-muted">
          No matching passages were found in your sources.
        </p>
      ) : null}
    </div>
  );
}
