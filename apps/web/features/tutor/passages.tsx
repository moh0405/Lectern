"use client";

import type { Chunk } from "@ai-study-mentor/api-client";
import { BookOpen, ChevronDown, ExternalLink } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { pageLabel, plural } from "@/lib/format";
import { queryTerms, splitByTerms } from "@/lib/highlight";
import { cn } from "@/lib/utils";

const EXCERPT = 240;

export const passageId = (prefix: string, index: number) => `${prefix}-passage-${index + 1}`;

/** "heaps.pdf · page 3" */
export function passageWhere(c: Pick<Chunk, "doc" | "page" | "end_page">): string {
  const page = pageLabel(c.page, c.end_page);
  return page ? `${c.doc} · ${page}` : c.doc;
}

/**
 * Which passage a free-text source label ("heaps.pdf (page 3)", "heaps.pdf") points to: the first
 * passage of that document, preferring the named page. -1 when none matches.
 */
export function matchPassage(label: string, chunks: Pick<Chunk, "doc" | "page" | "end_page">[]): number {
  const text = label.toLowerCase();
  const candidates = chunks.map((c, i) => [c, i] as const).filter(([c]) => c.doc && text.includes(c.doc.toLowerCase()));
  const first = candidates[0];
  if (!first) return -1;
  const page = /(?:\bp(?:age)?s?\.?\s*)(\d+)/i.exec(label.replace(first[0].doc, ""));
  if (page) {
    const n = Number(page[1]);
    const hit = candidates.find(([c]) => c.page && n >= c.page && n <= (c.end_page ?? c.page));
    if (hit) return hit[1];
  }
  return first[1];
}

function Highlighted({ text, query }: { text: string; query?: string }) {
  if (!query) return <>{text}</>;
  return (
    <>
      {splitByTerms(text, queryTerms(query)).map((p, i) => (p.match ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))}
    </>
  );
}

export const RELEVANCE_HELP =
  "Relevance runs from 0 to 1: how closely a passage matches what you asked. Even 0.3 can be the right passage when the wording differs.";

function PassageItem({ chunk, id, query, open, onToggle, showRelevance }: { chunk: Chunk; id: string; query?: string; open: boolean; onToggle: () => void; showRelevance?: boolean }) {
  const long = chunk.text.length > EXCERPT;
  const shown = open || !long ? chunk.text : `${chunk.text.slice(0, EXCERPT).trimEnd()}…`;
  const href = chunk.citation_url ?? chunk.url ?? undefined;
  return (
    <li id={id} tabIndex={-1} className="scroll-mt-24 rounded-lg border border-paper-line bg-paper-2/60 p-3 outline-offset-2 focus-visible:outline-2 focus-visible:outline-paper-accent" data-testid="passage">
      <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs text-paper-muted">{passageWhere(chunk)}</p>
        {showRelevance ? (
          <span className="font-mono text-xs text-paper-muted" title={RELEVANCE_HELP} data-testid="relevance">
            relevance {chunk.score.toFixed(2)}
          </span>
        ) : null}
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-6 items-center gap-1 text-xs text-paper-accent underline-offset-2 hover:underline">
            Open source <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        ) : null}
      </div>
      <p className="paper-serif whitespace-pre-wrap text-[15px] leading-relaxed" id={`${id}-text`}>
        <Highlighted text={shown} query={query} />
      </p>
      {long ? (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={`${id}-text`}
          className="mt-1.5 inline-flex min-h-11 items-center gap-1 text-xs font-medium text-paper-accent underline-offset-2 hover:underline sm:min-h-8"
        >
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} aria-hidden />
          {open ? "Show less" : "Show the whole passage"}
        </button>
      ) : null}
    </li>
  );
}

/**
 * The passages a tool result was built from, on the paper surface. `target` opens and focuses one
 * passage (bump `nonce` to repeat the same one).
 */
export function PassageList({
  chunks,
  prefix,
  query,
  title,
  note,
  target,
  showRelevance,
}: {
  chunks: Chunk[];
  prefix: string;
  query?: string;
  title?: string;
  note?: ReactNode;
  target?: { index: number; nonce: number } | null;
  showRelevance?: boolean;
}) {
  const [open, setOpen] = useState<Set<number>>(() => new Set());
  const [seenTarget, setSeenTarget] = useState(target);
  if (target !== seenTarget) {
    // Adjust state while rendering (not in an effect): a new target opens that passage.
    setSeenTarget(target);
    if (target && target.index >= 0 && !open.has(target.index)) setOpen(new Set(open).add(target.index));
  }

  useEffect(() => {
    if (!target || target.index < 0) return;
    const el = document.getElementById(passageId(prefix, target.index));
    el?.focus({ preventScroll: true });
    el?.scrollIntoView?.({ block: "nearest" });
  }, [target, prefix]);

  if (!chunks.length) return null;
  const toggle = (i: number) =>
    setOpen((s) => {
      const next = new Set(s);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  const headingId = `${prefix}-passages-heading`;

  return (
    <section className="paper rounded-xl border border-paper-line p-4" aria-labelledby={headingId} data-testid={`${prefix}-passages`}>
      <h2 id={headingId} className="eyebrow mb-1">
        <BookOpen aria-hidden /> {title ?? `Built from ${plural(chunks.length, "passage")}`}
      </h2>
      {note || showRelevance ? (
        <p className="mb-3 text-xs text-paper-muted">
          {note}
          {note && showRelevance ? " " : null}
          {showRelevance ? RELEVANCE_HELP : null}
        </p>
      ) : (
        <div className="mb-3" />
      )}
      <ol className="grid gap-2">
        {chunks.map((c, i) => (
          <PassageItem key={i} chunk={c} id={passageId(prefix, i)} query={query} open={open.has(i)} onToggle={() => toggle(i)} showRelevance={showRelevance} />
        ))}
      </ol>
    </section>
  );
}
