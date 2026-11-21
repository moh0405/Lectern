"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, Check, ChevronDown, Copy, Layers, Link2, Plus, Sparkles, Square, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Markdown } from "@/components/markdown";
import { ChunkCard } from "@/components/chunk-card";
import { Button } from "@/components/ui/button";
import { Badge, ErrorNotice, Notice } from "@/components/ui/feedback";
import { api, errorMessage, unwrap } from "@/lib/api";
import { useDemo } from "@/lib/demo";
import { pageLabel } from "@/lib/format";
import { addLocalCard } from "@/lib/local-cards";
import { cn } from "@/lib/utils";
import { CITE_PROBLEM, CitedMarkdown, CiteProvider, type Selection } from "./citation-chip";
import { linkCitations, type LinkedAnswer } from "./citations";
import { plainText } from "./flashcards";
import { groundingOf, verdictText } from "./grounding";
import type { Turn } from "./session";
import styles from "./ask.module.css";

export type { Selection } from "./citation-chip";

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

type Announce = (message: string) => void;

function CopyButton({ text, announce }: { text: string; announce?: Announce }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const errorId = useId();
  return (
    <span className={styles.copyControl}>
      <Button
        variant="ghost"
        size="sm"
        className={styles.actionButton}
        aria-label="Copy answer"
        aria-describedby={copyError ? errorId : undefined}
        onClick={async () => {
          setCopyError(false);
          try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            announce?.("Answer copied");
            setTimeout(() => setCopied(false), 1500);
          } catch {
            setCopyError(true);
          }
        }}
      >
        {copied ? <Check className="h-4 w-4 text-good" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
        <span className={styles.actionLabel}>{copied ? "Copied" : "Copy"}</span>
      </Button>
      {copyError ? (
        <span id={errorId} role="status" className={styles.copyFeedback}>
          Copy is unavailable. Select the answer text to copy it manually.
        </span>
      ) : null}
    </span>
  );
}

/**
 * Adds this question and answer to the spaced-repetition deck: on the server, or in this browser in the public demo
 * (which refuses server writes). Stays focusable once saved (aria-disabled), so keyboard focus is not lost.
 */
function SaveCardButton({ turn, announce }: { turn: Turn; announce?: Announce }) {
  const qc = useQueryClient();
  const demo = useDemo();
  const errorId = useId();
  const save = useMutation({
    mutationFn: async () => {
      const front = turn.question.slice(0, 1200);
      const back = plainText(turn.answer).slice(0, 1200);
      if (demo) return addLocalCard(front, back);
      return unwrap(await api.http.POST("/api/v1/cards", { body: { front, back, source: turn.chunks[0]?.doc ?? null } }));
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cards"] });
      announce?.(demo ? "Saved to flashcards in this browser" : "Saved to flashcards");
    },
    onError: (err) => announce?.(`Could not save the flashcard: ${errorMessage(err)}`),
  });
  const unavailable = save.isPending || save.isSuccess;
  return (
    <span className={styles.copyControl}>
      <Button
        variant="ghost"
        size="sm"
        className={styles.actionButton}
        aria-label={save.isSuccess ? "Saved as flashcard" : "Save as flashcard"}
        aria-describedby={save.isError ? errorId : undefined}
        aria-disabled={unavailable || undefined}
        title={save.isError ? errorMessage(save.error) : "Save as flashcard"}
        onClick={() => {
          if (!unavailable) save.mutate();
        }}
      >
        {save.isSuccess ? <Check className="h-4 w-4 text-good" aria-hidden="true" /> : <Layers className="h-4 w-4" aria-hidden="true" />}
        <span className={styles.actionLabel}>{save.isSuccess ? (demo ? "Saved to this browser" : "Saved") : "Save card"}</span>
      </Button>
      {save.isSuccess && demo ? <span className={styles.savedNote}>Saved to this browser</span> : null}
      {save.isError ? (
        <span id={errorId} className={styles.copyFeedback}>
          Could not save: {errorMessage(save.error)}
        </span>
      ) : null}
    </span>
  );
}

