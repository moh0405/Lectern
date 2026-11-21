import type { Chunk } from "@ai-study-mentor/api-client";
import type { CitationCheck } from "./session";

/**
 * Turns the citations in a finished answer into references the Evidence Desk can follow.
 *
 * The server has already checked every citation against the retrieved passages (`CitationCheck`). Here each
 * bracketed citation in the Markdown is replaced by a link to `#cite-<n>`, which the answer renders as a chip,
 * and each chip remembers which passage it points to and the sentence that cited it. Only citations the
 * server reported are linked, so ordinary brackets such as `nums[0]` are left alone.
 */

export type CitationStatus = CitationCheck["status"];

export interface CiteRef {
  id: number;
  /** Index into the turn's chunks, or null when the citation has no retrieved passage to show. */
  chunk: number | null;
  label: string;
  doc: string;
  page: number | null;
  status: CitationStatus;
  /** The answer text that made this citation, used to find the closest sentence in the passage. */
  sentence: string;
}

export const CITE_PREFIX = "#cite-";

// Same shape the server accepts as a citation (backend/citations.py `_BRACKET`).
const BRACKET = /(?<![\w\])])\[([^[\]\n]{3,200})\](?!\()/g;
// Code is never rewritten: fenced blocks and inline code spans are kept as they are.
const CODE = /(```[\s\S]*?```|`[^`\n]*`)/;

const norm = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");
const stem = (s: string) => norm(s).replace(/\.[a-z0-9]{1,5}$/, "");

function sameDoc(chunkDoc: string, citedDoc: string): boolean {
  const a = norm(chunkDoc);
  const b = norm(citedDoc);
  // A citation may add a section after the document name: "notes.md > Hashing".
  return a === b || stem(chunkDoc) === stem(citedDoc) || b.startsWith(a + " ") || b.startsWith(stem(chunkDoc) + " ");
}

/** The retrieved passage a verified citation points to, or null if there is none to show. */
export function chunkForCitation(c: Pick<CitationCheck, "doc" | "page" | "status">, chunks: Chunk[]): number | null {
  if (c.status !== "ok") return null;
  const sameDocument = chunks.map((ch, i) => [ch, i] as const).filter(([ch]) => sameDoc(ch.doc, c.doc));
  if (c.page == null) return sameDocument[0]?.[1] ?? null;
  const onPage = sameDocument.find(([ch]) => ch.page != null && ch.page <= c.page! && c.page! <= (ch.end_page ?? ch.page));
  return (onPage ?? sameDocument[0])?.[1] ?? null;
}

function stripMarkdown(s: string): string {
  return s.replace(/[*_`#>~]/g, "").replace(/\s+/g, " ").trim();
}

/** The sentence just before a citation: back to the previous sentence end, line break or citation. */
function citingSentence(before: string): string {
  const cut = Math.max(before.lastIndexOf("\n"), before.search(/[.!?]\s[^.!?]*$/) + 1, before.lastIndexOf("]") + 1);
  return stripMarkdown(before.slice(Math.max(0, cut)).slice(-400));
}

function matching(inner: string, citations: CitationCheck[]): CitationCheck[] {
  const text = norm(inner);
  const exact = citations.filter((c) => norm(c.label) === text);
  if (exact.length) return exact;
  const seen = new Set<string>();
  return citations.filter((c) => {
    const hit = text.includes(norm(c.label)) || (c.doc.length > 2 && text.includes(norm(c.doc)));
    const key = `${norm(c.doc)}|${c.page ?? ""}`;
    if (!hit || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function linkCitations(answer: string, citations: CitationCheck[] | undefined, chunks: Chunk[]): { markdown: string; refs: CiteRef[] } {
  const refs: CiteRef[] = [];
  if (!citations?.length) return { markdown: answer, refs };
  const parts = answer.split(CODE);
  const markdown = parts
    .map((part, i) => {
      if (i % 2 === 1) return part; // code
      return part.replace(BRACKET, (whole: string, inner: string, offset: number) => {
        const found = matching(inner, citations);
        if (!found.length) return whole;
        const sentence = citingSentence(part.slice(0, offset));
        return found
          .map((c) => {
            const ref: CiteRef = { id: refs.length, chunk: chunkForCitation(c, chunks), label: c.label, doc: c.doc, page: c.page ?? null, status: c.status, sentence };
            refs.push(ref);
            return `[${ref.id}](${CITE_PREFIX}${ref.id})`;
          })
          .join("");
      });
    })
    .join("");
  return { markdown, refs };
}

const STOP = new Set("the and for are but not you all any can had her was one our out has have this that with from they will what when which their there than then them these those into each also only such some more most other its it's very just like about over under been were your how why who use used uses using does".split(" "));

function words(s: string): Set<string> {
  return new Set((s.toLowerCase().match(/[a-z0-9]{3,}/g) ?? []).filter((w) => !STOP.has(w)));
}

/** Where the passage best matches the citing sentence, as character offsets, or null when nothing overlaps enough. */
export function closestSentence(text: string, sentence: string): { start: number; end: number } | null {
  const target = words(sentence);
  if (target.size === 0) return null;
  let best: { start: number; end: number; score: number } | null = null;
  for (const m of text.matchAll(/[^.!?\n]+[.!?]*/g)) {
    const span = m[0];
    const own = words(span);
    let overlap = 0;
    for (const w of own) if (target.has(w)) overlap++;
    if (overlap === 0) continue;
    const score = overlap / Math.sqrt(own.size + 1);
    if (!best || score > best.score) {
      const lead = span.length - span.trimStart().length;
      best = { start: m.index! + lead, end: m.index! + span.trimEnd().length, score };
    }
  }
  if (!best) return null;
  const needed = target.size >= 4 ? 2 : 1;
  const overlap = [...words(text.slice(best.start, best.end))].filter((w) => target.has(w)).length;
  return overlap >= needed ? { start: best.start, end: best.end } : null;
}

/** A short excerpt around the highlight, so long passages open on the part that matters. */
export function excerpt(text: string, focus: { start: number; end: number } | null, radius = 320): { text: string; offset: number; clippedStart: boolean; clippedEnd: boolean } {
  if (text.length <= radius * 2 + 120) return { text, offset: 0, clippedStart: false, clippedEnd: false };
  const centre = focus ? focus.start : 0;
  let start = Math.max(0, centre - radius);
  let end = Math.min(text.length, (focus ? focus.end : 0) + radius);
  if (start > 0) {
    const space = text.indexOf(" ", start);
    start = space >= 0 && space < centre ? space + 1 : start;
  }
  if (end < text.length) {
    const space = text.lastIndexOf(" ", end);
    end = space > (focus?.end ?? 0) ? space : end;
  }
  return { text: text.slice(start, end), offset: start, clippedStart: start > 0, clippedEnd: end < text.length };
}

export const twoDigits = (n: number) => String(n).padStart(2, "0");
