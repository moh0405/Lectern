"use client";

import { AlertTriangle, Check, CircleHelp, Minus, X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { twoDigits } from "./citations";
import { CITE_PROBLEM, type Selection } from "./citation-chip";
import { ATTEMPT_FORMATS, passagesFor, tally, UNCHECKED, verdictOf, type VerdictKind } from "./attempt";
import type { Turn } from "./session";
import styles from "./ask.module.css";

const ICON: Record<VerdictKind, ReactNode> = {
  supported: <Check aria-hidden="true" />,
  contradicted: <X aria-hidden="true" />,
  unchecked: <CircleHelp aria-hidden="true" />,
  not_covered: <Minus aria-hidden="true" />,
};

/**
 * Try first: the student's attempt, one row per step (or code line, or sentence), each with the verdict the server
 * checked against the passages. A verdict with a passage behind it is a button that opens that passage in the source
 * margin (below the feedback on narrow screens). The cited answer is only fetched when the student asks for it.
 */
export function AttemptFeedbackView({ turn, selection, onSelect, onEvidence, blocked, narrow, inlinePassage, evidenceLabel = "Show me the evidence", evidenceNote = "The full answer, with citations, when you are ready." }: {
  turn: Turn;
  selection?: Selection;
  onSelect?: (selection: Selection) => void;
  onEvidence?: () => void;
  blocked: boolean;
  narrow: boolean;
  /** The passage opened from a verdict, on narrow screens before the answer exists. */
  inlinePassage?: ReactNode;
  /** What the reveal button offers, on pages where the next step is not a cited answer. */
  evidenceLabel?: string;
  evidenceNote?: string;
}) {
  const attempt = turn.attempt!;
  const feedback = attempt.feedback;
  const titleId = useId();
  const summaryRef = useRef<HTMLParagraphElement>(null);
  const had = useRef(Boolean(feedback));
  // Move focus to the summary once, when feedback arrives, so keyboard and screen-reader users land on it.
  useEffect(() => {
    if (feedback && !had.current) summaryRef.current?.focus({ preventScroll: true });
    had.current = Boolean(feedback);
  }, [feedback]);
  const format = ATTEMPT_FORMATS.find((f) => f.value === (feedback?.format ?? attempt.format)) ?? ATTEMPT_FORMATS[0]!;
  const units = feedback?.units ?? [];
  const where = narrow ? "below" : "in the source margin";
  const unitName = format.unit.charAt(0).toUpperCase() + format.unit.slice(1);

  return (
    <section className={styles.attempt} data-step="evidence" aria-labelledby={titleId} data-format={format.value}>
      <p className="eyebrow">Try first / your attempt, checked</p>
      <h3 id={titleId} className={styles.attemptTitle}>
        Feedback on your {format.value === "code" ? "code" : format.value === "steps" ? "steps" : "answer"}
        {attempt.language && format.value === "code" ? <span className={styles.attemptLang}>{attempt.language}</span> : null}
      </h3>
      {!feedback ? (
        turn.status === "streaming" ? <p className={styles.quietNote}>Checking your attempt against your sources…</p> : null
      ) : (
        <>
          <p ref={summaryRef} tabIndex={-1} className={styles.attemptSummary}>{feedback.summary}</p>
          <p className={styles.attemptTally}>{tally(feedback)}</p>
          <ol className={styles.attemptLines} aria-label={`Your attempt, ${format.unit} by ${format.unit}`}>
            {units.map((text, i) => {
              const item = feedback.items.find((it) => it.unit === i + 1);
              const blank = !text.trim();
              if (blank && format.value === "code") {
                return <li key={i} className={styles.attemptLine} data-blank="true" aria-hidden="true"><span className={styles.lineNo}>{i + 1}</span></li>;
              }
              const v = item ? verdictOf(item) : null;
              const passages = item ? passagesFor(item, turn.chunks, text) : [];
              const bad = item?.citations.filter((c) => c.status !== "ok") ?? [];
              const open = (chunk: number) => onSelect?.({ ref: null, chunk, sentence: text });
              const first = passages[0];
              return (
                <li key={i} className={styles.attemptLine} data-verdict={v?.kind ?? "none"}>
                  <span className={styles.lineNo} aria-hidden="true">{i + 1}</span>
                  <div className={styles.lineBody}>
                    <p className={styles.lineText}>
                      <span className="sr-only">{item?.ref ?? `${unitName} ${i + 1}`}: </span>
                      {format.value === "code" ? <code>{text}</code> : text}
                    </p>
                    {item && v ? (
                      <div className={styles.verdictRow}>
                        {first !== undefined && onSelect ? (
                          <button
                            type="button"
                            className={styles.verdict}
                            data-kind={v.kind}
                            aria-pressed={selection?.chunk === first && selection.ref === null && selection.sentence === text}
                            aria-label={`${item.ref}: ${v.long}. Open passage ${first + 1} ${where}`}
                            onClick={() => open(first)}
                          >
                            {ICON[v.kind]}
                            <span>{v.label}</span>
                            <span className={styles.verdictPassage} aria-hidden="true">{twoDigits(first + 1)}</span>
                          </button>
                        ) : (
                          <span className={styles.verdict} data-kind={v.kind} data-static="true">
                            {ICON[v.kind]}
                            <span>{v.label}</span>
                          </span>
                        )}
                        {passages.slice(1).map((p) => (
                          <button key={p} type="button" className="cite-chip" aria-pressed={selection?.chunk === p && selection.sentence === text} aria-label={`Open passage ${p + 1} ${where}`} onClick={() => open(p)}>
                            {twoDigits(p + 1)}
                          </button>
                        ))}
                        {v.kind === "unchecked" ? <span className={styles.verdictNote}>{UNCHECKED}</span> : null}
                      </div>
                    ) : null}
                    {item?.note ? <p className={styles.lineNote}>{item.note}</p> : null}
                    {bad.length ? (
                      <p className={styles.lineWarn}>
                        <AlertTriangle aria-hidden="true" />
                        <span>
                          {bad.map((c, j) => (
                            <span key={c.label}>
                              {j ? "; " : ""}Cites <span className="font-mono">[{c.label}]</span>, but {CITE_PROBLEM[c.status]}
                            </span>
                          ))}
                          .
                        </span>
                      </p>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ol>
          {inlinePassage}
          <p className={styles.quietNote}>
            Verdicts are checked against the passages Lectern retrieved. One marked &ldquo;unchecked&rdquo; has no verified citation, so treat it as {UNCHECKED}.
            {feedback.withheld ? " Feedback that would have given the answer away was replaced with a pointer." : ""}
          </p>
        </>
      )}
      {!attempt.evidenceStarted ? (
        <div className={styles.attemptActions}>
          <Button disabled={blocked} onClick={onEvidence}>{evidenceLabel}</Button>
          <span className={styles.quietNote}>{evidenceNote}</span>
        </div>
      ) : null}
    </section>
  );
}
