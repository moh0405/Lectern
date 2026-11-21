"use client";

import { AlertTriangle, ArrowUpRight, Check, FileText, Minus, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { pageLabel } from "@/lib/format";
import { closestSentence, excerpt, twoDigits, type CiteRef } from "./citations";
import type { Turn } from "./session";
import type { Selection } from "./turn-card";
import styles from "./ask.module.css";

const PROBLEM: Record<string, string> = {
  unknown_source: "The answer names a source that was not among the passages Lectern retrieved, so there is nothing to show. It may be invented.",
  page_not_retrieved: "The document was retrieved, but not the page the answer cites, so that page cannot be shown here.",
};

function Intro() {
  return (
    <div className={styles.marginBody}>
      <p className="eyebrow">Your question, connected</p>
      <h2 className={`${styles.marginTitle} paper-serif`}>
        The passage,
        <br />
        beside the answer.
      </h2>
      <div className={styles.paperRule} />
      <p className={`${styles.marginLead} paper-serif`}>
        Ask a question and the passages it was answered from open here. Select a citation in the answer to read the words it came from, without leaving the conversation.
      </p>
      <nav aria-label="From here" className={styles.marginLinks}>
        <p className="eyebrow">From here, you could</p>
        <Link href="/sources">
          Add material to your library <ArrowUpRight aria-hidden="true" />
        </Link>
        <Link href="/study">
          Review your flashcards <ArrowUpRight aria-hidden="true" />
        </Link>
      </nav>
    </div>
  );
}

/** The highlighted passage, opening on the sentence that best matches what cited it. */
function Passage({ text, sentence, reason }: { text: string; sentence: string; reason: string }) {
  const [expanded, setExpanded] = useState(false);
  const focus = closestSentence(text, sentence);
  const cut = expanded ? { text, offset: 0, clippedStart: false, clippedEnd: false } : excerpt(text, focus);
  const clipped = cut.clippedStart || cut.clippedEnd;
  const start = focus ? Math.max(0, focus.start - cut.offset) : -1;
  const end = focus ? Math.min(cut.text.length, focus.end - cut.offset) : -1;
  const visible = focus !== null && start < end;
  return (
    <>
      <blockquote className={`${styles.passageQuote} paper-serif`} data-margin-anchor={visible ? undefined : "true"}>
        {cut.clippedStart ? "… " : null}
        {visible ? (
          <>
            {cut.text.slice(0, start)}
            <mark data-margin-anchor="true">{cut.text.slice(start, end)}</mark>
            {cut.text.slice(end)}
          </>
        ) : (
          cut.text
        )}
        {cut.clippedEnd ? " …" : null}
      </blockquote>
      {visible ? <p className={styles.matchNote}>Highlighted: the sentence closest to {reason}.</p> : null}
      {clipped || expanded ? (
        <button type="button" className={styles.contextToggle} aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          {expanded ? <Minus aria-hidden="true" /> : <Plus aria-hidden="true" />}
          {expanded ? "Show less" : "Read a little more context"}
        </button>
      ) : null}
    </>
  );
}

export function SourceMargin({ turn, refs, selection, onSelect }: { turn?: Turn; refs: CiteRef[]; selection: Selection; onSelect: (s: Selection) => void }) {
  if (!turn) {
    return (
      <>
        <div className={styles.marginBand}>
          <span className={styles.bandArrow} aria-hidden="true">
            <ArrowUpRight />
          </span>
          <div>
            <p className="eyebrow">The source margin</p>
            <p className={styles.bandText}>Your evidence has a place.</p>
          </div>
        </div>
        <Intro />
      </>
    );
  }

  const ref = selection.ref !== null ? refs[selection.ref] : undefined;
  const index = ref ? ref.chunk : selection.chunk;
  const chunk = index !== null && index !== undefined ? turn.chunks[index] : undefined;
  const where = chunk ? [chunk.doc, chunk.page ? pageLabel(chunk.page, chunk.end_page) : ""].filter(Boolean).join(" · ") : ref ? ref.label : "";
  const href = chunk ? (chunk.citation_url ?? chunk.url ?? undefined) : undefined;

  return (
    <>
      <div className={styles.marginBand}>
        <span className={`${styles.bandNumber} paper-serif`} aria-hidden="true">
          {chunk && index !== null ? twoDigits(index + 1) : ref && ref.status !== "ok" ? "?" : "–"}
        </span>
        <div className="min-w-0">
          <p className="eyebrow">{ref ? "Citation in focus" : chunk ? "Passage in focus" : "Sources"}</p>
          <p className={styles.bandText}>{where || (turn.status === "streaming" ? "Finding passages in your material…" : "No passages for this question")}</p>
        </div>
      </div>

      {turn.chunks.length > 1 ? (
        <div className={styles.passageTabs} role="group" aria-label="Retrieved passages">
          {turn.chunks.map((c, i) => (
            <button key={i} type="button" aria-pressed={index === i} onClick={() => onSelect({ ref: refs.find((r) => r.chunk === i)?.id ?? null, chunk: i })}>
              {twoDigits(i + 1)} · {c.doc.length > 22 ? `${c.doc.slice(0, 21)}…` : c.doc}
              {c.page ? ` ${pageLabel(c.page, c.end_page, true)}` : ""}
            </button>
          ))}
        </div>
      ) : null}

      <div className={styles.marginBody}>
        {ref && !chunk && ref.status === "ok" ? (
          <div className={`${styles.marginWarning} ${styles.marginNeutral}`} role="note">
            <Check aria-hidden="true" />
            <div>
              <p className={styles.marginWarningTitle}>Verified, but its passage is not in the list</p>
              <p className="font-mono text-xs">[{ref.label}]</p>
              <p>The server confirmed this document{ref.page != null ? " and page" : ""} among the passages the answer was given, but none of the passages listed here matches it, so there is nothing to show.</p>
            </div>
          </div>
        ) : ref && !chunk ? (
          <div className={styles.marginWarning} role="note">
            <AlertTriangle aria-hidden="true" />
            <div>
              <p className={styles.marginWarningTitle}>This citation could not be checked</p>
              <p className="font-mono text-xs">[{ref.label}]</p>
              <p>{PROBLEM[ref.status] ?? "It could not be matched to a retrieved passage."}</p>
            </div>
          </div>
        ) : chunk ? (
          <section aria-label={`Passage ${index! + 1}: ${where}`}>
            <div className={styles.passageHead}>
              <p className="eyebrow">Retrieved passage</p>
              <FileText aria-hidden="true" />
            </div>
            <h2 className={`${styles.marginTitle} ${styles.marginDoc} paper-serif`}>{chunk.doc}</h2>
            <div className={styles.paperRule} />
            <Passage key={`${turn.id}-${index}-${ref?.id ?? "p"}`} text={chunk.text} sentence={ref?.sentence || turn.question} reason={ref?.sentence ? "the cited sentence" : "your question"} />
            <dl className={styles.passageFacts}>
              <div>
                <dt>Relevance</dt>
                <dd>{chunk.score.toFixed(2)}</dd>
              </div>
              {chunk.page ? (
                <div>
                  <dt>Location</dt>
                  <dd>{pageLabel(chunk.page, chunk.end_page)}</dd>
                </div>
              ) : null}
            </dl>
            {href ? (
              <a className={styles.openSource} href={href} target="_blank" rel="noopener noreferrer">
                Open the source <ArrowUpRight aria-hidden="true" />
              </a>
            ) : null}
          </section>
        ) : turn.status === "streaming" ? (
          <p className={`${styles.marginLead} paper-serif`}>Finding the passages that answer your question…</p>
        ) : (
          <p className={`${styles.marginLead} paper-serif`}>No passages were retrieved for this question, so there is nothing to show here.</p>
        )}
        <p className={styles.marginNote}>
          Passages are the exact text Lectern retrieved for this question. Citations are checked against them before they are linked.
        </p>
      </div>
    </>
  );
}
