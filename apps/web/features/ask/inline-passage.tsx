"use client";

import { AlertTriangle, ArrowUpRight, Check, X } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import { pageLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Selection } from "./citation-chip";
import { twoDigits, type CiteRef } from "./citations";
import type { Turn } from "./session";
import { Passage, PROBLEM } from "./source-margin";
import styles from "./ask.module.css";

/**
 * On narrow screens, where the source margin sits far below the answer, the passage behind a citation opens here,
 * just under the answer, in the same paper style. Focus stays on the chip that opened it; "Back to answer" returns it there.
 */
export function InlinePassage({ turn, refs, selection, onClose, scope }: { turn: Turn; refs: CiteRef[]; selection: Selection; onClose: () => void; scope?: string }) {
  const titleId = useId();
  const box = useRef<HTMLElement>(null);
  const ref = selection.ref !== null ? refs[selection.ref] : undefined;
  const index = ref ? ref.chunk : selection.chunk;
  const chunk = index !== null && index !== undefined ? turn.chunks[index] : undefined;
  const where = chunk ? [chunk.doc, chunk.page ? pageLabel(chunk.page, chunk.end_page) : ""].filter(Boolean).join(" · ") : (ref?.label ?? "");
  const href = chunk ? (chunk.citation_url ?? chunk.url ?? undefined) : undefined;

  // Bring the card into view without moving focus away from the chip.
  useEffect(() => {
    const el = box.current;
    if (!el?.scrollIntoView) return;
    const motion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    el.scrollIntoView({ block: "nearest", behavior: motion });
  }, [selection.ref, selection.chunk]);

  if (!ref && !chunk) return null;
  return (
    <section
      ref={box}
      className={cn(styles.inlinePassage, "paper")}
      aria-labelledby={titleId}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }}
    >
      <div className={styles.inlineHead}>
        <span className={`${styles.inlineNumber} paper-serif`} aria-hidden="true">
          {chunk && index !== null ? twoDigits(index + 1) : "?"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="eyebrow">
            {ref ? "Citation in focus" : "Passage in focus"}
            {scope ? ` · ${scope}` : ""}
          </p>
          <h3 id={titleId} className={styles.inlineTitle}>
            {chunk && index !== null ? `Passage ${index + 1}: ${where}` : `Citation: ${where}`}
          </h3>
        </div>
      </div>
      {chunk ? (
        <>
          <Passage key={`${turn.id}-${index}-${ref?.id ?? "p"}-${selection.sentence ?? ""}`} anchor={false} text={chunk.text} sentence={ref?.sentence || selection.sentence || turn.question} reason={ref?.sentence ? "the cited sentence" : selection.sentence ? "your attempt" : "your question"} className={styles.inlineQuote} />
          {href ? (
            <a className={styles.openSource} href={href} target="_blank" rel="noopener noreferrer">
              Open the source <ArrowUpRight aria-hidden="true" />
            </a>
          ) : null}
        </>
      ) : ref?.status === "ok" ? (
        <div className={`${styles.marginWarning} ${styles.marginNeutral}`} role="note">
          <Check aria-hidden="true" />
          <div>
            <p className={styles.marginWarningTitle}>Verified, but its passage is not in the list</p>
            <p>The server confirmed this source among the passages the answer was given, but none of the passages listed here matches it.</p>
          </div>
        </div>
      ) : (
        <div className={styles.marginWarning} role="note">
          <AlertTriangle aria-hidden="true" />
          <div>
            <p className={styles.marginWarningTitle}>This citation could not be checked</p>
            <p className="font-mono text-xs">[{ref?.label}]</p>
            <p>{PROBLEM[ref?.status ?? ""] ?? "It could not be matched to a retrieved passage."}</p>
          </div>
        </div>
      )}
      <button type="button" className={styles.inlineBack} onClick={onClose}>
        <X aria-hidden="true" /> {turn.answer ? "Back to answer" : "Back to feedback"}
      </button>
    </section>
  );
}