function CitationWarnings({ turn }: { turn: Turn }) {
  const bad = (turn.citations ?? []).filter((c) => c.status !== "ok");
  if (bad.length === 0 && !turn.uncited) return null;
  return (
    <Notice>
      {bad.length > 0 ? (
        <>
          <p className="font-medium">{bad.length === 1 ? "This answer cites something it was not given." : "This answer cites things it was not given."} Check before relying on it.</p>
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

/** The question as the turn's heading: scaled by length and clamped to three lines, with a way to read all of it. */
function QuestionHeading({ question, headingRef }: { question: string; headingRef: React.RefObject<HTMLHeadingElement | null> }) {
  const [full, setFull] = useState(false);
  const [clipped, setClipped] = useState(false);
  const size = question.length > 160 ? "long" : question.length > 70 ? "medium" : "short";
  useLayoutEffect(() => {
    const el = headingRef.current;
    if (!el) return;
    // More than three lines of text (half a line of slack for descenders and rounding).
    const measure = () => {
      const line = parseFloat(getComputedStyle(el).lineHeight) || 40;
      setClipped(el.scrollHeight > line * 3.5);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [headingRef, question, full]);
  return (
    <div className={styles.titleArea}>
      <h2 ref={headingRef} tabIndex={-1} data-turn-heading className={styles.turnQuestion} data-size={size} data-clamped={full ? undefined : "true"}>
        {question}
      </h2>
      {clipped || full ? (
        <button type="button" className={styles.fullQuestion} aria-expanded={full} onClick={() => setFull(!full)}>
          {full ? "Show less" : "Show full question"}
        </button>
      ) : null}
    </div>
  );
}

export function TurnCard({
  turn,
  onStop,
  onNextHint,
  onEvidence,
  onRemove,
  onFresh,
  busy = false,
  selection,
  onSelect,
  linked: linkedProp,
  announce,
  inlinePassage,
  narrow = false,
  scope,
  onSearchShared,
}: {
  turn: Turn;
  onStop: () => void;
  onNextHint?: () => void;
  onEvidence?: () => void;
  onRemove: () => void;
  onFresh?: () => void;
  busy?: boolean;
  /** On the Evidence Desk: which citation is open in the source margin, and how to open another. */
  selection?: Selection;
  onSelect?: (selection: Selection) => void;
  /** The answer with its citations already linked (computed once by the desk); when absent, it is computed here. */
  linked?: LinkedAnswer | null;
  /** Say something through the desk's status region. */
  announce?: Announce;
  /** On narrow screens: the passage behind the selected citation, shown just below the answer. */
  inlinePassage?: ReactNode;
  narrow?: boolean;
  /** Where the passages came from, in the public demo. */
  scope?: string;
  /** For a question about the visitor's own documents that matched nothing: search the shared textbooks instead. */
  onSearchShared?: () => void;
}) {
  const streaming = turn.status === "streaming";
  const noKey = turn.error?.code === "llm_unavailable" && !turn.guided;
  const noLocalMatch = turn.error?.code === "no_local_match";
  const headingRef = useRef<HTMLHeadingElement>(null);
  const controlId = useId();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const stopRequested = useRef(false);
  // Citations become chips once the server has checked them (at the end of the stream).
  const ownLinked = useMemo(
    () => (linkedProp === undefined && onSelect && turn.status === "done" ? linkCitations(turn.answer, turn.citations, turn.chunks) : null),
    [linkedProp, onSelect, turn.status, turn.answer, turn.citations, turn.chunks],
  );
  const linked = linkedProp !== undefined ? linkedProp : ownLinked;
  const grounding = groundingOf(turn);
  const notFound = grounding.kind === "not-found";

  // After Stop the Stop button disappears; keep focus on this question rather than dropping it to the page.
  useEffect(() => {
    if (stopRequested.current && turn.status !== "streaming") {
      stopRequested.current = false;
      headingRef.current?.focus();
    }
  }, [turn.status]);
  useEffect(() => {
    if (confirmRemove) document.getElementById(`${controlId}-confirm`)?.focus();
  }, [confirmRemove, controlId]);
  const cancelRemove = () => {
    setConfirmRemove(false);
    requestAnimationFrame(() => document.getElementById(`${controlId}-remove`)?.focus());
  };

  return (
    <div className={`space-y-4 ${styles.turn}`} aria-busy={streaming}>
      <div className={styles.turnHeading}>
        <p className={cn(styles.eyebrow, styles.eyebrowArea)}>From a question to its evidence</p>
        <QuestionHeading key={turn.id} question={turn.question} headingRef={headingRef} />
        <div className={cn("flex flex-wrap gap-1.5", styles.badgeArea)}>
            {turn.mode ? <Badge>{MODE_LABEL[turn.mode]}</Badge> : null}
            {turn.model ? <Badge>{turn.model}</Badge> : null}
            {turn.cached ? <Badge title="Served from the cache; nothing new was sent to the model">cached</Badge> : null}
            {turn.agent ? <Badge title="Answered by the agentic workflow (LangGraph)">agentic</Badge> : null}
            {turn.status === "stopped" ? <Badge>stopped</Badge> : null}
        </div>
        <div className={styles.turnActions}>
          {streaming ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                stopRequested.current = true;
                onStop();
              }}
            >
              <Square className="h-3.5 w-3.5" aria-hidden="true" /> Stop
            </Button>
          ) : confirmRemove ? (
            <div
              className={styles.confirm}
              role="group"
              aria-label="Remove this question?"
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.stopPropagation();
                  cancelRemove();
                }
              }}
            >
              <p>Remove this question and its answer from your history?</p>
              <div className={styles.confirmActions}>
                <Button id={`${controlId}-confirm`} variant="danger" size="sm" onClick={onRemove}>
                  Confirm remove
                </Button>
                <Button variant="ghost" size="sm" onClick={cancelRemove}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              {turn.cached && !turn.guided && onFresh ? (
                <Button variant="ghost" size="sm" className={styles.actionButton} onClick={() => { onFresh?.(); if (turn.guided) headingRef.current?.focus(); }} disabled={busy}>
                  Fresh answer
                </Button>
              ) : null}
              {turn.answer ? <CopyButton text={turn.answer} announce={announce} /> : null}
              {turn.answer && turn.status === "done" && !notFound ? <SaveCardButton turn={turn} announce={announce} /> : null}
              <Button id={`${controlId}-remove`} variant="ghost" size="sm" className={styles.actionButton} aria-label="Remove" onClick={() => setConfirmRemove(true)}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                <span className={styles.actionLabel}>Remove</span>
              </Button>
            </>
          )}
        </div>
      </div>

      {noKey ? (
        <Notice>The server has no language-model key configured, so it cannot write an answer. Retrieval still works: the sources below are the passages it found.</Notice>
      ) : noLocalMatch ? (
        <div className={styles.neutralNotice} role="status">
          <p>{turn.error?.message}</p>
          <div className={styles.noticeActions}>
            {turn.guided && onFresh ? <Button variant="secondary" onClick={() => { onFresh?.(); if (turn.guided) headingRef.current?.focus(); }} disabled={busy}>Try this question again</Button> : null}
            {onSearchShared ? (
              <Button variant="secondary" size="sm" onClick={onSearchShared} disabled={busy}>
                Search the shared textbooks instead
              </Button>
            ) : null}
            <Link href="/sources" className={styles.noticeLink}>
              <Plus aria-hidden="true" /> Add material
            </Link>
          </div>
        </div>
      ) : turn.error ? (
        <div className="space-y-3">
          <ErrorNotice>
            <p className="font-medium">This question didn&apos;t reach your sources.</p>
            <p>{turn.error.message}</p>
          </ErrorNotice>
          {onFresh ? (
            <Button variant="secondary" onClick={() => { onFresh?.(); if (turn.guided) headingRef.current?.focus(); }} disabled={busy}>
              Try this question again
            </Button>
          ) : null}
        </div>
      ) : turn.status === "stopped" ? (
        <div className="space-y-3">
          <p className={styles.quietNote}>You stopped this {turn.guided && !turn.guided.evidenceStarted ? "hint request" : "answer"} before it finished{turn.answer ? "; what arrived is below" : ""}.</p>
          {onFresh ? (
            <Button variant="secondary" onClick={() => { onFresh?.(); if (turn.guided) headingRef.current?.focus(); }} disabled={busy}>
              Try this question again
            </Button>
          ) : null}
        </div>
      ) : null}

      {turn.guided ? <GuidedHints turn={turn} blocked={busy && !streaming} onNext={onNextHint} onEvidence={() => { onEvidence?.(); headingRef.current?.focus(); }} /> : null}
      <AgentSteps turn={turn} />

      {turn.answer || (streaming && (!turn.guided || turn.guided.evidenceStarted)) ? (
        <div className={styles.answer} data-step="evidence">
          <p className={styles.answerLabel}>
            <Sparkles aria-hidden="true" />
            {streaming ? "Building your answer" : notFound ? "What Lectern found" : turn.status === "done" ? "An explanation you can inspect" : "A partial answer"}
          </p>
          {grounding.kind !== "none" ? (
            <p className={styles.verdict} data-verdict={grounding.kind === "checked" ? (grounding.unchecked ? "warn" : "ok") : "none"}>
              {grounding.kind === "checked" ? grounding.unchecked ? <AlertTriangle aria-hidden="true" /> : <Check aria-hidden="true" /> : <BookOpen aria-hidden="true" />}
              {verdictText(grounding)}
            </p>
          ) : null}
          {turn.answer ? (
            <CiteProvider selectedRef={selection?.ref ?? null} onSelect={onSelect}>
              <CitedMarkdown markdown={turn.answer} linked={linked?.refs.length ? linked : null} streaming={streaming} />
            </CiteProvider>
          ) : (
            <p className="text-sm text-muted">Thinking…</p>
          )}
          {inlinePassage}
          {linked?.refs.some((r) => r.chunk !== null) ? (
            <p className={styles.traceHint}>
              <Link2 aria-hidden="true" />
              <span>
                <strong>Read the connection.</strong> {narrow ? "Select a citation to read its passage right here." : "Select a citation to open its passage in the source margin."}
              </span>
            </p>
          ) : null}
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
        <details open={!turn.answer || turn.status === "error"} className={styles.evidence} data-step="evidence">
          <summary className={styles.evidenceSummary}>
            <BookOpen aria-hidden="true" />
            <span className="mr-2">
              Sources ({turn.chunks.length}){scope ? <span className={styles.scopeTag}> · {scope}</span> : null}
            </span>
            <span className={styles.sourceBadges}>
              {turn.chunks.map((c, i) => (
                <Badge key={i} title={`Relevance ${c.score.toFixed(2)}`} className="font-mono">
                  [{i + 1}] {c.doc}
                  {c.page ? ` · ${pageLabel(c.page, c.end_page, true)}` : ""}
                </Badge>
              ))}
            </span>
            <ChevronDown className={styles.evidenceChevron} aria-hidden="true" />
          </summary>
          <div className={styles.passages}>
            {turn.chunks.map((c, i) => (
              <div key={i} className={styles.passage}>
                <ChunkCard chunk={c} query={turn.question} index={i} />
                {onSelect ? (
                  <button type="button" className={styles.passageOpen} aria-pressed={selection?.chunk === i && selection.ref === null} onClick={() => onSelect({ ref: null, chunk: i })}>
                    {narrow ? `Open passage ${i + 1}` : `Open passage ${i + 1} in the margin`}
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      ) : turn.status === "done" && !turn.answer && !turn.guided ? (
        <p className={cn("text-sm text-muted")}>No matching passages were found in your sources.</p>
      ) : null}
    </div>
  );
}

/** Hidden hints are stored on the turn, but only revealed text enters the DOM. */
function GuidedHints({ turn, blocked, onNext, onEvidence }: { turn: Turn; blocked: boolean; onNext?: () => void; onEvidence?: () => void }) {
  const guided = turn.guided!;
  const latest = useRef<HTMLDivElement>(null);
  const previous = useRef(guided.revealed);
  useEffect(() => {
    if (guided.revealed > previous.current) latest.current?.focus();
    previous.current = guided.revealed;
  }, [guided.revealed]);
  const hints = guided.hints ?? [];
  return (
    <section className={styles.guidedHints} data-step="evidence" aria-label="Guided hints">
      <p className="eyebrow">Guided / think it through</p>
      <p className={styles.quietNote}>Hints are prompts to help you think. Reveal the cited answer whenever you are ready.</p>
      <div aria-live="polite" aria-atomic="false">
        {hints.slice(0, guided.revealed).map((hint, i) => (
          <div key={i}>
            <p className="eyebrow">Hint {i + 1} of {hints.length}</p>
            <div data-guided-hint={i + 1} tabIndex={-1} ref={i === guided.revealed - 1 ? latest : undefined}><Markdown>{hint}</Markdown></div>
          </div>
        ))}
        {!guided.evidenceStarted && turn.status === "streaming" ? <p>Preparing your hints…</p> : null}
        {guided.hints && !hints.length ? <p>No hints were returned. You can still explore the evidence.</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {guided.revealed < hints.length ? <Button variant="secondary" onClick={onNext}>Next hint</Button> : null}
        {!guided.evidenceStarted ? <Button disabled={blocked} onClick={onEvidence}>Show me the evidence</Button> : null}
      </div>
    </section>
  );
}
